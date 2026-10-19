"""
sap_gosi.py — "citynet/jsp/sap/SAPGosiBizProcess.do" 게시판(viewData() 계열) 어댑터.

인천광역시청에서 실측 확인했다(2026-09-26). 화면은 <form name="myform"> JS 제출
(viewData()/goPage())을 쓰지만, viewData()가 만드는 action 문자열 자체가 이미 완성된
쿼리스트링 GET URL이라(sno/gosiGbn을 문자열에 직접 이어붙임, 실측 확인) 그대로 GET하면
된다. 페이지네이션은 currPageNo 파라미터.

목록: GET SAPGosiBizProcess.do?command=searchList&flag=gosiGL&svp=Y&sido=<sido>&currPageNo=<P>,
<tr onclick="viewData('<sno>','<gosiGbn>')"><td>번호</td><td>제목</td><td>부서</td><td>날짜</td><td>조회수</td>.

상세: GET SAPGosiBizProcess.do?command=searchDetail&flag=gosiGL&svp=Y&sido=<sido>&sno=<sno>&gosiGbn=<gosiGbn>.
첨부는 평범한 <a href="/citynet/jsp/cmm/attach/download.jsp?mode=download&fid=...&index=...">파일명</a>.

viewData()의 JS 주석에 "20140605 광주 서비스요청"이라는 메모가 있어 광주광역시가 같은
벤더를 쓸 가능성이 있지만(law.md 3-2, URL이 같다고 같은 벤더라고 가정하지 않는다) 아직
실측 확인 전이라 추가하지 않았다.

City.boards 항목 형식: {"name": "고시공고", "sido": "ic"}
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
_VIEWDATA_RE = re.compile(r"viewData\(\s*'([^']*)'\s*,\s*'([^']*)'\s*\)")


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(
        base_url,
        params={"command": "searchList", "flag": "gosiGL", "svp": "Y", "sido": board["sido"], "currPageNo": page_index},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for tr in soup.find_all("tr", onclick=lambda v: bool(v) and _VIEWDATA_RE.search(v)):
        m = _VIEWDATA_RE.search(tr.get("onclick", ""))
        sno, gosi_gbn = m.groups()

        tds = tr.find_all("td")
        texts = [td.get_text(strip=True) for td in tds]
        if len(tds) < 2:
            continue
        title = texts[1]
        notice_no = next((t for t in texts if _NOTICE_NO_RE.search(t)), "")
        date_str = next((t for t in texts if _DATE_CELL_RE.match(t)), "")
        post_date = None
        if date_str:
            try:
                post_date = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        detail_url = (
            f"{base_url}?command=searchDetail&flag=gosiGL&svp=Y&sido={board['sido']}"
            f"&sno={sno}&gosiGbn={gosi_gbn}"
        )
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
    for a in soup.select("a[href*='attach/download.jsp']"):
        name = a.get_text(strip=True)
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": urljoin(resp.url, a.get("href", "")), "ext": ext})
    return attachments
