"""
bbs_govstd_form.py — "bbs/list.do?key=" 게시판(goView/fn_egov_link_page 계열, <form name="frm">
GET 제출) 어댑터.

충남개발공사에서 실측 확인했다(2026-09-26). 화면은 <form name="frm">을 JS로 GET
제출하는 형태지만(goView()/fn_egov_link_page()), 실제로는 list.do/view.do 모두
평범한 쿼리스트링 GET으로 그대로 재현된다(실측 확인) — POST 불필요, 세션/TLS 이슈 없음.

목록: GET bbs/list.do?key=<key>&pageIndex=<P>, 제목 칸은
<a onclick="goView('<pstSn>')">. 날짜 칸은 <td data-cell-header="등록일">이지만
지자체마다 칸 구성이 다를 수 있어(law.md 3-2) 위치가 아니라 날짜 형식 정규식으로 찾는다.

상세: GET bbs/view.do?pstSn=<pstSn>&key=<key>. 첨부는 평범한
<a href="/atch/fileDown.do?enc_atchFileSn=...">파일명</a> — 파일명은 링크 텍스트 그대로.

City.boards 항목 형식: {"name": "보상공고", "key": "2404080036"}
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
_GOVIEW_RE = re.compile(r"goView\(\s*'([^']*)'\s*\)")
# 첨부 링크 텍스트 끝에 붙는 "(62 KB)" 같은 파일 크기 표기를 제거한다(실제 파일명이 아님).
_FILESIZE_SUFFIX_RE = re.compile(r"\s*\(\s*[\d.,]+\s*(?:Bytes|KB|MB|GB)\s*\)\s*$", re.IGNORECASE)


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    list_url = base_url.replace("view.do", "list.do")
    resp = session.get(
        list_url,
        params={"key": board["key"], "pageIndex": page_index},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for tr in soup.select("table tbody tr"):
        a_tag = tr.find("a", onclick=lambda v: bool(v) and _GOVIEW_RE.search(v))
        if a_tag is None:
            continue
        m = _GOVIEW_RE.search(a_tag.get("onclick", ""))
        pst_sn = m.group(1)
        title = a_tag.get_text(strip=True)

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

        detail_url = urljoin(resp.url, f"view.do?pstSn={pst_sn}&key={board['key']}")
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
    for a in soup.select("a[href*='fileDown.do']"):
        name = re.sub(r"\s+", " ", a.get_text(strip=True)).strip()
        name = _FILESIZE_SUFFIX_RE.sub("", name)
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": urljoin(resp.url, a.get("href", "")), "ext": ext})
    return attachments
