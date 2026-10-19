"""
geoje_board.py — "index.geoje?menuCd=" 게시판(거제시, eminwon/lga/homepage 계열) 어댑터.

거제시에서 실측 확인했다(2026-09-26). 목록/상세 모두 평범한 GET + 정적 <a href>
(JS 없음, 서버 렌더링 <table>). 첨부는 밀양시와 같은 GET 방식이지만 다운로드
엔드포인트 경로가 "/emwp/jsp/ofr/FileDown.jsp"가 아니라
"/emwp/jsp/lga/homepage/FileDown.jsp"로 달라(실측 확인) eminwon_list.py를 그대로
쓰지 못하고 별도 어댑터로 뒀다(law.md 3-2 — 겉보기 패턴이 비슷해도 실제 경로를
확인 없이 가정하지 않는다).

목록: GET index.geoje?menuCd=<menuCd>&startPage=<P>, <td class="tal title">
<a href="/index.geoje?menuCd=<상세menuCd>&m=D&idx=<id>&...">.

상세: 목록의 href를 그대로 GET. 첨부는
<a href="javascript:goDownLoad('<파일명>','<시스템파일명>','<경로>')">
— 값이 암호화되지 않은 평문이라 그대로 GET
https://eminwon.geoje.go.kr/emwp/jsp/lga/homepage/FileDown.jsp?user_file_nm=...
&sys_file_nm=...&file_path=... 로 재현된다.

City.boards 항목 형식: {"name": "고시공고", "menu_cd": "DOM_000008902001002000"}
"""

import datetime as dt
import re
from urllib.parse import quote, urljoin, urlsplit

from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

_DATE_CELL_RE = re.compile(r"^\d{4}\.\d{1,2}\.\d{1,2}$")
_NOTICE_NO_RE = re.compile(r"(공고|고시)\s*제\s*\d{4}\s*[-–]\s*\d+\s*호")
_GO_DOWNLOAD_RE = re.compile(r"goDownLoad\(\s*'(.*)'\s*,\s*'(.*)'\s*,\s*'(.*)'\s*\)")


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(
        base_url, params={"menuCd": board["menu_cd"], "startPage": page_index}, headers=HEADERS, timeout=15
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for tr in soup.select("table tbody tr"):
        subject_td = tr.find("td", class_="title")
        a_tag = subject_td.find("a") if subject_td else None
        if a_tag is None:
            continue
        title = re.sub(r"\s+", " ", a_tag.get_text(strip=True)).strip()
        detail_url = urljoin(resp.url, a_tag.get("href", ""))

        tds = tr.find_all("td")
        texts = [re.sub(r"\s+", " ", td.get_text(strip=True)).strip() for td in tds]
        notice_no = next((t for t in texts if _NOTICE_NO_RE.search(t)), "")
        date_str = next((t for t in texts if _DATE_CELL_RE.match(t)), "")
        post_date = None
        if date_str:
            try:
                post_date = dt.datetime.strptime(date_str, "%Y.%m.%d").date()
            except ValueError:
                pass

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


def _eminwon_host(url):
    netloc = urlsplit(url).netloc
    if netloc.startswith("www."):
        netloc = netloc[len("www."):]
    return "eminwon." + netloc


def fetch_attachments(session, detail_url):
    """상세 페이지의 첨부파일 [{"name","url","ext"}, ...] (다운로드는 하지 않음)."""
    resp = session.get(detail_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    host = _eminwon_host(resp.url)
    attachments = []
    for a in soup.find_all("a", href=lambda v: bool(v) and "goDownLoad" in v):
        m = _GO_DOWNLOAD_RE.search(a.get("href", ""))
        if m is None:
            continue
        user_name, sys_name, file_path = m.groups()
        ext = user_name.rsplit(".", 1)[-1].lower() if "." in user_name else ""
        url = (
            f"https://{host}/emwp/jsp/lga/homepage/FileDown.jsp"
            f"?user_file_nm={quote(user_name)}&sys_file_nm={quote(sys_name)}&file_path={quote(file_path)}"
        )
        attachments.append({"name": user_name, "url": url, "ext": ext})
    return attachments
