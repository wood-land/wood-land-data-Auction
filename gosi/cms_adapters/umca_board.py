"""
umca_board.py — "umca/bbs/list.do?bbsId=" 게시판(storyCms/HHBbs 계열,
bbs/view.do / bbs/FileDown.do) 어댑터.

울산도시공사에서 실측 확인했다(2026-09-26). "보상공고" 전용 게시판이라
(bbsId=BBS_0000000000000005) 대부분 이미 보상 관련이지만 키워드 필터는 그대로
거친다. 목록/상세는 평범한 GET(제목 <a>는 이미 완성된 href를 갖고 있다 — onclick의
fn_view()는 무시해도 된다, 실측 확인). 페이지네이션은 화면 goPage()가 쓰는 실제
파라미터명이 "pageIndex"가 아니라 "page"다(실측 확인 — pageIndex는 서버가 무시함).

첨부: onclick="HHBbs.DownFile('/umca', '<bbsId>','<atchFileId>','<fileSn>')" — 이
JS 함수(HHCommon.js)의 실제 동작은 GET
umca/bbs/FileDown.do?bbsId=<bbsId>&atchFileId=<atchFileId>&fileSn=<fileSn> 이다
(실측 확인, HHCommon.js DownFile() 정의 참고).

City.boards 항목 형식: {"name": "보상공고", "bbs_id": "BBS_0000000000000005", "m_id": "001001005000000000"}
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
_DOWNFILE_RE = re.compile(r"HHBbs\.DownFile\(\s*'[^']*'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*\)")
# 첨부 링크 텍스트 끝에 붙는 "(65.6KByte)" 같은 파일 크기 표기를 제거한다.
_FILESIZE_SUFFIX_RE = re.compile(r"\s*\(\s*[\d.,]+\s*(?:Bytes|KB|MB|GB|Byte|KByte|MByte|GByte)\s*\)\s*$", re.IGNORECASE)


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    list_url = base_url.replace("view.do", "list.do")
    resp = session.get(
        list_url,
        params={"bbsId": board["bbs_id"], "mId": board["m_id"], "page": page_index},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for tr in soup.select("table.tbl_bd_list tbody tr"):
        subject_td = tr.find("td", class_="ta_l")
        a_tag = subject_td.find("a") if subject_td else None
        if a_tag is None:
            continue
        title = a_tag.get_text(strip=True)
        detail_url = urljoin(resp.url, a_tag.get("href", ""))

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
    root = resp.url.split("/bbs/", 1)[0]
    attachments = []
    for a in soup.find_all("a", onclick=lambda v: bool(v) and _DOWNFILE_RE.search(v)):
        m = _DOWNFILE_RE.search(a.get("onclick", ""))
        bbs_id, atch_file_id, file_sn = m.groups()
        name = _FILESIZE_SUFFIX_RE.sub("", a.get_text(strip=True))
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        url = f"{root}/bbs/FileDown.do?bbsId={bbs_id}&atchFileId={atch_file_id}&fileSn={file_sn}"
        attachments.append({"name": name, "url": url, "ext": ext})
    return attachments
