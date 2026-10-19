"""
mnu_uid_board.py — "page.do?mnu_uid=" 게시판(울릉군·영주시 등, saeol/notice 계열) 어댑터.

울릉군·영주시에서 실측 확인했다(2026-09-26). JS 없이 평범한 GET + 정적 <a href>
(쿼리스트링 형태의 링크). 같은 "page.do?mnu_uid=" URL이라도 경산시는 완전히 다른
마크업(다른 쿼리 파라미터 세트)이라 이 어댑터를 쓰지 않는다(law.md 3-2).

목록: GET page.do?mnu_uid=<mnu_uid>&pageNo=<P>, <table class="tbl_board">
<a href="?...&mnu_uid=<>&not_ancmt_mgt_no=<id>&pageNo=1&cmd=2">.

상세: 목록의 href를 그대로 GET(상대 경로라 base_url 기준으로 풀린다). 첨부는 평범한
<a href="/programs/board/saeol/notice/download.do?file_seq=<n>&not_ancmt_mgt_no=<id>"
title="파일명.ext 파일 다운로드">파일명.ext</a> — 링크 텍스트가 그대로 파일명이다.

City.boards 항목 형식: {"name": "고시공고", "mnu_uid": "571"}
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
    resp = session.get(
        base_url, params={"mnu_uid": board["mnu_uid"], "pageNo": page_index}, headers=HEADERS, timeout=15
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    # 테이블 class가 지자체마다 다르다(울릉군 tbl_board, 영주시 tbl_list —
    # 실측 확인, 2026-09-26) — not_ancmt_mgt_no= 링크가 있는 테이블을 내용으로 찾는다.
    table = None
    for t in soup.find_all("table"):
        if t.find("a", href=re.compile(r"not_ancmt_mgt_no=")) is not None:
            table = t
            break
    if table is None:
        return []
    rows = []
    for tr in table.select("tbody tr"):
        a_tag = tr.find("a", href=re.compile(r"not_ancmt_mgt_no="))
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
    for a in soup.select("a[href*='/saeol/notice/download.do']"):
        name = a.get_text(strip=True)
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": urljoin(resp.url, a.get("href", "")), "ext": ext})
    return attachments
