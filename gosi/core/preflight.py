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
