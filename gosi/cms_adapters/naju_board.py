"""
naju_board.py — "www/administration/notice/gosi_new" 게시판(나주시) 어댑터.

나주시에서 실측 확인했다(2026-09-26). 목록/상세 모두 평범한 GET + 정적 <a href>
(JS 없음). 목록 표에 "고시공고번호" 칸이 따로 있어(예: "나주시 공고 제2026-1573호")
공고번호를 안정적으로 얻을 수 있다.

목록: GET gosi_new?page=<P>&start_date=<1년전>&finish_date=<오늘>,
<td class="align_left"><a href="gosi_new?idx=<id>&mode=view&...">.

상세: 목록의 href를 그대로 GET. 첨부는
<button onclick="window.open('https://eminwon.naju.go.kr/emwp/jsp/ofr/FileDown.jsp
?user_file_nm=<파일명>&sys_file_nm=<시스템파일명>&file_path=<경로>', '_blank')">다운로드</button>
— 이미 완성된 GET URL이라(밀양시와 같은 패턴, eminwon_list.py 참고) 그대로 쓴다.

City.boards 항목 형식: {"name": "고시공고"}
"""

import datetime as dt
import re
from urllib.parse import parse_qsl, unquote, urlsplit

from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

_DATE_CELL_RE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")
_NOTICE_NO_RE = re.compile(r"(공고|고시)\s*제\s*\d{4}\s*[-–]\s*\d+\s*호")
_FILEDOWN_RE = re.compile(r"window\.open\('(https://eminwon\.naju\.go\.kr[^']+)'")


def fetch_list_page(session, base_url, board, page_index, page_unit=15):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    today = dt.date.today()
    start = today - dt.timedelta(days=365)
    resp = session.get(
        base_url,
        params={"page": page_index, "start_date": start.isoformat(), "finish_date": today.isoformat()},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.select_one("table.table_list")
    if table is None:
        return []
    rows = []
    for tr in table.select("tbody tr"):
        subject_td = tr.find("td", class_="align_left")
        a_tag = subject_td.find("a") if subject_td else None
        if a_tag is None:
            continue
        title = a_tag.get_text(strip=True)
        detail_url = f"{base_url}?{urlsplit(a_tag.get('href', '')).query}"

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
    attachments = []
    for m in _FILEDOWN_RE.finditer(resp.text):
        url = m.group(1)
        query = dict(parse_qsl(urlsplit(url).query))
        name = unquote(query.get("user_file_nm", ""))
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": url, "ext": ext})
    return attachments
