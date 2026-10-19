"""
sangju_board.py — "page/<mn>/<page>.tc" 게시판(상주시, gosi/detail.tc / FileDownNew.jsp) 어댑터.

상주시에서 실측 확인했다(2026-09-26). 목록은 평범한 GET(JS는 무시 가능 — <form id="form1">이
GET으로 그대로 재현된다). 첨부 다운로드는 장성군·보령시와 같은 POST 방식(<form
id="form2">가 가리키는 FileDownNew.jsp, javascript:fnFileDown(...) 암호화 토큰이라
링크 텍스트를 파일명으로 씀)이라 eminwon_list.py의 download_attachment를 그대로
가져다 쓴다(law.md 3-2 — 목록 마크업은 다르지만 실제로 같다고 확인된 첨부 다운로드
부분만 재사용한다).

목록: GET page/<mn>/<page>.tc?pageIndex=<P>, <table class="com_table board">
<a onclick="fnDetail('<mgtNo>');">.

상세: GET gosi/detail.tc?mn=<mn>&mgtNo=<id>&notAncmtSeCode=<코드>.

City.boards 항목 형식: {"name": "고시공고", "mn": "10297", "not_ancmt_se_code": "01,02,03,04,05,07"}
"""

import datetime as dt
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from cms_adapters.eminwon_list import download_attachment  # noqa: F401

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

_DATE_CELL_RE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")
_NOTICE_NO_RE = re.compile(r"(공고|고시)\s*제\s*\d{4}\s*[-–]\s*\d+\s*호")
_FNDETAIL_RE = re.compile(r"fnDetail\(\s*'(\d+)'\s*\)")
_GO_DOWNLOAD_RE = re.compile(r"fnFileDown\(\s*'(.*)'\s*,\s*'(.*)'\s*,\s*'(.*)'\s*\)")


def fetch_list_page(session, base_url, board, page_index, page_unit=20):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(base_url, params={"pageIndex": page_index}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.select_one("table.com_table.board")
    if table is None:
        return []
    rows = []
    for tr in table.select("tbody tr"):
        a_tag = tr.find("a", onclick=lambda v: bool(v) and _FNDETAIL_RE.search(v))
        if a_tag is None:
            continue
        m = _FNDETAIL_RE.search(a_tag.get("onclick", ""))
        mgt_no = m.group(1)
        title = re.sub(r"\s+", " ", a_tag.get_text(strip=True)).strip()

        tds = tr.find_all("td")
        texts = [re.sub(r"\s+", " ", td.get_text(strip=True)).strip() for td in tds]
        notice_no = next((t for t in texts if _NOTICE_NO_RE.search(t)), "")
        date_str = next((t for t in texts if _DATE_CELL_RE.match(t)), "")
        post_date = None
        if date_str:
            try:
                post_date = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        detail_url = urljoin(
            resp.url,
            f"/gosi/detail.tc?mn={board['mn']}&mgtNo={mgt_no}&notAncmtSeCode={board['not_ancmt_se_code']}",
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
    down_form = soup.find("form", id="form2")
    if down_form is None:
        return []
    down_action = urljoin(resp.url, down_form.get("action", ""))

    attachments = []
    for a in soup.find_all("a", onclick=lambda v: bool(v) and _GO_DOWNLOAD_RE.search(v)):
        m = _GO_DOWNLOAD_RE.search(a.get("onclick", ""))
        user_name, sys_name, file_path = m.groups()
        display_name = re.sub(r"\s+", " ", a.get_text(strip=True)).strip().rstrip(",") or user_name
        if not display_name:
            continue
        ext = display_name.rsplit(".", 1)[-1].lower() if "." in display_name else ""
        attachments.append(
            {
                "name": display_name,
                "url": down_action,
                "ext": ext,
                "_dl_method": "POST",
                "_dl_action": down_action,
                "_dl_data": {"user_file_nm": user_name, "sys_file_nm": sys_name, "file_path": file_path},
            }
        )
    return attachments
