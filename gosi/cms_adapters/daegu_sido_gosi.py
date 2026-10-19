"""
daegu_sido_gosi.py — "front/daeguSidoGosi/..." 게시판(대구광역시청,
fn_goLinkView() 계열) 어댑터.

대구광역시청에서 실측 확인했다(2026-09-26). 화면은 <form id="sidoGosiAPIVO"> JS
제출(fn_goLinkView()/fn_egov_link_page())을 쓰지만, 실제 목록/상세 엔드포인트
(daeguSidoGosiList.do / daeguSidoGosiView.do)에 필요한 필드만 골라 직접 POST하면
그대로 재현된다(래핑 페이지 index.do를 거칠 필요 없음, 실측 확인).

목록: POST front/daeguSidoGosi/daeguSidoGosiList.do (pageIndex),
<td data-table-type="subject"><a href="javascript:fn_goLinkView('<sno>','<gosiGbn>')">.
공고번호는 td[data-table-type="number"], 날짜는 td[data-table-type="date"].

상세: POST front/daeguSidoGosi/daeguSidoGosiView.do (sno, gosi_gbn). 첨부는
전자정부프레임워크 공통 패턴 <a onclick="fn_egov_downFile('<atchFileId>','<fileSn>')">
— atchFileId 값에 공백이 섞여 있어(실측 확인) strip 처리한다. 다운로드는
GET icms/cmm/fms/FileDown.do?atchFileId=<id>&fileSn=<n>.

City.boards 항목 형식: {"name": "고시공고"}
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

_GOLINKVIEW_RE = re.compile(r"fn_goLinkView\(\s*'([^']*)'\s*,\s*'([^']*)'\s*\)")
_DOWNFILE_RE = re.compile(r"fn_egov_downFile\(\s*'([^']*)'\s*,\s*'([^']*)'\s*\)")
_DATE_CELL_RE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")
_SIZE_SUFFIX_RE = re.compile(r"\s*\[\s*[\d.,]+\s*byte\s*\]\s*$", re.IGNORECASE)


def fetch_list_page(session, base_url, board, page_index, page_unit=20):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    list_url = urljoin(base_url, "/front/daeguSidoGosi/daeguSidoGosiList.do")
    resp = session.post(list_url, data={"pageIndex": page_index}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for tr in soup.select("table#bbsList tbody tr"):
        subject_td = tr.find("td", attrs={"data-table-type": "subject"})
        a_tag = subject_td.find("a") if subject_td else None
        if a_tag is None:
            continue
        m = _GOLINKVIEW_RE.search(a_tag.get("href", ""))
        if m is None:
            continue
        sno, gosi_gbn = m.groups()
        title = a_tag.get_text(strip=True)

        number_td = tr.find("td", attrs={"data-table-type": "number"})
        notice_no = number_td.get_text(strip=True) if number_td else ""
        date_td = tr.find("td", attrs={"data-table-type": "date"})
        date_str = date_td.get_text(strip=True) if date_td else ""
        post_date = None
        if date_str and _DATE_CELL_RE.match(date_str):
            try:
                post_date = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        detail_url = f"{base_url}#daegu-sno={sno}&gosiGbn={gosi_gbn}"
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
    detail_url은 합성 키다(POST 전용이라 sno/gosiGbn을 복원해 다시 POST한다)."""
    base_url, frag = detail_url.split("#daegu-sno=")
    sno, gosi_gbn = frag.split("&gosiGbn=")
    view_url = urljoin(base_url, "/front/daeguSidoGosi/daeguSidoGosiView.do")
    resp = session.post(view_url, data={"sno": sno, "gosi_gbn": gosi_gbn}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    attachments = []
    for a in soup.find_all("a", href=lambda v: bool(v) and _DOWNFILE_RE.search(v)):
        m = _DOWNFILE_RE.search(a.get("href", ""))
        atch_file_id, file_sn = (g.strip() for g in m.groups())
        name = _SIZE_SUFFIX_RE.sub("", a.get_text(strip=True))
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        url = urljoin(resp.url, f"/icms/cmm/fms/FileDown.do?atchFileId={atch_file_id}&fileSn={file_sn}")
        attachments.append({"name": name, "url": url, "ext": ext})
    return attachments
