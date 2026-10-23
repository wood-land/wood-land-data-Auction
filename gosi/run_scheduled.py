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
REGION_PROVINCES = {"전국1": ["중앙기관"], "전국2": ["공기업", "관보"]}
REGIONS = ["강원", "경기", "경남", "경북", "광주", "대구", "대전", "부산", "세종", "울산", "인천", "전남", "전북",
           "제주", "충남", "충북", "전국1", "전국2"]


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


def job_gosigongo(con, days, delay, provinces, cities, region=None, blocked="all", reread=False):
    started = S.now()
    P = discover_provinces()
    wanted = provinces or list(P)
    tmp = Path(tempfile.mkdtemp(prefix="gosigongo_"))
    resolver = PnuResolver(con)
    total, new_parcels, dropped, failed = 0, 0, 0, []
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
                records = run_city(city, days=days, output_dir=tmp, dry_run=False, delay=delay, jose_sink=sink,
                                   skip_keys=seen, outcomes=outcomes)
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

    provinces, modules = a.province, a.module
    if a.region:
        provinces = REGION_PROVINCES.get(a.region, [a.region])
        modules = [a.region]
    db = a.db or (region_db_path(a.region) if a.region else DEFAULT_DB)
    LOG.region = a.log_prefix + (a.region or "전체")
    log_path = str(DATA_DIR / "logs" / f"{LOG.region}_수집로그.xlsx")
    con = S.connect(db)
    blocked_ip = False
    LOG.summary("실행환경", f"{_runner_info()}; 모드 blocked={a.blocked}; 고시공고 {a.gosi_days}일, 공보 {a.gazette_days}일")
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
            ok, total, bad = PF.probe(board_urls(provinces, modules, a.city, a.excel, a.only, a.region, a.blocked))
            msg = f"사전 점검: 사이트 {total}곳 중 {ok}곳 접속 가능" + (f", 안 닿는 곳 {bad[:8]}" if bad else "")
            if PF.looks_blocked(ok, total):
                msg += f" -> 이 러너 IP 가 막힌 것으로 보여 수집하지 않음(종료코드 {PF.EXIT_BLOCKED}, 새 러너로 재시도)"
                blocked_ip = True
            print(msg)
            LOG.summary("사전점검", msg)
        if blocked_ip:
            pass
        elif a.only != "gazette":
            job_gosigongo(con, a.gosi_days, a.delay, provinces, a.city, a.region, a.blocked, a.reread)
        if not blocked_ip and a.only != "gosigongo":
            job_gazette(con, a.gazette_days, a.workers, a.excel, modules, a.city, a.blocked, a.reread)
    finally:
        con.close()
        LOG.flush_sheets()
        LOG.flush(log_path)  # 문제 단서(원인코드·조치 힌트)를 엑셀로 남긴다. 실패해도 수집 결과에는 영향 없음
    if blocked_ip:
        sys.exit(PF.EXIT_BLOCKED)


if __name__ == "__main__":
    main()
