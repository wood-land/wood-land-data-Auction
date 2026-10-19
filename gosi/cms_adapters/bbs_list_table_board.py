"""
bbs_list_table_board.py — "board/list.<지자체별칭>?boardId=...&menuCd=..." 게시판
(table.bbs_list_t 스킨) 어댑터.

부안군·김제시에서 실측 확인했다(2026-09-28). URL 모양은 bbs_list_skin(고창군)·
uiryeong_board(의령군)와 같은 계열이지만 마크업은 또 다르다(law.md 3-2 — URL
모양만으로 같은 벤더라고 가정하지 않는다): <table class="bbs_list_t"><tbody><tr>
<td class="title"><a href="board/view.<별칭>?...&dataSid=<id>" title="제목">제목</a></td>.

날짜 형식이 지자체마다 갈린다 — 부안군은 "YY.MM.DD"(2자리 연도, 점 구분), 김제시는
"YYYY-MM-DD"(4자리 연도, 대시 구분)를 쓴다(실측 확인). 둘 다 지원한다.

첨부파일은 상세 페이지의 <a href="board/download.<별칭>?...">에서 찾는다. 부안군은
title 속성이 이미 순수 파일명이고, 김제시는 title이 "파일명.ext 다운로드"(링크 텍스트
자체는 "다운로드"뿐)라 " 다운로드" 접미사를 뗀다(실측 확인).

City.boards 항목 형식: {"name": "고시공고", "board_id": "BBS_0000054", "menu_cd": "DOM_..."}
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

# 부안군: "26.09.23"(2자리 연도), 김제시: "2026-09-23"(4자리 연도) 둘 다 지원한다.
_DATE_CELL_RE = re.compile(r"^(\d{2}|\d{4})[.\-](\d{1,2})[.\-](\d{1,2})$")
_NOTICE_NO_RE = re.compile(r"(공고|고시)\s*제\s*\d{4}\s*[-–]\s*\d+\s*호")


def _parse_date_cell(text):
    m = _DATE_CELL_RE.match(text)
    if not m:
        return None, ""
    year, month, day = m.groups()
    if len(year) == 2:
        year = "20" + year
    date_str = f"{year}-{int(month):02d}-{int(day):02d}"
    try:
        return dt.datetime.strptime(date_str, "%Y-%m-%d").date(), date_str
    except ValueError:
        return None, ""


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(
        base_url,
        params={"boardId": board["board_id"], "menuCd": board["menu_cd"], "startPage": page_index, "paging": "ok"},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for tr in soup.select("table.bbs_list_t tbody tr"):
        subject_td = tr.find("td", class_="title")
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
        post_date, date_str = None, ""
        for t in texts:
            post_date, date_str = _parse_date_cell(t)
            if post_date is not None:
                break

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
    for a in soup.select("a[href*='download.']"):
        href = a.get("href", "")
        if "boardId=" not in href:
            continue
        title_attr = (a.get("title") or "").strip()
        text = re.sub(r"\s+", " ", a.get_text(strip=True)).strip()
        name = title_attr or text
        name = re.sub(r"\s*다운로드$", "", name).strip()
        if not name or "." not in name:
            continue
        ext = name.rsplit(".", 1)[-1].lower()
        attachments.append({"name": name, "url": urljoin(resp.url, href), "ext": ext})
    return attachments
