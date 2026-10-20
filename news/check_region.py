"""
check_region.py - 지역의 신문사를 하나씩 접속해 검색어 1개로 시험 검색·기사 추출을 해 보고 표로 요약한다.
저장은 하지 않는다. 실행 환경(GitHub Actions 해외 IP 등)에서 막히는 신문사를 찾는 용도.

  python check_region.py 경북 --keyword 보상 --limit-sec 150
"""
import argparse, importlib, io, os, signal, sys, time, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from crawler_core import Crawler, Settings  # noqa: E402

ALIAS = {"강원": "12_1_gangwon", "경기": "12_2_gyeonggi_incheon", "전라": "12_3_jeolla_gwangju",
         "충청": "12_4_chungcheong_daejeon_sejong", "경북": "12_5_gyeongbuk_daegu_ulsan", "경남": "12_6_gyeongnam_busan"}


class Timeout(Exception):
    pass


def _alarm(signum, frame):
    raise Timeout()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("region")
    ap.add_argument("--keyword", default="보상")
    ap.add_argument("--limit-sec", type=int, default=150)
    ap.add_argument("--paper", action="append")
    a = ap.parse_args()
    mod = importlib.import_module("regions." + ALIAS[a.region])
    crawler = Crawler(Settings(save_directory=os.path.join(HERE, "output"), keywords=[a.keyword], blacklist_keywords=[],
                               search_period_days=3, max_old_in_a_row=3, max_pages_per_keyword=1,
                               headless=True, workers=1, min_score=0))
    signal.signal(signal.SIGALRM, _alarm)
    rows = []
    for s in mod.SITES:
        if a.paper and s.name not in a.paper:
            continue
        buf = io.StringIO(); t0 = time.time(); status = ""
        signal.alarm(a.limit_sec)
        try:
            with contextlib.redirect_stdout(buf):
                ok = crawler.check_site(s, a.keyword)
            status = "정상" if ok else "확인필요"
        except Timeout:
            status = "시간초과(%ds)" % a.limit_sec
        except Exception as e:  # noqa: BLE001
            status = "오류:" + type(e).__name__
        finally:
            signal.alarm(0)
        out = buf.getvalue()
        reason = next((l.strip() for l in out.splitlines() if "✘" in l), "")
        rows.append((s.name, s.fetch, s.enabled, status, round(time.time() - t0, 1), reason[:110]))
        print(f"{s.name:<14} fetch={s.fetch:<9} enabled={s.enabled!s:<5} {status:<14} {rows[-1][4]:>6}s  {reason[:110]}", flush=True)
    crawler.close()
    ok = sum(1 for r in rows if r[3] == "정상")
    print(f"\n요약: 전체 {len(rows)}곳 / 정상 {ok} / 문제 {len(rows) - ok}")
    summ = os.environ.get("GITHUB_STEP_SUMMARY")
    if summ:
        with open(summ, "a", encoding="utf-8") as f:
            f.write(f"### {a.region} 시험 검색 (키워드 {a.keyword})\n\n| 신문사 | 방식 | 활성 | 결과 | 초 | 사유 |\n|---|---|---|---|---|---|\n")
            for r in rows:
                f.write("| " + " | ".join(str(x).replace("|", "/") for x in r) + " |\n")


if __name__ == "__main__":
    main()
