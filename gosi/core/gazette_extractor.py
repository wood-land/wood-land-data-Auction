"""
core/gazette_extractor.py — 시보·군보·도보·구보·공보(지자체 공보) 한 호(PDF/HWPX 등)에서
"보상 관련 공고"만 골라 그 안의 소재지·지번을 뽑는 공통 로직(지자체 무관).

공보 한 호에는 고시·공고 수십 건이 한 파일에 들어 있다. 그래서
  1) 파일 -> 본문 텍스트(줄바꿈 유지)
  2) 본문 -> 공고 단위로 분할("... 공고 제2026-123호" 같은 머리글 기준)
  3) 보상 관련 공고만 선별(제목 부근에 보상 키워드가 있는 공고)
  4) 선별된 공고 본문에서 기존 토지조서 엔진의 본문 주소 규칙(Regions.rows_from_text)으로
     소재지·지번 추출 -> jose_extractor.finalize_rows / dedupe_parcels 로 주소 정리
순서로 처리한다. 표(토지조서)는 텍스트로 펴진 형태를 Regions.rows_from_text 규칙 A가 읽는다.
새 지자체를 추가해도 이 파일은 건드리지 않는 것이 원칙이다(지자체별 Regions 만 바뀐다).
"""

import io
import os
import re
import shutil
import subprocess
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor

from core import jose_extractor

# 공고 머리글: 줄 시작의 "<기관명?> 공고|고시 제YYYY-N호"
NOTICE_HEAD_RE = re.compile(
    r"(?m)^[ \t]*[○◉●■▣◆◇▶▷□▪\-\*·]*[ \t]*(?:[가-힣A-Za-z0-9·]{1,12}[ \t]*){0,3}?(?:공고|고시|공시송달|알림)[ \t]*제[ \t]*\d{4}[ \t]*[-–][ \t]*\d+[ \t]*호"
)
# 목차 줄("...----- 21", "······ 18")은 공고 머리글이 아니다
TOC_LINE_RE = re.compile(r"[-·.…]{4,}\s*\d+\s*$")

# 보상 관련성 판단 키워드 (cities/_shared.DEFAULT_KEYWORDS 와 같은 결 + 공보 본문에 자주 나오는 표현)
COMP_KEYWORDS = [
    "보상", "협의", "사업인정", "수용", "재결", "토지조서", "물건조서", "지장물", "이주대책",
    "공익사업", "출입", "의견 청취", "의견청취", "지형도면", "정비사업", "조성사업", "정비공사",
    "노선 지정", "자연재해위험개선지구",
]
HEAD_WINDOW = 350  # 공고 제목 부근으로 보는 글자 수


def sniff_kind(data):
    """확장자를 믿지 않고 파일 서명으로 형식을 판정: pdf / hwpx / docx / xlsx / hwp(구버전, 미지원) / zip / unknown"""
    if data.startswith(b"%PDF"):
        return "pdf"
    if data.startswith(b"PK\x03\x04"):
        try:
            names = zipfile.ZipFile(io.BytesIO(data)).namelist()
        except zipfile.BadZipFile:
            return "unknown"
        if any(n.startswith("Contents/section") for n in names):
            return "hwpx"
        if any(n.startswith("word/") for n in names):
            return "docx"
        if any(n.startswith("xl/") for n in names):
            return "xlsx"
        return "zip"
    if data.startswith(b"\xd0\xcf\x11\xe0"):
        return "hwp"
    return "unknown"


# pypdfium2는 여러 스레드가 동시에 쓰면 프로세스가 비정상 종료한다 — 한 번에 하나만 실행한다.
_PDFIUM_LOCK = threading.Lock()


def _pdfium_text(data):
    import pypdfium2 as pdfium

    with _PDFIUM_LOCK:
        pdf = pdfium.PdfDocument(data)
        parts = []
        try:
            for i in range(len(pdf)):
                page = pdf[i]
                textpage = page.get_textpage()
                parts.append(textpage.get_text_range())
                textpage.close()
                page.close()
        finally:
            pdf.close()
    return "\n".join(parts)


def _pdf_text(data):
    """PDF 본문(줄바꿈 유지). pypdfium2가 빠르므로 먼저 쓰고, 안 되면 pdfplumber."""
    try:
        text = _pdfium_text(data)
        if text.strip():
            return text.replace("\r\n", "\n").replace("\r", "\n")
    except Exception:
        pass
    import pdfplumber

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return "\n".join((p.extract_text() or "") for p in pdf.pages)


# ---- 스캔형(이미지) PDF -> OCR (테서랙트 kor+eng) ----
TESSERACT = os.environ.get("TESSERACT_CMD") or shutil.which("tesseract") or "C:/Program Files/Tesseract-OCR/tesseract.exe"
_OCR_SEM = threading.Semaphore(3)  # 동시에 도는 테서랙트 프로세스 수 제한(CPU)


def ocr_available():
    return bool(TESSERACT) and os.path.exists(TESSERACT)


def _render_pages(data, scale, max_pages):
    """PDF -> 페이지별 PNG 바이트(흑백). pypdfium2는 잠금 안에서만 쓴다."""
    import pypdfium2 as pdfium

    pngs = []
    with _PDFIUM_LOCK:
        pdf = pdfium.PdfDocument(data)
        try:
            for i in range(min(len(pdf), max_pages)):
                page = pdf[i]
                pil = page.render(scale=scale).to_pil().convert("L")
                buf = io.BytesIO()
                pil.save(buf, "PNG")
                pngs.append(buf.getvalue())
                page.close()
        finally:
            pdf.close()
    return pngs


def _ocr_png(png, lang):
    with _OCR_SEM:
        proc = subprocess.run(
            [TESSERACT, "stdin", "stdout", "-l", lang, "--psm", "4"],
            input=png, capture_output=True, timeout=240,
        )
    return proc.stdout.decode("utf-8", "replace")


def ocr_pdf_text(data, lang="kor+eng", scale=3.0, max_pages=3000):
    """스캔형 PDF -> 본문 텍스트(OCR). 테서랙트가 없으면 None. 페이지 순서를 유지해 줄바꿈으로 잇는다."""
    if not ocr_available():
        return None
    pngs = _render_pages(data, scale, max_pages)
    with ThreadPoolExecutor(3) as ex:
        pages = list(ex.map(lambda b: _ocr_png(b, lang), pngs))
    return "\n".join(pages)


def _hwpx_text(data):
    """HWPX 본문: 문단(<p>)마다 줄바꿈."""
    import xml.etree.ElementTree as ET

    out = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        secs = sorted(n for n in z.namelist() if re.match(r"Contents/section\d+\.xml$", n))
        for n in secs:
            root = ET.fromstring(z.read(n))
            for p in root.iter():
                if jose_extractor._lname(p) == "p":
                    txt = "".join(
                        (t.text or "")
                        for t in p.iter()
                        if jose_extractor._lname(t) == "t"
                    )
                    if txt.strip():
                        out.append(txt)
    return "\n".join(out)


def _docx_text(data):
    grids = jose_extractor.docx_grids(data)
    return jose_extractor.grids_text(grids)


def document_text(data, kind=None):
    """파일 바이트 -> 본문 텍스트. 지원하지 않는 형식(구버전 hwp 등)이면 None."""
    kind = kind or sniff_kind(data)
    if kind == "pdf":
        return _pdf_text(data)
    if kind == "hwpx":
        return _hwpx_text(data)
    if kind == "docx":
        return _docx_text(data)
    if kind == "hwp":  # 구버전 이진 한글(.hwp) — 암호/배포용 문서는 읽지 못하고 None
        from core import hwp_text

        try:
            return hwp_text.hwp_to_text(data)
        except hwp_text.HwpUnsupported:
            return None
    return None


def split_notices(text):
    """본문 -> [공고 텍스트, ...]. 머리글이 하나도 없으면 문서 전체를 한 덩어리로 돌려준다."""
    starts = []
    for m in NOTICE_HEAD_RE.finditer(text):
        line_end = text.find("\n", m.start())
        line = text[m.start(): line_end if line_end != -1 else len(text)]
        if TOC_LINE_RE.search(line):
            continue
        starts.append(m.start())
    if not starts:
        return [text] if text.strip() else []
    starts.append(len(text))
    return [text[a:b] for a, b in zip(starts, starts[1:])]


def notice_title(notice):
    """공고 첫머리에서 사람이 읽을 제목 한 줄(머리글 + 다음 줄들 일부)."""
    lines = [ln.strip() for ln in notice.splitlines() if ln.strip()]
    return " ".join(lines[:3])[:160]


def is_compensation(notice):
    """제목 부근에 보상 키워드가 있거나, 토지조서/물건조서/보상계획이 본문에 있으면 보상 관련으로 본다."""
    # 공백을 모두 없애고 비교한다(PDF/OCR 본문은 '토지 조서'처럼 글자 사이가 벌어지는 일이 많다)
    head = "".join(notice[:HEAD_WINDOW].split())
    if any("".join(k.split()) in head for k in COMP_KEYWORDS):
        return True
    whole = "".join(notice.split())
    return any(k in whole for k in ("토지조서", "물건조서", "보상계획", "협의보상"))


# ---- 읍면·리 목록 없이 동작하는 자체 주소 규칙 (Regions 규칙이 못 읽을 때의 대체 경로) ----
JIMOK_CHARS = "전답과목임잡대장학차주창도철제천구유양수공체원종사묘염광"
_SIDO = r"[가-힣]{2,6}(?:특별시|광역시|특별자치시|특별자치도|도)"
_SIGUN = r"[가-힣]{1,5}[시군구]"
PROSE_ADDR_RE = re.compile(
    rf"(?:(?P<sido>{_SIDO})\s*)?(?:(?P<sigun>{_SIGUN})\s*)?(?:(?P<eup>[가-힣]{{1,4}}[읍면])\s*)?"
    r"(?P<ri>[가-힣0-9]{1,6}[동리가])\s*(?P<jibun>산?\s?\d{1,5}(?:\s*-\s*\d{1,4})?)\s*번지"
)
TABLE_ROW_RE = re.compile(
    r"(?:(?P<eup>[가-힣]{1,4}[읍면])\s+)?(?P<ri>[가-힣0-9]{1,6}[동리])\s+(?P<jibun>산?\s?\d{1,5}(?:\s*-\s*\d{1,4})?)"
    rf"\s+(?P<jimok>[{JIMOK_CHARS}])(?=\s)"
    r"(?:\s+(?P<owner>[가-힣()·]{1,12}))?(?:\s+(?P<a1>\d[\d,]*(?:\.\d+)?))?(?:\s+(?P<a2>\d[\d,]*(?:\.\d+)?))?"
)
_NOT_RI = {"공동", "지동", "이동", "변동", "활동", "행동", "운동", "노동", "작동", "자동", "기동", "연동"}

# 소재지 열이 '면 | 리' 두 칸으로 나뉘고 값에 접미사가 없는 표('대강 당동 193-23 구거 607 412' = 대강면 당동리, 단양군보
# 공고 제2026-1284호 실측 2026-10-17). 이 행을 TABLE_ROW_RE 로 읽으면 면이 빠지고 '당동'이 동 이름으로 오인된다.
BARE_ROW_RE = re.compile(
    r"(?<![가-힣0-9])(?P<a>[가-힣]{1,4})\s+(?P<b>[가-힣]{1,5})\s+(?P<jibun>산?\s?\d{1,5}(?:\s*-\s*\d{1,4})?)"
    rf"\s+(?P<jimok>[{JIMOK_CHARS}])(?=\s)"
    r"(?:\s+(?P<a1>\d[\d,]*(?:\.\d+)?))?(?:\s+(?P<a2>\d[\d,]*(?:\.\d+)?))?"
)


def _bare_rows(text, notice_text):
    """'면 | 리' 열 표의 행 -> [(eup, ri, 정규식 매치)]. 면·리 접미사는 표 머리글(면/리 열 이름) 또는 같은 공고 본문에
    적힌 말('대강면', '당동리')로 확인될 때만 붙이고, 확인이 안 되면 그 행은 읽지 않는다."""
    out = []
    cue = jose_extractor.BARE_HEADER_RE.search(text)
    for m in BARE_ROW_RE.finditer(text):
        pair = jose_extractor.bare_myeon_ri(m.group("a"), m.group("b"), notice_text,
                                            bool(cue) and cue.start() < m.start())
        if pair:
            out.append((pair[0], pair[1], m))
    return out


def _clean_jibun(j):
    return re.sub(r"\s+", "", j).replace("−", "-")


def generic_rows(notice, default_sido="", default_sigun=""):
    """읍면·리 목록 없이 문장형('… 소야리 산 62번지')과 표 행형('적성면 소야리 산62 임 …')을 읽는다."""
    text = re.sub(r"\s+", " ", notice)
    rows, seen = [], set()

    def add(sido, sigun, eup, ri, jibun, jimok="", area="", remark=""):
        if ri in _NOT_RI:
            return
        j = _clean_jibun(jibun)
        if re.fullmatch(r"산?0+(-0+)?", j):
            return
        soj = " ".join(x for x in ((sido or default_sido), (sigun or default_sigun), eup, ri) if x)
        key = (soj, j)
        if key in seen:
            return
        seen.add(key)
        rows.append({"sojaeji": soj, "jibun_incl": j, "jimok": jimok, "area_incl": area, "remark": remark})

    for m in PROSE_ADDR_RE.finditer(text):
        tail = text[m.end():m.end() + 14]
        rem = "본문 번지 표기" + (" (외 N필지)" if re.match(r"\s*외\s*\d+\s*필지", tail) else "")
        add(m.group("sido"), m.group("sigun"), m.group("eup"), m.group("ri"), m.group("jibun"), remark=rem)
    # '면 | 리' 두 칸 표(접미사 없음)를 먼저 읽고, 같은 자리를 TABLE_ROW_RE 가 다시 읽지 않게 구간을 기억한다
    bare = _bare_rows(text, text)
    spans = [(m.start(), m.end()) for _, _, m in bare]
    for n, (eup, ri, m) in enumerate(bare):
        nxt = bare[n + 1][2].start() if n + 1 < len(bare) else m.end() + 80
        seg = text[m.end():nxt]  # 면적 뒤 ~ 다음 행 앞: 소유자 칸 글자
        if re.match(r"\s*[국공]\s*\(", seg):
            continue  # 면적 바로 뒤 소유자 칸이 '국(기획재정부)' 처럼 국·공유 표기면 제외(사용자 지시). 사유지는 이 칸 앞에 주소 칸이 와서 걸리지 않는다
        areas = [x for x in (m.group("a1"), m.group("a2")) if x]
        add(None, None, eup, ri, m.group("jibun"), jimok=m.group("jimok"),
            area=(areas[-1] if areas else ""), remark="표 행(면·리 열)")
    for m in TABLE_ROW_RE.finditer(text):
        if any(a <= m.start() < b for a, b in spans):
            continue
        if not m.group("eup") and re.search(r"(?<![\d-])\d{1,3}\s+[가-힣]{1,4}\s$", text[max(0, m.start() - 12):m.start()]):
            continue  # '연번 단어 리 지번' = 면 열 값이 접미사 없이 앞에 붙은 행인데 면·리를 문서에서 확인 못 했다 -> 리만 떼어 쓰면 틀린 주소가 되므로 읽지 않는다
        if jose_extractor.is_public_owner(m.group("owner") or ""):
            continue  # 소유자가 국가·지자체·공공기관인 필지는 제외(사용자 지시)
        areas = [x for x in (m.group("a1"), m.group("a2")) if x]
        add(None, None, m.group("eup"), m.group("ri"), m.group("jibun"), jimok=m.group("jimok"),
            area=(areas[-1] if areas else ""), remark="표 행")
    return rows


def extract_rows(notice, regions, site_name="", source_file="", title="", collected_at="",
                 default_sido="", default_sigun=""):
    """보상 관련 공고 본문 -> jose_row 형식 dict 리스트(소재지·지번 등).
    1) 지자체 Regions 규칙(읍면·리 목록이 있을 때 정확) 2) 없거나 결과가 0건이면 자체 규칙(generic_rows)."""
    project = jose_extractor.project_name_from_title(title or notice_title(notice))
    rows = []
    if regions is not None and not callable(regions):
        rows = regions.rows_from_text(notice)
        if rows:
            for r in rows:
                r["project_name"] = project
                r["source_file"] = source_file
            rows = jose_extractor.finalize_rows(rows, regions)
            rows = jose_extractor.dedupe_parcels(rows)
    if not rows:
        rows = generic_rows(notice, default_sido, default_sigun)
        for r in rows:
            r["project_name"] = project
    rows = jose_extractor.apply_declared_locations(notice, rows)  # 위쪽에 '아산시 음봉면 동암리, 덕지리 일원'으로 적고 표에는 리만 적는 공고
    return [
        {
            "site_name": site_name,
            "sojaeji": r.get("sojaeji", ""),
            "jibun": r.get("jibun_incl", ""),
            "jimok": r.get("jimok", ""),
            "area_incl": r.get("area_incl", ""),
            "project_name": r.get("project_name", ""),
            "remark": r.get("remark", ""),
            "source_file": source_file,
            "collected_at": collected_at,
        }
        for r in rows
    ]
