"""
yanggu_board.py — "user_sub?gfnc=www&mu_idx=" 게시판(양구군) 어댑터.

양구군에서 실측 확인했다(2026-09-26). 목록/상세 모두 평범한 GET + 정적 <a href>
(JS 없음). 첨부만 JS(opendownload(bcd, bn, num))를 쓰지만 실제로는 평범한 GET
fnc_bbs/user_bbs_download?bcd=<bcd>&bn=<bn>&num=<num> 로 재현된다.

목록: GET user_sub?gfnc=www&mu_idx=<mu_idx>&pg=<P>, <td class="tl title">
<a href="user_sub?gfnc=www&pg=1&bk=<bk>&mu_idx=<mu_idx>&bt=rd&pgsize=10&bcd=<bcd>">.

상세: 목록의 href를 그대로 GET. 첨부는
<a href="javascript:opendownload('<bcd>', <bn>, <num>)">파일명.ext</a>
— 링크 텍스트가 그대로 파일명이다.

City.boards 항목 형식: {"name": "고시공고", "mu_idx": "226"}
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
_NOTICE_NO_RE = re.compile(r"(공고|고시)\s*제\s*\d{4}\s*[-–&]\S{0,6}\s*\d+\s*호")
_OPENDOWNLOAD_RE = re.compile(r"opendownload\(\s*'([^']*)'\s*,\s*(\d+)\s*,\s*(\d+)\s*\)")


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(
        base_url, params={"gfnc": "www", "mu_idx": board["mu_idx"], "pg": page_index}, headers=HEADERS, timeout=15
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for tr in soup.select("table.tc tr"):
        subject_td = tr.find("td", class_="title")
        a_tag = subject_td.find("a") if subject_td else None
        if a_tag is None:
            continue
        title = re.sub(r"\s+", " ", a_tag.get_text(strip=True)).strip()
        detail_url = urljoin(resp.url, a_tag.get("href", ""))

        tds = tr.find_all("td")
        texts = [re.sub(r"\s+", " ", td.get_text(strip=True)).strip() for td in tds] + [title]
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
    attachments = []
    seen = set()
    for a in soup.find_all("a", href=lambda v: bool(v) and "opendownload" in v):
        m = _OPENDOWNLOAD_RE.search(a.get("href", ""))
        if m is None:
            continue
        bcd, bn, num = m.groups()
        name = a.get_text(strip=True)
        if not name:
            continue
        url = urljoin(resp.url, f"/fnc_bbs/user_bbs_download?bcd={bcd}&bn={bn}&num={num}")
        if url in seen:
            continue
        seen.add(url)
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": url, "ext": ext})
    return attachments
