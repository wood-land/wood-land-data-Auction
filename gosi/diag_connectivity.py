"""
diag_connectivity.py - 지자체 사이트가 이 실행 환경(IP)에서 왜 안 열리는지 단계별로 진단한다.

각 호스트마다 DNS -> TCP(443/80) -> TLS -> HTTP GET 을 따로 재서 어느 단계에서 끊기는지 기록한다.
  - TCP 에서 시간초과: IP 대역 차단(방화벽·지역 ACL)일 가능성이 크다.
  - TCP/TLS 는 되고 HTTP 만 실패·403: 사이트 방화벽(WAF)·UA 차단일 가능성이 크다.
같은 환경에서 잘 되는 통제군(타 지역) 호스트와 비교해야 '환경 전체 문제'와 '사이트별 차단'이 갈린다.

사용: python diag_connectivity.py hosts.json out.json   (hosts.json: {그룹: {호스트: 대표URL}})
"""
import json
import socket
import ssl
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import requests
import urllib3

urllib3.disable_warnings()
UA_BROWSER = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
T = 8


def probe(host, url):
    u = urlparse(url)
    port = u.port or (443 if u.scheme == "https" else 80)
    r = {"host": host, "url": url, "port": port}
    t0 = time.time()
    try:
        ip = socket.getaddrinfo(host, port, socket.AF_INET)[0][4][0]
        r["ip"] = ip
        r["dns_s"] = round(time.time() - t0, 2)
    except Exception as e:
        r["dns_err"] = type(e).__name__
        return r
    t0 = time.time()
    try:
        s = socket.create_connection((ip, port), timeout=T)
        r["tcp_s"] = round(time.time() - t0, 2)
    except Exception as e:
        r["tcp_err"] = f"{type(e).__name__}:{e}"[:80]
        r["tcp_s"] = round(time.time() - t0, 2)
        return r
    if u.scheme == "https":
        t0 = time.time()
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            ctx.set_ciphers("DEFAULT@SECLEVEL=1")
            s = ctx.wrap_socket(s, server_hostname=host)
            r["tls_s"] = round(time.time() - t0, 2)
        except Exception as e:
            r["tls_err"] = f"{type(e).__name__}:{e}"[:80]
            r["tls_s"] = round(time.time() - t0, 2)
            return r
    try:
        s.close()
    except OSError:
        pass
    for tag, ua in (("py", None), ("browser", UA_BROWSER)):
        t0 = time.time()
        try:
            h = {"User-Agent": ua} if ua else {}
            resp = requests.get(url, headers=h, timeout=(T, 15), verify=False, allow_redirects=False)
            r[f"http_{tag}"] = resp.status_code
        except Exception as e:
            r[f"http_{tag}"] = f"ERR:{type(e).__name__}"
        r[f"http_{tag}_s"] = round(time.time() - t0, 2)
    return r


def main(hosts_file, out_file):
    groups = json.load(open(hosts_file, encoding="utf-8"))
    env = {}
    try:
        env = requests.get("https://ipinfo.io/json", timeout=10).json()
    except Exception as e:
        env = {"err": str(e)}
    jobs = [(g, h, u) for g, d in groups.items() for h, u in d.items()]
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda j: dict(probe(j[1], j[2]), group=j[0]), jobs))
    json.dump({"env": env, "results": res}, open(out_file, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("env:", env.get("ip"), env.get("country"), env.get("org"))
    for g in groups:
        rs = [x for x in res if x["group"] == g]
        ok = [x for x in rs if x.get("http_py") not in (None,) and not str(x.get("http_py")).startswith("ERR")]
        tcp_fail = [x for x in rs if "tcp_err" in x]
        print(f"[{g}] {len(rs)}곳: HTTP 응답 {len(ok)} / TCP 실패 {len(tcp_fail)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
