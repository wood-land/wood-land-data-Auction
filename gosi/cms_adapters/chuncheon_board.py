"""
chuncheon_board.py — "_chuncheon/noticeList.do"/"noticeView.do" JSON API
(춘천시청) 어댑터.

춘천시에서 실측 확인했다(2026-09-26). 화면(notice-announcement/)은 Vue 계열
SPA라 서버 HTML에 목록이 없다 — 브라우저 네트워크 탭으로 실제 JSON API를
찾았다(jeju_sido_api.py와 같은 패턴).

목록: GET _chuncheon/noticeList.do?pageIndex=<P>&searchWrd=&searchCnd=
-> {"total": N, "noticeList": [{"notAncmtMgtNo","notAncmtRegNo","notAncmtSj",
"pbsHopYmd", ...}, ...]}.

상세: GET _chuncheon/noticeView.do?notAncmtMgtNo=<id> ->
{"file": [{"file_nm","sys_file_nm","file_path","file_size"}, ...], "board": {...}}.
다운로드는 다른 eminwon 계열과 같은 GET 패턴:
eminwon.chuncheon.go.kr/emwp/jsp/ofr/FileDown.jsp?user_file_nm=<file_nm>&
sys_file_nm=<sys_file_nm>&file_path=<file_path>(실측 확인, 바이트 크기까지 일치).

City.boards 항목 형식: {"name": "고시공고"}
"""

import datetime as dt
from urllib.parse import quote, urljoin

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

_LIST_PATH = "/_chuncheon/noticeList.do"
_VIEW_PATH = "/_chuncheon/noticeView.do"
_FILEDOWN_BASE = "https://eminwon.chuncheon.go.kr/emwp/jsp/ofr/FileDown.jsp"


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(
        urljoin(base_url, _LIST_PATH),
        params={"pageIndex": page_index, "searchWrd": "", "searchCnd": ""},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    rows = []
    for item in data.get("noticeList", []):
        mgt_no = item.get("notAncmtMgtNo", "")
        if not mgt_no:
            continue
        date_str = item.get("pbsHopYmd", "") or ""
        post_date = None
        if date_str:
            try:
                post_date = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        rows.append(
            {
                "board": board["name"],
                "notice_no": item.get("notAncmtRegNo", "") or "",
                "title": item.get("notAncmtSj", "") or "",
                "date": post_date,
                "date_str": date_str,
                "detail_url": f"{urljoin(base_url, _VIEW_PATH)}?notAncmtMgtNo={mgt_no}",
            }
        )
    return rows


def fetch_attachments(session, detail_url):
    """상세 페이지의 첨부파일 [{"name","url","ext"}, ...] (다운로드는 하지 않음)."""
    resp = session.get(detail_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    attachments = []
    for f in data.get("file", []) or []:
        name = f.get("file_nm") or ""
        sys_file_nm = f.get("sys_file_nm") or ""
        file_path = f.get("file_path") or ""
        if not name or not sys_file_nm:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        url = (
            f"{_FILEDOWN_BASE}?user_file_nm={quote(name)}"
            f"&sys_file_nm={quote(sys_file_nm)}&file_path={quote(file_path)}"
        )
        attachments.append({"name": name, "url": url, "ext": ext})
    return attachments
