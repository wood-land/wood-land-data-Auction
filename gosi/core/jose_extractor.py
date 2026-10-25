"""
jose_extractor.py — 고시/공고 붙임파일에서 "토지조서(jose_rows)"를 뽑아내는 공통 엔진.

지자체마다 다른 부분(게시판 URL, 키워드, 법정동 목록)은 이 모듈에 넣지 않는다.
이 모듈은 어떤 지자체에서 왔는지 몰라도 동작해야 하며, 지자체별 정보는 모두
호출하는 쪽(예: wonju_crawler.py)이 Regions 객체·project_name 등으로 넘겨준다.

새 지자체를 추가할 때 이 파일은 건드리지 않는 것이 원칙이다. 표 양식이 정말
새로운 경우에만(COLUMN_RULES 로 못 잡는 머리글) 이 파일의 COLUMN_RULES 를 넓힌다.

지원 형식: hwpx, docx, xlsx/xlsm, pdf (표 우선, 표가 없으면 본문 텍스트 규칙).
구버전 이진 .hwp 는 순수 파이썬으로 표를 읽을 수 없어 지원하지 않는다(스킵).

핵심 함수:
  - extract_from_attachment(data, ext, filename, title, regions) -> jose_row 리스트
  - Regions(...)  지자체별 법정동/리 목록으로 소재지를 검증·완성

원본: 500_local/62. 고시 공고 데이터/62_101_강원_원주시_0920_v4.py (원주시 파일럿, 검증된 로직).
이 파일은 그 스크립트에서 지자체와 무관한 부분만 뽑아 파라미터화한 것이다.
"""

import io
import re
import zipfile
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

# ============================================================ 공통 유틸
def clean(s):
    return re.sub(r"[\s 　]+", " ", s or "").strip()


def squash(s):
    return re.sub(r"[\s 　]+", "", s or "")


def is_ditto(s):
    return bool(re.fullmatch(r"[\"'`“”‘’〃ˮ″]+", squash(s))) and bool(s)


def num(s):
    """'1,394' -> '1394', '1,394㎡' -> '1394'. 숫자가 아니면 원문 유지."""
    t = squash(s).replace(",", "")
    t = re.sub(r"(㎡|m2|m²|M2|평방미터)$", "", t)
    if re.fullmatch(r"\d+(\.\d+)?", t):
        return t
    return clean(s)


# ============================================================ 소유구분 (국공유/사유/법인)
# 소유자 "이름/기관명" 원문은 저장하지 않고, 분류 결과만 남긴다.
_OWNER_PUBLIC_RE = re.compile(
    r"대한민국|국가|국유지|공유지|시유지|도유지|군유지|"
    r"기획재정부|국토교통부|산림청|환경부|해양수산부|농림축산식품부|"
    r"[가-힣]{2,6}(?:특별자치)?(?:시|도|군|구)(?:청)?$|"
    r"[가-힣]{2,6}(?:공사|공단|처|청)$"
)
_OWNER_CORP_RE = re.compile(
    r"주식회사|\(주\)|㈜|유한회사|합자회사|합명회사|"
    r"조합$|재단법인|사단법인|학교법인|영농조합법인|농업회사법인|산림조합"
)


def classify_owner(text):
    """소유자 칸 원문 -> '국공유' / '법인' / '사유' / ''(빈 칸) / '확인필요'.
    이름·주소 등 원문은 호출하는 쪽에서 절대 저장하지 않아야 한다 (개인정보)."""
    t = clean(text)
    if not t:
        return ""
    t = re.sub(r"\s*외\s*\d+\s*(명|인)\s*$", "", t).strip()
    if _OWNER_PUBLIC_RE.search(t):
        return "국공유"
    if _OWNER_CORP_RE.search(t):
        return "법인"
    if re.fullmatch(r"[가-힣]{2,4}", t):          # 성명 2~4자 (예: 홍길동)
        return "사유"
    return "확인필요"


# 소유자가 국가·지자체·공공기관인 필지도 수집하되 owner_type='국공유'(DB 의 owner_kind='공공')로 표시한다(사용자 지시 2026-10-26: QGIS 에서 경공매와 겹침 확인에 쓴다. 이전 2026-10-16 지시는 사유지만).
# 표의 소유자 칸은 '국'/'공' 같은 한 글자 구분, 기관명('국토교통부', '경기도', '한국도로공사'), 사람 이름이 섞여 있다.
_PUBLIC_CODES = {"국", "공", "국유", "공유", "시유", "도유", "군유", "구유", "국공유", "국유지", "공유지", "시유지", "도유지", "군유지"}
_PUBLIC_AGENCY_RE = re.compile(
    r"대한민국|국가|"
    r"(?:기획재정|국토교통|산림|환경|해양수산|농림축산식품|국방|행정안전|산업통상자원|문화체육관광|교육|보건복지|과학기술정보통신|"
    r"법무|외교|통일|고용노동|여성가족|중소벤처기업|농촌진흥|소방|경찰|문화재|조달|국세|관세|기상|통계|특허|질병관리|방위사업|병무|우정사업)[가-힣]{0,6}(?:부|청|본부)|"
    r"[가-힣]{2,10}(?:공사|공단|공단|공사|진흥원|관리원|위원회|사업단|개발청)|"
    r"한국[가-힣]{2,10}(?:공사|공단|원|청|센터)"
)
# '포천시'·'경기도'·'가평군'·'단원구' 형태. 사람 이름('이영구', '박상군')과 겹칠 수 있어 소유자 주소로 한 번 더 가른다.
_PUBLIC_LOCAL_RE = re.compile(r"[가-힣]{2,8}(?:특별자치)?(?:특별시|광역시|도|시|군|구)(?:청|의회|교육청)?")


def is_public_owner(name, addr=None):
    """소유자 이름(성명/기관명) 칸과 소유자 주소 칸으로 국가·지자체·공공기관 소유인지 판별한다.
    addr 가 None 이면 주소를 모르는 경우: 이름이 사람 이름과 겹칠 수 있는 '○○군/○○구' 형태는 공공으로 보지 않는다
    (사유지를 잘못 버리는 것이 공유지를 하나 더 담는 것보다 나쁘다)."""
    t = clean(name)
    if not t:
        return False
    t = re.sub(r"\s*외\s*\d+\s*(명|인)\s*$", "", t).strip()
    t = re.sub(r"^[\(（]|[\)）]$", "", t).strip()
    if t in _PUBLIC_CODES:
        return True
    if _OWNER_CORP_RE.search(t):
        return False
    if _PUBLIC_AGENCY_RE.fullmatch(t):
        return True
    if re.fullmatch(r"(?:서울|부산|대구|인천|광주|대전|울산|세종)(?:특별시|광역시|특별자치시)|경기도|강원(?:특별자치)?도|충청[남북]도|"
                    r"전라[남북]도|전북특별자치도|경상[남북]도|제주(?:특별자치)?도", t):
        return True  # 시·도 이름은 사람 이름일 수 없다
    if _PUBLIC_LOCAL_RE.fullmatch(t):
        if addr is None:
            return False
        a = clean(addr)
        if not a or re.search(r"(시|군|구|도)청|청$", a):  # 주소가 비었거나 청사 주소
            return True
        return not re.search(r"\d|\*|[동리로길가]$", a)  # 번지·도로명 숫자가 있으면 개인 주소로 본다
    return False


def classify_owner_row(div, name, addr=None):
    """소유구분 칸·성명 칸·소유자 주소 칸으로 '국공유'/'법인'/'사유'/''/'확인필요' 를 정한다."""
    if is_public_owner(div, addr) or is_public_owner(name, addr) or is_public_owner(addr, ""):
        return "국공유"
    return normalize_owner_div(div) if clean(div) else classify_owner(name)


_OWNER_DIV_MAP = {
    "국유": "국공유", "공유": "국공유", "시유": "국공유", "도유": "국공유",
    "군유": "국공유", "국공유": "국공유", "사유": "사유", "법인": "법인", "민유": "사유",
}


def normalize_owner_div(text):
    """표에 이미 '소유구분' 칸이 따로 있는 경우 그 값을 정규화한다."""
    t = clean(text)
    return _OWNER_DIV_MAP.get(t, classify_owner(t) if t else "")


# ============================================================ 표(grid) 만들기 — HTML/HWPX/DOCX/XLSX/PDF
class Grid(list):
    """표(행 리스트). heading: 표 바로 위 문단에 적힌 소재지(예: '경기도 포천시 가산면 방축리').
    편입용지조서 PDF 는 소재지를 표 열이 아니라 표 위 제목줄에 쓰는 경우가 있다(포천시 실측 2026-10-16)."""
    heading = ""


def pad_grid(grid):
    width = max((len(r) for r in grid), default=0)
    out = Grid(list(r) + [""] * (width - len(r)) for r in grid)
    out.heading = getattr(grid, "heading", "")
    return out


# 표 위 제목줄이 '소재지만 적힌 줄'인지 판별한다(예: '경기도 포천시 가산면 방축리', '소재지 : 가산면 방축리')
_HEADING_LOC_RE = re.compile(
    r"^(?:소\s*재\s*지|위\s*치)?\s*[:：]?\s*[<\[(【]?\s*"
    r"((?:[가-힣]{2,8}(?:특별시|광역시|특별자치시|특별자치도|도)\s+)?(?:[가-힣]{1,6}[시군구]\s+)*"
    r"(?:[가-힣0-9]{1,5}[읍면]\s+)?[가-힣0-9]{1,6}[동리])\s*[>\])】]?\s*(?:일원)?$")


def region_heading(text):
    """표 위 텍스트의 마지막 줄들 중 '소재지만 적힌 줄'이 있으면 그 소재지를, 없으면 ''."""
    for line in reversed([clean(x) for x in (text or "").splitlines() if clean(x)][-4:]):
        m = _HEADING_LOC_RE.match(line)
        if m and len(line) <= 40:
            return m.group(1)
    return ""


def heading_from_grid(grid, upto=6):
    """표 맨 위 몇 줄 중 '값이 하나뿐인 줄'(병합 칸)이 소재지만 적힌 줄이면 그 소재지를 돌려준다.
    xlsx 용지조서가 소재지를 표 열이 아니라 표 안쪽 병합 줄('경상북도 경주시 강동면 유금리')에 적는 경우가 있다
    (경주시 도로구역 용지조서 실측 2026-10-17). pdf_grids 는 표 위 문단에서 읽지만 xlsx/hwpx/docx 는 표 안에 있다."""
    for row in grid[:upto]:
        vals = {clean(c) for c in row if clean(c)}
        if len(vals) == 1:
            h = region_heading(next(iter(vals)))
            if h:
                return h
    return ""


def expand_html_table(table):
    """<table> -> 2차원 리스트. rowspan/colspan 을 펼친다."""
    grid, span = [], {}
    for tr in table.find_all("tr"):
        if tr.find_parent("table") is not table:
            continue
        row, c = [], 0

        def fill():
            nonlocal c
            while c in span and span[c][0] > 0:
                while len(row) <= c:
                    row.append("")
                row[c] = span[c][1]
                span[c][0] -= 1
                c += 1

        for cell in tr.find_all(["td", "th"], recursive=False):
            fill()
            t = clean(cell.get_text(" "))
            rs = int(re.sub(r"\D", "", cell.get("rowspan", "1")) or 1)
            cs = int(re.sub(r"\D", "", cell.get("colspan", "1")) or 1)
            for k in range(cs):
                while len(row) <= c + k:
                    row.append("")
                row[c + k] = t
                if rs > 1:
                    span[c + k] = [rs - 1, t]
            c += cs
        fill()
        grid.append(row)
    return pad_grid(grid)


def html_tables(html):
    soup = BeautifulSoup(html, "html.parser")
    return [(1, i, expand_html_table(t)) for i, t in enumerate(soup.find_all("table"))]


def _lname(el):
    t = el.tag
    return t.rsplit("}", 1)[-1] if isinstance(t, str) else ""


def _hwpx_text(el):
    paras, cur = [], []

    def walk(node):
        for ch in node:
            n = _lname(ch)
            if n == "tbl":
                continue
            if n == "t":
                cur.append(ch.text or "")
                for sub in ch:
                    cur.append(" " if _lname(sub) in ("tab", "lineBreak", "fwSpace", "nbSpace") else "")
                    cur.append(sub.tail or "")
                continue
            walk(ch)
            if n == "p":
                paras.append("".join(cur))
                del cur[:]

    walk(el)
    if cur:
        paras.append("".join(cur))
    return clean(" ".join(paras))


def hwpx_grids(data):
    """HWPX(zip+XML) -> [(1, 번호, grid), ...]."""
    out = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        secs = sorted(n for n in z.namelist() if re.search(r"Contents/section\d+\.xml$", n))
        for sn in secs:
            root = ET.fromstring(z.read(sn))
            for tbl in root.iter():
                if _lname(tbl) != "tbl":
                    continue
                R, C = int(tbl.get("rowCnt", 0) or 0), int(tbl.get("colCnt", 0) or 0)
                if not R or not C:
                    continue
                g = [[""] * C for _ in range(R)]
                for tr in tbl:
                    if _lname(tr) != "tr":
                        continue
                    for tc in tr:
                        if _lname(tc) != "tc":
                            continue
                        ad = next((k for k in tc if _lname(k) == "cellAddr"), None)
                        sp = next((k for k in tc if _lname(k) == "cellSpan"), None)
                        if ad is None:
                            continue
                        c0, r0 = int(ad.get("colAddr")), int(ad.get("rowAddr"))
                        cs = int(sp.get("colSpan", 1)) if sp is not None else 1
                        rs = int(sp.get("rowSpan", 1)) if sp is not None else 1
                        txt = _hwpx_text(tc)
                        for r in range(r0, min(R, r0 + rs)):
                            for c in range(c0, min(C, c0 + cs)):
                                g[r][c] = txt
                out.append(g)
    return [(1, i, g) for i, g in enumerate(out)]


def _docx_text(el, W):
    paras, cur = [], []

    def walk(node):
        for ch in node:
            if ch.tag == W + "tbl":
                continue
            if ch.tag == W + "t":
                cur.append(ch.text or "")
                continue
            if ch.tag in (W + "tab", W + "br"):
                cur.append(" ")
                continue
            walk(ch)
            if ch.tag == W + "p":
                paras.append("".join(cur))
                del cur[:]

    walk(el)
    if cur:
        paras.append("".join(cur))
    return clean(" ".join(paras))


def docx_grids(data):
    """DOCX(zip+XML) -> [(1, 번호, grid), ...]."""
    W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    out = []
    for tbl in root.iter(W + "tbl"):
        grid = []
        for tr in tbl:
            if tr.tag != W + "tr":
                continue
            row, c = [], 0
            for tc in tr:
                if tc.tag != W + "tc":
                    continue
                span, vm = 1, None
                pr = tc.find(W + "tcPr")
                if pr is not None:
                    gs = pr.find(W + "gridSpan")
                    if gs is not None:
                        span = int(gs.get(W + "val", 1) or 1)
                    v = pr.find(W + "vMerge")
                    if v is not None:
                        vm = v.get(W + "val", "continue")
                txt = _docx_text(tc, W)
                if vm == "continue" and grid and c < len(grid[-1]):
                    txt = grid[-1][c]
                row.extend([txt] * span)
                c += span
            grid.append(row)
        if grid:
            out.append(pad_grid(grid))
    return [(1, i, g) for i, g in enumerate(out)]


def xlsx_grids(data):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)

    def txt(v):
        if v is None:
            return ""
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        return clean(str(v))

    out = []
    for si, ws in enumerate(wb.worksheets, 1):
        g = [[txt(v) for v in row] for row in ws.iter_rows(values_only=True)]
        for mr in ws.merged_cells.ranges:
            try:
                v = g[mr.min_row - 1][mr.min_col - 1]
                for r in range(mr.min_row - 1, mr.max_row):
                    for c in range(mr.min_col - 1, mr.max_col):
                        g[r][c] = v
            except IndexError:
                pass
        if g:
            out.append((si, 0, pad_grid(g)))
    return out


def pdf_grids(data):
    import pdfplumber
    out = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for pn, page in enumerate(pdf.pages, 1):
            for ti, tb in enumerate(page.find_tables() or []):
                g = pad_grid([[clean(c or "") for c in row] for row in tb.extract()])
                top = tb.bbox[1]
                if top > 5:  # 표 위 제목줄에서 소재지를 읽는다
                    try:
                        g.heading = region_heading(page.within_bbox((0, 0, page.width, top)).extract_text())
                    except Exception:  # 제목줄 해석 실패는 표 추출을 막지 않는다
                        g.heading = ""
                out.append((pn, ti, g))
    return out


def pdf_text(data):
    import pdfplumber
    parts = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            parts.append(clean(page.extract_text() or ""))
    return " ".join(parts)


def local_grids(ext, data):
    """원본 파일 바이트 -> [(쪽, 표번호, grid), ...]. 지원하지 않는 형식이면 None.

    hwpx/docx/xlsx 는 zip 컨테이너(PK 서명)여야 하는데, 확장자만 .hwpx 이고 실제로는
    구버전 이진 HWP(OLE 서명 D0 CF 11 E0)인 첨부파일이 실제로 있었다(원주시 실데이터로
    확인). 이런 경우 zip 파싱 예외를 그대로 던지지 않고 "지원 안 함"으로 처리한다."""
    ext = (ext or "").lower()
    if ext == "pdf":
        return pdf_grids(data)
    if ext in ("hwpx", "xlsx", "xlsm", "docx") and not data.startswith(b"PK\x03\x04"):
        return None
    if ext == "hwpx":
        return hwpx_grids(data)
    if ext in ("xlsx", "xlsm"):
        return xlsx_grids(data)
    if ext == "docx":
        return docx_grids(data)
    return None


def grids_text(grids):
    return " ".join(" ".join(c for c in row if c) for _, _, g in grids for row in g)


# ============================================================ 지번 해석
PARCEL_RE = re.compile(r"(?<![\d-])(산\s*)?(\d{1,5})(?:\s*-\s*(\d{1,4}))?(?!\d)(?:\s*번지)?(?:\s*\(\s*([\d,.]+)\s*\))?")


def parse_jibun_cell(text):
    t = clean(text)
    if not t:
        return []
    t = re.sub(r"(\d)\s*번지\s*의\s*(\d)", r"\1-\2", t)
    t = re.sub(r"외\s*\d+\s*필지", " ", t)
    t = re.sub(r"일\s*원", " ", t)
    hits = list(PARCEL_RE.finditer(t))
    if not hits:
        return []
    rest = PARCEL_RE.sub(" ", t)
    rest = re.sub(r"[,，、·ㆍ/~\s외등번지필지\-.()]", "", rest)
    if len(rest) > 3:
        return []
    out = []
    for m in hits:
        if int(m.group(2)) == 0:
            continue
        j = ("산" if m.group(1) else "") + m.group(2) + ("-" + m.group(3) if m.group(3) else "")
        out.append((j, m.group(4).replace(",", "") if m.group(4) else None))
    return out


def looks_like_data_row(row):
    return any(re.fullmatch(r"산?\s*\d{1,5}(-\d{1,4})?(\s*번지)?", clean(c)) for c in row)


def is_index_row(row):
    vals = []
    for c in row:
        t = clean(c)
        if t and (not vals or vals[-1] != t):
            vals.append(t)
    if len(vals) < 3 or not all(re.fullmatch(r"\d{1,2}", v) for v in vals):
        return False
    n = [int(v) for v in vals]
    return all(b - a == 1 for a, b in zip(n, n[1:]))


# --- 표 열 이름 판별 규칙 (공백 제거 후 정규식 검색). 새 표 양식이 나오면 여기에 표기를 추가한다. ---
COLUMN_RULES = {
    "jibun_orig": r"당초지번|원지번|종전지번|분할전|모지번|원래",
    "jibun":      r"지번|번지",
    "jimok":      r"지목",
    "area_incl":  r"편입|수용면적|취득면적|보상면적",
    "area_orig":  r"지적|공부|전체면적|원면적|총면적|^면적|>면적",
    "loc":        r"소재|위치|행정구역|시/면|동/리|읍[,·ㆍ‧]?면|시군|동명|리명|면‧리‧동|면·리·동|(^|>)(시|군|구|읍|면|동|리)$",
    "div":        r"(^|>)구분$",
    "owner_div":  r"소유구분|권리구분|소유자구분",
    "owner_grp":  r"소유자|공고대상자|토지주",
    "other_grp":  r"관계인|공동|권리|이해|이외",
    "name":       r"성명|명칭|성함",
    "addr":       r"주소",
    "remark":     r"비고",
}
# 토지가 아닌 조서(물건조서 등)는 건너뛴다
NON_LAND_TABLE = r"물건의종류|지장물|구조및규격|주택규모|건폐율|용적률|사업기간|사업의규모"


def is_title_row(row):
    """'편 입 용 지 조 서' / '【사업의 명칭 : …】' 처럼 표 전체에 걸친 제목줄(서로 다른 값이 1개 이하).
    머리글에 섞이면 모든 열 이름에 '편입' 같은 글자가 붙어 열 판별이 망가진다(가평군 xlsx 실측)."""
    return len(row) >= 4 and len({clean(c) for c in row if clean(c)}) <= 1


def fill_header_groups(grid, hdr_rows):
    """PDF 표는 병합된 머리글('지 번' 아래 '당초|변경')이 첫 칸에만 글자가 있고 오른쪽 칸은 비어 나온다(포천시 실측).
    윗줄 머리글이 비어 있고 아래 줄에 값이 있으면 왼쪽 칸의 머리글을 이어 받아 '지번>변경' 처럼 그룹을 복원한다."""
    out = [list(r) for r in grid[:hdr_rows]] + [list(r) for r in grid[hdr_rows:]]
    for r in range(hdr_rows - 1):
        if is_index_row(out[r]) or is_title_row(out[r]):
            continue
        for c in range(1, len(out[r])):
            if not clean(out[r][c]) and clean(out[r][c - 1]) and any(clean(out[rr][c]) for rr in range(r + 1, hdr_rows)):
                out[r][c] = out[r][c - 1]
    return out


def classify_heads(grid, hdr_rows):
    """각 열의 머리글(위/아래 칸을 '>' 로 이음)을 읽어 열 역할을 정한다."""
    ncol = len(grid[0])
    heads, raws = [], []
    grid = fill_header_groups(grid, hdr_rows)
    for c in range(ncol):
        parts, raw = [], []
        for r in range(hdr_rows):
            if is_index_row(grid[r]) or is_title_row(grid[r]):
                continue
            t = squash(grid[r][c])
            if t and t not in parts:
                parts.append(t)
                raw.append(clean(grid[r][c]))
        heads.append(">".join(parts))
        raws.append(" ".join(raw))
    R = {k: re.compile(v) for k, v in COLUMN_RULES.items()}
    cols = {"loc": [], "div": []}
    for c, h in enumerate(heads):
        if not h:
            continue
        if R["owner_div"].search(h):
            cols.setdefault("owner_div", c)
            continue
        if R["remark"].search(h) and not R["addr"].search(h):
            cols.setdefault("remark", c)
            continue
        other = bool(R["other_grp"].search(h))
        if "소재" in h and not other:  # '주소>소재지' 처럼 주소 머리글 아래 붙은 소재지 열(안산시 실측)
            cols["loc"].append(c)
            continue
        if R["addr"].search(h) and not other and "addr" not in cols and not re.search(r"지번|번지|지목", h):  # '주소>지번' 은 지번 열
            cols["addr"] = c
            continue
        if R["name"].search(h) and not other and "name" not in cols:
            cols["name"] = c
            continue
        if other:
            continue
        if R["jibun_orig"].search(h):
            cols.setdefault("jibun_orig", c)
            continue
        if R["jibun"].search(h):
            if "jibun" in cols:  # '지번>당초' / '지번>변경' 처럼 지번 열이 둘이면 뒤쪽은 보조(앞쪽이 빈 신규·분할 필지용)
                cols.setdefault("jibun_alt", c)
            else:
                cols["jibun"] = c
            continue
        if R["jimok"].search(h):
            cols.setdefault("jimok", c)
            continue
        if R["area_incl"].search(h) and not re.search("잔여", h):
            cols.setdefault("area_incl_all", []).append(c)
            continue
        if R["area_orig"].search(h) and not re.search("잔여|보상가|단가|금액", h):
            cols.setdefault("area_orig", c)
            continue
        if R["loc"].search(h):
            cols["loc"].append(c)
            continue
        if R["div"].search(h):
            cols["div"].append(c)
    inc = cols.pop("area_incl_all", [])
    if inc:
        pref = [c for c in inc if "변경" in heads[c]] or [c for c in inc if heads[c].endswith(">계")]
        cols["area_incl"] = pref[-1] if pref else inc[0]
    prefix = ""
    for c in cols["loc"]:
        m = re.search(r"\(([^)]{2,20})\)", raws[c])
        if m:
            prefix = clean(m.group(1))
    cols["loc_prefix"] = prefix
    return cols, heads


_LOC_VALUE_RE = re.compile(r"(?:[가-힣]{1,6}\s+)*[가-힣0-9]{1,6}[읍면동리가]")


def split_loc_jibun_cell(text, cur=""):
    """소재지와 지번이 한 칸에 이어 적힌 칸('소재지 및 지번' 열)을 [(소재지, 지번), ...] 로 쪼갠다.

    문서에 적힌 것만 쓴다(추측 없음): 지번 앞에 소재지(읍면동리로 끝나는 말)가 적혀 있으면 그 소재지를 새로 쓰고,
    지번만 적혀 있으면 직전에 적힌 소재지(cur)를 그대로 이어 붙인다. 반환: (쪼갠 목록, 마지막 소재지).
    예) '평택시 안중읍 학현리 465-8, 465-11, 산70-4, 평택시 안중읍 안중리 244-37'
        -> 학현리 465-8 / 465-11 / 산70-4, 안중리 244-37 (평택시 공고, 경북도청 게시판 실측 2026-10-17)"""
    t = re.sub(r"외\s*\d+\s*필지|일\s*원", " ", clean(text))
    out = []
    for piece in re.split(r"\s*[,，、]\s*|\s+및\s+", t):
        piece = piece.strip()
        m = PARCEL_RE.search(piece)
        if not m:
            continue
        head = re.sub(r"^(?:소\s*재\s*지|위\s*치)\s*[:：]?\s*", "", piece[:m.start()]).strip()
        if head and re.search(r"[가-힣][동리가읍면]$", head):
            cur = head
        parcels = parse_jibun_cell(piece[m.start():])
        for j, _area in parcels:
            if cur:
                out.append((cur, j))
    return out, cur


def expand_loc_jibun_grid(grid, hdr, lc, blank_cols=()):
    """'소재지 및 지번' 한 열(lc)에 소재지와 지번이 함께 적힌 표를, 열 하나를 더해 '소재지 열 + 지번 열' 표로 펼친다.
    한 칸에 지번이 여러 개면 지번마다 한 행으로 늘린다. 같은 칸의 소유자 등 나머지 칸은 모든 행에 그대로 복사하되,
    면적·지목처럼 필지마다 값이 다른 열(blank_cols)은 첫 행에만 두고 나머지는 비운다(한 칸에 합쳐진 값이라 필지별 값을 알 수 없다)."""
    out = Grid()
    for r in range(hdr):
        out.append(list(grid[r]) + ["지번"])
    out.heading = getattr(grid, "heading", "")
    cur = getattr(grid, "heading", "") or ""
    for r in range(hdr, len(grid)):
        row = list(grid[r])
        pairs, cur = split_loc_jibun_cell(row[lc], cur)
        if not pairs:
            out.append(row + [""])
            continue
        for k, (loc, j) in enumerate(pairs):
            nr = list(row)
            nr[lc] = loc
            if k > 0:
                for c in blank_cols:
                    nr[c] = ""
            out.append(nr + [j])
    return out


def rows_from_grid(grid, ctx):
    """grid 하나에서 토지조서 행들을 뽑는다. ctx: {'lastLoc':..., 'prev':..., 'debug':[...], 'tag':...}"""
    if not grid or not grid[0]:
        return []
    prev = ctx.get("prev")
    if (prev and len(grid[0]) == prev["ncol"] and looks_like_data_row(grid[0]) and not is_index_row(grid[0])
            and parse_jibun_cell(grid[0][prev["jcol"]])):
        return rows_by_cols(grid, 0, prev["cols"], prev["heads"], ctx)
    if len(grid) < 2:
        return []
    hdr = None
    for i in range(1, min(len(grid), 6)):
        if looks_like_data_row(grid[i]) and not is_index_row(grid[i]):
            hdr = i
            break
    if hdr is None:
        hdr = min(2, len(grid) - 1)
        if not any(re.search(r"지번|번지|소재", squash(" ".join(r))) for r in grid[:hdr]):
            return []
    head_text = squash(" ".join(" ".join(r) for r in grid[:hdr]))
    if re.search(NON_LAND_TABLE, head_text):
        return []
    cols, heads = classify_heads(grid, hdr)
    jcol = cols.get("jibun", cols.get("jibun_orig"))
    if jcol is None:
        lj = [c for c in cols["loc"] if re.search(r"지번|번지", heads[c])]
        if lj:  # '소재지 및 지번' 처럼 한 열에 소재지+지번이 함께 적힌 표
            blank = [cols[k] for k in ("area_incl", "area_orig", "jimok") if k in cols]
            grid = expand_loc_jibun_grid(grid, hdr, lj[0], blank)
            cols, heads = classify_heads(grid, hdr)
            jcol = cols.get("jibun", cols.get("jibun_orig"))
    if jcol is None:
        if cols["loc"] and ("jimok" in cols or "name" in cols):
            return rows_embedded(grid, hdr, cols, ctx)
        ctx["debug"].append({"tag": ctx["tag"], "reason": "no-jibun-col", "heads": heads})
        return []
    if not cols["loc"]:  # 머리글이 비어 있지만 값이 전부 '평창 병내리' 같은 소재지인 열(지번 열 왼쪽)을 소재지 열로 본다
        for c in range(jcol):
            if heads[c]:
                continue
            vals = [clean(grid[r][c]) for r in range(hdr, min(len(grid), hdr + 40)) if clean(grid[r][c])]
            if len(vals) >= 3 and sum(bool(_LOC_VALUE_RE.fullmatch(v)) for v in vals) >= 0.8 * len(vals):
                cols["loc"].append(c)
                break
    ctx["prev"] = {"ncol": len(grid[0]), "cols": cols, "heads": heads, "jcol": jcol}
    return rows_by_cols(grid, hdr, cols, heads, ctx)


def rows_by_cols(grid, hdr, cols, heads, ctx):
    """열 구성(cols)이 정해진 표에서 자료 행을 읽는다. 소유자 '이름'은 저장하지 않고 분류값(owner_type)만 남긴다."""
    jcol = cols.get("jibun", cols.get("jibun_orig"))
    out = []
    for r in range(hdr, len(grid)):
        row = grid[r]
        cell = row[jcol]
        if re.search(r"지번|번지", squash(cell)):
            continue
        if any(re.fullmatch(r"(합계|소계|총계|계)", squash(x)) for x in row[:jcol + 1]):
            continue  # 합계행('합 계 | 3필지')을 지번 3 으로 읽지 않는다(가평군 실측)
        pre = ""
        m = PARCEL_RE.search(clean(cell))
        if m and m.start() > 0:
            head_txt = clean(cell)[:m.start()].strip()
            if re.search(r"[가-힣]", head_txt) and len(head_txt) <= 30:
                pre, cell = head_txt, clean(cell)[m.start():]
        parcels = parse_jibun_cell(cell)
        if not parcels and "jibun_alt" in cols:  # 당초 지번이 비어 있으면(분할·신규 필지) 변경 지번을 쓴다(포천 실측)
            parcels = parse_jibun_cell(row[cols["jibun_alt"]])
        if not parcels:
            continue
        parts = []

        def add(t):
            t = clean(t)
            if t and not is_ditto(t) and t not in parts and not re.fullmatch(r"[-–—]+", t):
                parts.append(t)

        for c in cols["div"]:
            if not re.fullmatch(r"[\d.\s]*", row[c] or ""):
                add(row[c])
        for c in cols["loc"]:
            add(row[c])
        add(pre)
        loc = " ".join(parts)
        if cols["loc_prefix"] and cols["loc_prefix"] not in loc:
            loc = (cols["loc_prefix"] + " " + loc).strip()
        if loc and re.fullmatch(r"[A-Za-z0-9\-]{1,6}\s*(블록|블럭|획지|BL)?", squash(loc)):
            ctx["debug"].append({"tag": f"{ctx['tag']}:r{r + 1}", "reason": "non-parcel-lot",
                                 "heads": [loc, clean(cell)]})
            continue  # 'A1 1-4' = 블록 A1 의 획지 1-4. 지번이 아니라 PNU 를 만들 수 없다(광주시 송정지구 실측)
        if loc:
            ctx["lastLoc"] = loc
        else:
            loc = ctx.get("lastLoc", "")
        g = lambda k: clean(row[cols[k]]) if k in cols else ""
        orig_j = ""
        if "jibun_orig" in cols and "jibun" in cols:
            oj = parse_jibun_cell(row[cols["jibun_orig"]])
            orig_j = oj[0][0] if oj else ""
        owner_type = classify_owner_row(g("owner_div"), g("name"), g("addr") if "addr" in cols else None)
        for j, par_area in parcels:
            area_incl = num(g("area_incl")) if "area_incl" in cols else ""
            if not area_incl and par_area:
                area_incl = par_area
            area_orig = num(g("area_orig")) if "area_orig" in cols else ""
            if ("area_incl" not in cols and "area_orig" in cols and not par_area
                    and not re.search(r"지적|공부|전체|원면적|총면적", heads[cols["area_orig"]])):
                area_incl, area_orig = area_orig, ""
            out.append({
                "sojaeji": loc, "jibun_incl": j, "jibun_orig": orig_j or j,
                "jimok": g("jimok"), "area_incl": area_incl, "area_orig": area_orig,
                "owner_type": owner_type, "remark": g("remark"),
                "extract_loc": f"{ctx['tag']}:r{r + 1}",
            })
    return out


def rows_embedded(grid, hdr, cols, ctx):
    """지번 열이 따로 없고 소재지 칸에 '문막읍 궁촌리 457-2' 처럼 붙어 있는 표"""
    out = []
    lc = cols["loc"][0]
    for r in range(hdr, len(grid)):
        m = re.match(r"^(.*[가-힣])\s*((?:산\s*)?\d+(?:-\d+)?)\s*(?:번지)?\s*$", clean(grid[r][lc]))
        if not m:
            continue
        g = lambda k: clean(grid[r][cols[k]]) if k in cols else ""
        j = re.sub(r"\s", "", m.group(2))
        owner_type = classify_owner_row(g("owner_div"), g("name"), g("addr") if "addr" in cols else None)
        out.append({
            "sojaeji": m.group(1), "jibun_incl": j, "jibun_orig": j,
            "jimok": g("jimok"), "area_incl": num(g("area_incl")) if "area_incl" in cols else num(g("area_orig")),
            "area_orig": num(g("area_orig")) if "area_incl" in cols else "",
            "owner_type": owner_type, "remark": g("remark"),
            "extract_loc": f"{ctx['tag']}:r{r + 1}",
        })
    return out


def project_name_from_grids(grids):
    """공고문 첫 표의 '사업명' 칸 값을 사업명으로 쓴다 (없으면 None)"""
    for g in grids[:3]:
        for r in range(min(2, len(g) - 1)):
            heads = [squash(x) for x in g[r]]
            for c, h in enumerate(heads):
                if h in ("사업명", "사업의종류와명칭", "공사명", "사업의명칭"):
                    v = clean(g[r + 1][c]) if r + 1 < len(g) else ""
                    if v:
                        return v
    return None


def project_name_from_title(title):
    t = clean(title)
    for pat in (r"\[(.+)\]", r"『(.+?)』", r"「(.+?)」", r"[（(](.+)[）)]\s*$"):
        m = re.search(pat, t)
        if m and len(m.group(1)) >= 3:
            return clean(m.group(1))
    return re.sub(r"(공익사업\s*준비를\s*위한\s*)?(토지\s*출입\s*(허가)?\s*)?(보상계획\s*열람\s*)?(공시송달\s*)?공고", "", t).strip() or t


def rows_from_document_grids(grids, source_file, title=""):
    """grids: [(page_no, table_idx, grid), ...] -> (행 리스트, 해석 못한 표 목록)."""
    ctx_all, rows, debug = {"lastLoc": "", "prev": None}, [], []
    grids = [(pg, ti, pad_grid(g)) for pg, ti, g in grids]
    project = project_name_from_grids([g for _, _, g in grids]) or project_name_from_title(title)
    for page, ti, g in grids:
        ctx = {"lastLoc": getattr(g, "heading", "") or heading_from_grid(g) or ctx_all["lastLoc"],
               "prev": ctx_all["prev"], "debug": debug,
               "tag": f"{source_file}#p{page}t{ti + 1}"}
        got = rows_from_grid(g, ctx)
        if ctx.get("skipped_public"):
            debug.append({"tag": ctx["tag"], "reason": "public-owner", "heads": [str(ctx["skipped_public"])]})
        if got:
            ctx_all["lastLoc"] = ctx["lastLoc"]
        ctx_all["prev"] = ctx["prev"]
        for r in got:
            r["project_name"] = project
            r["source_file"] = source_file
        rows += got
    return rows, debug


# ============================================================ 본문 텍스트에서 지번 추출 (표가 없을 때)
def _build_jimok():
    names = set("전 답 과 목 임 광 염 대 장 학 차 주 창 도 철 제 천 구 유 양 수 공 체 원 종 사 묘 잡".split())
    names |= set("임야 잡종지 공장용지 학교용지 주차장 주유소용지 창고용지 도로 철도용지 제방 하천 구거 유지 양어장 "
                 "수도용지 공원 체육용지 유원지 종교용지 사적지 묘지 광천지 염전 목장용지 과수원 대지".split())
    return "|".join(sorted(names, key=len, reverse=True))


_JIMOK = _build_jimok()
_NUM = r"\d[\d,]*(?:\.\d+)?"
_JB = r"(?:산\s?)?\d{1,5}(?:-\d{1,4})?"
ROW_RE = re.compile(r"(?<![\d,.\-])(?P<jibun>%s)\s*(?:번지)?\s*(?P<jimok>%s)(?=\s)\s+(?P<a1>%s)(?![\d,])" % (_JB, _JIMOK, _NUM))
A2_RE = re.compile(r"\s+(%s)(?![\d,.])" % _NUM)
NEXT_ROW_RE = re.compile(r"\s*(?:〃|[가-힣]{1,5}\d?[동리](?![가-힣])|%s\s*(?:번지)?\s*(?:%s)(?=\s)\s+%s)" % (_JB, _JIMOK, _NUM))
DITTO_CHARS = "“”\"″〃ˮ‶"


def norm_text(s):
    s = re.sub(r"\s+", " ", s or "")
    s = re.sub(r"(?:(?<=\s)|^)[%s](?=\s)" % re.escape(DITTO_CHARS), "〃", s)
    s = re.sub(r"(?<=[동리])(?=(?:산\s?)?\d)", " ", s)
    s = re.sub(r"(\d)\s*번지\s*의\s*(\d)", r"\1-\2", s)
    s = re.sub(r"(\d)\s*-\s*(\d)", r"\1-\2", s)
    return s


# 문서가 게시판 지자체와 다른 시·군을 직접 적은 소재지: [시도] 시|군 [구] [읍면] 동|리 (Regions._foreign_region)
_FOREIGN_RE = re.compile(
    r"(?:(?P<sido>[가-힣]{2,6}(?:특별시|광역시|특별자치시|특별자치도|도))\s*)?"
    r"(?P<sigun>[가-힣]{1,4}[시군])\s*(?P<gu>[가-힣]{1,4}구)?\s*"
    r"(?:(?P<eup>[가-힣]{1,4}[읍면])\s*)?(?P<dr>[가-힣]{1,5}\d?[동리])")


# 소재지 열이 '면 | 리' 두 칸으로 나뉘고 값에 접미사가 없는 표('대강 당동 193-23' = 대강면 당동리). 단양군보 공고 제2026-1284호
# 실측(2026-10-17): 접미사 없이 '당동'만 읽으면 동 이름으로 오인되고 면이 빠진다. 근거 두 가지만 인정한다(추측 금지).
BARE_HEADER_RE = re.compile(r"소\s*재\s*지(?:(?!\d).){0,60}?(?<![가-힣])면(?![가-힣])(?:(?!\d).){0,20}?(?<![가-힣])리(?![가-힣])", re.S)
BARE_PAIR_RE = re.compile(r"(?<![가-힣])([가-힣]{1,4})\s+([가-힣]{1,5})\s*$")


def _suffix_by_text(token, kinds, text):
    """token 뒤에 kinds 중 하나를 붙인 말(예: '당동'+'리')이 본문에 실제 적혀 있고 그 접미사가 하나뿐이면 그 말, 아니면 None."""
    hits = [k for k in kinds if re.search(re.escape(token + k) + r"(?![가-힣])", text)]
    return token + hits[0] if len(hits) == 1 else None


_JIMOK_WORDS = frozenset("전 답 과 대 장 학 차 주 창 도 철 제 천 구 유 양 수 공 체 원 종 사 묘 잡 임 임야 대지 도로 하천 구거 제방 유지 잡종지 공원 학교용지 주차장 창고용지 주유소용지 공장용지 염전 광천지 철도용지 수도용지 체육용지 종교용지 사적지 묘지 양어장 목장용지".split())


def bare_myeon_ri(a, b, notice_text, has_header_cue):
    """'면 | 리' 열 값 두 개(a, b)에 접미사를 붙인다 -> (면 이름, 리 이름) 또는 None.
    근거 1) 표 머리글에 '소재지'와 따로 떨어진 '면', '리' 글자가 있다(열 이름이 면·리). 근거 2) 같은 공고 본문에
    '대강면', '당동리' 처럼 접미사를 붙인 말이 실제로 적혀 있다. 둘 다 없으면 None 이라 호출하는 쪽이 그 행을 읽지 않는다."""
    # 접미사가 이미 붙었거나(a 가 읍·면으로, b 가 리로 끝남) 한 글자이거나 지목 글자(임·전·답…)면 '접미사 없는 면·리 이름'이 아니다 -> 읽지 않는다.
    # (2026-10-18: 머리글 근거가 있으면 아무 두 단어에나 면·리를 붙여 '유구읍면 명곡리리', '임면 구리' 같은 가짜 소재지를 만들었다)
    if any(len(t) < 2 or t in _JIMOK_WORDS for t in (a, b)) or a[-1] in "읍면" or b[-1] == "리":
        return None
    if has_header_cue:
        return a + "면", b + "리"
    eup = _suffix_by_text(a, ("면", "읍"), notice_text)
    ri = _suffix_by_text(b, ("리", "동"), notice_text)
    return (eup, ri) if eup and ri else None


# 문서 위쪽에 '위치 : 충청남도 아산시 음봉면 동암리, 덕지리, 월랑리 일원' 처럼 상위 행정구역과 리 목록을 한 번만 적고, 아래 표에는 '동암리 701-6'
# 처럼 리만 적는 문서가 있다(사용자 지적 2026-10-18). 이때 리의 시군·읍면은 문서에 적힌 그 위치로 채운다(문서에 적힌 것만 쓴다).
_DECL_SIDO = r"[가-힣]{2,6}(?:특별시|광역시|특별자치시|특별자치도|도)"
_DECL_RI = r"[가-힣0-9]{1,6}[동리가]"
_DECL_RE = re.compile(
    rf"(?:(?P<sido>{_DECL_SIDO})\s*)?(?P<sigun>[가-힣]{{1,5}}[시군구])\s*(?:(?P<eup>[가-힣]{{1,4}}[읍면])\s*)?"
    rf"(?P<ris>{_DECL_RI}(?:\s*(?:,|·|、|및|와|과)\s*{_DECL_RI})*)\s*(?:일원|일대)")


def declared_locations(text):
    """본문에서 '<시도> <시군> [읍면] 리, 리, 리 일원' 으로 선언된 위치 -> {리: (시도, 시군, 읍면)}. 같은 리가 서로 다른 곳으로 선언되면 뺀다."""
    out, bad = {}, set()
    for m in _DECL_RE.finditer(text or ""):
        for ri in re.split(r"\s*(?:,|·|、|및|와|과)\s*", m.group("ris").strip()):
            val = (m.group("sido") or "", m.group("sigun"), m.group("eup") or "")
            if out.setdefault(ri, val) != val:
                bad.add(ri)
    return {k: v for k, v in out.items() if k not in bad}


def apply_declared_locations(text, rows):
    """소재지가 리뿐인 행(또는 도청 소재지 기본값이 붙은 행)에 문서가 선언한 위치(declared_locations)의 시군·읍면을 채운다.
    행 자신이 그 시군을 리와 함께 문서에 적었으면(예: '홍성군 동암리') 건드리지 않는다. rows 의 sojaeji 는 끝에 지번이 붙어 있어도 된다."""
    decl = declared_locations(text)
    if not decl:
        return rows
    flat = re.sub(r"\s+", "", text or "")
    for r in rows:
        soj, jb = r.get("sojaeji", ""), r.get("jibun_incl", "")
        tail = ""
        if jb and soj.endswith(jb):
            soj, tail = soj[:len(soj) - len(jb)].strip(), " " + jb
        words = soj.split()
        ri = next((w for w in reversed(words) if re.fullmatch(_DECL_RI, w)), None)
        if ri not in decl:
            continue
        sido, sigun, eup = decl[ri]
        cur_sigun = next((w for w in words if re.fullmatch(r"[가-힣]{1,5}[시군구]", w)), "")
        if cur_sigun and cur_sigun != sigun and re.search(re.escape(cur_sigun) + r"(?:[가-힣]{1,4}[읍면])?" + re.escape(ri), flat):
            continue  # 행 자신이 다른 시군을 리와 함께 적었다
        cur_sido = next((w for w in words if re.fullmatch(_DECL_SIDO, w)), "")
        r["sojaeji"] = " ".join(x for x in (sido or cur_sido, sigun, eup, ri) if x) + tail
    return rows


_PUBLIC_HEAD_RE = re.compile(r"(?:국\s*·?\s*공\s*유\s*지|국\s*유\s*지|공\s*유\s*지|시\s*유\s*지|군\s*유\s*지|도\s*유\s*지|구\s*유\s*지)")
_PRIVATE_HEAD_RE = re.compile(r"사\s*유\s*지|민\s*유\s*지")


def _public_heading_before(text, pos, window=300):
    """표 시작(pos) 바로 앞 window 글자 안에서 가장 가까운 소제목이 국유지·공유지류이면 True(사유지류가 더 가까우면 False)."""
    seg = text[max(0, pos - window):pos]
    pub = [m.start() for m in _PUBLIC_HEAD_RE.finditer(seg)]
    prv = [m.start() for m in _PRIVATE_HEAD_RE.finditer(seg)]
    return bool(pub) and (not prv or max(pub) > max(prv))


_ABBREV_LOC_RE = re.compile(r"([가-힣]{2,4})\s+([가-힣0-9]{1,5}\d?[동리])")


class Regions:
    """지자체별 법정동/리 목록으로 소재지를 검증하고 '완전한 주소'로 만든다.
    지자체를 추가할 때는 이 클래스를 새 sido_name/sigun_name/eupmyeon_ri 로 인스턴스화하면 된다
    (이 클래스 자체는 고치지 않는다)."""

    def __init__(self, sido_name, sigun_name, eupmyeon_ri=None, legal_dongs="", admin_dongs="",
                 not_region_words="", extra_files=()):
        self.sido_name = sido_name
        self.sigun_name = sigun_name
        self.eups = set((eupmyeon_ri or {}).keys())
        self.dongs = set(legal_dongs.split())
        self.admin_dongs = set(admin_dongs.split())
        self.not_region_words = set(not_region_words.split()) if isinstance(not_region_words, str) else set(not_region_words)
        self.ri_parent = {}
        self.pairs = set()
        self.candidates = {}
        for eup, ris in (eupmyeon_ri or {}).items():
            for ri in ris.split():
                self.add_pair(eup, ri)
        for p in extra_files:
            self.load(p)

        sido_base = re.escape(sido_name[:-1]) if sido_name.endswith("도") else re.escape(sido_name)
        sido_pat = rf"{sido_base}(?:특별자치)?도" if sido_name.endswith("도") else re.escape(sido_name)
        sigun_pat = re.escape(sigun_name)
        self._r_full = re.compile(rf"({sido_pat})?({sigun_pat})?([가-힣]{{1,4}}[읍면])?([가-힣]{{1,5}}\d?[동리])?")
        self._r_tail = re.compile(rf"(?:({sigun_pat})\s*)?([가-힣]{{1,4}}[읍면])?([가-힣]{{1,5}}\d?[동리])$")
        self._tail_full = re.compile(
            rf"(?<![가-힣0-9])(?:({sido_pat})\s*)?(?:({sigun_pat})\s*)?(?:([가-힣]{{1,4}}[읍면])\s*)?([가-힣]{{1,5}}\d?[동리])\s*$")
        self._tail_dr = re.compile(r"(?<![가-힣0-9])([가-힣]{1,5}\d?[동리])\s*$")
        self._prose_re = re.compile(
            rf"(?<![가-힣0-9])(?:({sido_pat})\s*)?(?:({sigun_pat})\s*)?(?:([가-힣]{{1,4}}[읍면])\s*)?(?P<dr>[가-힣]{{1,5}}\d?[동리])\s*"
            r"(?P<lst>%s\s*(?:번지)?(?:\s*(?:[,、·]|및)\s*%s\s*(?:번지)?)*)" % (_JB, _JB))

    def add_pair(self, eup, ri):
        self.ri_parent.setdefault(ri, set()).add(eup)
        self.pairs.add((eup, ri))

    def load(self, path):
        """<지자체>_regions.txt: 한 줄에 '동' 또는 '읍면 리'. # 은 주석"""
        try:
            with open(path, encoding="utf-8-sig") as f:
                for ln in f:
                    ln = ln.split("#", 1)[0].strip()
                    if not ln:
                        continue
                    parts = ln.split()
                    if len(parts) == 1:
                        if parts[0].endswith("동"):
                            self.dongs.add(parts[0])
                        elif parts[0].endswith("리"):
                            self.ri_parent.setdefault(parts[0], set())
                    elif len(parts) >= 2 and parts[1].endswith("리"):
                        self.eups.add(parts[0])
                        self.add_pair(parts[0], parts[1])
        except OSError:
            pass

    def is_known_dr(self, dr):
        return dr in self.dongs or dr in self.ri_parent

    @staticmethod
    def base_len(dr):
        return len(re.sub(r"\d", "", dr)) - 1

    def candidate(self, dr, ctx=""):
        if dr not in self.candidates:
            self.candidates[dr] = ctx

    def _foreign_region(self, raw):
        """문서가 이 게시판 지자체와 '다른 시·군'을 소재지에 직접 적은 경우(예: 경상북도청 게시판에 올라온 평택시 공고의
        '평택시 안중읍 학현리') 문서에 적힌 그대로 소재지를 만든다. 게시판 지자체의 시도·시군을 앞에 붙이면
        '경상북도 안동시 택시안중읍 학현리' 처럼 없는 주소가 된다(2026-10-17 수집 로그 실측). 시도는 문서에 적혀 있을 때만 쓴다.
        시·군·읍면·리가 문서 표기와 정확히 맞아떨어질 때만 처리하고, 아니면 None(기존 규칙으로 계속)."""
        s = re.sub(r"[\(\)\[\]<>·,.]+", " ", clean(raw))
        s = re.sub(r"\s*(일원|일대|외\s*\d*\s*필지|지내|번지)\s*$", "", s).strip()
        m = _FOREIGN_RE.fullmatch(s)
        if not m or m.group("sigun") == self.sigun_name:
            return None
        parts = [m.group(k) for k in ("sido", "sigun", "gu", "eup", "dr") if m.group(k)]
        return {"region": " ".join(parts), "status": "CHECK",
                "note": f"타 시군 표기({m.group('sigun')}): 게시판 지자체({self.sigun_name})와 달라 문서 표기 그대로 사용",
                "eup": m.group("eup"), "dr": m.group("dr")}

    def resolve(self, raw):
        """소재지 원문 -> {'region','status','note','eup','dr'} 또는 None(읍면동리를 못 찾음).
        status: OK(검증 통과) / CHECK(검증 필요) / BAD(리·동을 못 찾음)"""
        foreign = self._foreign_region(raw)
        if foreign is not None:
            return foreign
        ab = _ABBREV_LOC_RE.fullmatch(clean(raw))
        if ab and not re.search(r"[도시군구읍면동리가]$", ab.group(1)):
            # '평창 병내리'(시·군 약칭 + 리): 합쳐 읽으면 '평창병내리'라는 없는 리가 되고, 게시판 지자체를 붙이면 엉뚱한 곳이 된다
            return {"region": f"{ab.group(1)} {ab.group(2)}", "status": "CHECK",
                    "note": f"시·군 약칭('{ab.group(1)}') + 리: 문서 표기 그대로 사용", "eup": None, "dr": ab.group(2)}
        s = squash(raw)
        s = re.sub(r"[\(\)\[\]<>·,.]+", "", s)
        s = re.sub(r"(일원|일대|외\d*필지|지내|번지)+$", "", s)
        if not s:
            return None
        notes, status = [], "OK"
        for tok in re.findall(r"[가-힣]{1,4}[시군]", clean(raw)):
            if tok != self.sigun_name and tok not in ("특별자치",):
                status = "CHECK"
                notes.append(f"타 시군 표기({tok})")
        m = self._r_full.fullmatch(s)
        if m and (m.group(3) or m.group(4)):
            sido, sigun, eup, dr = m.groups()
        else:
            m = self._r_tail.search(s)
            if not m:
                return None
            sigun, eup, dr = m.groups()
        if eup and eup not in self.eups and not re.fullmatch(r"[가-힣]{1,4}[읍면]", eup):
            eup = None
        if not dr:
            return {"region": " ".join(x for x in (self.sido_name, self.sigun_name, eup) if x), "status": "BAD",
                    "note": "리·동을 찾지 못함", "eup": eup, "dr": ""}
        suffix = dr[-1]
        if self.base_len(dr) == 1:
            notes.append("한글자 지명")
        if suffix == "동":
            if dr in self.dongs:
                pass
            elif dr in self.admin_dongs:
                status = "CHECK"
                notes.append("행정동 표기(법정동 확인)")
            else:
                status = "CHECK"
                notes.append("미등록 동")
                self.candidate(dr, "동")
            if eup:
                status = "CHECK"
                notes.append(f"동 앞에 읍면({eup})")
        else:
            parents = self.ri_parent.get(dr, set())
            if eup:
                if (eup, dr) in self.pairs:
                    pass
                elif parents:
                    status = "CHECK"
                    notes.append(f"{dr}은 {'/'.join(sorted(parents))} 소속(문서 표기 {eup})")
                else:
                    status = "CHECK"
                    notes.append("미등록 리")
                    self.candidate(dr, "리")
            else:
                if len(parents) == 1:
                    eup = next(iter(parents))
                    notes.append(f"읍면 보완({eup})")
                elif len(parents) > 1:
                    status = "CHECK"
                    notes.append(f"읍면 불명(후보 {'/'.join(sorted(parents))})")
                else:
                    status = "CHECK"
                    notes.append("미등록 리, 읍면 없음")
                    self.candidate(dr, "리")
        region = " ".join(x for x in (self.sido_name, self.sigun_name, eup, dr) if x)
        return {"region": region, "status": status, "note": "; ".join(notes), "eup": eup, "dr": dr}

    def _tail_region(self, chunk):
        m = self._tail_full.search(chunk)
        if not m:
            return None
        sido, sigun, eup, dr = m.groups()
        if eup and eup not in self.eups:
            m2 = self._tail_dr.search(chunk)
            if not m2:
                return None
            sido = sigun = eup = None
            dr = m2.group(1)
        raw = " ".join(x for x in (sido, sigun, eup, dr) if x)
        return {"raw": raw, "dr": dr, "explicit": bool(sido or sigun or eup)}

    def _accept_region(self, tr, have_last):
        dr = tr["dr"]
        if self.is_known_dr(dr) or tr["explicit"] or not have_last:
            return True
        if self.base_len(dr) == 1:
            self.candidate(dr, "본문 후보")
            return False
        return True

    def rows_from_text_A(self, text, last_region=None):
        """규칙 A: 표를 글로 펴 놓은 형태. 반환: (행 목록, 마지막 지역명)"""
        rows, pos, last = [], 0, last_region
        cue = BARE_HEADER_RE.search(text)
        cue_at = cue.start() if cue else None
        first = ROW_RE.search(text)
        head = text[:first.start()] if first else ""
        i_in, i_or = head.rfind("편입"), max(head.rfind("지적"), head.rfind("공부"), head.rfind("전체"))
        incl_first = i_in >= 0 and i_or >= 0 and i_in < i_or
        pub_section, prev_end = False, -10**9  # '국유지/공유지' 소제목 아래 표인지(같은 표가 이어지는 동안 유지)
        for m in ROW_RE.finditer(text):
            if m.start() < pos:
                continue
            gap = text[max(prev_end, 0):m.start()]
            if m.start() - prev_end > 150 or _PUBLIC_HEAD_RE.search(gap) or _PRIVATE_HEAD_RE.search(gap):
                pub_section = _public_heading_before(text, m.start())  # 표가 끊겼거나 새 소제목(국유지·공유지·사유지)이 나오면 다시 판단
            chunk = text[pos:m.start()].rstrip()
            bare = None
            if not chunk.endswith("〃") and (bp := BARE_PAIR_RE.search(chunk)):
                bare = bare_myeon_ri(bp.group(1), bp.group(2), text, cue_at is not None and cue_at < m.start())
            if chunk.endswith("〃"):
                region = last
            elif bare:  # '면 | 리' 열 표: 문서가 보여 주는 접미사를 붙여 '대강면 당동리'로 읽는다
                region = last = f"{bare[0]} {bare[1]}"
            else:
                tr = self._tail_region(chunk)
                if tr and self._accept_region(tr, last is not None):
                    region = tr["raw"]
                    last = region
                else:
                    region = last
            end = m.end()
            a1 = m.group("a1").strip(",")
            a2 = None
            m2 = A2_RE.match(text, end)
            if m2:
                cand = m2.group(1).strip(",")
                small = re.fullmatch(r"\d{1,3}", cand) is not None
                if not (small and NEXT_ROW_RE.match(text, m2.end())):
                    a2 = cand
                    end = m2.end()
            pos = end
            jb = re.sub(r"\s", "", m.group("jibun"))
            if not region or re.fullmatch(r"산?0+(-0+)?", jb):
                continue
            prev_end = end
            public = bool(re.match(r"\s*[국공]\s*\(", text[end:end + 12]))  # 면적 바로 뒤 소유자 칸이 '국(기획재정부)' 처럼 국·공유 표기면 공공 소유로 표시(수집은 한다: law.md 1-2절)
            ow = re.match(r"\s*([가-힣()·]{2,14})", text[end:end + 30])
            public = public or bool(pub_section or (ow and is_public_owner(ow.group(1))))  # 소유자 칸이 국가·공공기관이거나 '국유지·공유지' 소제목 아래 표면 공공 소유로 표시
            if a2 is not None:
                orig, incl = (a2, a1) if incl_first else (a1, a2)
            else:
                orig, incl = "", a1
            rows.append({"sojaeji": region, "jibun_incl": jb, "jibun_orig": jb, "jimok": m.group("jimok"),
                         "area_incl": num(incl), "area_orig": num(orig), "owner_type": "국공유" if public else "", "remark": ""})
        return rows, last

    def rows_from_text_B(self, text):
        """규칙 B: 문장 속 '지역명 지번번지'. 표가 없어 A 로 못 읽었을 때의 대체 경로."""
        rows = []
        for m in self._prose_re.finditer(text):
            sido, sigun, eup, dr = m.group(1), m.group(2), m.group(3), m.group("dr")
            if eup and eup not in self.eups:
                continue
            lst = m.group("lst")
            tail = text[m.end():m.end() + 12]
            if "번지" not in lst and not re.match(r"\s*(?:일원|일대|외\s*\d+\s*필지)", tail):
                continue
            explicit = bool(sido or sigun or eup)
            short = self.base_len(dr) == 1
            known = self.is_known_dr(dr)
            if not (known or explicit):
                if short and dr not in self.not_region_words:
                    pass
                else:
                    self.candidate(dr, "본문(번지)")
                    continue
            elif short and dr in self.not_region_words and not (known or eup or sigun):
                continue
            raw = " ".join(x for x in (sido, sigun, eup, dr) if x)
            rem = "본문 번지 표기" + (" (일원)" if re.match(r"\s*(?:일원|일대)", tail) else "")
            for jm in re.finditer(_JB, lst):
                jb = re.sub(r"\s", "", jm.group(0))
                if re.fullmatch(r"산?0+(-0+)?", jb):
                    continue
                rows.append({"sojaeji": raw, "jibun_incl": jb, "jibun_orig": jb, "jimok": "", "area_incl": "",
                             "area_orig": "", "owner_type": "", "remark": rem})
        return rows

    def rows_from_text(self, text):
        """본문 글 -> 행 (규칙 A 우선, 없으면 규칙 B). 소재지는 원문 지역명 상태."""
        t = norm_text(text)
        rows, _ = self.rows_from_text_A(t)
        if not rows:
            rows = self.rows_from_text_B(t)
        return rows


def finalize_rows(rows, regions, sojaeji_with_jibun=True):
    """추출한 행의 소재지를 '완전한 주소'로 바꾸고 주소 검증 결과(addr_status/addr_note)를 채운다."""
    for r in rows:
        raw = r.get("sojaeji", "")
        j = r.get("jibun_incl", "")
        res = regions.resolve(raw)
        if res is None:
            r["addr_status"], r["addr_note"] = "BAD", "소재지(읍면동리) 못 찾음: " + clean(raw)[:40]
            r["sojaeji"] = clean((raw + " " + j) if sojaeji_with_jibun else raw)
        else:
            r["addr_status"], r["addr_note"] = res["status"], res["note"]
            r["sojaeji"] = (res["region"] + " " + j).strip() if sojaeji_with_jibun else res["region"]
        r["pnu_status"] = "UNRESOLVED" if r["addr_status"] == "OK" else "ADDR_CHECK"
        r.setdefault("pnu", "")
    return rows


def dedupe_parcels(rows, sojaeji_with_jibun=True):
    """한 문서 안에서 같은 편입지번(완전한 주소)은 1행만 남긴다."""
    out, idx = [], {}
    rank = {"OK": 0, "CHECK": 1, "BAD": 2}
    for r in rows:
        k = r["sojaeji"] if sojaeji_with_jibun else (r["sojaeji"], r["jibun_incl"])
        if k not in idx:
            idx[k] = len(out)
            out.append(r)
            continue
        f = out[idx[k]]
        for fld in ("jimok", "area_incl", "area_orig", "jibun_orig", "remark", "owner_type"):
            if not f.get(fld) and r.get(fld):
                f[fld] = r[fld]
        if rank.get(r.get("addr_status"), 3) < rank.get(f.get("addr_status"), 3):
            f["addr_status"], f["addr_note"], f["pnu_status"] = r["addr_status"], r["addr_note"], r["pnu_status"]
    return out


# ============================================================ 최종 스키마로 정리 (jose_rows)
# pnu / geometry 는 이 모듈에서 채우지 않는다 (VWorld 조회 등 후처리 단계의 몫).
JOSE_FIELDS = [
    "site_name", "sojaeji", "jibun", "jimok", "area_incl", "area_orig",
    "owner_type", "project_name", "pnu", "pnu_status", "source_file", "collected_at", "geometry",
]




def full_text(ext, data):
    """AI 보정용 본문 전체(표 밖 문단 포함). 읽지 못하면 ''."""
    ext = (ext or "").lower()
    try:
        if ext == "pdf":
            import pdfplumber
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                return "\n".join((pg.extract_text() or "") for pg in pdf.pages)
        if ext == "hwpx" and data.startswith(b"PK\x03\x04"):
            lines = []
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for sn in sorted(n for n in z.namelist() if re.search(r"Contents/section\d+\.xml$", n)):
                    root = ET.fromstring(z.read(sn))
                    for p in root.iter():
                        if _lname(p) != "p" or any(_lname(x) == "p" for x in p.iter() if x is not p):
                            continue
                        t = clean("".join(x.text or "" for x in p.iter() if _lname(x) == "t"))
                        if t:
                            lines.append(t)
            return "\n".join(lines)
        if ext == "docx" and data.startswith(b"PK\x03\x04"):
            W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                root = ET.fromstring(z.read("word/document.xml"))
            paras = (clean("".join(x.text or "" for x in p.iter(W + "t"))) for p in root.iter(W + "p"))
            return "\n".join(t for t in paras if t)
        grids = local_grids(ext, data)
        return grids_text(grids) if grids else ""
    except Exception:  # 본문을 못 읽으면 AI 보정을 건너뛸 뿐이다
        return ""


# 토지 목록이 아닌 양식 첨부(의견제출서·이의신청서·동의서 등). 파일명에 '조서'가 있으면 양식이라도 읽는다.
FORM_FILENAME_RE = re.compile(r"의견\s*(제출)?서|제출서|신청서|동의서|추천서|위임장|서약서|확인서|\(서식\s*\d*\)|\[서식\s*\d*\]|양식")


# 공사·용역 입찰 서류(설계내역서·견적·계약조건 등): 필지 목록이 아니므로 읽지 않는다
NON_LAND_FILENAME_RE = re.compile(r"설계\s*(설명|내역)서|내역서|입찰|견적|계약\s*(이행|조건)|과업\s*지시|시방서|공내역")


# 입찰·견적·제안서·용역 공고(제목 기준). 파일명에 '조서'가 있으면 토지조서일 수 있어 여기에 넣지 않는다.
BID_TITLE_RE = re.compile(r"입찰|견적|제안서|제안\s*요청|용역|수의\s*계약|낙찰|발주|공개\s*경쟁")
_BID_LABEL = r"(?:공\s*사\s*현\s*장|공\s*사\s*위\s*치|공\s*사\s*장\s*소|사\s*업\s*위\s*치|사\s*업\s*대\s*상\s*지|과\s*업\s*위\s*치|위\s*치|대\s*상\s*지)"
_BID_ADMIN = r"(?:[가-힣]{1,6}(?:특별시|광역시|특별자치시|특별자치도|도|시|군|구|읍|면)\s+)"
_BID_PLACE = r"[가-힣][가-힣0-9]{0,5}(?:읍|면|동|리|가)"
_BID_JIBUN = r"산?\s?\d{1,5}(?:\s*-\s*\d{1,4})?"
# '공사현장: 상주시 사벌국면 매호리 255-9번지 일원' — 이름표 + 콜론 + 소재지 + 지번 + '번지'
BID_LABEL_RE = re.compile(rf"{_BID_LABEL}\s*[:：]\s*(?P<addr>{_BID_ADMIN}{{0,4}}{_BID_PLACE})\s*(?P<jibun>{_BID_JIBUN})\s*번지")
# '(고아읍 관심리 557-3)', '(구포동 976-8)' — 괄호 안 소재지 + 지번
BID_PAREN_RE = re.compile(rf"[\(（]\s*(?P<addr>{_BID_ADMIN}{{0,2}}{_BID_PLACE})\s+(?P<jibun>{_BID_JIBUN})\s*[\)）]")


def bid_location_rows(text):
    """입찰·견적·제안서류 본문에서 소재지와 지번이 함께 적힌 공사 위치만 뽑는다(지번 없는 '○○리 일원' 은 제외). -> 행 리스트"""
    rows, seen = [], set()
    t = re.sub(r"\s+", " ", text or "")
    for rx, note in ((BID_LABEL_RE, "공사 위치"), (BID_PAREN_RE, "공사 위치(괄호)")):
        for m in rx.finditer(t):
            addr = m.group("addr").strip()
            place = re.findall(r"[가-힣0-9]+(?:읍|면|동|리|가)$", addr)
            if not place or re.fullmatch(r"제?\d+", re.sub(r"(읍|면|동|리|가)$", "", place[-1])):
                continue  # '제3동' 같은 건물 호수는 지명이 아니다
            jibun = re.sub(r"\s+", "", m.group("jibun"))
            if re.fullmatch(r"산?0+(-0+)?", jibun) or (addr, jibun) in seen:
                continue
            seen.add((addr, jibun))
            rows.append({"sojaeji": addr, "jibun_incl": jibun, "jibun_orig": jibun, "jimok": "", "area_incl": "", "area_orig": "",
                         "owner_type": "", "remark": note, "extract_loc": "bid-location"})
    return rows


def _looks_like_land_list(text):
    """본문에 지번 형태가 여러 개 있고 토지보상 문서로 보이는가(AI 호출 낭비 방지)."""
    if len(re.findall(r"(?<![\d-])(?:산\s*)?\d{1,5}(?:-\d{1,4})?\s*번?지?", text)) < 3:
        return False
    return bool(re.search(r"편입|보상|수용|토지조서|용지|소재지|지번|지목", text))


def extract_from_attachment(data, ext, filename, title, regions, site_name="", collected_at="",
                             sojaeji_with_jibun=True, ai=None, report=None):
    """첨부파일 바이트(다운로드 직후, 디스크에 남기지 말고 메모리에서 바로 처리) -> jose_row 리스트.
    표를 못 읽으면 본문 텍스트 규칙(regions.rows_from_text)으로 대체한다.
    그래도 0행이거나 모든 행의 소재지를 못 찾으면 ai(core.ai_extract.AiDocExtractor)가 있을 때 DeepSeek 으로 읽는다.
    지원하지 않는 형식(예: 구버전 .hwp)은 빈 리스트를 반환한다 — 호출하는 쪽에서 로그만 남기면 된다.
    report(dict, 선택): 수집 로그용 처리 내역을 채운다(code/detail/table_rows/text_rows/ai_rows/bad_rows/skipped_lots)."""
    ext = (ext or "").lower()
    rep = report if report is not None else {}
    rep.update({"code": "OK", "detail": "", "table_rows": 0, "text_rows": 0, "ai_rows": 0, "bad_rows": 0, "skipped_lots": 0,
                "skipped_public": 0})
    if FORM_FILENAME_RE.search(filename or "") and "조서" not in (filename or ""):
        rep["code"], rep["detail"] = "FORM", "의견서·신청서 등 양식 첨부(필지 목록 아님)라 읽지 않음"
        return []
    nonland_file = bool(NON_LAND_FILENAME_RE.search(filename or "")) and "조서" not in (filename or "")
    bid_title = bool(BID_TITLE_RE.search(title or "")) and "조서" not in (filename or "")
    if nonland_file or bid_title:
        # 입찰·견적·제안서·용역 공고: 문서가 '공사현장: …리 255-9번지', '(고아읍 관심리 557-3)' 처럼 위치를 지번까지 정확히 적었으면
        # 그 지번만 읽고 표는 읽지 않는다. 표 전체를 필지 목록으로 읽으면 금액·기간 숫자가 지번으로 잡히는 쓰레기 행이 생긴다
        # (상주시 견적 공고, 구미시 제안서 공고 실측 2026-10-18; 사용자 지시: 정확한 지번이 있으면 정보가 될 수 있다).
        # 그런 위치가 없으면 이전과 똑같이 처리한다(설계내역서 등 입찰 서류 파일명은 건너뜀, 그 밖은 일반 규칙).
        rows = bid_location_rows(full_text(ext, data))
        if rows:
            project = project_name_from_title(title)
            for r in rows:
                r["project_name"] = project
                r["source_file"] = filename
            rep["text_rows"] = len(rows)
            rows = dedupe_parcels(finalize_rows(rows, regions, sojaeji_with_jibun=sojaeji_with_jibun),
                                  sojaeji_with_jibun=sojaeji_with_jibun)
            rep["bad_rows"] = sum(1 for r in rows if r.get("addr_status") == "BAD")
            rep["code"] = "ADDR_CHECK" if rep["bad_rows"] else "OK"
            rep["detail"] = f"입찰·견적·제안서류: 공사 위치 지번 {len(rows)}건만 읽음(표는 읽지 않음)"
            return _to_jose_out(rows, filename, site_name, collected_at)
        if nonland_file:
            rep["code"], rep["detail"] = "NOT_LAND", "입찰·설계·계약 서류(필지 목록 아님)라 읽지 않음"
            return []
    grids = local_grids(ext, data)
    if grids is None:
        rep["code"], rep["detail"] = "UNSUPPORTED", f"형식 {ext} 을(를) 표로 읽을 수 없음(또는 확장자와 실제 형식 불일치)"
        return []
    rows, debug = rows_from_document_grids(grids, filename, title)
    rep["table_rows"] = len(rows)
    rep["skipped_lots"] = sum(1 for d in debug if d.get("reason") == "non-parcel-lot")
    rep["skipped_public"] = sum(int(d["heads"][0]) for d in debug if d.get("reason") == "public-owner")
    if not rows:
        text = pdf_text(data) if ext == "pdf" else grids_text(grids)
        rows = regions.rows_from_text(text)
        project = project_name_from_title(title)
        for r in rows:
            r["project_name"] = project
            r["source_file"] = filename
        rep["text_rows"] = len(rows)
    rows = finalize_rows(rows, regions, sojaeji_with_jibun=sojaeji_with_jibun)
    rows = dedupe_parcels(rows, sojaeji_with_jibun=sojaeji_with_jibun)
    rep["bad_rows"] = sum(1 for r in rows if r.get("addr_status") == "BAD")
    if ai is not None and getattr(ai, "enabled", False) and (not rows or rep["bad_rows"] == len(rows)):
        body = full_text(ext, data)
        if _looks_like_land_list(body):
            ai_rows, note = ai.extract(body, title, site_name)
            if ai_rows:
                project = project_name_from_title(title)
                got = [{"sojaeji": a["sojaeji"], "jibun_incl": a["jibun"], "jibun_orig": a["jibun"],
                        "jimok": a["jimok"], "area_incl": a["area_incl"], "area_orig": "",
                        "owner_type": "확인필요", "remark": "", "extract_loc": "ai",
                        "project_name": project, "source_file": filename} for a in ai_rows]
                got = finalize_rows(got, regions, sojaeji_with_jibun=sojaeji_with_jibun)
                got = dedupe_parcels(got, sojaeji_with_jibun=sojaeji_with_jibun)
                if len(got) >= len(rows):  # 규칙 결과(없거나 전부 소재지 없음)보다 낫다
                    rows, rep["ai_rows"] = got, len(got)
                    rep["bad_rows"] = sum(1 for r in rows if r.get("addr_status") == "BAD")
                    rep["code"], rep["detail"] = "AI_USED", note
            else:  # AI 호출이 실패했을 때만 '실패'. 정상 응답인데 0필지면 지번 목록이 없는 문서다.
                failed = getattr(ai, "last_failed", 0)
                rep["code"], rep["detail"] = ("AI_FAIL" if failed else "NO_PARCELS"), note
    if rep["code"] == "OK" and not rows and not rep["skipped_public"]:
        # 본문에 지번 목록이 아예 없으면 읽기 실패가 아니라 '필지 목록이 없는 공고'다(사용자: 필요 없음, 2026-10-17).
        # 지번 목록처럼 보이는데 못 읽은 경우만 ZERO_ROWS(주의)로 남겨 사람이 보게 한다.
        if not _looks_like_land_list(full_text(ext, data)):
            rep["code"], rep["detail"] = "NO_PARCELS", "본문에 지번 목록이 없음(필지 목록이 없는 공고)"
    if rep["code"] == "OK":
        if not rows and rep["skipped_public"]:
            rep["code"], rep["detail"] = "ALL_PUBLIC", f"소유자가 국가·지자체·공공기관인 필지 {rep['skipped_public']}건만 있어 제외"
        elif not rows:
            tags = "; ".join(f"{d['tag'][-24:]}:{d['reason']}" for d in debug[:3] if d["reason"] != "public-owner")
            rep["code"], rep["detail"] = "ZERO_ROWS", f"표 {len(grids)}개 해석했으나 필지 0행; 해석 못 한 표 {len(debug)}개 {tags}"
        elif rep["bad_rows"]:
            rep["code"] = "NO_REGION" if rep["bad_rows"] == len(rows) else "ADDR_CHECK"
            first = next((r["addr_note"] for r in rows if r.get("addr_status") == "BAD"), "")
            rep["detail"] = f"{rep['bad_rows']}/{len(rows)}행 소재지 못 찾음 예: {first}"
        elif rep["skipped_lots"]:
            rep["detail"] = f"블록/획지 번호 {rep['skipped_lots']}행 제외"
        if rows and rep["skipped_public"] and rep["code"] in ("OK", "ADDR_CHECK"):
            rep["detail"] = (rep["detail"] + "; " if rep["detail"] else "") + f"공공 소유 {rep['skipped_public']}건 제외"
    if rows and re.search(r"일원|일대", full_text(ext, data) or ""):
        rows = apply_declared_locations(full_text(ext, data), rows)
    return _to_jose_out(rows, filename, site_name, collected_at)


def _to_jose_out(rows, filename, site_name, collected_at):
    out = []
    for r in rows:
        out.append({
            "site_name": site_name,
            "sojaeji": r.get("sojaeji", ""),
            "jibun": r.get("jibun_incl", ""),
            "jimok": r.get("jimok", ""),
            "area_incl": r.get("area_incl", ""),
            "area_orig": r.get("area_orig", ""),
            "owner_type": r.get("owner_type", ""),
            "project_name": r.get("project_name", ""),
            "pnu": r.get("pnu", ""),
            "pnu_status": r.get("pnu_status", ""),
            "source_file": r.get("source_file", filename),
            "collected_at": collected_at,
            "geometry": None,
        })
    return out
