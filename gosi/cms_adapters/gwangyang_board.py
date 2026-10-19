"""
gwangyang_board.py — "saeol/gosi.es?mid=&act=view&seq=" 게시판(광양시) 어댑터.

광양시에서 실측 확인했다(2026-09-26). std_ezweb.py와 같은 "p-table" 스킨을
쓰지만 URL 체계(selectBbsNttList.do가 아니라 saeol/gosi.es?act=view&seq=)와
제목 칸 class(td.p-subject가 아니라 class 없음)가 달라 std_ezweb.py를 그대로
못 쓴다(law.md 3-2).

목록: GET saeol/gosi.es?mid=<mid>&nPage=<P>, <table class="p-table">
<td><a href="?mid=<mid>&act=view&type_code=&seq=<id>&nPage=">제목</a></td>.
공고번호는 제목 칸 바로 앞 <td>.

상세: 목록 href를 그대로 GET. 첨부는 <form name="nnn"> POST 방식
(eminwon.gwangyang.go.kr/emwp/jsp/ofr/FileDownNew.jsp)이라 eminwon_list.py의
fetch_attachments/download_attachment를 그대로 재사용한다(보령시와 같은 패턴).

City.boards 항목 형식: {"name": "고시공고", "mid": "a11005020000"}
"""

import datetime as dt
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from cms_adapters.eminwon_list import download_attachment, fetch_attachments  # noqa: F401

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
    resp = session.get(base_url, params={"mid": board["mid"], "nPage": page_index}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    rows = []
    for tr in soup.select("table.p-table tbody tr"):
        a_tag = tr.find("a", href=re.compile(r"act=view"))
        if a_tag is None:
            continue
        title = re.sub(r"\s+", " ", a_tag.get_text(strip=True)).strip()
        detail_url = urljoin(resp.url, a_tag.get("href", ""))

        tds = tr.find_all("td")
        texts = [re.sub(r"\s+", " ", td.get_text(strip=True)).strip() for td in tds]
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
