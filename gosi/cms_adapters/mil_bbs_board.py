"""
mil_bbs_board.py — 국방부 계열 "/bbs/<사이트>/<게시판>/artclList.do" 게시판 어댑터.

국방부(mnd.go.kr, 고시·공고 게시판 157)와 국방시설본부(dia.mil.kr, 공지사항 4459)에서
실측 확인했다(2026-09-28). 두 사이트가 같은 플랫폼(table.board-table, artclList.do /
artclView.do / download.do)이다. 목록/상세/첨부 모두 평범한 GET + 정적 <a href>(JS 없음).

목록: GET <base_url>?page=<P>. 행은 table.board-table tbody tr, 제목은
<td class="td-title"><a href="/bbs/<site>/<id>/<글번호>/artclView.do"><strong>제목</strong>
(<span class="new">새글</span> 은 strong 밖이라 제목에 안 섞인다), 작성일은
<td class="td-date">YYYY.MM.DD. 번호 칸(td-num)이 숫자가 아닌 행(상단 고정 공지)은
날짜가 오래돼 cutoff 판정을 망치므로 건너뛴다.

상세: 목록의 href를 그대로 GET. 첨부는 <ul><li><a href="/bbs/<site>/<id>/<첨부id>/
download.do"><span>파일명</span></a>(+ "다운로드" 버튼 a가 같은 href로 하나 더) — 같은
href는 하나로 합치고 파일명은 span이 있는 쪽을 쓴다.

국방부·국방시설본부는 게시판 성격이 일반 공지(국방시설본부 4459는 "인터넷용 공지사항")라
사용자가 지정한 검색어 "매입"으로 제목을 거른다(cities/central_agencies.py의 keywords).

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

_NOTICE_NO_RE = re.compile(r"(공고|고시)\s*제\s*\d{4}\s*[-–]\s*\d+\s*호")
_BUTTON_TEXTS = {"다운로드", "미리보기"}


def _parse_date(text):
    try:
        return dt.datetime.strptime(text.strip(), "%Y.%m.%d").date()
    except ValueError:
        return None


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(base_url, params={"page": page_index}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for tr in soup.select("table.board-table tbody tr"):
        num_td = tr.find("td", class_="td-num")
        title_td = tr.find("td", class_="td-title")
        date_td = tr.find("td", class_="td-date")
        if num_td is None or title_td is None or date_td is None:
            continue
        if not num_td.get_text(strip=True).isdigit():
            continue
        a_tag = title_td.find("a")
        if a_tag is None:
            continue
        strong = a_tag.find("strong")
        title = (strong or a_tag).get_text(" ", strip=True)
        notice = _NOTICE_NO_RE.search(title)
        date_str = date_td.get_text(strip=True)
        rows.append(
            {
                "board": board["name"],
                "notice_no": notice.group(0) if notice else "",
                "title": title,
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
    names = {}  # href -> 파일명 (같은 href의 "다운로드" 버튼 a는 파일명 a로 덮어쓴다)
    for a in soup.select("a[href$='/download.do']"):
        text = a.get_text(strip=True)
        href = a.get("href", "")
        if href not in names or names[href] in _BUTTON_TEXTS:
            names[href] = text
    attachments = []
    for href, name in names.items():
        if not name or name in _BUTTON_TEXTS:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": urljoin(resp.url, href), "ext": ext})
    return attachments
