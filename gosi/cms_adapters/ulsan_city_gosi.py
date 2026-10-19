"""
ulsan_city_gosi.py — "u/rep/transfer/notice/list.ulsan" 게시판(울산광역시청) 어댑터.

울산광역시청에서 실측 확인했다(2026-09-26). 목록/상세 모두 평범한 GET + 정적 <a href>
(JS 없음). 첨부 다운로드 엔드포인트(minwon.ulsan.go.kr/citynet/jsp/cmm/attach/
download.jsp)가 인천광역시청(sap_gosi)·충청남도청(chungnam_do_board)과 똑같아
(같은 SAP 계열 벤더로 보인다, law.md 3-2 — 그래도 목록/상세 마크업 자체는 이
사이트만의 것이라 별도 어댑터로 뒀다) 첨부 파싱 로직만 재사용한다.

목록: GET list.ulsan?mId=<mId>&curPage=<P>, <td class="gosi"><a href="./<id>.ulsan?mId=<mId>&gosiGbn=A">.

상세: 목록의 href를 그대로 GET. 첨부는 평범한
<a href="https://minwon.ulsan.go.kr/.../attach/download.jsp?...">파일명</a>.

City.boards 항목 형식: {"name": "고시공고", "m_id": "001004002000000000"}
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


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(
        base_url,
        params={"mId": board["m_id"], "curPage": page_index},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for tr in soup.select("table.tbl_bd_list tbody tr"):
        subject_td = tr.find("td", class_="gosi")
        a_tag = subject_td.find("a") if subject_td else None
        if a_tag is None:
            continue
        title = a_tag.get_text(strip=True)
        detail_url = urljoin(resp.url, a_tag.get("href", ""))

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
    soup = BeautifulSoup(resp.text, "html.parser")
    attachments = []
    for a in soup.select("a[href*='attach/download.jsp']"):
        name = a.get_text(strip=True)
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": urljoin(resp.url, a.get("href", "")), "ext": ext})
    return attachments
