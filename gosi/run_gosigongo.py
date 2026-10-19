"""
run_gosigongo.py - 지역별 고시공고 크롤링 실행기

사용 예
  python run_gosigongo.py                     # 인자 없이: DEFAULT_PROVINCES 실행
  python run_gosigongo.py 강원                 # 강원권 전체 (cities/gangwon.py에 등록된 모든 시)
  python run_gosigongo.py 강원 --city 원주시    # 도 안에서 특정 지자체만
  python run_gosigongo.py --all                # cities/*.py 로 등록된 모든 도
  python run_gosigongo.py 강원 --dry-run        # 상세페이지 조회 없이 목록만 저장
  옵션: --days 12  --delay 0.3  --output output  --load-bigquery --config config.json

새 도 추가: cities/XXXX.py 파일을 만들고 PROVINCE_NAME 과 CITIES 를 정의하면 자동 인식된다.
새 지자체 추가: 먼저 실제 게시판 구조(목록/상세/첨부 URL 패턴)를 탐색해 확인한 뒤,
  해당 cities/XXXX.py 의 CITIES 리스트에 City(...) 를 하나 더 추가한다 (law.md 3-2 참고).
"""
import argparse
import importlib
import os
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from core.board_crawler import run_city  # noqa: E402

DEFAULT_PROVINCES = ["강원"]


def discover_provinces():
    """cities/*.py 파일을 찾아 {도 이름: 모듈} 로 반환."""
    provinces = {}
    cities_dir = Path(HERE) / "cities"
    for path in sorted(cities_dir.glob("*.py")):
        if path.stem.startswith("_"):
            continue
        mod = importlib.import_module(f"cities.{path.stem}")
        provinces[mod.PROVINCE_NAME] = mod
    return provinces


def main():
    parser = argparse.ArgumentParser(description="지역별 고시공고 크롤러")
    parser.add_argument("provinces", nargs="*", help="실행할 도 이름 (예: 강원)")
    parser.add_argument("--all", action="store_true", help="등록된 모든 도 실행")
    parser.add_argument("--city", action="append", help="도 안에서 이 지자체만 (여러 번 지정 가능)")
    parser.add_argument("--days", type=int, default=12, help="최근 며칠 이내 항목만 수집 (기본 12)")
    parser.add_argument("--output", type=str, default="output", help="결과 저장 폴더")
    parser.add_argument("--dry-run", action="store_true", help="상세페이지 조회 없이 목록만 저장")
    parser.add_argument("--delay", type=float, default=0.3, help="요청 간 대기 시간(초)")
    parser.add_argument(
        "--load-bigquery",
        action="store_true",
        help="크롤링 후 config.json 설정으로 BigQuery에 바로 적재",
    )
    parser.add_argument("--config", type=str, default="config.json", help="BigQuery 설정 파일 경로")
    args = parser.parse_args()

    provinces = discover_provinces()
    if not provinces:
        print("cities/*.py 파일이 없습니다.")
        return
    wanted = list(provinces) if args.all else (args.provinces or DEFAULT_PROVINCES)
    unknown = [p for p in wanted if p not in provinces]
    if unknown:
        print(f"알 수 없는 도: {unknown} / 등록된 도: {list(provinces)}")
        return

    output_dir = Path(args.output)
    all_records = []
    for name in wanted:
        mod = provinces[name]
        cities = [c for c in mod.CITIES if not args.city or c.city in args.city]
        if not cities:
            print(f"[{name}] --city 조건에 맞는 지자체가 없습니다. (등록: {[c.city for c in mod.CITIES]})")
            continue
        for city in cities:
            records = run_city(
                city, days=args.days, output_dir=output_dir, dry_run=args.dry_run, delay=args.delay
            )
            all_records += records

    if args.load_bigquery:
        import bigquery_loader

        bigquery_loader.load_records(all_records, config_path=args.config)


if __name__ == "__main__":
    main()
