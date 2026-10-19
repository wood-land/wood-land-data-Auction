"""
krds_board.py — "board/list.do?boardId=" 게시판(정부 KRDS 디자인시스템 계열,
board/view.do / board/download.do) 어댑터.

부산도시공사에서 실측 확인했다(2026-09-26). 목록/상세 모두 평범한 GET + 정적 <a href>
(JS 없음) — 세션/TLS 이슈 없음. 이 사이트는 "보상계획" 전용 게시판이 따로 있어
(boardId=BBS_0000005) 대부분 이미 보상 관련이지만, 그래도 키워드 필터는 그대로 거친다.

목록: GET board/list.do?boardId=<id>&menuCd=<menuCd>&startPage=<P>, 제목 칸은
<td class="tdTitle"><a href="/board/view.do?...&dataSid=<id>">. 날짜는 "YYYY.MM.DD"
형식(점 구분 — 다른 지자체의 "YYYY-MM-DD"와 다르다, law.md 3-2).

상세: 목록의 href를 그대로 GET. 첨부는 <span class="fileName">파일명</span> +
형제 <a href="/board/download.do?...&fileSid=...">다운로드</a> — 파일명은 fileName
span에서 가져온다(다운로드 링크 텍스트 자체엔 파일명이 없음).

City.boards 항목 형식: {"name": "보상계획", "board_id": "BBS_0000005", "menu_cd": "DOM_..."}
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
    list_url = base_url.replace("view.do", "list.do")
    resp = session.get(
        list_url,
        params={"boardId": board["board_id"], "menuCd": board["menu_cd"], "startPage": page_index},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for tr in soup.select("table.table tbody tr"):
        subject_td = tr.find("td", class_="tdTitle")
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
    for a in soup.select("a[href*='/board/download.do']"):
        li = a.find_parent("li")
        name_el = li.select_one(".fileName") if li else None
        name = name_el.get_text(strip=True) if name_el else a.get_text(strip=True)
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": urljoin(resp.url, a.get("href", "")), "ext": ext})
    return attachments
