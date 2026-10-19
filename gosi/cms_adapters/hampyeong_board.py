"""
hampyeong_board.py — "pg/GosiList.do?pageId=" 게시판(함평군, GosiDetail.do /
FileDownNew.jsp) 어댑터.

함평군에서 실측 확인했다(2026-09-26). 목록/상세 모두 평범한 GET + 정적 <a href>
(JS 없음) — <table>이 아니라 <div class="body_row"> 레이아웃이다. 첨부 다운로드는
장성군·상주시와 같은 POST 방식(<form name="ffile">이 가리키는 FileDownNew.jsp,
javascript:goDown(...) 암호화 토큰)이라 eminwon_list.py의 download_attachment를
재사용한다(law.md 3-2 — 목록 마크업은 다르지만 실제로 같다고 확인된 첨부 다운로드
부분만 재사용한다).

목록: GET pg/GosiList.do?pageId=<pageId>&pageIndex=<P>,
<div class="body_row"><div class="gosinum">고시번호</div>
<div class="subject"><a href="/pg/GosiDetail.do?SEQ=<id>&...">제목</a></div>
<div class="regdate">YYYY-MM-DD</div></div>.

City.boards 항목 형식: {"name": "고시공고", "page_id": "www273", "not_ancmt_se_code": "01,02,03,04"}
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
_GO_DOWNLOAD_RE = re.compile(r"goDown\(\s*'(.*)'\s*,\s*'(.*)'\s*,\s*'(.*)'\s*\)")


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(
        base_url, params={"pageId": board["page_id"], "pageIndex": page_index}, headers=HEADERS, timeout=15
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for row in soup.select("div.board_list_body div.body_row"):
        subject_div = row.find("div", class_="subject")
        a_tag = subject_div.find("a") if subject_div else None
        if a_tag is None:
            continue
        title = re.sub(r"\s+", " ", a_tag.get_text(strip=True)).strip()
        detail_url = urljoin(resp.url, a_tag.get("href", ""))

        divs = row.find_all("div")
        texts = [re.sub(r"\s+", " ", d.get_text(strip=True)).strip() for d in divs]
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
    down_form = soup.find("form", {"name": "ffile"})
    if down_form is None:
        return []
    down_action = urljoin(resp.url, down_form.get("action", ""))

    attachments = []
    for a in soup.find_all("a", onclick=lambda v: bool(v) and _GO_DOWNLOAD_RE.search(v)):
        m = _GO_DOWNLOAD_RE.search(a.get("onclick", ""))
        user_name, sys_name, file_path = m.groups()
        display_name = re.sub(r"\s+", " ", a.get_text(strip=True)).strip() or user_name
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
