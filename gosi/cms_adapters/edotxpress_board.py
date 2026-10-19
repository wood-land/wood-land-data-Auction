"""
edotxpress_board.py — "open_content/ko/page.do?mnu_uid=" 게시판(경산시 등,
"EDotXPress" CMS 계열) 어댑터.

경산시에서 실측 확인했다(2026-09-26). 같은 "page.do?mnu_uid=" URL을 쓰는
울릉군·영주시(mnu_uid_board.py, saeol/notice 계열)와는 완전히 다른 마크업/쿼리
파라미터 세트다(law.md 3-2 — URL 모양만으로 같은 벤더라고 가정하지 않는다).

목록: GET open_content/ko/page.do?mnu_uid=<mnu_uid>&pageNo=<P>,
<table class="table_st02"><td class="sub_tit"><a href="...&parm_bod_uid=<id>&...">.
고시공고번호 칸이 따로 없어 제목 텍스트에서 정규식으로 뽑아낸다.

상세: 목록 href를 그대로 GET. 첨부는 <a onclick="openDownloadFiles(fileUid,bodUid,
mnuUid)">파일명</a> — 링크 텍스트가 그대로 파일명이고, 실제 다운로드 URL은
JS 함수(design2021/common/js/utility.js) 그대로 재현해
/programs/board/download.do?parm_file_uid=<fileUid>&bod_uid=<bodUid>&mnu_uid=<mnuUid>.

City.boards 항목 형식: {"name": "고시공고", "mnu_uid": "2160"}
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

_DATE_RE = re.compile(r"\d{4}-\d{1,2}-\d{1,2}")
_NOTICE_NO_RE = re.compile(r"(공고|고시)\s*제\s*\d{4}\s*[-–]\s*\d+\s*호")
_OPENDOWNLOAD_RE = re.compile(r"openDownloadFiles\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)")


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(
        base_url, params={"mnu_uid": board["mnu_uid"], "pageNo": page_index}, headers=HEADERS, timeout=15
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    table = None
    for t in soup.find_all("table"):
        if t.find("a", href=re.compile(r"parm_bod_uid=")) is not None:
            table = t
            break
    if table is None:
        return []

    rows = []
    for tr in table.select("tbody tr"):
        title_td = tr.find("td", class_=re.compile(r"sub_tit"))
        a_tag = title_td.find("a") if title_td else None
        if a_tag is None:
            continue
        title = re.sub(r"\s+", " ", a_tag.get_text(strip=True)).strip()
        detail_url = urljoin(resp.url, a_tag.get("href", ""))

        notice_m = _NOTICE_NO_RE.search(title)
        notice_no = notice_m.group(0) if notice_m else ""

        date_td = tr.find("td", class_=re.compile(r"con_rgstDateTime"))
        date_str = ""
        post_date = None
        if date_td:
            m = _DATE_RE.search(date_td.get_text(strip=True))
            if m:
                date_str = m.group(0)
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
    for a in soup.find_all("a", onclick=lambda v: bool(v) and _OPENDOWNLOAD_RE.search(v)):
        m = _OPENDOWNLOAD_RE.search(a.get("onclick", ""))
        file_uid, bod_uid, mnu_uid = m.groups()
        name = re.sub(r"\s+", " ", a.get_text(strip=True)).strip()
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        url = urljoin(
            resp.url,
            f"/programs/board/download.do?parm_file_uid={file_uid}&bod_uid={bod_uid}&mnu_uid={mnu_uid}",
        )
        attachments.append({"name": name, "url": url, "ext": ext})
    return attachments
