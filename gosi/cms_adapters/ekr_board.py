"""
ekr_board.py — 한국농어촌공사(ekr.or.kr) "보상계획 공고"(planweb/board/list.krc) 어댑터.

한국농어촌공사에서 실측 확인했다(2026-09-28). 목록/상세/첨부 모두 평범한 GET + 정적 <a href>
(JS 없음)이다.

목록: GET list.krc?page=<P>&boardUid=&contentUid=&categoryUid2= (base_url에 세 uid가 이미
쿼리스트링으로 들어 있고, 어댑터는 page만 덧붙인다). 행은 table tbody tr, 칸 class는
num/title/name/file/date/views, 등록일은 "YYYY-MM-DD". 제목 링크는 ./view.krc?dataUid=...
(상대경로).

상세: 목록의 href를 그대로 GET. 첨부는 <a href="./download.krc?fileUid=..&boardUid=..">파일명</a>
(링크 텍스트가 파일명이다).

City.boards 항목 형식: {"name": "보상계획공고"}
"""

import datetime as dt
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


def _parse_date(text):
    try:
        return dt.datetime.strptime(text.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _with_page(url, page_index):
    p = urlsplit(url)
    q = dict(parse_qsl(p.query, keep_blank_values=True))
    q["page"] = str(page_index)
    return urlunsplit((p.scheme, p.netloc, p.path, urlencode(q), ""))


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(_with_page(base_url, page_index), headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for tr in soup.select("table tbody tr"):
        a_tag = tr.select_one("td.title a")
        date_td = tr.select_one("td.date")
        if a_tag is None or date_td is None:
            continue
        date_str = date_td.get_text(strip=True)
        rows.append(
            {
                "board": board["name"],
                "notice_no": "",
                "title": a_tag.get_text(" ", strip=True),
                "date": _parse_date(date_str),
                "date_str": date_str,
                "detail_url": urljoin(resp.url, a_tag.get("href", "")),
            }
        )
    return rows


def fetch_attachments(session, detail_url):
    """상세 페이지의 첨부파일 [{"name","url","ext"}, ...] (다운로드는 하지 않음)."""
    resp = session.get(detail_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    attachments = []
    for a in soup.select("a[href*='download.krc']"):
        name = a.get_text(strip=True)
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": urljoin(resp.url, a.get("href", "")), "ext": ext})
    return attachments
