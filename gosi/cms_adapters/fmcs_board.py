"""
fmcs_board.py — "/fmcs/<번호>?action=..." 게시판(부천도시공사 CMS) 어댑터.

부천도시공사에서 실측 확인했다(2026-09-26). 목록/상세 모두 평범한 GET + 정적 <a href>
(JS 없음) — 세션/TLS 이슈 없음. 고시공고 전용 게시판이 아니라 일반 공지사항 게시판이라
(spreadsheet가 가리킨 URL이 fmcs/156 공지사항판), 다른 지자체와 마찬가지로 키워드
필터로 보상 관련만 걸러진다.

목록: GET <base_url>?page=<P>, 제목 칸은 <a href="?action=read&action-value=<id>">.

상세: GET <base_url>?action=read&action-value=<id>. 첨부는 각 <li> 안에
<strong>파일명.ext</strong> + <a class="action_download" href="/File/Download/<hash>">
— 파일명은 형제 <strong> 태그에서 가져온다(다운로드 링크 자체엔 파일명이 없음).

City.boards 항목 형식: {"name": "공지사항"}
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
    resp = session.get(base_url, params={"page": page_index}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if table is None:
        return []
    rows = []
    for tr in table.select("tbody tr"):
        a_tag = tr.find("a", href=re.compile(r"action=read"))
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
    for a in soup.select("a[href*='/File/Download/']"):
        li = a.find_parent("li")
        name_el = li.find("strong") if li else None
        name = name_el.get_text(strip=True) if name_el else a.get_text(strip=True)
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": urljoin(resp.url, a.get("href", "")), "ext": ext})
    return attachments
