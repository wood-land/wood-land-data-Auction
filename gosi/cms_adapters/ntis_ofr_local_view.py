"""
ntis_ofr_local_view.py — "common/program/eminwonView.jsp" 로컬 GET 래퍼를 통한
NTIS eMinwon 고시공고 어댑터.

서산시에서 실측 확인했다(2026-09-27). ntis_ofr.py와 같은 NTIS eMinwon 백엔드
(OfrNotAncmtEJB)를 쓰지만, 사이트가 그 백엔드(OfrAction.do)에 브라우저가 직접
POST하는 대신 자기 사이트의 로컬 JSP(common/program/eminwonView.jsp)가 서버 측에서
그 POST를 대신 해주고 결과를 평범한 GET 응답으로 돌려준다 — 그래서 ntis_ofr.py처럼
OfrAction.do로 POST하지 않고, 같은 eminwonView.jsp에 method/methodnm만 바꿔 GET한다
(list 페이지에서 읽은 <form name="form1"> 숨은 필드를 그대로 재사용하는 방식은
ntis_ofr.py와 동일해 그 헬퍼(_form_fields)와 목록 파싱(_raw_items_from_table)을
그대로 재사용한다).

첨부파일 다운로드 서버(eminwon.<도메인>)는 목록 사이트(www.<도메인>)와 다른
서브도메인이라(실측 확인) ntis_ofr.py의 "base_url과 같은 호스트"라는 가정을 그대로
못 쓴다 — www.<도메인> -> eminwon.<도메인>으로 호스트를 바꿔 조립한다. goDownLoad()
JS 구현이 그대로 GET(구버전, 익산시와 같은 패턴)이라 <form name="nnn"> POST 방식은
없다(실측 확인).

City.boards 항목 형식: {"name": "고시공고"}
"""

import datetime as dt
import re
from urllib.parse import quote, urlsplit

from bs4 import BeautifulSoup

from cms_adapters.ntis_ofr import HEADERS, _GO_DOWNLOAD_RE, _form_fields, _raw_items_from_table

_DETAIL_MARKER = "#local-mgtno="
_DATE_CELL_RE = re.compile(r"^\d{4}[.\-]\d{1,2}[.\-]\d{1,2}$")


def _eminwon_host(url):
    netloc = urlsplit(url).netloc
    if netloc.startswith("www."):
        netloc = netloc[len("www."):]
    return "eminwon." + netloc


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]
    base_url은 method=selectListOfrNotAncmt 등을 포함한 eminwonView.jsp 전체 URL이다."""
    resp = session.get(base_url, params={"pageIndex": page_index}, headers=HEADERS, timeout=40)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    raw_items = _raw_items_from_table(soup)
    if not raw_items:
        return []

    rows = []
    for mgt_no, notice_no, title, date_str in raw_items:
        post_date = None
        if date_str:
            try:
                post_date = dt.datetime.strptime(date_str.replace(".", "-"), "%Y-%m-%d").date()
            except ValueError:
                pass
        rows.append(
            {
                "board": board["name"],
                "notice_no": notice_no,
                "title": title,
                "date": post_date,
                "date_str": date_str,
                "detail_url": base_url + _DETAIL_MARKER + mgt_no,
            }
        )
    return rows


def fetch_attachments(session, detail_url):
    """상세 페이지의 첨부파일 [{"name","url","ext"}, ...] (다운로드는 하지 않음)."""
    base_url, marker, mgt_no = detail_url.partition(_DETAIL_MARKER)
    if not marker:
        return []
    fields, _soup, _resp = _form_fields(session, base_url, "form1")
    if fields is None:
        return []
    fields["method"] = "selectOfrNotAncmt"
    fields["methodnm"] = "selectOfrNotAncmtRegst"
    fields["not_ancmt_mgt_no"] = mgt_no
    jsp_path = base_url.split("?", 1)[0]
    resp = session.get(jsp_path, params=fields, headers=HEADERS, timeout=40)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    host = _eminwon_host(resp.url)

    attachments = []
    for a in soup.find_all("a", href=re.compile(r"^javascript:goDownLoad\(")):
        m = _GO_DOWNLOAD_RE.search(a.get("href", ""))
        if not m:
            continue
        user_name, sys_name, file_path = m.groups()
        ext = user_name.rsplit(".", 1)[-1].lower() if "." in user_name else ""
        url = (
            f"https://{host}/emwp/jsp/ofr/FileDown.jsp"
            f"?user_file_nm={quote(user_name)}&sys_file_nm={quote(sys_name)}&file_path={quote(file_path)}"
        )
        attachments.append({"name": user_name, "url": url, "ext": ext})
    return attachments
