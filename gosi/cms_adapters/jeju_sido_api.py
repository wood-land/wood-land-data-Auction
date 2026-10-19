"""
jeju_sido_api.py — "tool/sido/api.jsp" JSON API(제주특별자치도청) 어댑터.

제주도청에서 실측 확인했다(2026-09-26). 화면(jeju2.htm)은 Vue.js SPA라 서버 HTML에
목록이 없고, 브라우저 네트워크 탭으로 실제 API를 찾아 확인했다: GET
tool/sido/api.jsp?act=index&page=<P> (목록), GET tool/sido/api.jsp?act=view&gb=<gb>&no=<no>
(상세).

함정: act=view 응답의 "files" 필드(HTML 조각, citynet/jsp/cmm/attach/download.jsp
링크)는 실제로 다운로드가 안 되는 죽은 값이었다(실측 확인 — 그대로 GET하면 404).
Vue 프론트는 이 필드를 쓰지 않고, 클릭 시 별도로
GET tool/sido/gosi.jsp?act=fid&no=<gosiNo>&title=<title>&date=<YYYYMMDD>를 불러
진짜 fid(예: "F26092318482474450")를 받은 뒤
GET tool/sido/file.jsp?mode=download&fid=<fid>&index=<i>&name=<fname> 로 내려받는다
(브라우저 네트워크 탭으로 실측 확인) — 그래서 이 어댑터도 그 경로를 그대로 따른다.

City.boards 항목 형식: {"name": "고시공고"}
"""

import datetime as dt
from urllib.parse import urlencode, urljoin

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(base_url, params={"act": "index", "page": page_index}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    items = data.get("gosis", []) or []

    rows = []
    for item in items:
        title = (item.get("title") or "").strip()
        if not title:
            continue
        date_str = item.get("date", "") or ""
        post_date = None
        if date_str:
            try:
                post_date = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                pass
        notice_no = item.get("gosiNo", "")

        detail_url = f"{base_url}?act=view&gb={item.get('gb', '')}&no={item.get('no', '')}"
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
    """상세 첨부파일 [{"name","url","ext"}, ...] (다운로드는 하지 않음).
    act=view로 gosiNo/title/date/gosiFiles를 얻은 뒤, act=fid로 진짜 fid를 받아
    file.jsp 다운로드 URL을 조립한다(모듈 docstring 참고 — files 필드는 죽은 값)."""
    resp = session.get(detail_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    gosi = resp.json().get("gosi") or {}
    gosi_files = gosi.get("gosiFiles") or []
    if not gosi_files:
        return []

    gosi_jsp = urljoin(detail_url, "gosi.jsp")
    file_jsp = urljoin(detail_url, "file.jsp")
    fid_resp = session.get(
        gosi_jsp,
        params={
            "act": "fid",
            "no": gosi.get("gosiNo", ""),
            "title": gosi.get("title", ""),
            "date": (gosi.get("date") or "").replace("-", ""),
        },
        headers=HEADERS,
        timeout=15,
    )
    fid_resp.raise_for_status()
    fid = fid_resp.json().get("fid", "")
    if not fid:
        return []

    attachments = []
    for i, f in enumerate(gosi_files):
        name = (f.get("fname") or "").strip()
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        url = f"{file_jsp}?{urlencode({'mode': 'download', 'fid': fid, 'index': i, 'name': name})}"
        attachments.append({"name": name, "url": url, "ext": ext})
    return attachments
