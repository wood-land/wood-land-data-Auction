# -*- coding: utf-8 -*-
r"""
clean_news_csv.py - 크롤링 결과 CSV 주소 완성 및 다수 신문사 중복 기사 정제기

기능:
1. [주소 완전화]: '영동읍 계산리 583-11번지' -> '충청북도 영동군 영동읍 계산리 583-11번지'로 시·도 및 시·군·구 자동 완성
2. [중복 기사 통합]: 동일 지번/주소에 대해 지자체 보도자료를 여러 신문사가 동시 보도한 경우,
   가장 내용이 충실한 1개 기사만 남기고 중복 기사 행 자동 제거
3. [언론 주목도 보존]: '동일보도_신문사' 컬럼을 추가하여 함께 보도한 다른 신문사 목록과 보도 건수 기록

사용법:
    python clean_news_csv.py                                       # output 폴더의 최신 CSV 자동 정제
    python clean_news_csv.py output/충청·대전·세종_2026-09-26.csv    # 특정 파일 지정 정제
    python clean_news_csv.py output/충청·대전·세종_2026-09-26.csv --inplace # 원본 덮어쓰기
"""
import argparse
import csv
import glob
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from common.pnu_resolver import build_context, complete_korean_address, parse_address


def find_latest_csv(directory: str) -> Optional[str]:
    """지정된 디렉토리에서 가장 최근에 생성된 원본 크롤링 CSV 탐색"""
    csv_files = glob.glob(os.path.join(directory, "*.csv"))
    # _정리완료 또는 _with_pnu 파일은 원본이 아니므로 제외
    csv_files = [f for f in csv_files if "_정리완료" not in f and "_with_pnu" not in f]
    if not csv_files:
        return None
    return max(csv_files, key=os.path.getmtime)


def clean_address_text(addr: str) -> str:
    """주소에서 '번지' 단어를 깔끔하게 제거하고 공백을 정돈 (예: '583-11번지' -> '583-11', '산38번지' -> '산38')"""
    if not addr:
        return ""
    # 숫자 바로 뒤에 붙은 '번지' 제거
    cleaned = re.sub(r"(\d+)\s*번지(?:\s|$)", r"\1 ", addr).strip()
    # 단어 끝의 '번지' 제거
    cleaned = re.sub(r"\s*번지(?:\s|$)", " ", cleaned).strip()
    return re.sub(r"\s+", " ", cleaned)


def clean_and_complete_addresses(raw_addrs_str: str, area_hint: str, paper: str, body: str, title: str) -> List[Tuple[str, str]]:
    """기사에서 추출된 주소 목록을 하나씩 분리하여 온전한 한국식 표준 주소로 완성.
    반환값: List[(단일_원본주소, 단일_완전주소)]
    """
    if not raw_addrs_str:
        return []
    parts = re.split(r"[,;\n/]+", raw_addrs_str.strip("[]'\" "))
    parts = [p.strip().strip("'\"") for p in parts if p.strip()]

    results: List[Tuple[str, str]] = []
    context = build_context(title, body)     # PNU 단계(pnu_pipeline)와 같은 문맥을 써야 두 단계의 완성 주소가 같다
    for p in parts:
        raw_clean = clean_address_text(p)
        comp = complete_korean_address(p, area_hint=area_hint, paper=paper, context_text=context)
        comp_clean = clean_address_text(comp) if comp else raw_clean
        if comp_clean:
            results.append((raw_clean, comp_clean))
    return results


def deduplicate_news_records(records: List[dict]) -> Tuple[List[dict], int]:
    """
    1. [1셀 1주소]: 기사 1건에 주소가 2개 이상이면 각각 개별 행으로 분리(Explode).
    2. ['번지' 제거]: 모든 주소 뒤의 '번지' 단어 제거.
    3. [중복 기사 통합]: 동일한 완전주소를 가진 여러 신문사의 기사 중 대표 1건만 남기고 중복 제거.
    """
    # 1단계: 1셀 1주소로 행 분리 및 '번지' 제거
    exploded_records = []
    for row in records:
        r = dict(row)
        raw_addrs = r.get("주소추출", "")
        area_hint = r.get("지역힌트", "")
        paper = r.get("신문사", "")
        body = r.get("본문", "")
        title = r.get("제목", "")

        addr_pairs = clean_and_complete_addresses(raw_addrs, area_hint, paper, body, title)
        if not addr_pairs:
            # 주소가 없는 기사는 1행 그대로 유지
            r_single = dict(r)
            r_single["완전주소"] = clean_address_text(raw_addrs)
            exploded_records.append(r_single)
        else:
            # 주소가 N개면 N개의 행으로 분리하여 각 셀에 주소 1개만 배정
            for single_raw, single_comp in addr_pairs:
                r_single = dict(r)
                r_single["주소추출"] = single_raw
                r_single["완전주소"] = single_comp
                exploded_records.append(r_single)

    # 2단계: '완전주소' 기준으로 그룹화하여 동일 지번 다수 신문사 보도 중복 탐색
    addr_groups: Dict[str, List[dict]] = {}
    no_addr_records: List[dict] = []

    for r in exploded_records:
        comp_str = r.get("완전주소", "").strip()
        if comp_str:
            # 시·도/시군구가 없는 주소('마산리 46-1')는 지역이 다른 같은 이름의 주소일 수 있으므로 신문사끼리 합치지 않는다
            parsed = parse_address(comp_str)
            has_region = bool(parsed and (parsed.prov or parsed.sg))
            key = comp_str if has_region else f"{r.get('신문사', '')}|{comp_str}"
            addr_groups.setdefault(key, []).append(r)
        else:
            no_addr_records.append(r)

    cleaned_records = []
    total_duplicates_removed = 0

    for addr_key, group in addr_groups.items():
        if len(group) == 1:
            rec = group[0]
            rec["동일보도_신문사"] = f"{rec.get('신문사', '')} (단독)"
            cleaned_records.append(rec)
            continue

        # 2건 이상: 동일 주소/지번에 대한 기사들 통합
        # (최근 수집 기간 내 동일 지번 보도는 신문사별 보도자료 전재이므로 가장 상세한 1건만 유지)
        subgroups: List[List[dict]] = []
        for item in group:
            item_year = (item.get("날짜", "")[:4]) if len(item.get("날짜", "")) >= 4 else ""
            placed = False
            for sg in subgroups:
                rep_year = (sg[0].get("날짜", "")[:4]) if len(sg[0].get("날짜", "")) >= 4 else ""
                # 연도가 같거나 1년 이내면 동일 사업 보도로 묶음
                if not item_year or not rep_year or abs(int(item_year) - int(rep_year)) <= 1:
                    sg.append(item)
                    placed = True
                    break
            if not placed:
                subgroups.append([item])

        for sg in subgroups:
            if len(sg) == 1:
                rec = sg[0]
                rec["동일보도_신문사"] = f"{rec.get('신문사', '')} (단독)"
                cleaned_records.append(rec)
            else:
                # 동일 주소 다수 신문사 보도 -> 본문이 가장 긴(상세한) 기사를 대표로 선정
                sg.sort(key=lambda x: len(x.get("본문", "")), reverse=True)
                rep = sg[0]
                other_papers = [x.get("신문사", "") for x in sg[1:]]
                unique_others = list(dict.fromkeys(other_papers))

                rep["동일보도_신문사"] = f"{rep.get('신문사', '')} (대표) | 동일보도: {', '.join(unique_others)} (총 {len(sg)}개사)"
                cleaned_records.append(rep)

                removed_cnt = len(sg) - 1
                total_duplicates_removed += removed_cnt
                print(f"  [중복 통합] '{rep.get('완전주소')}' -> {rep.get('신문사')} 대표 선정 (중복 {removed_cnt}건 제외: {', '.join(unique_others)})")

    # 주소 없는 기사 추가
    for r in no_addr_records:
        r["동일보도_신문사"] = f"{r.get('신문사', '')} (주소미확인)"
        cleaned_records.append(r)

    return cleaned_records, total_duplicates_removed


def process_clean_file(input_csv: str, output_csv: Optional[str] = None) -> str:
    """CSV 파일을 읽어 주소를 완전한 형태로 보완하고 중복 신문기사를 제거하여 저장"""
    if not os.path.isfile(input_csv):
        print(f"[오류] 파일을 찾을 수 없습니다: {input_csv}")
        return ""

    if not output_csv:
        base, ext = os.path.splitext(input_csv)
        output_csv = f"{base}_정리완료{ext}"

    print(f"\n==================================================")
    print(f"  [CSV 주소 완전화 및 중복 기사 정리 시작]")
    print(f"  - 원본 파일: {input_csv}")
    print(f"  - 대상 파일: {output_csv}")
    print(f"==================================================")

    with open(input_csv, "r", encoding="utf-8-sig") as f:
        reader = list(csv.DictReader(f))

    if not reader:
        print("  [알림] 데이터가 비어 있습니다.")
        return ""

    initial_count = len(reader)
    cleaned_rows, removed_count = deduplicate_news_records(reader)

    # 출력 컬럼 정의
    orig_fields = list(reader[0].keys())
    fieldnames = []
    # '완전주소'와 '동일보도_신문사'를 보기 좋은 위치(주소추출 옆)에 배치
    for col in orig_fields:
        fieldnames.append(col)
        if col == "주소추출":
            if "완전주소" not in fieldnames:
                fieldnames.append("완전주소")
        if col == "신문사":
            if "동일보도_신문사" not in fieldnames:
                fieldnames.append("동일보도_신문사")

    for extra in ["동일보도_신문사", "완전주소"]:
        if extra not in fieldnames:
            fieldnames.append(extra)

    save_path = output_csv
    try:
        f = open(save_path, "w", encoding="utf-8-sig", newline="")
    except PermissionError:
        base, ext = os.path.splitext(output_csv)
        save_path = f"{base}_new{ext}"
        print(f"  [안내] 기존 파일이 엑셀 등에서 열려 있어 새 이름으로 저장합니다: {save_path}")
        f = open(save_path, "w", encoding="utf-8-sig", newline="")

    with f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(cleaned_rows)

    print(f"\n==================== 정제 요약 ====================")
    print(f"  - 원본 수집 기사: {initial_count}건")
    print(f"  - 다수 신문사 중복 기사 제거: {removed_count}건")
    print(f"  - 1셀 1주소 분리 후 최종 고유 행수: {len(cleaned_rows)}건")
    print(f"  - 저장 완료 파일: {save_path}")
    print(f"==================================================\n")

    return save_path


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="크롤링 CSV 주소 완전화 및 중복 기사 정리기")
    parser.add_argument("input_csv", nargs="?", default="", help="입력 CSV 파일 경로 (생략 시 최신 파일)")
    parser.add_argument("--out", "-o", default="", help="저장할 CSV 파일 경로")
    parser.add_argument("--inplace", action="store_true", help="새 파일 대신 원본 파일을 덮어쓰기")
    args = parser.parse_args()

    target = args.input_csv
    if not target:
        target = find_latest_csv(os.path.join(HERE, "output"))
        if not target:
            print("[오류] output 폴더에 처리할 CSV 파일이 없습니다.")
            return

    out_file = target if args.inplace else args.out
    process_clean_file(target, out_file)


if __name__ == "__main__":
    main()
