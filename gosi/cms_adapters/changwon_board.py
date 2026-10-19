"""
changwon_board.py — "cwportal/.../*.web?amode=view&not_ancmt_mgt_no=" 게시판
(창원시) 어댑터.

창원시에서 실측 확인했다(2026-09-26). 같은 ".web" 확장자를 쓰는 haman_web_board.py
계열(함안군 등, <ul class="lst1">)과는 완전히 다른 마크업(<table class="t3">)이라
그 어댑터를 재사용할 수 없다(law.md 3-2).

목록: GET .../10439.web?cpage=<P>, <table class="t3">
<a class="a1" href="?amode=view&not_ancmt_mgt_no=<id>&section=gosi">제목</a>.
고시공고번호 칸은 같은 행의 다른 <td>에 있다(줄바꿈 포함 텍스트).

상세: 목록 href를 그대로 GET(상대경로, 같은 페이지에 쿼리만 붙는다). 첨부는
자체 프록시 다운로더 <a href="/cwportal/DownloadEx.do?url=<encoded eminwon
FileDown.jsp URL>&name=<encoded 파일명>">파일명</a> — 링크 텍스트가 그대로
파일명이고 href 자체가 이미 완성된 다운로드 URL이라 그대로 쓴다.

City.boards 항목 형식: {"name": "고시공고"}
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
    resp = session.get(base_url, params={"cpage": page_index}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    rows = []
    for a_tag in soup.find_all("a", class_="a1", href=re.compile(r"not_ancmt_mgt_no=")):
        tr = a_tag.find_parent("tr")
        if tr is None:
            continue
        title = re.sub(r"\s+", " ", a_tag.get_text(strip=True)).strip()
        detail_url = urljoin(resp.url, a_tag.get("href", ""))

        tds = tr.find_all("td")
        texts = [re.sub(r"\s+", " ", td.get_text(" ", strip=True)).strip() for td in tds]
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
    for a in soup.select("div.attach1 a[href*='DownloadEx.do']"):
        name = re.sub(r"\s+", " ", a.get_text(strip=True)).strip()
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": urljoin(resp.url, a.get("href", "")), "ext": ext})
    return attachments
