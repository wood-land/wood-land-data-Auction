"""
lh_board.py — LH(한국토지주택공사, lh.or.kr) "보상정보" 게시판(board.es?mid=&bid=) 어댑터.

LH 토지보상 공고 게시판(bid=0060)에서 실측 확인했다(2026-09-28). 목록/상세/첨부 모두
평범한 GET이다(JS는 상세 링크 생성 goView3()뿐이고, 그 인자가 이미 완성된 URL이다).

목록: GET board.es?mid=<mid>&bid=<bid>&nPage=<P>. 행은 table tbody tr, 칸은 번호/분류/
제목/등록일("YYYY-MM-DD")/조회수/첨부. 제목은 <td class="txt_left"><a onclick="goView3(
'<list_no>','/board.es?mid=..&act=view&list_no=..&nPage=1')"> 이고 "새글" 표식이
<span class="sr_only">로 제목 앞에 섞여 들어온다(제거한다).

이 게시판은 제목에 분류(보상계획/보상협의/대토보상/현물보상, 15페이지 실측)가 빠져 있다.
분류 정보를 잃지 않도록 제목 앞에 "[분류] "를 붙이고, 이 게시판엔 공고번호 칸이 없어
notice_no는 비워 둔다. 모든 글이 보상 대상이라 cities/central_agencies.py에서
City.match_all=True로 키워드 필터 없이 전체를 수집한다(사용자 확인, 2026-09-28).

상세: goView3의 두 번째 인자 URL을 GET. 첨부는 <a href="/boardDownload.es?bid=&list_no=&seq=">
다운로드</a> 이고 파일명은 링크 title 속성("파일명 다운로드")에 있다.

City.boards 항목 형식: {"name": "보상정보", "mid": "a10403170500", "bid": "0060"}
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

_GOVIEW_RE = re.compile(r"goView3\('(\d+)'\s*,\s*'([^']+)'")


def _parse_date(text):
    try:
        return dt.datetime.strptime(text.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(
        base_url,
        params={"mid": board["mid"], "bid": board["bid"], "nPage": page_index},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for tr in soup.select("table tbody tr"):
        a_tag = tr.select_one("td.txt_left a")
        m = _GOVIEW_RE.search(a_tag.get("onclick", "")) if a_tag else None
        if m is None:
            continue
        for junk in a_tag.select(".sr_only"):
            junk.decompose()
        tds = tr.find_all("td")
        category = tds[1].get_text(strip=True) if len(tds) > 1 else ""
        date_str = tds[3].get_text(strip=True) if len(tds) > 3 else ""
        title = a_tag.get_text(" ", strip=True)
        rows.append(
            {
                "board": board["name"],
                "notice_no": "",
                "title": f"[{category}] {title}" if category else title,
                "date": _parse_date(date_str),
                "date_str": date_str,
                "detail_url": urljoin(resp.url, m.group(2)),
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
    for a in soup.select("a[href*='boardDownload.es']"):
        href = a.get("href", "")
        if href in seen:
            continue
        seen.add(href)
        name = re.sub(r"\s*다운로드\s*$", "", a.get("title", "")).strip()
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": urljoin(resp.url, href), "ext": ext})
    return attachments
