"""
yeonggwang_board.py — 영광군 그누보드(Gnuboard) 계열 게시판(b_id=gosigonggo) 어댑터.

영광군에서 실측 확인했다(2026-09-27). 목록은 JS 없이 평범한 서버 렌더링 <table>
이지만, 페이지네이션이 다른 곳들의 pageIndex/page가 아니라 그누보드 특유의
"offset"(건너뛸 게시물 수, page_unit=10 기준 offset=(page-1)*10)이다. 제목 칸은
class="txt_l t_title"인데, 공고번호 칸도 class="txt_l t_title1"이라 "title"
문자열만으로는 구분이 안 된다 — 공고번호 칸은 <a> 없이 순수 텍스트뿐이라 <a>가
있는 칸(t_title)만 제목으로 인정한다(eminwon_list.py의 판별 방식과 동일).

첨부파일은 <a href="javascript:goDownLoad(a,b,c)">인데, goDownLoad()의 실제 구현이
"https://eminwon.yeonggwang.jeonnam.kr/emwp/jsp/ofr/FileDown.jsp"로 GET한다 —
도메인이 이 사이트(yeonggwang.go.kr)도, 일반적인 "eminwon.<같은도메인>" 규칙도
아니라(jeonnam.kr 지역도메인) eminwon_list.py의 일반 규칙을 못 쓴다(실측 확인).

City.boards 항목 형식: {"name": "고시공고", "b_id": "gosigonggo", "site": "headquarter_new", "mn": 9059}
"""

import datetime as dt
import re
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

_DATE_CELL_RE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")
_NOTICE_NO_RE = re.compile(r"(공고|고시)\s*제\s*\d{4}\s*[-–]\s*\d+\s*호")
_GO_DOWNLOAD_RE = re.compile(r"goDownLoad\('([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\)")
_FILEDOWN_BASE = "https://eminwon.yeonggwang.jeonnam.kr/emwp/jsp/ofr/FileDown.jsp"


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    offset = (page_index - 1) * page_unit
    resp = session.get(
        base_url,
        params={"b_id": board["b_id"], "site": board["site"], "mn": board["mn"], "offset": offset},
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
        subject_td = None
        for td in tr.find_all("td"):
            classes = td.get("class") or []
            if any("title" in c for c in classes) and td.find("a") is not None:
                subject_td = td
                break
        if subject_td is None:
            continue
        a = subject_td.find("a")
        href = a.get("href", "")
        if not href:
            continue
        detail_url = urljoin(resp.url, href)
        title = re.sub(r"\s+", " ", a.get_text(strip=True)).strip()

        texts = [td.get_text(strip=True) for td in tr.find_all("td")]
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
    for a in soup.find_all("a", href=re.compile(r"^javascript:goDownLoad\(")):
        m = _GO_DOWNLOAD_RE.search(a.get("href", ""))
        if m is None:
            continue
        user_name, sys_name, file_path = m.groups()
        ext = user_name.rsplit(".", 1)[-1].lower() if "." in user_name else ""
        url = f"{_FILEDOWN_BASE}?user_file_nm={quote(user_name)}&sys_file_nm={quote(sys_name)}&file_path={quote(file_path)}"
        attachments.append({"name": user_name, "url": url, "ext": ext})
    return attachments
