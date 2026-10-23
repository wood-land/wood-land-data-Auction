"""
core/preflight.py - 수집 전에 이 실행 환경(러너 IP)이 해당 지역 사이트에 닿는지 가볍게 확인한다.

2026-10-23 진단(history/17): GitHub 러너 9대 중 8대는 전남 25곳 중 22곳에 접속했는데 1대는 25곳 전부 TCP 시간초과였다.
국가 단위 차단이 아니라 '그날 배정된 러너 IP 하나가 막힌 것'이라, 그 지역을 통째로 25분 돌려 봐야 전부 오류로 남는다.
그래서 지역마다 시작할 때 호스트들에 TCP 연결만 해 보고, 대부분 안 닿으면 수집을 건너뛰어(종료코드 75) 워크플로가 새 러너(다른 IP)로 다시 돌게 한다.
"""
import socket
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

EXIT_BLOCKED = 75        # 사전 점검에서 러너 IP 차단이 의심돼 수집하지 않고 끝낸 경우(워크플로가 이 코드를 보고 재시도한다)
MIN_HOSTS = 5            # 이보다 호스트가 적은 지역은 표본이 작아 판정하지 않는다
MIN_OK_RATIO = 0.3       # 닿은 호스트 비율이 이보다 낮으면 차단 의심(정상 러너는 75~90%, 차단된 러너는 0%였다)
TIMEOUT = 6


SKIP_HOSTS = ("facebook.com",)   # 게시판 URL 로 잘못 잡힌 공유 링크(강진·장흥 간행물). 지자체 사이트가 아니라 점검 대상에서 뺀다


def host_port(url):
    u = urlparse(url or "")
    if not u.hostname or u.hostname.endswith(SKIP_HOSTS):
        return None
    return u.hostname, u.port or (443 if u.scheme == "https" else 80)


def reachable(hp, timeout=TIMEOUT, connect=socket.create_connection):
    """TCP 연결만 해 본다. 일시 실패를 가리려고 한 번 더 시도한다."""
    for _ in range(2):
        try:
            connect(hp, timeout=timeout).close()
            return True
        except OSError:
            continue
    return False


def probe(urls, workers=16, check=reachable):
    """urls -> (닿은 호스트 수, 전체 호스트 수, 안 닿은 호스트 목록). 같은 호스트는 한 번만 본다."""
    hps = sorted({hp for hp in map(host_port, urls) if hp})
    with ThreadPoolExecutor(workers) as ex:
        oks = list(ex.map(check, hps))
    return sum(oks), len(hps), [f"{h}:{p}" for (h, p), ok in zip(hps, oks) if not ok]


def looks_blocked(ok, total):
    return total >= MIN_HOSTS and ok / total < MIN_OK_RATIO


# ---- 접속 실패 원인 진단 (수집 로그에 '왜 안 열렸는지'를 남긴다) ----
UA_BROWSER = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
NET_HINTS = {
    "DNS": "도메인 이름을 IP 로 못 바꿈. 이 러너의 DNS 가 해외 요청에 응답하지 않거나 도메인이 바뀐 것. 국내 IP 에서 nslookup 으로 비교",
    "TCP_TIMEOUT": "서버가 연결에 응답하지 않음. IP 대역 차단(방화벽)이나 사이트 다운. 같은 지역 다른 사이트도 모두 이 코드면 러너 IP 차단, 이 사이트만이면 사이트별 차단",
    "TCP_REFUSED": "서버가 연결을 거부함(포트 닫힘/방화벽 거부). 주소의 http/https·포트가 맞는지 확인",
    "TCP_ERROR": "TCP 연결 중 기타 오류(네트워크 경로 문제). 상세 메시지 확인",
    "TLS": "TLS 협상 실패. 구형 서버면 core 의 _SECLEVEL_HOSTS, 중간 인증서 누락이면 _DOWNLOAD_SERVER_CA_HOSTS 에 호스트 등록 검토",
    "HTTP_ERROR": "TCP·TLS 는 되는데 HTTP 요청이 예외로 끝남(응답 지연/연결 끊김). 요청 간격·헤더 점검",
    "HTTP_4XX": "접속은 되고 4xx 응답. 사이트 방화벽(WAF)·User-Agent/Referer 차단이나 주소 변경 의심",
    "HTTP_5XX": "접속은 되는데 서버 오류. 사이트 장애면 다음 실행에서 자동 회복",
    "OK": "지금은 열림(수집 때만 실패). 수집 중 요청 빈도 제한(rate limit)·일시 장애·러너 IP 별 간헐 차단 의심. 간격(--delay)·재시도 늘리기 검토",
}
_diag_cache = {}


def diagnose_host(host, port=443, timeout=TIMEOUT):
    """호스트가 어느 단계(DNS -> TCP -> TLS -> HTTP)에서 끊기는지 가린다. -> (코드, 짧은 설명). 결과는 호스트별로 한 번만 잰다."""
    key = (host, port)
    if key in _diag_cache:
        return _diag_cache[key]
    import ssl
    import time
    t0 = time.time()
    try:
        ip = socket.getaddrinfo(host, port, socket.AF_INET)[0][4][0]
    except OSError as e:
        return _diag_cache.setdefault(key, ("DNS", f"DNS 실패({type(e).__name__})"))
    try:
        sock = socket.create_connection((ip, port), timeout=timeout)
    except socket.timeout:
        return _diag_cache.setdefault(key, ("TCP_TIMEOUT", f"TCP 시간초과 {timeout}초({ip})"))
    except ConnectionRefusedError:
        return _diag_cache.setdefault(key, ("TCP_REFUSED", f"TCP 연결 거부({ip})"))
    except OSError as e:
        return _diag_cache.setdefault(key, ("TCP_ERROR", f"TCP 오류 {type(e).__name__}: {str(e)[:60]}"))
    try:
        if port == 443:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            ctx.set_ciphers("DEFAULT@SECLEVEL=1")
            sock = ctx.wrap_socket(sock, server_hostname=host)
    except (ssl.SSLError, OSError) as e:
        return _diag_cache.setdefault(key, ("TLS", f"TLS 실패 {type(e).__name__}: {str(e)[:60]}"))
    finally:
        try:
            sock.close()
        except OSError:
            pass
    try:
        import requests
        import urllib3
        urllib3.disable_warnings()
        scheme = "https" if port == 443 else "http"
        r = requests.get(f"{scheme}://{host}:{port}/", headers={"User-Agent": UA_BROWSER}, timeout=(timeout, 10),
                         verify=False, allow_redirects=False)
        code = "OK" if r.status_code < 400 else ("HTTP_4XX" if r.status_code < 500 else "HTTP_5XX")
        return _diag_cache.setdefault(key, (code, f"HTTP {r.status_code} ({time.time() - t0:.1f}초)"))
    except Exception as e:  # noqa: BLE001 - 진단은 어떤 예외든 코드로 바꿔 남긴다
        return _diag_cache.setdefault(key, ("HTTP_ERROR", f"HTTP 예외 {type(e).__name__}"))


def _hp(text):
    host, _, port = text.rpartition(":")
    return host, int(port)


def stage_counts(bad):
    """probe 가 돌려준 안 닿는 'host:port' 목록 -> '{TCP_TIMEOUT: 20, DNS: 2}' 처럼 단계별 개수(어디서 끊기는지 가르는 단서)."""
    with ThreadPoolExecutor(16) as ex:
        codes = list(ex.map(lambda t: diagnose_host(*_hp(t))[0], bad))
    cnt = {}
    for c in codes:
        cnt[c] = cnt.get(c, 0) + 1
    return dict(sorted(cnt.items(), key=lambda x: -x[1]))


def stage_examples(bad, n=5):
    return [f"{t}={diagnose_host(*_hp(t))[1]}" for t in bad[:n]]
