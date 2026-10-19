"""
gg_board.py — "bbs/board.do?bsIdx=" 게시판(경기도청, ajax/board/getList.do JSON API /
boardView.do / cmmn/download.do) 어댑터.

경기도청에서 실측 확인했다(2026-09-26). 목록은 화면이 JS로 채우는 JSON API라
(<table id="boardList">가 로더 placeholder만 갖고 있고 실제 데이터는
POST ajax/board/getList.do 응답으로 채워짐, 브라우저 네트워크 탭으로 실측 확인)
상세 페이지처럼 HTML을 파싱하지 않고 JSON을 그대로 쓴다.

목록: POST ajax/board/getList.do (bsIdx, bcIdx=0(전체), menuId, isManager=false,
isCharge=false, offset=(page_index-1)*limit, limit=10). 응답 JSON의 items 배열에
SUBJECT(제목)·WRITE_DATE2(날짜, "YYYY-MM-DD")·B_IDX(상세 idx)가 들어있다.

상세: GET bbs/boardView.do?bIdx=<B_IDX>&bsIdx=<bsIdx>&bcIdx=0&menuId=<menuId>.
첨부는 <a href="/cmmn/download.do?idx=<id>" class="filename">파일명.ext [40KB]</a>
— 링크 텍스트 끝에 "[크기]"가 붙어 있어 제거해야 한다.

City.boards 항목 형식: {"name": "고시공고", "bs_idx": "469", "menu_id": "1547"}
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

_DATE_RE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")
_NOTICE_NO_RE = re.compile(r"(공고|고시)\s*제\s*\d{4}\s*[-–]\s*\d+\s*호")
_SIZE_SUFFIX_RE = re.compile(r"\s*\[\s*[\d.,]+\s*(?:Bytes|KB|MB|GB)\s*\]\s*$", re.IGNORECASE)


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    api_url = urljoin(base_url, "/ajax/board/getList.do")
    resp = session.post(
        api_url,
        data={
            "bsIdx": board["bs_idx"],
            "bcIdx": "0",
            "menuId": board["menu_id"],
            "isManager": "false",
            "isCharge": "false",
            "offset": (page_index - 1) * page_unit,
            "limit": page_unit,
        },
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    items = data.get("items", []) or []

    rows = []
    for item in items:
        title = (item.get("SUBJECT") or "").strip()
        if not title:
            continue
        date_str = item.get("WRITE_DATE2", "")
        post_date = None
        if date_str and _DATE_RE.match(date_str):
            try:
                post_date = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                pass
        notice_no = next((v for v in item.values() if isinstance(v, str) and _NOTICE_NO_RE.search(v)), "")

        b_idx = item.get("B_IDX", "")
        detail_url = (
            f"{urljoin(base_url, '/bbs/boardView.do')}?bIdx={b_idx}&bsIdx={board['bs_idx']}"
            f"&bcIdx=0&menuId={board['menu_id']}"
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
    for a in soup.select("a.filename[href*='/cmmn/download.do']"):
        name = _SIZE_SUFFIX_RE.sub("", a.get_text(strip=True))
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": urljoin(resp.url, a.get("href", "")), "ext": ext})
    return attachments
