"""
tests/make_fixtures.py - 실제 공고 첨부문서에서 '표 구조'만 뽑아 tests/fixtures/*.json 으로 저장한다(네트워크 필요, 가끔만 실행).

원본 파일은 저장하지 않는다. 표(머리글·제목줄·표 위 소재지)는 그대로 두고, 소유자 이름/주소 칸의 개인 정보는 가짜 값으로
바꾼다(국·공·기관명처럼 공공 소유 판별에 필요한 값만 남긴다). 표는 머리글 + 최대 MAX_ROWS 행만 보관한다.
사용: python tests/make_fixtures.py
"""
import glob
import importlib
import json
import os
import re
import sys

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.stdout.reconfigure(encoding="utf-8")

from core import jose_extractor as J  # noqa: E402

MAX_ROWS = 14
CASES = [
    # (이름, 지자체, 상세 URL, 첨부 파일명에 들어 있는 말)
    ("pocheon_pdf_heading", "포천시",
     "https://www.pocheon.go.kr/www/selectEminwonView.do?pageUnit=10&searchCnd=all&pageIndex=4&key=3712&notAncmtMgtNo=68311&notAncmtSeCode=01",
     "편입용지조서"),
    ("gapyeong_xlsx_titlerow", "가평군",
     "https://www.gp.go.kr/portal/selectGosiData.do?key=2148&not_ancmt_mgt_no=56896&not_ancmt_se_code=01", "편입용지"),
    ("gapyeong_hwpx_total_row", "가평군",
     "https://www.gp.go.kr/portal/selectGosiData.do?key=2148&not_ancmt_mgt_no=56932&not_ancmt_se_code=01", "열람공고문"),
    ("gwangju_hwpx_block_lots", "광주시",
     "https://www.gjcity.go.kr/portal/saeol/gosi/view.do?notAncmtMgtNo=80060&mId=0202010000", "고시문"),
    ("ansan_hwpx_addr_head", "안산시",
     "https://www.ansan.go.kr/www/common/bbs/selectBbsDetail.do?key=271&bbs_code=WWW13&bbs_seq=1684978", "공고문"),
    ("gimpo_hwpx_abbrev", "김포시",
     "https://www.gimpo.go.kr/portal/ntfcPblancView.do?key=1004&ntcn_no=75919&pageIndex=4&searchCnd=40900000000&cate_cd=1", "손실보상"),
]


def find_city(name):
    for f in glob.glob(os.path.join(ROOT, "cities", "*.py")):
        mod = importlib.import_module("cities." + os.path.basename(f)[:-3])
        for c in getattr(mod, "CITIES", []):
            if c.city == name:
                return c
    raise SystemExit(f"지자체 없음: {name}")


def sample_rows(g, hdr):
    """머리글 + 앞쪽 몇 행 + (앞쪽에 없으면) 공공이 아닌 소유자 행 몇 개를 고른다. 공공 소유만 앞에 몰린 표도 사유 행이 테스트에 들어가게."""
    head, body = [list(r) for r in g[:hdr]], [list(r) for r in g[hdr:]]
    picked = body[:6]
    private = [r for r in body[6:] if not any(J.is_public_owner(c, "") for c in r[8:14])]
    return head + picked + private[:6]


def mask_grid(grid, hdr):
    """소유자·관계인 칸의 개인 정보를 가짜 값으로 바꾼다. 공공 소유 판별에 필요한 값(국/공/기관명)은 남긴다.
    칸 구분은 머리글의 맨 아래 줄(leaf)로 한다: 성명/명칭/소유자 = 이름, 주소 = 주소, 주민/생년/연락 = 식별번호."""
    leaf_rows = [r for r in range(min(hdr, len(grid))) if not J.is_title_row(grid[r])]
    leaf = [J.squash(grid[leaf_rows[-1]][c]) if leaf_rows else "" for c in range(len(grid[0]))]
    out = []
    for ri, row in enumerate(grid):
        new = list(row)
        if ri >= hdr:
            for c, h in enumerate(leaf):
                cell = row[c]
                if not cell:
                    continue
                if re.search(r"주민|생년|연락", h):
                    new[c] = "000000-*******"
                elif re.search(r"성명|명칭|^소유자$", h):
                    if not J.is_public_owner(cell):
                        new[c] = "김*수"
                elif h == "주소":
                    if not (J.is_public_owner(cell, "") or J.is_public_owner(row[max(c - 1, 0)], "")):
                        new[c] = "서울시 강남구 테헤란로 1"
        out.append(new)
    return out


def main():
    os.makedirs(os.path.join(HERE, "fixtures"), exist_ok=True)
    for name, city_name, url, key in CASES:
        city = find_city(city_name)
        ad = importlib.import_module("cms_adapters." + city.adapter)
        s = requests.Session()
        if hasattr(ad, "prepare_session"):
            ad.prepare_session(s, city)
        att = next(a for a in ad.fetch_attachments(s, url) if key in a["name"] and a["ext"] in ("pdf", "hwpx", "xlsx", "docx"))
        data = s.get(att["url"], headers={**ad.HEADERS, "Referer": url}, timeout=40).content
        grids = J.local_grids(att["ext"], data)
        # 실제 추출 함수로 어느 표에서 행이 나오는지 찾고, 처음 행이 나오는 표부터 이어지는 표(최대 3개)를 보관한다
        rows, debug = J.rows_from_document_grids(grids, att["name"], "")
        tag = re.compile(r"#p\d+t(\d+)")
        made = sorted({int(tag.search(x).group(1)) - 1
                       for x in [r["extract_loc"] for r in rows] + [d["tag"] for d in debug
                                                                   if d["reason"] in ("non-parcel-lot", "public-owner")]
                       if tag.search(x)}) or [0]
        tables = [(pg, ti, J.pad_grid(g)) for pg, ti, g in grids]
        keep = []
        for i, (pg, ti, g) in enumerate(tables[made[0]:], made[0]):
            hdr = next((k for k in range(1, min(len(g), 6)) if J.looks_like_data_row(g[k])), min(2, len(g) - 1))
            has_private = any(not any(J.is_public_owner(c, "") for c in r[8:14]) for r in g[hdr:])
            if att["ext"] == "pdf" and keep and not has_private:  # PDF 는 표마다 머리글이 있어 건너뛰어도 된다
                continue
            keep.append({"page": pg, "idx": ti, "heading": getattr(g, "heading", ""),
                         "grid": mask_grid(sample_rows(g, hdr), hdr)})
            if len(keep) >= 3:
                break
        path = os.path.join(HERE, "fixtures", name + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"name": name, "city": city_name, "file": att["name"], "tables": keep}, f, ensure_ascii=False, indent=1)
        print("저장", path, f"표 {len(keep)}개")


if __name__ == "__main__":
    main()
