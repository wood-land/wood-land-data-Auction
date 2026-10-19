"""
gb_do_board.py — "page/<menuId>/<pageNo>.do" 게시판(경상북도청, boardList.view() /
file/readFile.do 계열) 어댑터.

경상북도청에서 실측 확인했다(2026-09-26). 목록은 서버 렌더링 HTML(JS 없이도 접근
가능)이지만, 상세는 CSRF 토큰이 있어야 열린다(토큰 없이 GET하면 "게시글 조회
권한이 없습니다" 오류) — 그래서 상세 조회 전에 매번 목록 페이지를 다시 열어
<input name="_csrf">를 읽는다(실측 확인 — 목록 페이지 GET에는 인증이 필요 없다).

목록: GET page/<menuId>/<pageNo>.do?pageIndex=<P>, <tr onclick="boardList.view('<boardNo>');">.

상세: GET page/<menuId>/<pageNo>.do?boardNo=<id>&boardMngNo=<mngNo>&pageDtlOrdrNo=1&
pageIndex=&searchStrtDt=&searchEndDt=&searchCondition=1&searchKeyword=&
recordCountPerPage=10&_csrf=<토큰>&importUrl=/board/view.do — 응답 HTML 안에
"boardView.viewFile.putFileHtml(fileId, fileNo, fileNm, fileSz, fileExtn)" JS 호출이
있어 정규식으로 뽑는다. 다운로드는 file/readFile.do?fileId=<fileId>&fileNo=<fileNo>
(fileupload.js의 viewFile.putFileHtml 구현 참고, 실측 확인).

City.boards 항목 형식: {"name": "고시공고", "board_mng_no": "71"}
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
_VIEW_RE = re.compile(r"boardList\.view\(\s*'(\d+)'\s*\)")
_PUTFILE_RE = re.compile(
    r"putFileHtml\(\s*\"([^\"]*)\"\s*,\s*\"([^\"]*)\"\s*,\s*\"([^\"]*)\"\s*,\s*\"([^\"]*)\"\s*,\s*\"([^\"]*)\""
)
_CSRF_RE = re.compile(r'name="_csrf"\s+value="([^"]+)"')


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(base_url, params={"pageIndex": page_index}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    seen = set()
    for tr in soup.select("table.notice tbody tr"):
        m = _VIEW_RE.search(str(tr))
        if m is None:
            continue
        board_no = m.group(1)
        if board_no in seen:
            continue
        seen.add(board_no)

        title_td = tr.find("td", class_="pointer")
        title_p = tr.find("p", class_="except")
        title = title_p.get_text(strip=True) if title_p else (title_td.get_text(strip=True) if title_td else "")
        if not title:
            continue

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

        detail_url = f"{base_url}#gb-boardNo={board_no}&boardMngNo={board['board_mng_no']}"
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
    """상세 페이지의 첨부파일 [{"name","url","ext"}, ...] (다운로드는 하지 않음).

    detail_url은 합성 키다(모듈 docstring 참고 — 상세 조회에 매번 최신 _csrf가
    필요해 목록 페이지를 다시 열어야 한다)."""
    base_url, frag = detail_url.split("#gb-boardNo=")
    board_no, board_mng_no = frag.split("&boardMngNo=")

    list_resp = session.get(base_url, headers=HEADERS, timeout=15)
    list_resp.raise_for_status()
    m = _CSRF_RE.search(list_resp.text)
    if m is None:
        return []
    csrf = m.group(1)

    resp = session.get(
        base_url,
        params={
            "pageDtlOrdrNo": "1",
            "pageIndex": "",
            "boardNo": board_no,
            "boardMngNo": board_mng_no,
            "searchCondition": "1",
            "searchKeyword": "",
            "recordCountPerPage": "10",
            "_csrf": csrf,
            "importUrl": "/board/view.do",
        },
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()

    file_url = urljoin(base_url, "/file/readFile.do")
    attachments = []
    for file_id, file_no, name, _size, _ext in _PUTFILE_RE.findall(resp.text):
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        url = f"{file_url}?fileId={file_id}&fileNo={file_no}"
        attachments.append({"name": name, "url": url, "ext": ext})
    return attachments
