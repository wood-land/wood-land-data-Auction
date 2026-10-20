r"""
run_crawl.py - 지역별 신문 기사 수집 실행기

사용 방법:
  1. VSCode에서 실행(F5 또는 재생 버튼):
     - 터미널에 번호 메뉴가 표시되며 원하는 지역 번호(1~6 또는 7 전체) 입력
  2. 터미널 명령어로 지역 지정 실행:
     python run_crawl.py 경남                  # 경남·부산 권역 23곳 → output/경남·부산_날짜.csv
     python run_crawl.py 충청                  # 충청 권역 31곳 → output/충청·대전·세종_날짜.csv
     python run_crawl.py 경북                  # 경북·대구·울산 권역 31곳 → output/경북·대구·울산_날짜.csv
     python run_crawl.py 강원 경기             # 여러 지역 순차 수집 (각각 개별 CSV로 분리 저장)
     python run_crawl.py --all                 # 활성화된 모든 지역 순차 수집
  3. 특정 신문사만 수집/점검:
     python run_crawl.py 경남 --paper 합천신문          # 합천신문만 수집하여 CSV 저장
     python run_crawl.py 경남 --paper 합천신문 --check  # 저장 없이 선택자 및 수집 점검
  4. 주요 옵션:
     --days 30          # 최근 N일 이내 기사만 수집 (기본: 15일)
     --keyword 보상     # --check 점검 시 사용할 검색어 (기본: 일대)
     --out 저장폴더     # 결과 CSV 저장 위치 (기본: output/)
     --pnu              # 수집 후 지번 주소 완성 및 국토부 PNU 매핑 파이프라인 자동 실행
"""
import argparse
import importlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from crawler_core import Crawler, Settings  # noqa: E402

# =============================== 사용자 설정 ===============================
# 결과 저장 폴더 (다른 PC / 깃 자동 실행에서도 돌도록 경로를 고정하지 않는다)
#   우선순위: --out 옵션  >  환경변수 NEWS_SAVE_DIR  >  이 폴더 아래 output\  (깃에는 올리지 않음: .gitignore)
#   예) 내 PC에서 예전처럼 쓰려면:  set NEWS_SAVE_DIR=D:\12.신문기사 수집
SAVE_DIRECTORY = os.environ.get("NEWS_SAVE_DIR") or os.path.join(HERE, "output")

DEFAULT_REGIONS = ["충청"]        # 인자 없이 실행할 때 돌릴 지역

# 1. 수집 대상 검색 키워드 (보상/사업 관련 핵심 단어)
DEFAULT_KEYWORDS = [
    "토지 보상", "보상 협의", "손실보상", "사업인정", "실시계획",
    "재해위험", "개선복구", "실시설계", "정비사업", "투자심사", "조성사업",
]

# 2. 제외 대상 블랙리스트 키워드 (행사, 사설 등 보상 무관 노이즈 단어)
DEFAULT_BLACKLIST_KEYWORDS = [
    "행사", "사설",
]

SEARCH_PERIOD_DAYS = 15      # 최근 N일 이내 기사만 수집
MAX_OLD_IN_A_ROW = 3         # 기간보다 오래된 기사가 연속 N건이면 다음 키워드로
MAX_PAGES_PER_KEYWORD = 30   # 안전장치
HEADLESS = False             # True면 브라우저 창 없이 실행 (Selenium 사용 신문사만 해당)
# ==========================================================================


def load_keyword_file(filename: str, default_list: list, label: str = "키워드") -> list:
    """키워드 파일(코드 폴더 또는 저장 폴더)이 있으면 읽고, 없으면 기본 목록 반환 (통합 로더)."""
    candidates = [
        os.path.join(HERE, filename),
        os.path.join(SAVE_DIRECTORY, filename),
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8-sig") as f:
                lines = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
            content = ",".join(lines)
            keywords = [kw.strip().strip("'\"").strip() for kw in content.split(",") if kw.strip().strip("'\"").strip()]
            if keywords:
                print(f"[{label}] 파일 사용: {path} ({', '.join(keywords)})")
                return keywords
    return list(default_list)


def discover_regions():
    """Load numbered region modules from regions/ (12_1 through 12_8)."""
    regions = {}
    region_dir = os.path.join(HERE, "regions")
    for fn in sorted(os.listdir(region_dir)):
        if fn.startswith("12_") and fn.endswith(".py"):
            mod = importlib.import_module(f"regions.{fn[:-3]}")
            regions[mod.REGION_NAME] = mod
    return regions


def main():
    # Keep Windows console checks from crashing on symbols such as checkmarks.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description="지역별 신문 기사 수집기")
    parser.add_argument("regions", nargs="*", help="실행할 지역 이름 (예: 강원 충청)")
    parser.add_argument("--all", action="store_true", help="등록된 모든 지역 실행")
    parser.add_argument("--paper", action="append", help="지역 안에서 이 신문사만 (여러 번 지정 가능)")
    parser.add_argument("--part", default="", help="지역의 활성 신문사를 M개로 나눠 N번째만 수집 (예: 1/2). 큰 지역을 나눠 돌릴 때 사용")
    parser.add_argument("--check", action="store_true", help="저장 없이 선택자만 점검")
    parser.add_argument("--keyword", default="일대", help="--check 에서 쓸 검색어 (기본: 일대)")
    parser.add_argument("--days", type=int, default=SEARCH_PERIOD_DAYS, help="수집 기간(일)")
    parser.add_argument("--headless", action="store_true", help="브라우저 창 없이 실행")
    parser.add_argument("--workers", type=int, default=8, help="requests 방식 신문사 동시 수집 개수 (1=순차, 기본 8)")
    parser.add_argument("--min-score", type=int, default=0, help="보상 관련도 최소 점수 (0=기본값 사용)")
    parser.add_argument("--out", default="", help="결과 저장 폴더 (기본: 환경변수 NEWS_SAVE_DIR 또는 output\\)")
    parser.add_argument("--pnu", action="store_true", help="수집 완료 후 자동으로 주소 완성 및 PNU 발급(SQLite 저장)")
    args, _ = parser.parse_known_args()   # IDE에서 낯선 인자가 붙어도 무시

    regions = discover_regions()
    if not regions:
        print("region_*.py 파일이 없습니다.")
        return

    REGION_ALIASES = {
        "강원": "강원",
        "강원도": "강원",
        "경기": "경기·인천",
        "인천": "경기·인천",
        "경기인천": "경기·인천",
        "경기·인천": "경기·인천",
        "전라": "전라·광주",
        "전라도": "전라·광주",
        "광주": "전라·광주",
        "전북": "전라·광주",
        "전남": "전라·광주",
        "전라·광주": "전라·광주",
        "충청": "충청·대전·세종",
        "충청도": "충청·대전·세종",
        "대전": "충청·대전·세종",
        "세종": "충청·대전·세종",
        "충북": "충청·대전·세종",
        "충남": "충청·대전·세종",
        "충청·대전·세종": "충청·대전·세종",
        "경북": "경북·대구·울산",
        "경상북도": "경북·대구·울산",
        "대구": "경북·대구·울산",
        "울산": "경북·대구·울산",
        "경북·대구·울산": "경북·대구·울산",
        "경남": "경남·부산",
        "경상남도": "경남·부산",
        "부산": "경남·부산",
        "경남·부산": "경남·부산",
    }

    # 터미널에서 인자 없이 실행(VSCode 실행 버튼 포함)했을 때 대화형 메뉴 제공
    if not args.all and not args.regions:
        if sys.stdin.isatty():
            active_regions = [r for r in regions.keys() if any(s.enabled for s in regions[r].SITES)]
            print("\n" + "═" * 60)
            print("  📰 [지역별 신문 기사 수집기] - 추출할 지역을 선택하세요")
            print("═" * 60)
            for idx, rname in enumerate(active_regions, 1):
                mod = regions[rname]
                active_cnt = sum(1 for s in mod.SITES if s.enabled)
                print(f"   [{idx}] {rname:<16} : {active_cnt}개 신문사 활성")
            print(f"   [{len(active_regions) + 1}] {'전체 지역':<16} : 모든 권역 순차 수집")
            print("─" * 60)
            try:
                choice = input(f"👉 지역 번호 또는 이름 입력 (1~{len(active_regions)+1}, Enter=충청): ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n실행이 취소되었습니다.")
                return

            if not choice:
                raw_wanted = DEFAULT_REGIONS
            elif choice in (str(len(active_regions) + 1), "전체", "all", "ALL"):
                raw_wanted = active_regions
            else:
                parts = [p.strip() for p in re.split(r"[, ]+", choice) if p.strip()]
                resolved = []
                for p in parts:
                    if p.isdigit() and 1 <= int(p) <= len(active_regions):
                        resolved.append(active_regions[int(p) - 1])
                    else:
                        resolved.append(p)
                raw_wanted = resolved
        else:
            raw_wanted = DEFAULT_REGIONS
    else:
        raw_wanted = list(regions) if args.all else args.regions

    wanted = [REGION_ALIASES.get(r, r) for r in raw_wanted]
    unknown = [r for r in wanted if r not in regions]
    if unknown:
        print(f"알 수 없는 지역: {unknown} / 등록된 지역: {list(regions)}")
        return

    settings = Settings(
        save_directory=args.out or SAVE_DIRECTORY,
        keywords=load_keyword_file("search_keywords.txt", DEFAULT_KEYWORDS, "수집 키워드"),
        blacklist_keywords=load_keyword_file("blacklist_keywords.txt", DEFAULT_BLACKLIST_KEYWORDS, "블랙리스트"),
        search_period_days=args.days,
        max_old_in_a_row=MAX_OLD_IN_A_ROW,
        max_pages_per_keyword=MAX_PAGES_PER_KEYWORD,
        headless=HEADLESS or args.headless,
        workers=args.workers,
        min_score=args.min_score,
    )
    crawler = Crawler(settings)
    try:
        for name in wanted:
            mod = regions[name]
            if args.check:
                results = {s.name: crawler.check_site(s, args.keyword)
                           for s in mod.SITES if not args.paper or s.name in args.paper}
                print("\n점검 결과:", {k: ("정상" if v else "확인 필요") for k, v in results.items()})
            else:
                only = args.paper
                if args.part:
                    n, m = (int(x) for x in args.part.split("/"))
                    active = [x.name for x in mod.SITES if x.enabled]
                    only = [nm for i, nm in enumerate(active) if i % m == n - 1]   # 번갈아 나눠 큰 신문사가 한쪽에 몰리지 않게 한다
                    print(f"[{name}] {args.part} 부분: 활성 {len(active)}곳 중 {len(only)}곳 -> {', '.join(only)}")
                csv_path = crawler.run_region(name, mod.SITES, only=only)
                if csv_path and os.path.exists(csv_path):
                    # 크롤링 완료 후 자동으로 주소 완전화 및 중복 기사 1건만 남기기 정제 실행
                    from clean_news_csv import process_clean_file
                    cleaned_csv = process_clean_file(csv_path)

                    target_for_pnu = cleaned_csv or csv_path
                    if args.pnu and target_for_pnu and os.path.exists(target_for_pnu):
                        from pnu_pipeline import process_csv_file
                        db_path = os.path.join(settings.save_directory, "news_articles_pnu.db")
                        print(f"\n🚀 [--pnu] 정제된 기사의 주소 완성 및 PNU 발급 파이프라인 가동...")
                        process_csv_file(target_for_pnu, db_path)
    except KeyboardInterrupt:
        print("\n\n🛑 [중단 안내] 사용자에 의해 작업이 안전하게 중단되었습니다 (Ctrl+C).")
        print("💾 중단 시점까지 수집된 모든 기사는 CSV 파일에 실시간으로 안전하게 저장되어 있습니다.")
        print("🔄 나중에 다시 실행하시면 이미 확인한 기사는 건너뛰고 이어서 수집됩니다.")
    finally:
        crawler.close()


if __name__ == "__main__":
    main()
