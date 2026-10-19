"""
molit_bord0201.py — 국토교통부 산하기관 게시판(USR/BORD0201/.../LST.jsp) 공통 어댑터.

원주·대전·부산지방국토관리청, 서울·부산지방항공청에서 실측 확인했다(2026-09-25).
국토교통부(molit.go.kr) 산하 여러 기관이 같은 게시판 시스템(LCMS)을 쓴다 — 같은
table.list_area 구조에 사이트별 URL 세그먼트(wrocm/drocm/irocm/brocm/sroa/broa 등)와
게시판 id(wcmo0402, dcmo0402, icmo0402, pcmo0401, sraac_0401, phc0401 등)만 다르다.

spreadsheet의 원래 URL은 "BRD.jsp"(진입 페이지, 프레임)였는데 실제 목록/페이지네이션은
"LST.jsp?id=<게시판id>"이 처리한다 — BRD.jsp를 한 번 읽어 그 안의 "LST.jsp?id=..."
링크에서 게시판 id를 추출한 뒤, 이후로는 LST.jsp를 직접 쓴다(City.base_url을 처음부터
LST.jsp?id=... 형태로 등록해 둔다).

열 구성이 사이트마다 다르다(구분 칸이 있는 곳/없는 곳, 5~6칸) — 그래서 class로
판별한다: 제목 칸은 어디서나 td.txt-l, 날짜 칸은 내용 패턴("YYYY.MM.DD" 또는
"YYYY-MM-DD")으로 찾는다(부산지방국토관리청·서울지방항공청은 대시 형식,
나머지는 점 형식). 공고/고시 구분("공고"/"고시"/"일반" 등)이 있으면 제목 칸
바로 앞 칸에서 정보용으로 가져온다(공고번호 형식이 없어 std_ezweb류의 "제YYYY-N호"
패턴은 여기선 안 씀).

첨부파일은 <a href="/LCMS/DWN.jsp?fold=...&fileName=..." title="진짜파일명.ext">
형태의 이미 완성된 GET 링크다 — JS 파싱 불필요.
"""

import datetime as dt
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

_DATE_FORMATS = ["%Y.%m.%d", "%Y-%m-%d"]
_DATE_CELL_RE = re.compile(r"^\d{4}[.\-]\d{1,2}[.\-]\d{1,2}$")


def _parse_post_date(date_str):
    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]
    base_url은 (게시판 id를 포함한) LST.jsp 전체 URL이다."""
    resp = session.get(base_url, params={"lcmspage": page_index}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.select_one("table.list_area")
    if table is None:
        return []
    rows = []
    for tr in table.find_all("tr"):
        subject_td = tr.select_one("td.txt-l")
        if subject_td is None:
            continue
        a = subject_td.find("a")
        if a is None or not a.get("href"):
            continue
        detail_url = urljoin(resp.url, a.get("href"))
        title = re.sub(r"\s+", " ", a.get_text(strip=True)).strip()
        tds = tr.find_all("td")
        try:
            subject_idx = tds.index(subject_td)
        except ValueError:
            subject_idx = 0
        notice_no = tds[subject_idx - 1].get_text(strip=True) if subject_idx > 0 else ""
        date_str = ""
        for td in tds:
            text = td.get_text(strip=True)
            if _DATE_CELL_RE.match(text):
                date_str = text
                break
        post_date = _parse_post_date(date_str) if date_str else None
        rows.append(
            {
                "board": board["name"],
                "notice_no": notice_no,
                "title": title,
                "date": post_date,
                "date_str": date_str,
                "detail_url": detail_url,
            }
        )
    return rows


def fetch_attachments(session, detail_url):
    """상세 페이지의 첨부파일 [{"name", "url", "ext"}, ...] (다운로드는 하지 않음)."""
    resp = session.get(detail_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    attachments = []
    for a in soup.select("a[href*='DWN.jsp']"):
        url = urljoin(resp.url, a.get("href", ""))
        name = a.get("title") or a.get_text(strip=True)
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": url, "ext": ext})
    return attachments
