"""
publicnotice_prog.py — "prog/publicNotice/.../list.do" 게시판(세종특별자치시·당진시 등) 어댑터.

세종시에서 실측 확인했다(2026-09-26). JS 없이 평범한 GET + 정적 <a href>. 날짜 칸이
"등록일"(단일 날짜, 당진시) 또는 "게시기간"("2026-09-23 ~ 2026-10-07" 범위, 세종시)
로 지자체마다 다르다 — 범위 표기는 첫 날짜만 쓴다. 테이블 class도 지자체마다 다르지만
(세종 table.table-bordered, 당진 table.basic_table) 행 안의 not_ancmt_mgt_no= 링크로
찾으면 class에 의존하지 않는다(law.md 3-2).

첨부는 밀양시·나주시와 같은 GET 방식 — 상세 페이지에 이미 완성된
<a href="https://eminwon.<도메인>/emwp/jsp/ofr/FileDown.jsp?user_file_nm=...&sys_file_nm=...&file_path=...">
링크가 그대로 있다.

City.boards 항목 형식: {"name": "고시공고"}
"""

import datetime as dt
import re
from urllib.parse import parse_qsl, unquote, urljoin, urlsplit

from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

_DATE_RE = re.compile(r"\d{4}-\d{1,2}-\d{1,2}")
_NOTICE_NO_RE = re.compile(r"(공고|고시)\s*제\s*\d{4}\s*[-–]\s*\d+\s*호")
_MGT_NO_RE = re.compile(r"not_ancmt_mgt_no=(\d+)")
_FILEDOWN_RE = re.compile(r'href="(https://eminwon\.[^"]*FileDown\.jsp[^"]*)"')


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(base_url, params={"pageIndex": page_index}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for tr in soup.select("table tbody tr"):
        a_tag = tr.find("a", href=_MGT_NO_RE.search)
        if a_tag is None:
            continue
        title = re.sub(r"\s+", " ", a_tag.get_text(strip=True)).strip()
        detail_url = urljoin(resp.url, a_tag.get("href", ""))

        tds = tr.find_all("td")
        texts = [re.sub(r"\s+", " ", td.get_text(strip=True)).strip() for td in tds]
        notice_no = next((t for t in texts if _NOTICE_NO_RE.search(t)), "")
        date_str = ""
        for t in texts:
            m = _DATE_RE.search(t)
            if m:
                date_str = m.group(0)
                break
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
