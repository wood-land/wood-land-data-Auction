"""
seongju_board.py — 성주군청 게시판(page.do?mnu_uid=, 새올 saeol_gosi 계열 마크업)
전용 페이지네이션 어댑터.

성주군에서 실측 확인했다(2026-09-28). 목록 마크업(td.list_tit a, td.list_date)은
saeol_gosi.py가 이미 지원하는 것과 동일하지만, 페이지네이션이 단순히 "page"나
"pageNo" 하나만 보내서는 안 먹힌다 — 실제 "다음 페이지" 링크를 그대로 따라가 보니
pageNo와 함께 srchEnable=1, srchSDate/srchKwd/srchColumn/srchEDate/srchDept(빈 문자열),
srchBgpUid=-1을 전부 같이 보내야 다음 페이지 내용이 나온다(하나라도 빠지면 항상
1페이지 내용만 반환, 실측 확인) — 그래서 saeol_gosi.py를 고치는 대신 이 파라미터
조합을 그대로 보내는 전용 어댑터를 뒀다. 목록 파싱 자체는 saeol_gosi.py와 같은
selector를 쓴다.

또 하나 실측으로 확인한 함정: 날짜순 정렬과 무관하게 "공지글"(<td class="list_num">
안에 alt="공지글" <img>)로 고정된 12개 행이 모든 페이지 맨 앞에 항상 반복해서
나오는데, 이 공지글들의 등록일이 최신 글보다 훨씬 오래됐다(예: 2025-12-01) —
건드리지 않고 그대로 두면 board_crawler.py의 cutoff 판정이 1페이지만 보고
"오래된 글 발견"으로 오판해 2페이지부터는 있는 최신 글도 못 가져온다. 그래서
공지글 행은 아예 목록에서 건너뛴다(날짜 판정에서 배제 — 공지글은 보통 안내성
글이라 키워드 매칭 손실도 거의 없다).

첨부파일은 saeol_gosi.py와 동일한 goDownload(...) 패턴이라 그 fetch_attachments를
그대로 재사용한다.

City.boards 항목 형식: {"name": "고시공고", "mnu_uid": "1044"}
"""

import datetime as dt
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from cms_adapters.saeol_gosi import fetch_attachments  # noqa: F401

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
        params={
            "mnu_uid": board["mnu_uid"],
            "pageNo": page_index,
            "srchEnable": 1,
            "srchSDate": "",
            "srchKwd": "",
            "srchColumn": "",
            "srchEDate": "",
            "srchBgpUid": -1,
            "srchDept": "",
        },
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.select_one("table.bod_list") or soup.find("table")
    if table is None:
        return []

    rows = []
    for tr in table.select("tbody tr"):
        num_td = tr.select_one("td.list_num")
        if num_td is not None and num_td.find("img", alt="공지글") is not None:
            continue  # 공지글(상단 고정, 실제 날짜와 무관) — cutoff 오판 방지
        a = tr.select_one("td.list_tit a")
        if a is None:
            continue
        detail_url = urljoin(resp.url, a.get("href", ""))
        title = re.sub(r"\s+", " ", a.get_text(strip=True)).strip()

        texts = [td.get_text(strip=True) for td in tr.find_all("td")]
        notice_no = next((t for t in texts if _NOTICE_NO_RE.search(t)), "")
        date_td = tr.select_one("td.list_date")
        date_str = date_td.get_text(strip=True) if date_td else ""
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
