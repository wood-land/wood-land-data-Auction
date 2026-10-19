"""
zboard_govstd.py — "zboard/list.do?lmCode=" 게시판(zboard/read.do / printFileDown.do 계열) 어댑터.

충북개발공사에서 실측 확인했다(2026-09-26). 목록/상세 모두 평범한 GET + 정적 <a href>
(JS 없음) — 세션/TLS 이슈 없음.

목록: GET zboard/list.do?lmCode=<code>&pageIndex=<P>, <td class="subject"><p class="stitle">
<a href="/zboard/read.do?...&pd_pkid=<id>">제목</a>. 날짜 칸은 <td class="date">지만
지자체마다 칸 구성이 다를 수 있어(law.md 3-2) 위치가 아니라 날짜 형식 정규식으로 찾는다.

상세: GET zboard/read.do?lmCode=<code>&pd_pkid=<id>. 첨부는
<a href="/zboard/printFileDown.do?atchFileId=...&fileSn=...">1 : 파일명.ext [12345 byte]</a>
형태라 링크 텍스트에서 "N : " 접두사와 "[size byte]" 접미사를 제거해야 실제 파일명이 나온다.

City.boards 항목 형식: {"name": "보상공고", "lm_code": "BBSMSTR_000000000016"}
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
_ATTACH_NAME_RE = re.compile(r"^\s*\d+\s*:\s*(.+?)\s*\[[\d,]+\s*byte\]\s*$", re.IGNORECASE)


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    list_url = base_url.replace("read.do", "list.do")
    resp = session.get(
        list_url,
        params={"lmCode": board["lm_code"], "pageIndex": page_index},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for tr in soup.select("table.board-list-table tbody tr, table.board-list-table tr"):
        subject_td = tr.find("td", class_="subject")
        if subject_td is None:
            continue
        a_tag = subject_td.find("a", href=re.compile(r"pd_pkid="))
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
    for a in soup.select("a[href*='printFileDown.do']"):
        raw = re.sub(r"\s+", " ", a.get_text(strip=True)).strip()
        m = _ATTACH_NAME_RE.match(raw)
        name = m.group(1) if m else raw
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": urljoin(resp.url, a.get("href", "")), "ext": ext})
    return attachments
