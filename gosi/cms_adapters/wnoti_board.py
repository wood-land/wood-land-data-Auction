"""
wnoti_board.py — "wnoti_list.php?strBoardID=" 게시판(wnoti_view.php / fileDown3.php 계열) 어댑터.

강원개발공사에서 실측 확인했다(2026-09-26). 목록/상세 모두 일반 GET + 평범한 <a href>
링크뿐이라(JS 없음) 다른 사이트들보다 단순하다. TLS/세션 문제 없음(plain requests로
바로 접속됨).

목록: GET wnoti_list.php?strBoardID=<ID>&page=<P>&pageSize=10, <table class="board-common">
안의 각 행이 <td>번호</td><td><a href="wnoti_view.php?intSeq=...">제목</a></td><td>날짜</td>.

첨부: 상세 페이지의 <a href="/lib/fileDown3.php?filename=...&orgfilename=<실제파일명>&intIdx=...">
— orgfilename 쿼리 파라미터에 실제 파일명이 그대로 들어있어 별도 추출 로직이 필요 없다.

City.boards 항목 형식: {"name": "보상공고", "board_id": "REWARDNOTI"}
"""

import datetime as dt
import re
from urllib.parse import parse_qs, urljoin, urlsplit

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
    list_url = base_url.replace("wnoti_view.php", "wnoti_list.php")
    resp = session.get(
        list_url,
        params={"strBoardID": board["board_id"], "page": page_index, "pageSize": page_unit},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.select_one("table.board-common")
    if table is None:
        return []
    rows = []
    for tr in table.select("tbody tr"):
        a_tag = tr.find("a", href=re.compile(r"wnoti_view\.php"))
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
    for a in soup.select("a[href*='fileDown3.php']"):
        href = a.get("href", "")
        qs = parse_qs(urlsplit(href).query)
        name = qs.get("orgfilename", [a.get_text(strip=True)])[0]
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": urljoin(resp.url, href), "ext": ext})
    return attachments
