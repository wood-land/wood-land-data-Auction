"""
openworks_board.py — "OpenWorks" CMS 게시판(BD_board.list.do/BD_board.view.do/
component/file/ND_fileDownload.do) 어댑터.

파주시에서 실측 확인했다(2026-09-27). 목록/상세 이동이 <a href="javascript:void(0)"
onclick="jsView('<bbsCd>','<seq>','N','Y')">뿐이라 href를 못 쓴다 — jsView()의 실제
구현(resources/user/board/board.js)이 openYn='Y'일 때 dataForm의 bbsCd/seq를
"BD_board.view.do"로 GET 제출하는 것을 확인해 그 URL을 직접 조립한다. 페이지네이션도
onclick="jsListReq(<N>)"뿐인데, 실제 구현은 q_currPage를 "BD_board.list.do"로 POST
제출하지만 실측 결과 GET 쿼리스트링으로 보내도 그대로 먹힌다.

날짜는 "YYYY/MM/DD"(슬래시) 형식이라 다른 어댑터들의 대시/점 형식과 다르다. 등록일
칸(class="cell-tit")에 "게재기간" 칸도 같은 class를 써서, "<b>등록일 : </b>" 라벨이
붙은 칸만 골라야 한다(게재기간 칸은 "YYYY/MM/DD ~ YYYY/MM/DD" 범위라 자동으로도
걸러지긴 하지만, 라벨로 한 번 더 명확히 한다).

첨부파일은 <a href="/component/file/ND_fileDownload.do?id=<uuid>">파일명.ext</a>
형태의 이미 완성된 GET 링크(링크 텍스트가 파일명).

City.boards 항목 형식: {"name": "고시공고", "bbs_cd": 1022, "q_ctg_cd": 4063}
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

_JSVIEW_RE = re.compile(r"jsView\(\s*'([^']*)'\s*,\s*'([^']*)'\s*,")
_DATE_CELL_RE = re.compile(r"^\d{4}/\d{1,2}/\d{1,2}$")


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(
        base_url,
        params={"bbsCd": board["bbs_cd"], "q_ctgCd": board.get("q_ctg_cd", ""), "q_currPage": page_index},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if table is None:
        return []

    rows = []
    for tr in table.select("tbody tr"):
        subject_td = tr.find("td", class_="cell-subject")
        a = subject_td.find("a") if subject_td else None
        if a is None:
            continue
        m = _JSVIEW_RE.search(a.get("onclick", ""))
        if m is None:
            continue
        bbs_cd, seq = m.groups()
        detail_url = urljoin(resp.url, f"BD_board.view.do?bbsCd={bbs_cd}&seq={seq}")
        title = re.sub(r"\s+", " ", a.get_text(strip=True)).strip()

        date_str = ""
        for td in tr.find_all("td", class_="cell-tit"):
            if "등록일" in td.get_text():
                i_tag = td.find("i")
                text = i_tag.get_text(strip=True) if i_tag else ""
                if _DATE_CELL_RE.match(text):
                    date_str = text
                break
        post_date = None
        if date_str:
            try:
                post_date = dt.datetime.strptime(date_str, "%Y/%m/%d").date()
            except ValueError:
                pass

        rows.append(
            {
                "board": board["name"],
                "notice_no": "",
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
    for a in soup.select("a[href*='ND_fileDownload.do']"):
        href = urljoin(resp.url, a.get("href", ""))
        name = re.sub(r"\s+", " ", a.get_text(strip=True)).strip()
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": href, "ext": ext})
    return attachments
