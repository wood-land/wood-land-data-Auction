"""
devcorp_bbs_api.py — 지방개발공사 공통 JSON 게시판 API(getBbsArticleList.do) 어댑터.

경상북도개발공사·경상남도개발공사에서 실측 확인했다(2026-09-25). 여러 지방개발공사가
같은 벤더 CMS를 쓰는 것으로 보인다(경북개발공사 페이지에 "전국 지방 개발공사" 링크
목록이 있어 후보를 알 수 있음) — 새 기관을 추가할 때는 그 기관의 게시판 페이지를
브라우저로 열어 실제 getBbsArticleList.do 요청(BBS_ID, 필요하면 ATTR01)을
직접 확인한 뒤 추가한다(law.md 3-2, 임의 추측 금지).

목록: GET <base_url>/getBbsArticleList.do?BBS_ID=<board.bbs_id>&BBS_TYPE=L&
     CURRENT_PAGE=<page>&SEARCH_CONTITION=CPDS_SUBJECT_CONTENT&SEARCH_KEYWORD=
     (+ 사이트에 따라 board.attr01 같은 카테고리 필터 파라미터가 더 필요할 수 있다 —
     경남개발공사는 BBS_ID 하나에 여러 카테고리가 섞여 있어 ATTR01로 좁혀야 했다)
     JSON 응답의 resultList 안에 제목(CPDS_SUBJECT)·날짜(CPDS_WDATE)·첨부파일
     경로(sysFileNameStr, "|"로 여러 개 이어짐)·원래 파일명(orgFileNameStr)이 전부
     들어있어 상세 페이지를 따로 열 필요가 없다(실측 확인 — 상세는 JS 팝업이라 실제
     GET URL이 없다).

첨부파일: sysFileNameStr의 각 경로(예: /privatefiles/BOARD/<uuid>/<uuid>.pdf)가
이미 완성된 상대경로라 도메인만 붙이면 바로 GET 다운로드된다 — JS 파싱도, 상세
페이지 재조회도 필요 없다. fetch_list_page 단계에서 이미 다 알고 있으므로
detail_url에 파일 목록을 그대로 실어 두고(쿼리스트링), fetch_attachments는
네트워크 요청 없이 그걸 풀어서 쓴다.
"""

import datetime as dt
from urllib.parse import parse_qsl, urlencode, urlsplit

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

_API_PATH = "/getBbsArticleList.do"


def _site_root(url):
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]
    base_url은 사이트 루트(예: https://www.gndc.co.kr)다."""
    params = {
        "BBS_ID": board["bbs_id"],
        "BBS_TYPE": "L",
        "CURRENT_PAGE": page_index,
        "SEARCH_CONTITION": "CPDS_SUBJECT_CONTENT",
        "SEARCH_KEYWORD": "",
    }
    if board.get("attr01"):
        params["ATTR01"] = board["attr01"]
    resp = session.get(_site_root(base_url) + _API_PATH, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    items = data.get("resultList", []) or []

    rows = []
    for item in items:
        title = (item.get("CPDS_SUBJECT") or "").strip()
        if not title:
            continue
        date_str = (item.get("CPDS_WDATE") or "").split(" ")[0]
        post_date = None
        if date_str:
            try:
                post_date = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                pass
        detail_query = urlencode(
            {
                "_root": _site_root(base_url),
                "_sys": item.get("sysFileNameStr", ""),
                "_org": item.get("orgFileNameStr", ""),
            }
        )
        rows.append(
            {
                "board": board["name"],
                "notice_no": item.get("IPDS_IDX", ""),
                "title": title,
                "date": post_date,
                "date_str": date_str,
                "detail_url": f"{_site_root(base_url)}{_API_PATH}?{detail_query}",
            }
        )
    return rows


def fetch_attachments(session, detail_url):
    """상세 페이지의 첨부파일 [{"name","url","ext"}, ...] (다운로드는 하지 않음).
    fetch_list_page가 이미 실어 둔 파일 목록을 그대로 풀어 쓴다 — 네트워크 요청 없음."""
    query = dict(parse_qsl(urlsplit(detail_url).query))
    root = query.get("_root", "")
    sys_names = [s for s in (query.get("_sys", "") or "").split("|") if s]
    org_names = [s for s in (query.get("_org", "") or "").split("|") if s]
    attachments = []
    for i, sys_path in enumerate(sys_names):
        name = org_names[i] if i < len(org_names) else sys_path.rsplit("/", 1)[-1]
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": root + sys_path, "ext": ext})
    return attachments
