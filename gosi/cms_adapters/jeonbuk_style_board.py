"""
jeonbuk_style_board.py — "board/list.<city>?boardId=&menuCd=" 게시판(이지사이트 계열
board/view.<city> / board/download.<city>) 어댑터.

전북특별자치도청에서 실측 확인했다(2026-09-26). 광주광역시도시공사(board_es.py)·
부산도시공사(krds_board.py)와 URL 모양은 비슷하지만 실제 마크업은 또 다르다
(table.bbs_table, td[data-cell-header], 날짜가 "YYYY-MM-DD" 점이 아니라 대시 —
law.md 3-2, 겉모양이 비슷하다고 어댑터를 공유하지 않는다) — 그래서 별도 어댑터로 뒀다.

목록: GET board/list.<city>?boardId=<id>&menuCd=<menuCd>&startPage=<P>,
<td class="title"><a href="/board/view.<city>?...&dataSid=<id>">.

상세: 목록의 href를 그대로 GET. 첨부는
<a href="/board/download.<city>?...&fileSid=<n>" title="파일명.ext" class="ico_file">다운로드</a>
— title 속성에 순수 파일명이 있어 그걸 쓴다(광주광역시도시공사와 달리 링크 텍스트
자체는 "다운로드"라는 라벨뿐).

City.boards 항목 형식: {"name": "고시공고", "board_id": "BBS_0000129", "menu_cd": "DOM_...", "path": "jeonbuk"}
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

_DATE_CELL_RE = re.compile(r"^\d{4}[.\-]\d{1,2}[.\-]\d{1,2}$")
_NOTICE_NO_RE = re.compile(r"(공고|고시)\s*제\s*\d{4}\s*[-–]\s*\d+\s*호")


def _parse_date(date_str):
    for fmt in ("%Y-%m-%d", "%Y.%m.%d"):
        try:
            return dt.datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    list_url = f"{base_url}/board/list.{board['path']}"
    resp = session.get(
        list_url,
        params={"boardId": board["board_id"], "menuCd": board["menu_cd"], "startPage": page_index},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for tr in soup.select("table tbody tr"):
        # 제목 칸 class가 지자체마다 "title"(전북특별자치도·고성군) 또는
        # "subject"(금정구)로 갈린다(실측 확인, 2026-09-26).
        subject_td = tr.find("td", class_="title") or tr.find("td", class_="subject")
        a_tag = subject_td.find("a") if subject_td else None
        if a_tag is None:
            continue
        title = a_tag.get_text(strip=True)
        detail_url = urljoin(resp.url, a_tag.get("href", ""))

        tds = tr.find_all("td")
        texts = [td.get_text(strip=True) for td in tds]
        notice_no = next((t for t in texts if _NOTICE_NO_RE.search(t)), "")
        date_str = next((t for t in texts if _DATE_CELL_RE.match(t)), "")
        post_date = _parse_date(date_str) if date_str else None

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
    for a in soup.select("a.ico_file[href*='/board/download.']"):
        name = a.get("title", "").strip() or a.get_text(strip=True)
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": urljoin(resp.url, a.get("href", "")), "ext": ext})
    return attachments
