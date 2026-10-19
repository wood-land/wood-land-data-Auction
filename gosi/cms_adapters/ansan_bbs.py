"""
ansan_bbs.py — "www/common/bbs/selectPageListBbs.do" 게시판(안산시) 어댑터.

안산시에서 실측 확인했다(2026-09-26). 화면은 <form id="aform"> JS 제출
(fnGoDetail()/fnFileDownLoad())을 쓰지만 실제로는 GET이라 그대로 재현된다. p-table
스킨(원주시와 유사한 부분도 있지만 URL 패턴이 전혀 달라 std_ezweb.py를 쓰지 않고
별도 어댑터로 뒀다 — law.md 3-2).

목록: GET selectPageListBbs.do?bbs_code=<code>&currentPage=<P>, <td class="p-subject">
<a onclick="fnGoDetail( <bbs_seq> ); return false;">.

상세: GET selectBbsDetail.do?key=<key>&bbs_code=<code>&bbs_seq=<id> (key는 목록
페이지의 <form id="aform"> hidden input에서 읽는다). 첨부는
<a onclick="fnFileDownLoad('<file_id>'); return false;" class="p-attach__link">
<span>파일명.ext</span></a> — 다운로드는 GET
common/file/FileDown.do?file_id=<file_id>.

City.boards 항목 형식: {"name": "고시공고", "bbs_code": "WWW13"}
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
_GODETAIL_RE = re.compile(r"fnGoDetail\(\s*(\d+)\s*\)")
_FILEDOWN_RE = re.compile(r"fnFileDownLoad\(\s*'([^']*)'\s*\)")


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(
        base_url, params={"bbs_code": board["bbs_code"], "currentPage": page_index}, headers=HEADERS, timeout=15
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    form = soup.find("form", id="aform")
    key = ""
    if form is not None:
        key_input = form.find("input", {"name": "key"})
        key = key_input.get("value", "") if key_input else ""

    rows = []
    for tr in soup.select("table.p-table tbody tr"):
        subject_td = tr.find("td", class_="p-subject")
        a_tag = subject_td.find("a") if subject_td else None
        if a_tag is None:
            continue
        m = _GODETAIL_RE.search(a_tag.get("onclick", ""))
        if m is None:
            continue
        bbs_seq = m.group(1)
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

        detail_url = urljoin(
            resp.url, f"selectBbsDetail.do?key={key}&bbs_code={board['bbs_code']}&bbs_seq={bbs_seq}"
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
    attachments = []
    for a in soup.select("a.p-attach__link"):
        m = _FILEDOWN_RE.search(a.get("onclick", ""))
        if m is None:
            continue
        file_id = m.group(1)
        # 첫 span은 "hwpx 문서" 같은 아이콘 라벨, 진짜 파일명은 마지막 span에
        # 있다(실측 확인 — std_ezweb.py의 p-attach__link 처리와 같은 패턴).
        spans = a.find_all("span")
        name = spans[-1].get_text(strip=True) if spans else a.get_text(strip=True)
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        url = urljoin(resp.url, f"/common/file/FileDown.do?file_id={file_id}")
        attachments.append({"name": name, "url": url, "ext": ext})
    return attachments
