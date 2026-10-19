"""
bbs_list_skin.py — "board/list.<지자체별칭>" 게시판(ul.bbs_list) 전용 어댑터.

고창군에서 실측 확인했다(2026-09-25). URL이 "index.<별칭>?menuCd=..." 형태로 보이는
다른 지자체(부산 동구·임실군 등)도 같은 벤더처럼 보였지만 실제로는 완전히 다른
시스템이었다 — URL 모양이 같다고 같은 벤더라고 가정하면 안 된다(law.md 3-2). 이
어댑터는 지금은 고창군 전용이고, 나중에 같은 "board/list.XXX?boardId=...&menuCd=..."
+ ul.bbs_list 구조를 실제로 확인한 지자체가 나오면 그때 재사용한다.

목록: GET board/list.<별칭>?boardId=<B>&menuCd=<M>&startPage=<N>&paging=ok
     (contentsSid는 없어도 동작함 — 실측 확인)
  <ul class="bbs_list"><li><a href="board/view.<별칭>?...&dataSid=<id>">
    <strong><em class="ico_notice">[번호]</em>제목<span class="ico_file">...</span></strong>
    <em class="info">공고번호 등록일 : YYYY-MM-DD 공고부서 : 부서명</em>
  </a></li></ul>
상세: 위 detail_url 그대로 GET.
첨부파일: <a class="ico_file" href="board/download.<별칭>?...&fileSid=<id>">
  href가 이미 완성된 GET 링크라 JS 파싱이 필요 없다. 파일명은 title 속성에서 읽는다.
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

_DATE_RE = re.compile(r"등록일\s*:\s*(\d{4}-\d{1,2}-\d{1,2})")
_NOTICE_NO_RE = re.compile(r"(공고|고시)\s*제\s*\d{4}\s*[-–]\s*\d+\s*호")


def _clean_title(strong_tag):
    strong = BeautifulSoup(str(strong_tag), "html.parser").strong
    for bad in strong.select("em.ico_notice, span.ico_file, span"):
        bad.decompose()
    return re.sub(r"\s+", " ", strong.get_text(strip=True)).strip()


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]
    base_url은 boardId/menuCd를 포함한 board/list.<별칭> 전체 URL이다."""
    resp = session.get(base_url, params={"startPage": page_index, "paging": "ok"}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    ul = soup.select_one("ul.bbs_list")
    if ul is None:
        return []
    rows = []
    for li in ul.find_all("li", recursive=False):
        a = li.find("a")
        if a is None or not a.get("href"):
            continue
        detail_url = urljoin(resp.url, a.get("href"))
        strong = a.find("strong")
        title = _clean_title(strong) if strong is not None else ""
        info = a.find("em", class_="info")
        info_text = re.sub(r"\s+", " ", info.get_text(" ", strip=True)) if info is not None else ""
        m_no = _NOTICE_NO_RE.search(info_text)
        notice_no = m_no.group(0) if m_no else ""
        m_date = _DATE_RE.search(info_text)
        date_str = m_date.group(1) if m_date else ""
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
    """상세 페이지의 첨부파일 [{"name", "url", "ext"}, ...] (다운로드는 하지 않음)."""
    resp = session.get(detail_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    attachments = []
    for a in soup.select("a.ico_file[href]"):
        href = a.get("href", "")
        if "download" not in href.lower():
            continue
        url = urljoin(resp.url, href)
        name = a.get("title") or a.get_text(strip=True)
        name = re.sub(r"\(\d+(\.\d+)?\s*[kKmM]?[bB]\)\s*$", "", name).strip()
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": url, "ext": ext})
    return attachments
