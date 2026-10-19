# -*- coding: utf-8 -*-
r"""
pnu_pipeline.py - 신문 기사 추출 결과(CSV/엑셀) → 주소 완성 → PNU 발급 → SQLite 저장 파이프라인

사용 예시:
  # 1. 특정 크롤링 CSV 파일 처리
  python pnu_pipeline.py --input output/강원_2026-09-26.csv

  # 2. output 폴더 내 최신 CSV 자동 탐색 후 처리
  python pnu_pipeline.py

  # 3. SQLite 데이터베이스 경로 지정
  python pnu_pipeline.py --input output/경기·인천_2026-09-26.csv --db output/my_pnu.db

  # 4. 단일 주소 테스트
  python pnu_pipeline.py --test "지정면 신평리 400" --hint "원주시"
"""

import argparse
import csv
import glob
import os
import sys
import sqlite3
from typing import List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from common.pnu_resolver import PNUResolver, complete_korean_address  # noqa: E402


def find_latest_csv(directory: str) -> Optional[str]:
    """지정된 디렉토리에서 가장 최근에 생성된 CSV 파일 탐색"""
    csv_files = glob.glob(os.path.join(directory, "*.csv"))
    # _with_pnu 파일은 제외
    csv_files = [f for f in csv_files if not f.endswith("_with_pnu.csv")]
    if not csv_files:
        return None
    return max(csv_files, key=os.path.getmtime)


def process_csv_file(input_csv: str, db_path: str, output_csv: Optional[str] = None):
    """
    크롤링 CSV 파일을 읽어 주소를 완성하고 PNU를 발급한 뒤 SQLite와 새 CSV에 기록
    """
    if not os.path.isfile(input_csv):
        print(f"❌ 파일을 찾을 수 없습니다: {input_csv}")
        return

    print(f"\n📂 입력 파일: {input_csv}")
    print(f"🗄️ SQLite 데이터베이스: {db_path}")

    resolver = PNUResolver(db_path=db_path)

    # 결과 저장용 CSV 경로
    if not output_csv:
        base, ext = os.path.splitext(input_csv)
        output_csv = f"{base}_with_pnu{ext}"

    rows_with_addr = 0
    total_addrs = 0
    success_pnus = 0
    total_saved_db = 0
    total_duplicates_skipped = 0

    with open(input_csv, "r", encoding="utf-8-sig") as infile:
        reader = list(csv.DictReader(infile))

    fieldnames = list(reader[0].keys()) if reader else []
    for col in ["완성주소", "PNU", "PNU발급출처", "표준주소명"]:
        if col not in fieldnames:
            fieldnames.append(col)

    output_rows = []

    print(f"총 {len(reader)}건의 기사 레코드를 검토합니다...")

    for idx, row in enumerate(reader, start=1):
        raw_addrs_str = row.get("주소추출", "") or ""
        paper = row.get("신문사", "")
        area_hint = row.get("지역힌트", "")
        title = row.get("제목", "")
        body = row.get("본문", "")
        link = row.get("링크", "")

        # 쉼표나 세미콜론 등으로 구분된 여러 주소 처리
        addr_list = [a.strip() for a in re_split_addrs(raw_addrs_str) if a.strip()]

        if not addr_list:
            output_rows.append(row)
            continue

        rows_with_addr += 1
        pnu_results = []
        completed_list = []
        pnu_list = []
        source_list = []
        std_name_list = []

        for raw_addr in addr_list:
            total_addrs += 1
            res = resolver.resolve(
                raw_addr=raw_addr,
                area_hint=area_hint,
                paper=paper,
                context_text=f"{title} {body[:200]}"
            )
            pnu_results.append(res)
            completed_list.append(res.completed_address)
            pnu_list.append(res.pnu or "")
            source_list.append(res.source)
            std_name_list.append(res.standard_name)

            if res.status == "SUCCESS" and res.pnu:
                success_pnus += 1
                print(f"  ✔ [{paper}] '{raw_addr}' → '{res.completed_address}' → PNU: {res.pnu} ({res.source})")
            else:
                print(f"  ✘ [{paper}] '{raw_addr}' → '{res.completed_address}' → 실패: {res.error_message}")

        # SQLite 저장 (동일 PNU + 동일 기사 중복 자동 방지)
        article_meta = {
            "link": link,
            "paper": paper,
            "keyword": row.get("검색어", ""),
            "title": title,
            "date": row.get("날짜", ""),
            "area": area_hint,
            "address_extracted": raw_addrs_str,
            "relevance_score": int(row.get("보상점수") or 0) if str(row.get("보상점수", "")).lstrip("-").isdigit() else None,
            "relevance_keywords": row.get("보상키워드", ""),
            "body": body,
        }
        saved_cnt, dup_cnt = resolver.save_article_and_addresses(article_meta, pnu_results)
        total_saved_db += saved_cnt
        total_duplicates_skipped += dup_cnt

        # 갱신된 필드 반영
        new_row = dict(row)
        new_row["완성주소"] = " | ".join(completed_list)
        new_row["PNU"] = " | ".join(pnu_list)
        new_row["PNU발급출처"] = " | ".join(source_list)
        new_row["표준주소명"] = " | ".join(std_name_list)
        output_rows.append(new_row)

    # 파일 출력
    with open(output_csv, "w", encoding="utf-8-sig", newline="") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    resolver.close()

    print(f"\n==================== 처리 요약 ====================")
    print(f"  기사 총 건수: {len(reader)}건")
    print(f"  주소 포함 기사: {rows_with_addr}건")
    print(f"  발굴된 개별 주소: {total_addrs}건")
    print(f"  PNU 발급 성공: {success_pnus}건 (성공률: {success_pnus/total_addrs*100:.1f}%)" if total_addrs else "  주소 없음")
    print(f"  [DB] SQLite 신규 저장: {total_saved_db}건")
    print(f"  [중복 제외] 동일 PNU 기사: {total_duplicates_skipped}건")
    print(f"  [DB] SQLite DB 파일: {db_path}")
    print(f"  [CSV] 확장 CSV 파일: {output_csv}")
    print(f"==================================================")


def re_split_addrs(text: str) -> List[str]:
    """쉼표, 세미콜론, 줄바꿈 등으로 묶인 주소 목록 분리"""
    import re
    if not text:
        return []
    # [ '주소1', '주소2' ] 형태나 '주소1, 주소2' 형태 처리
    cleaned = text.strip("[]'\" ")
    parts = re.split(r"[,;\n|/]+", cleaned)
    return [p.strip().strip("'\"") for p in parts if p.strip()]


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    parser = argparse.ArgumentParser(description="신문 기사 주소 완성 및 PNU 발급 파이프라인")
    parser.add_argument("--input", "-i", help="입력 크롤링 CSV 파일 경로")
    parser.add_argument("--db", default=os.path.join(HERE, "output", "news_articles_pnu.db"),
                        help="저장할 SQLite 데이터베이스 경로")
    parser.add_argument("--out", "-o", help="결과를 저장할 CSV 파일 경로")
    parser.add_argument("--test", help="단일 주소 테스트 (예: '지정면 신평리 400')")
    parser.add_argument("--hint", default="", help="--test 시 함께 제공할 지역힌트 (예: '원주시')")
    args = parser.parse_args()

    if args.test:
        resolver = PNUResolver(db_path=args.db)
        print(f"\n[단일 주소 테스트]")
        print(f"  입력 주소: {args.test}")
        print(f"  지역 힌트: {args.hint}")
        res = resolver.resolve(args.test, area_hint=args.hint)
        print(f"  완성 주소: {res.completed_address}")
        print(f"  PNU 결과: {res.pnu} ({res.source})")
        print(f"  표준 명칭: {res.standard_name}")
        print(f"  좌표: x={res.x}, y={res.y}")
        print(f"  상태: {res.status} {res.error_message}")
        resolver.close()
        return

    input_file = args.input
    if not input_file:
        latest = find_latest_csv(os.path.join(HERE, "output"))
        if latest:
            print(f"ℹ️ 입력 파일이 지정되지 않아 output 폴더의 최신 CSV를 선택합니다: {latest}")
            input_file = latest
        else:
            print("❌ 처리할 CSV 파일이 없습니다. --input <경로> 를 지정하세요.")
            return

    process_csv_file(input_file, args.db, args.out)


if __name__ == "__main__":
    main()
