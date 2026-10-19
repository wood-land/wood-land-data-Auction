"""
uljin_board.py — 울진군청 게시판(/index.uljin?menuCd=, ul.bbs_list 스킨) 어댑터.

울진군에서 실측 확인했다(2026-09-28). <table>이 아니라 <ul class="bbs_list">
<li><a href="/index.uljin?menuCd=<menuCd>&type=view&ancmtMgtNo=<id>"><strong>제목</strong>
<span>요약</span><em class="info">공고번호 : <..><span>|</span>부서 : <..><span>|</span>
게재일 : YYYY-MM-DD</em></a></li> 레이아웃이다. 페이지네이션은 onclick="goPage('<N>')"
뿐인데, 실제 구현이 히든필드 startPage를 채워 같은 페이지로 GET 제출하는 것이라
"startPage" 쿼리파라미터로 대신한다.

첨부파일은 상세 페이지의 <a href="https://eminwon.울진군.../FileDown.jsp?...">이미
완성된 GET 링크라 eminwon_list.py의 fetch_attachments를 그대로 재사용한다(law.md 3-2).

City.boards 항목 형식: {"name": "고시공고", "menu_cd": "DOM_000000103002007001"}
"""

import datetime as dt
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from cms_adapters.eminwon_list import fetch_attachments  # noqa: F401

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

_NOTICE_NO_RE = re.compile(r"(공고|고시)\s*제\s*\d{4}\s*[-–]\s*\d+\s*호")
_DATE_RE = re.compile(r"게재일\s*:\s*(\d{4}-\d{1,2}-\d{1,2})")


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(
        base_url, params={"menuCd": board["menu_cd"], "startPage": page_index}, headers=HEADERS, timeout=15
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    ul = soup.select_one("ul.bbs_list")
    if ul is None:
        return []

    rows = []
    for li in ul.select("li"):
        a = li.find("a", href=re.compile(r"ancmtMgtNo="))
        if a is None:
            continue
        detail_url = urljoin(resp.url, a.get("href", ""))
        title_el = a.find("strong")
        title = re.sub(r"\s+", " ", title_el.get_text(strip=True)).strip() if title_el else ""

        info_el = a.find("em", class_="info")
        info_text = info_el.get_text(" ", strip=True) if info_el else ""
        notice_no_m = _NOTICE_NO_RE.search(info_text)
        notice_no = notice_no_m.group(0) if notice_no_m else ""
        date_m = _DATE_RE.search(info_text)
        date_str = date_m.group(1) if date_m else ""
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
