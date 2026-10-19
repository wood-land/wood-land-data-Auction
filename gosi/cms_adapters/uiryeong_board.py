"""
uiryeong_board.py — "board/list.<지자체별칭>?boardId=...&menuCd=..." 게시판
(table.list01 스킨) 어댑터.

의령군에서 실측 확인했다(2026-09-28). URL 모양이 bbs_list_skin(고창군)과 비슷해
보이지만 실제 마크업은 <ul class="bbs_list">가 아니라 <table class="list01">
<tbody><tr>이다(law.md 3-2 — URL 모양만으로 같은 벤더라고 가정하지 않는다).

목록: GET board/list.<별칭>?boardId=<B>&menuCd=<M>&startPage=<N>
  <table class="list01"><tbody><tr>
    <td>번호</td>
    <td class="txt_left"><a href="board/view.<별칭>?...&dataSid=<id>">제목</a></td>
    <td>부서</td>
    <td><!-- YYYYMMDD 주석 --> YYYY-MM-DD (날짜 텍스트 앞에 HTML 주석이 붙어 있지만
      BeautifulSoup.get_text()는 Comment를 제외하므로 그대로 써도 된다)</td>
    <td><img alt="첨부파일 있음" ...></td>
    <td>조회수</td>
  </tr></tbody></table>
상세: 위 detail_url 그대로 GET.
첨부파일: 상세 페이지가 eminwon.<도메인>/emwp/jsp/ofr/FileDown.jsp 완성된 GET 링크를
  그대로 쓴다(eminwon_list.py의 fetch_attachments 재사용 — law.md 3-2, 목록 마크업은
  다르지만 첨부 다운로드 부분만 실제로 같다고 확인된 걸 재사용한다).

City.boards 항목 형식: {"name": "고시공고", "board_id": "BBS_0000070", "menu_cd": "DOM_..."}
"""

import datetime as dt
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from cms_adapters.eminwon_list import fetch_attachments  # noqa: F401

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
        base_url,
        params={"boardId": board["board_id"], "menuCd": board["menu_cd"], "startPage": page_index},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for tr in soup.select("table.list01 tbody tr"):
        subject_td = tr.find("td", class_="txt_left")
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
