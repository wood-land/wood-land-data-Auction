"""
nbgosi_board.py — "nbgosi" 게시판(부산광역시청, nbgosi/view / nbgosi/download) 어댑터.

부산광역시청에서 실측 확인했다(2026-09-26). 목록/상세 모두 평범한 GET + 정적 <a href>
(JS 없음) — 세션/TLS 이슈 없음. 날짜는 "YYYY.MM.DD"(점 구분).

목록: GET nbgosi?curPage=<P>, <td class="title"><a href="/nbgosi/view?sno=<id>&gosiGbn=<gbn>&curPage=<P>">.

상세: 목록의 href를 그대로 GET. 첨부는
<a href="/nbgosi/download?fileId=<id>&seq=<n>" title="파일명.ext">파일명.ext (용량 : 66 KB)</a>
— title 속성에 크기 표기 없는 순수 파일명이 있어 그걸 쓴다.

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

_DATE_CELL_RE = re.compile(r"^\d{4}\.\d{1,2}\.\d{1,2}$")
_NOTICE_NO_RE = re.compile(r"(공고|고시)\s*제\s*\d{4}\s*[-–]\s*\d+\s*호")


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(base_url, params={"curPage": page_index}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for tr in soup.select("table.boardList tbody tr"):
        subject_td = tr.find("td", class_="title")
        a_tag = subject_td.find("a") if subject_td else None
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


def fetch_attachments(session, detail_url):
    """상세 페이지의 첨부파일 [{"name","url","ext"}, ...] (다운로드는 하지 않음)."""
    resp = session.get(detail_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    attachments = []
    seen_urls = set()
    # 같은 href가 파일명 링크 + "다운로드" 버튼(title="새창")으로 두 번 나온다(실측 확인)
    # — title에 확장자가 있는(진짜 파일명) 것만, href당 한 번만 쓴다.
    for a in soup.select("a[href*='/nbgosi/download']"):
        title = a.get("title", "").strip()
        if "." not in title:
            continue
        url = urljoin(resp.url, a.get("href", ""))
        if url in seen_urls:
            continue
        seen_urls.add(url)
        ext = title.rsplit(".", 1)[-1].lower()
        attachments.append({"name": title, "url": url, "ext": ext})
    return attachments
