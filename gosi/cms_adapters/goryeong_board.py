"""
goryeong_board.py — "boardList.do?IDX=&BRD_ID=" 게시판(고령군청) 어댑터.

고령군에서 실측 확인했다(2026-09-27). 목록은 JS 없이 평범한 서버 렌더링
<table class="boardList_table">이지만, 제목 칸이 <a href="javascript:;"
onclick="fn_articleLink(<id>);">뿐이라 href를 못 쓴다 — fn_articleLink()의 실제
구현(공용 common.js)이 "/kor/boardView.do?IDX=<IDX>&BRD_ID=<BRD_ID>&BOARD_IDX=<id>
&page=1"로 이동하는 것을 확인해 그 URL을 직접 조립한다. 번호/날짜/조회수 칸이 전부
class="lblPcViewer"를 공유해(실측 확인) class로는 날짜 칸을 못 가리고, 항상
"YYYY-MM-DD" 형식 내용으로 판별한다. 페이지네이션은 목록 하단 링크가 "?pageIndex=<N>"
로 보이지만 실제로 그 값을 읽는 건 fnLinkPage()가 채우는 히든 필드 "page"다(실측
확인, 2026-09-27 — pageIndex로 보내면 서버가 조용히 무시하고 항상 1페이지를
반환해 cutoff에 걸리지 않고 끝까지 순회하는 버그가 났었다) — 그래서 "page"로 보낸다.

첨부파일은 상세 페이지의 <a class="subBtnSuq" href="/front/downFile.do?IDX_FI=<id>
&BRD_ID=<BRD_ID>">다운로드</a>(완성된 GET 링크)이고, 파일명은 옆의
<a class="bV_file">파일명.ext  [ext, size]</a>에서 " [ext, size]" 꼬리를 뗀 것이다.

City.boards 항목 형식: {"name": "고시공고", "idx": 154, "brd_id": 1023}
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
_ARTICLE_LINK_RE = re.compile(r"fn_articleLink\(\s*(\d+)\s*\)")
_SIZE_SUFFIX_RE = re.compile(r"\s*\[[^\[\]]*\]\s*$")


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(
        base_url,
        params={
            "IDX": board["idx"],
            "BRD_ID": board["brd_id"],
            "searchType": "",
            "searchValue": "",
            "page": page_index,
        },
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.select_one("table.boardList_table")
    if table is None:
        return []

    rows = []
    for tr in table.select("tbody tr"):
        title_td = tr.find("td", class_="bL_tableTitle")
        a_tag = title_td.find("a") if title_td else None
        if a_tag is None:
            continue
        m = _ARTICLE_LINK_RE.search(a_tag.get("onclick", ""))
        if m is None:
            continue
        detail_url = urljoin(
            resp.url,
            f"boardView.do?IDX={board['idx']}&BRD_ID={board['brd_id']}&BOARD_IDX={m.group(1)}&page=1",
        )
        title = re.sub(r"\s+", " ", a_tag.get_text(strip=True)).strip()

        tds = tr.find_all("td")
        texts = [td.get_text(strip=True) for td in tds]
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
    for dl_a in soup.select("a.subBtnSuq[href*='downFile.do']"):
        href = urljoin(resp.url, dl_a.get("href", ""))
        file_a = dl_a.find_previous_sibling("a", class_="bV_file")
        name = ""
        if file_a is not None:
            name = re.sub(r"\s+", " ", file_a.get_text(strip=True)).strip()
            name = _SIZE_SUFFIX_RE.sub("", name).strip()
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": href, "ext": ext})
    return attachments
