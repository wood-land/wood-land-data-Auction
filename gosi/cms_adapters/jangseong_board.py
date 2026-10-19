"""
jangseong_board.py — "home/www/news/jangseong/announcement" 게시판(장성군) 어댑터.

장성군에서 실측 확인했다(2026-09-26). 목록은 이 사이트 전용 마크업(plain href,
/announcement/show/<id>)이라 eminwon_list.py와 다르지만, 첨부 다운로드는 보령시와
똑같은 POST 방식(<form name="nnn">이 가리키는 FileDownNew.jsp, javascript:goDownLoad(...)
암호화 토큰이라 링크 텍스트를 파일명으로 씀)이라 그 로직을 그대로 가져다 쓴다
(law.md 3-2 — 목록 마크업까지 같다고 가정하지 않고, 실제로 같다고 확인된 첨부
다운로드 부분만 재사용한다).

목록: GET home/www/news/jangseong/announcement?page=<P>,
<table id="board_list_table"><a href="/home/www/news/jangseong/announcement/show/<id>?page=1">.

City.boards 항목 형식: {"name": "고시공고"}
"""

import datetime as dt
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from cms_adapters.eminwon_list import download_attachment, fetch_attachments  # noqa: F401

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
    resp = session.get(base_url, params={"page": page_index}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", id="board_list_table")
    if table is None:
        return []
    rows = []
    for tr in table.select("tbody tr"):
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue
        a_tag = None
        for td in tds:
            a_tag = td.find("a", href=re.compile(r"/show/\d+"))
            if a_tag is not None:
                break
        if a_tag is None:
            continue
        title = a_tag.get_text(strip=True)
        detail_url = urljoin(resp.url, a_tag.get("href", ""))

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
