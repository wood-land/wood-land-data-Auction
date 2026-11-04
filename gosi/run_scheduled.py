"""
run_scheduled.py - GitHub Actions(스케줄)용 수집 실행기: 고시공고 + 공보(시보·군보 등) -> SQLite.

  python run_scheduled.py                       # 고시공고(12일) + 공보(15일) 모두
  python run_scheduled.py --region 강원          # 지역 그룹 하나(고시공고+공보) -> data/gosi/강원.sqlite
  python run_scheduled.py --only gazette --module 경기
  python run_scheduled.py --only gosigongo --province 강원
  python run_scheduled.py --region 경북 --blocked only   # 호스티드 러너에서 막히는 게시판만(국내 IP 러너용, core/blocked_sites.py)
  python run_scheduled.py --region 전남 --preflight      # 시작 전에 이 IP 가 사이트들에 닿는지 확인, 막힌 IP 면 수집 없이 종료코드 75(core/preflight.py)
결과는 data/gosi/gosigongo.sqlite (또는 --region 지정 시 data/gosi/{지역}.sqlite) 에 누적된다(core/sqlite_store.py). 공보 게시판 목록은
output/시군구_공보게시판_목록_new.xlsx(git 추적) 의 '공보게시판' 시트를 읽는다.
"""
import argparse
import os
import sys
import tempfile
import threading
import time
import traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from core import sqlite_store as S  # noqa: E402
from core.paths import DATA_DIR  # noqa: E402
from core.pnu import PnuResolver  # noqa: E402
from core.run_log import LOG  # noqa: E402
from core.board_crawler import run_city  # noqa: E402
from core.blocked_sites import should_run  # noqa: E402
from core import preflight as PF  # noqa: E402
import run_gazette as G  # noqa: E402
from run_gosigongo import discover_provinces  # noqa: E402

DEFAULT_DB = str(DATA_DIR / "gosigongo.sqlite")
DEFAULT_EXCEL = os.path.join(HERE, "output", "시군구_공보게시판_목록_new.xlsx")


# 지역 그룹 -> 고시공고 도(cities/*.py PROVINCE_NAME) 목록. 공보는 엑셀의 '권역(파일)' 이 지역 이름과 같은 게시판.
# 전국은 기관이 많아 실행 시간이 길어지므로 둘로 나눠 각각 따로 돈다(DB 파일도 전국1/전국2 로 분리: 같은 파일을 두 job 이 동시에 커밋하면 충돌).
# 공보 엑셀에는 '전국' 권역이 없어 전국1/2 는 고시공고만 수집한다.
# 2026-11-04 전국1/전국2 를 기관 유형별 7개 그룹으로 세분화했다(그룹마다 DB 파일·수집로그 탭·워크플로 job 이 따로 생긴다).
# 새 기관은 cities/central_agencies.py·dev_corps.py 에 City 를 추가하고 아래 REGION_CITIES 의 알맞은 그룹에 이름만 넣는다.
REGION_PROVINCES = {
    "중앙국토부": ["중앙기관"], "중앙환경청": ["중앙기관"], "중앙보상": ["중앙기관"], "중앙국방": ["중앙기관"],
    "공기업개발공사": ["공기업"], "공기업도시공사": ["공기업"], "관보": ["관보"],
}
REGION_CITIES = {
    "중앙국토부": ["원주지방국토관리청", "대전지방국토관리청", "익산지방국토관리청", "부산지방국토관리청",
               "서울지방항공청", "부산지방항공청"],
    "중앙환경청": ["금강유역환경청", "한강유역환경청", "낙동강유역환경청", "영산강유역환경청"],
    "중앙보상": ["한국부동산원", "LH보상정보"],
    "중앙국방": ["국방시설본부", "국방부고시공고"],
    "공기업개발공사": ["경상북도개발공사", "경상남도개발공사", "전북개발공사", "강원개발공사", "충남개발공사", "충북개발공사"],
    "공기업도시공사": ["부천도시공사", "서울주택도시공사(SH)", "부산도시공사", "인천도시공사", "대전도시공사",
                "울산도시공사", "광주광역시도시공사"],
    "관보": ["전자관보"],
}
WIDE_REGIONS = list(REGION_CITIES)  # 지자체 16곳과 달리 기관이 많아 5일에 한 번 도는 그룹들
REGIONS = ["강원", "경기", "경남", "경북", "광주", "대구", "대전", "부산", "세종", "울산", "인천", "전남", "전북",
           "제주", "충남", "충북"] + WIDE_REGIONS


def region_db_path(region):
    return str(DATA_DIR / f"{region}.sqlite")


def _log_skipped(blocked, city, kind, url):
    """--blocked skip 으로 건너뛴 게시판을 로그에 남긴다(PC 가 대신 수집하는 곳이라는 표시. 이 행은 정상·오류 어느 쪽 증거도 아니다)."""
    if blocked == "skip":
        LOG.board({"city": city, "kind": kind, "status": "건너뜀(막힌 게시판: PC 수집)",
                   "detail": "호스티드 러너에서 접속이 막혀 core/blocked_sites.py 목록에 있음", "url": url})


def _runner_info():
    """이 실행이 어디서 도는지(Actions 인지 PC 인지)와 외부 IP 대략. 접속 차단 원인을 가릴 때 쓴다."""
    where = "GitHub Actions" if os.environ.get("GITHUB_ACTIONS") else "PC"
    ip = ""
    try:
        import requests
        ip = requests.get("https://api.ipify.org", timeout=8).text.strip()[:45]
    except Exception:
        ip = "IP 확인 실패"
    return f"{where} {os.environ.get('RUNNER_OS', sys.platform)} IP {ip}"


def board_urls(provinces, modules, cities, excel, only, region, blocked):
    """이번 실행이 열어 볼 게시판 주소들(사전 점검용). 실제 수집과 같은 조건(지역·지자체·막힌 게시판 제외)으로 고른다."""
    urls = []
    if only != "gazette":
        P = discover_provinces()
        for name in provinces or list(P):
            for city in getattr(P.get(name), "CITIES", []):
                if (not cities or city.city in cities) and should_run(blocked, region or name, city.city):
                    urls.append(city.base_url)
    if only != "gosigongo":
        for b in G.load_boards(excel):
            if (not modules or b["module"] in modules) and (not cities or b["city"] in cities) and should_run(blocked, b["module"], b["city"]):
                urls.append(b["url"])
    return urls


STALL_SECONDS = 300  # 지자체 하나가 이 시간(초) 동안 아무 출력·진행이 없으면 멈춘 것으로 보고 다음 지자체로 넘어간다


class _ActivityStdout:
    """표준출력에 뭔가 찍힐 때마다 '마지막 진행 시각'을 갱신한다(수집은 쪽/글마다 계속 출력한다)."""

    def __init__(self, inner):
        self._inner = inner
        self.last = time.time()

    def write(self, text):
        self.last = time.time()
        return self._inner.write(text)

    def flush(self):
        return self._inner.flush()

    def __getattr__(self, name):
        return getattr(self._inner, name)


def run_with_stall_guard(fn, activity, stall=STALL_SECONDS):
    """fn() 을 별도 스레드에서 돌리고 -> (끝났는지, 반환값, 예외). stall 초 동안 출력이 없으면 기다리지 않고 (False, None, None).
    멈춘 스레드는 죽일 수 없어 데몬으로 그냥 두고(결과는 버림) 다음 지자체로 넘어간다. 다음 스케줄 실행에서 다시 수집한다."""
    box = {}

    def target():
        try:
            box["value"] = fn()
        except BaseException as e:  # noqa: BLE001 - 호출한 쪽에서 다시 던진다
            box["error"] = e

    t = threading.Thread(target=target, daemon=True)
    activity.last = time.time()
    t.start()
    while t.is_alive():
        t.join(5)
        if t.is_alive() and time.time() - activity.last > stall:
            return False, None, None
    return True, box.get("value"), box.get("error")


def job_gosigongo(con, days, delay, provinces, cities, region=None, blocked="all", reread=False):
    started = S.now()
    P = discover_provinces()
    wanted = provinces or list(P)
    tmp = Path(tempfile.mkdtemp(prefix="gosigongo_"))
    resolver = PnuResolver(con)
    total, new_parcels, dropped, failed = 0, 0, 0, []
    activity = _ActivityStdout(sys.stdout)
    sys.stdout = activity
    for name in wanted:
        if name not in P:
            print(f"[건너뜀] 알 수 없는 도: {name}")
            continue
        for city in P[name].CITIES:
            if cities and city.city not in cities:
                continue
            if not should_run(blocked, region or name, city.city):  # 키는 지역 그룹 이름(--region), 지정이 없으면 도 모듈 이름
                _log_skipped(blocked, city.city, "고시공고", city.base_url)
                continue
            try:
                sink, outcomes = [], []
                seen = set() if reread else S.load_seen(con, "고시공고", city.city)  # 지난 실행에서 끝낸 글은 다시 받지 않는다
                done, records, err = run_with_stall_guard(
                    lambda: run_city(city, days=days, output_dir=tmp, dry_run=False, delay=delay, jose_sink=sink,
                                     skip_keys=seen, outcomes=outcomes), activity)
                if not done:  # 멈춤: 이 지자체는 포기하고(저장·처리기록 없음) 다음 지자체로. 다음 스케줄에 다시 수집된다
                    msg = f"{STALL_SECONDS // 60}분 넘게 진행이 없어 건너뜀(다음 스케줄에 다시 수집)"
                    print(f"[멈춤] {name}/{city.city}: {msg}", flush=True)
                    failed.append(f"{name}/{city.city}: 멈춤")
                    LOG.board({"city": city.city, "kind": "고시공고", "status": "오류(멈춤)", "detail": f"{name}/{city.city} {msg}",
                               "url": city.base_url, "errors": ["STALL"]}, "STALL")
                    continue
                if err is not None:
                    raise err
                total += len(records)
                n, d = S.save_parcels(con, resolver, city.city, "고시공고", sink)
                new_parcels, dropped = new_parcels + n, dropped + d
                S.record_seen(con, "고시공고", city.city, outcomes)  # 필지를 저장한 뒤에 기록한다
            except Exception as e:
                failed.append(f"{name}/{city.city}: {type(e).__name__}")
                traceback.print_exc()
                LOG.board({"city": city.city, "kind": "고시공고", "status": "오류(지자체 전체)", "detail": f"{name}/{city.city} 수집 중 예외",
                           "url": city.base_url, "errors": [f"{type(e).__name__}: {str(e)[:150]}"]},
                          f"{type(e).__name__}: {str(e)[:150]}")
    sys.stdout = activity._inner
    summary = f"고시공고 {total}건, 새 필지(PNU) {new_parcels}건, PNU 변환실패 {dropped}건, PNU {resolver.stats}, 실패 {len(failed)}곳 {failed[:20]}, {LOG.code_summary()}"
    print(summary)
    S.log_run(con, started, "gosigongo", days, summary)


def job_gazette(con, days, workers, excel, modules, cities, blocked="all", reread=False):
    started = S.now()
    boards = G.load_boards(excel)
    if cities:
        boards = [b for b in boards if b["city"] in cities]
    if modules:
        boards = [b for b in boards if b["module"] in modules]
    for b in boards:
        if not should_run(blocked, b["module"], b["city"]):
            _log_skipped(blocked, b["city"], b["kind"], b["url"])
    boards = [b for b in boards if should_run(blocked, b["module"], b["city"])]
    idx = G.regions_index()
    seen_by = {} if reread else {(b["module"], b["city"]): S.load_seen(con, "공보", f'{b["module"]}/{b["city"]}') for b in boards}
    jobs = [(b, days, idx.get((b["module"], b["city"])), seen_by.get((b["module"], b["city"]))) for b in boards]
    print(f"공보 게시판 {len(jobs)}곳, 최근 {days}일")
    resolver = PnuResolver(con)
    new_addr, dropped, counts = 0, 0, Counter()
    t0 = time.time()
    # 일정 수만큼 끊어 저장해, 실행 시간 제한으로 끊겨도 앞부분 결과는 DB에 남긴다
    chunk = max(workers * 3, 12)
    with ThreadPoolExecutor(workers) as ex:
        for i in range(0, len(jobs), chunk):
            results = list(ex.map(G.process_board, jobs[i:i + chunk]))
            n, d = S.save_gazette(con, results, resolver)  # 필지 저장 뒤 처리한 글을 기록한다(save_gazette 안)
            new_addr, dropped = new_addr + n, dropped + d
            counts.update(r["status"] for r in results)
            print(f"  진행 {min(i + chunk, len(jobs))}/{len(jobs)} ({time.time() - t0:.0f}초)", flush=True)
    summary = f"공보 {len(jobs)}곳, 새 필지(PNU) {new_addr}건, PNU 변환실패 {dropped}건, PNU {resolver.stats}, 상태 {dict(counts)}"
    print(summary)
    S.log_run(con, started, "gazette", days, summary)


def main():
    ap = argparse.ArgumentParser(description="스케줄 수집 -> SQLite")
    ap.add_argument("--only", choices=["gosigongo", "gazette"])
    ap.add_argument("--region", choices=REGIONS, help="지역 그룹 하나만 실행하고 data/{지역}.sqlite 에 저장")
    ap.add_argument("--db", default=None)
    ap.add_argument("--excel", default=DEFAULT_EXCEL)
    ap.add_argument("--gosi-days", type=int, default=7)
    ap.add_argument("--gazette-days", type=int, default=7)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--delay", type=float, default=0.3)
    ap.add_argument("--province", action="append", help="고시공고: 도 이름 (예: 강원)")
    ap.add_argument("--module", action="append", help="공보: 권역(파일) 이름")
    ap.add_argument("--city", action="append")
    ap.add_argument("--reread", action="store_true",
                    help="이미 처리한 글(seen_posts)도 건너뛰지 않고 모두 다시 읽는다(추출 코드를 고친 뒤 수동 재수집용)")
    ap.add_argument("--log-prefix", default="",
                    help="수집로그 시트 탭 이름 앞에 붙일 말(PC 수집은 'PC' -> 'PC경북_게시판상태'). Actions 로그와 섞이지 않게 한다")
    ap.add_argument("--preflight", action="store_true",
                    help="수집 전에 이 IP 가 지역 사이트들에 닿는지 확인하고, 대부분 안 닿으면 수집하지 않고 종료코드 75 로 끝낸다(워크플로가 새 러너로 재시도)")
    ap.add_argument("--blocked", choices=["all", "skip", "only"], default="all",
                    help="호스티드 러너에서 막히는 게시판(core/blocked_sites.py): all=전부(기본), skip=건너뜀, only=그곳만(국내 IP 러너용)")
    a = ap.parse_args()

    provinces, modules, cities = a.province, a.module, a.city
    if a.region:
        provinces = REGION_PROVINCES.get(a.region, [a.region])
        modules = [a.region]
        cities = cities or REGION_CITIES.get(a.region)
    db = a.db or (region_db_path(a.region) if a.region else DEFAULT_DB)
    LOG.region = a.log_prefix + (a.region or "전체")
    log_path = str(DATA_DIR / "logs" / f"{LOG.region}_수집로그.xlsx")
    con = S.connect(db)
    blocked_ip = False
    attempt = os.environ.get("ATTEMPT") or "1"  # 워크플로가 러너 IP 차단 의심으로 다시 돌린 횟수(1=첫 실행)
    LOG.summary("실행환경", f"{_runner_info()}; 모드 blocked={a.blocked}; 고시공고 {a.gosi_days}일, 공보 {a.gazette_days}일; 시도 {attempt}회차"
                          f"{' (미리 점검 켬)' if a.preflight else ''}")
    try:
        # 이전 실행에서 PNU로 못 바꾼 주소를 먼저 다시 시도(코드/규칙이 개선됐으면 여기서 복구된다)
        n_reset = S.reset_recent_unresolved(con)  # 추출 규칙 버전이 오르면 최근 글의 미해결 행을 비워 새 규칙으로 다시 만들게 한다
        if n_reset:
            print(f"추출 규칙 버전 갱신: 최근 글의 미해결 {n_reset}행을 비움(다시 읽어 새로 만든다)")
        started = S.now()
        resolver = PnuResolver(con)
        tried, fixed = S.retry_unresolved(con, resolver)
        left = con.execute("SELECT count(*) FROM parcels_unresolved").fetchone()[0]
        msg = f"미해결 재시도 {tried}건 중 {fixed}건 복구, 남은 미해결 {left}건, PNU {resolver.stats}"
        print(msg)
        S.log_run(con, started, "retry", 0, msg)
        S.prune_old(con)  # 오래된 점검용 행 정리(필지·공고는 그대로)
        if a.preflight:
            ok, total, bad = PF.probe(board_urls(provinces, modules, cities, a.excel, a.only, a.region, a.blocked))
            msg = f"사전 점검(시도 {attempt}회차): 사이트 {total}곳 중 {ok}곳 접속 가능({ok * 100 // max(total, 1)}%, 기준 {int(PF.MIN_OK_RATIO * 100)}% 미만이면 차단 의심)"
            if bad:
                msg += f", 안 닿는 {len(bad)}곳 단계별 {PF.stage_counts(bad)}, 예 {PF.stage_examples(bad, 5)}"
            if PF.looks_blocked(ok, total):
                msg += f" -> 이 러너 IP 가 막힌 것으로 보여 수집하지 않음(종료코드 {PF.EXIT_BLOCKED}, 새 러너로 재시도)"
                blocked_ip = True
            print(msg)
            LOG.summary("사전점검", msg)
        if blocked_ip:
            pass
        elif a.only != "gazette":
            job_gosigongo(con, a.gosi_days, a.delay, provinces, cities, a.region, a.blocked, a.reread)
        if not blocked_ip and a.only != "gosigongo":
            job_gazette(con, a.gazette_days, a.workers, a.excel, modules, cities, a.blocked, a.reread)
    finally:
        con.close()
        net = LOG.network_summary()  # 목록 오류가 있으면 접속 단계별로 세어 러너 IP 차단/사이트 문제를 한 줄로 판정(게시판상태 행에도 진단이 붙는다)
        if net:
            print(net)
            LOG.summary("접속진단", net)
        LOG.flush_sheets()
        LOG.flush(log_path)  # 문제 단서(원인코드·조치 힌트)를 엑셀로 남긴다. 실패해도 수집 결과에는 영향 없음
    if blocked_ip:
        sys.exit(PF.EXIT_BLOCKED)


if __name__ == "__main__":
    main()
