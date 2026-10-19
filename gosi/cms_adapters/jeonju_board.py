"""
jeonju_board.py — "planweb/board/list.9is" 게시판(전주시) 어댑터.

전주시에서 실측 확인했다(2026-09-26). 목록/상세 모두 평범한 GET + 정적 <a href>
(JS 없음). spreadsheet가 가리킨 URL 자체가 keyword=보상 서버측 사전 필터라(이미
"보상" 포함 결과만 나옴) base_url에 그대로 두었다 — 크롤러 자체의 키워드 필터와
중복되지만 해가 없고, 서버가 미리 걸러줘서 페이지 수가 훨씬 적다(경남개발공사의
ATTR01 카테고리 필터와 같은 방식).

목록: GET list.9is?boardUid=<>&contentUid=<>&rowCount=10&searchType=dataContent&
keyword=보상&page=<P>, <td class="title"><a href="view.9is?dataUid=<id>&...">.
고시/공고번호 칸이 따로 있다("전주시 공고 제2026-2027호").

상세: 목록의 href를 그대로 GET. 첨부는
<a href="/planweb/board/download.9is?fileUid=<id>&boardUid=<>">파일명.ext(64KB)</a>
— 링크 텍스트 끝에 "(크기)"가 붙어 있어 제거해야 한다.

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
_SIZE_SUFFIX_RE = re.compile(r"\s*\(\s*[\d.,]+\s*(?:Bytes|KB|MB|GB)\s*\)\s*$", re.IGNORECASE)


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(base_url, params={"page": page_index}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    # 전주시는 table.bbs_table, 해남군은 같은 .9is 플랫폼인데 table.board_list로
    # 스킨이 다르다(실측 확인, 2026-09-26) — 행/칸 구조(td.title)는 같아 selector만 늘렸다.
    table = soup.select_one("table.bbs_table") or soup.select_one("table.board_list")
    if table is None:
        return []
    rows = []
    for tr in table.select("tbody tr"):
        subject_td = tr.find("td", class_="title")
        a_tag = subject_td.find("a") if subject_td else None
        if a_tag is None:
            continue
        title = a_tag.get_text(strip=True)
        detail_url = urljoin(resp.url, a_tag.get("href", ""))

        tds = tr.find_all("td")
        texts = [re.sub(r"\s+", " ", td.get_text(strip=True)) for td in tds]
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
    for a in soup.select("a[href*='download.9is']"):
        name = _SIZE_SUFFIX_RE.sub("", a.get_text(strip=True))
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": urljoin(resp.url, a.get("href", "")), "ext": ext})
    return attachments
