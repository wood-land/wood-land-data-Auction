"""
damyang_eminwon_api.py — 담양군 고시/공고 JSON API 전용 어댑터.

담양군 페이지는 순수 JS 렌더링이라(초기 HTML의 <tbody>가 비어 있고, 실제 데이터는
페이지 로드 후 별도 요청으로 채워짐) 브라우저로 실제 네트워크 요청을 관찰해 확인했다
(2026-09-25):
  - 목록: GET /eminwon/getSearchList?listType=01,02,03,04&searchKey=B_Subject&
          searchVal=&ROW_CNT=10&BEGIN_ROW_IDX=<n>&CUR_PAGE_IDX=<page> (JSON)
  - 상세: GET /eminwon/getSearchDetail?notAncmtMgtNo=<id> (JSON)
    (내부적으로 정읍시/익산시와 같은 NTIS eMinwon 백엔드(jndinm=OfrNotAncmtEJB)를 쓰지만
    담양군 프론트엔드가 JSON으로 감싸서 내려준다 — cms_adapters/ntis_ofr.py 참고)
  - 첨부파일: 상세 응답의 fileScriptArrList 안에 "javascript:goDownLoad(user,sys,path)"
    문자열이 그대로 들어있다. 실제 goDownLoad 구현은 페이지의 inline <script> 소스를
    직접 읽어 확인했다(개발자도구 네트워크 탭엔 안 잡힘 — location.href 이동이라):
    GET으로 eminwon.damyang.jeonnam.kr/emwp/jsp/ofr/FileDownNew.jsp 를 호출한다
    (다운로드 서버 도메인이 damyang.go.kr이 아니라 damyang.jeonnam.kr이라 일반화해서
    유추할 수 없었다 — 이 어댑터는 담양군 전용이다).
"""

import datetime as dt
import re
from urllib.parse import parse_qsl, quote, urlsplit

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

_LIST_URL = "https://www.damyang.go.kr/eminwon/getSearchList"
_DETAIL_URL = "https://www.damyang.go.kr/eminwon/getSearchDetail"
_DOWNLOAD_URL = "https://eminwon.damyang.jeonnam.kr/emwp/jsp/ofr/FileDownNew.jsp"
_GO_DOWNLOAD_RE = re.compile(r"goDownLoad\('(.*)'\s*,\s*'(.*)'\s*,\s*'(.*)'\)")
_DATE_FORMATS = ["%Y.%m.%d", "%Y-%m-%d"]


def _parse_post_date(date_str):
    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]
    base_url은 브라우저용 searchList 전체 URL(domainId/menuCd/contentsSid 포함) —
    그 값을 그대로 상세 링크 템플릿을 만드는 데도 재사용한다."""
    params = {
        "listType": "01,02,03,04",
        "listGubun": "",
        "searchKey": "B_Subject",
        "searchVal": "",
        "ROW_CNT": page_unit,
        "BEGIN_ROW_IDX": (page_index - 1) * page_unit + 1,
        "CUR_PAGE_IDX": page_index,
    }
    resp = session.get(_LIST_URL, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    items = data.get("RSLT_DATA", {}).get("searchList", {}).get("dataMap", []) or []

    base_parts = urlsplit(base_url)
    base_query = dict(parse_qsl(base_parts.query))

    rows = []
    for item in items:
        mgt_no = item.get("col0", "")
        if not mgt_no:
            continue
        date_str = item.get("col5", "")
        query = dict(base_query)
        query["notAncmtMgtNo"] = mgt_no
        detail_url = base_parts._replace(
            path=base_parts.path.replace("searchList", "searchDetail"),
            query="&".join(f"{k}={v}" for k, v in query.items()),
        ).geturl()
        rows.append(
            {
                "board": board["name"],
                "notice_no": item.get("col2", ""),
                "title": item.get("col3", ""),
                "date": _parse_post_date(date_str),
                "date_str": date_str,
                "detail_url": detail_url,
            }
        )
    return rows


def fetch_attachments(session, detail_url):
    """상세 페이지의 첨부파일 [{"name", "url", "ext"}, ...] (다운로드는 하지 않음)."""
    query = dict(parse_qsl(urlsplit(detail_url).query))
    mgt_no = query.get("notAncmtMgtNo", "")
    if not mgt_no:
        return []
    resp = session.get(_DETAIL_URL, params={"notAncmtMgtNo": mgt_no}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    detail = data.get("RSLT_DATA", {}).get("searchDetail", {})
    scripts = detail.get("fileScriptArrList", []) or []

    attachments = []
    for script in scripts:
        m = _GO_DOWNLOAD_RE.search(script)
        if not m:
            continue
        user_name, sys_name, file_path = m.groups()
        url = (
            _DOWNLOAD_URL
            + f"?user_file_nm={quote(user_name)}&sys_file_nm={quote(sys_name)}&file_path={quote(file_path)}"
        )
        ext = user_name.rsplit(".", 1)[-1].lower() if "." in user_name else ""
        attachments.append({"name": user_name, "url": url, "ext": ext})
    return attachments
