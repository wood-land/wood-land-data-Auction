# -*- coding: utf-8 -*-
"""옥션원 NPL 목록 <-> 두인 시트 매칭 (순수 함수만 - 브라우저/시트 없이 테스트 가능).

옥션원 목록의 사건번호는 '24-639 (2)' 처럼 법원명이 없다. 그래서 (연도2자리, 번호)로 두인 후보를
찾고, 감정가/매각기일/소재지로 점수를 매겨 같은 물건인지 확인한다.
"""
import re
from urllib.parse import urlparse, parse_qs

MATCH_MIN_SCORE = 3


def normalize_case_key(text):
    """'24-639 (2)' / '2024타경639' / '서울중앙 2024타경639(2)' -> ('24', '639') 또는 None."""
    s = str(text or "")
    m = re.search(r"(\d{2,4})\s*타[경채]?\s*(\d+)", s) or re.search(r"(?<!\d)(\d{2,4})\s*-\s*(\d+)", s)
    if not m:
        return None
    return m.group(1)[-2:], str(int(m.group(2)))


def case_item_no(text):
    m = re.search(r"\((\d+)\)", str(text or ""))
    return m.group(1) if m else ""


def to_int(v):
    d = re.sub(r"[^\d]", "", str(v or ""))
    return int(d) if d else None


def date_part(v):
    s = str(v or "")
    m = re.search(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"(\d{2})[-./](\d{1,2})[-./](\d{1,2})", s)
    return f"20{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""


def addr_tokens(addr):
    return {t for t in re.split(r"[\s,()]+", str(addr or "")) if len(t) >= 2}


def add_tab_to_index(index, seen, values, tab_title):
    """두인 시트 탭 하나(get_all_values 결과)를 {(yy,num): [후보,...]} 색인에 더한다.
    경매(caView) 상세페이지가 있는 행만, tid 당 첫 행만 쓴다(필지 분리 행은 건너뜀)."""
    if not values:
        return 0
    hdr = {n: i for i, n in enumerate(values[0]) if n}
    if "사건번호" not in hdr or "상세페이지" not in hdr:
        return 0
    n_added = 0
    for row in values[1:]:
        def g(name):
            i = hdr.get(name)
            return row[i] if i is not None and i < len(row) else ""
        url = g("상세페이지")
        key = normalize_case_key(g("사건번호"))
        if not key or "caView" not in url:
            continue
        q = parse_qs(urlparse(url).query)
        tid = (q.get("tid") or [""])[0]
        if not tid or tid in seen:
            continue
        seen.add(tid)
        base = {name: (row[i] if i < len(row) else "") for name, i in hdr.items()}
        index.setdefault(key, []).append({
            "tid": tid, "chk": (q.get("chkNo") or ["1"])[0], "tot": (q.get("TotNo") or ["1"])[0],
            "case": g("사건번호"), "addr": g("주소"), "date": date_part(g("입찰일")),
            "apsl": to_int(g("감평가")), "min": to_int(g("최저가")), "url": url,
            "tab": tab_title, "base": base,
        })
        n_added += 1
    return n_added


def match_one(row, index):
    """row: 옥션원 목록 dict. 반환 (후보 또는 None, 점수)."""
    key = normalize_case_key(row.get("사건번호"))
    if not key:
        return None, 0
    best, best_score = None, 0
    for c in index.get(key, []):
        score = 1
        item = case_item_no(c["case"])
        if row.get("물번") and item and str(row["물번"]) != item:
            continue
        if row.get("감정가") and c["apsl"] and row["감정가"] == c["apsl"]:
            score += 3
        if row.get("매각기일") and c["date"] and row["매각기일"] == c["date"]:
            score += 2
        a, b = addr_tokens(row.get("소재지")), addr_tokens(c["addr"])
        if a and b and len(a & b) >= 3:
            score += 2
        elif a and b and len(a & b) >= 2:
            score += 1
        if score > best_score:
            best, best_score = c, score
    return (best, best_score) if best_score >= MATCH_MIN_SCORE else (None, best_score)
