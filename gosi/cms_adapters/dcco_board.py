"""
dcco_board.py — "web/board/list.do?mId=" 게시판(대전도시공사 CMS,
board/view.do / board/download.do 계열) 어댑터.

대전도시공사에서 실측 확인했다(2026-09-26). 목록/상세 모두 평범한 GET + 정적 <a href>
(JS 없음) — 세션/TLS 이슈 없음. 전용 보상 게시판이 아니라 일반 게시판(공지사항류)이라
다른 지자체와 같이 키워드 필터로 걸러진다.

목록: GET web/board/list.do?mId=<mId>&page=<P>, <td class="subject"><a href="view.do?mId=<mId>&brdIdx=<id>">.

상세: GET web/board/view.do?mId=<mId>&brdIdx=<id>. 첨부는 평범한
<a href="download.do?mId=<mId>&brdIdx=<id>&fidx=<n>&itId=file" class="fn_filedown">파일명.ext</a>.

City.boards 항목 형식: {"name": "공지사항", "m_id": "113"}
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

_DATE_CELL_RE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")
_NOTICE_NO_RE = re.compile(r"(공고|고시)\s*제\s*\d{4}\s*[-–]\s*\d+\s*호")


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    list_url = base_url.replace("view.do", "list.do")
    resp = session.get(list_url, params={"mId": board["m_id"], "page": page_index}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for tr in soup.select("table.listTypeA tbody tr"):
        subject_td = tr.find("td", class_="subject")
        if subject_td is None:
            continue
        a_tag = subject_td.find("a")
        if a_tag is None:
            continue
        title = a_tag.get_text(strip=True)
        detail_url = urljoin(resp.url, a_tag.get("href", ""))

        tds = tr.find_all("td")
        texts = [td.get_text(strip=True) for td in tds]
        notice_no = next((t for t in texts if _NOTICE_NO_RE.search(t)), "")
        date_str = next((t for t in texts if _DATE_CELL_RE.match(t)), "")
        post_date = None
        if date_str:
            try:
                post_date = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
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


def fetch_attachments(session, detail_url):
    """상세 페이지의 첨부파일 [{"name","url","ext"}, ...] (다운로드는 하지 않음)."""
    resp = session.get(detail_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    attachments = []
    for a in soup.select("a.fn_filedown"):
        name = a.get_text(strip=True)
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": urljoin(resp.url, a.get("href", "")), "ext": ext})
    return attachments
