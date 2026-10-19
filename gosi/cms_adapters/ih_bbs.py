"""
ih_bbs.py — "bbs/bbsMsgList.do?bcd=" 게시판(인천도시공사 CMS,
bbsMsgDetail.do / bbsMsgFileDown.do 계열) 어댑터.

인천도시공사에서 실측 확인했다(2026-09-26). 목록/상세 모두 평범한 GET + 정적 <a href>
(JS 없음). 목록 페이지의 사람이 보는 notice.jsp URL(?page=N)은 pgno를 무시하고
항상 1페이지만 보여준다(실측 확인) — 실제 페이징은 /main/bbs/bbsMsgList.do?bcd=notice&pgno=<N>
로 해야 한다(화면 페이징 링크가 가리키는 진짜 엔드포인트).

목록: GET bbs/bbsMsgList.do?bcd=<bcd>&pgno=<P>, <p class="title"><a href="bbsMsgDetail.do?msg_seq=<id>&bcd=<bcd>">.
날짜는 "YYYY.MM.DD" 형식(점 구분).

상세: GET bbs/bbsMsgDetail.do?msg_seq=<id>&bcd=<bcd>. 첨부는
<a href="bbsMsgFileDown.do?bcd=<bcd>&msg_seq=<id>&fileno=<n>"><img alt="ext"/> 파일명.ext</a>
<span class="byte">[크기]</span> — byte 크기는 <a> 밖 형제 span이라 파일명에 안 섞인다.

City.boards 항목 형식: {"name": "공지사항", "bcd": "notice"}
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

_DATE_CELL_RE = re.compile(r"^\d{4}\.\d{1,2}\.\d{1,2}$")
_NOTICE_NO_RE = re.compile(r"(공고|고시)\s*제\s*\d{4}\s*[-–]\s*\d+\s*호")


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    list_url = urljoin(base_url, "/main/bbs/bbsMsgList.do")
    resp = session.get(list_url, params={"bcd": board["bcd"], "pgno": page_index}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for li in soup.select("div.board_list ul.generalList > li"):
        title_p = li.find("p", class_="title")
        a_tag = title_p.find("a") if title_p else None
        if a_tag is None:
            continue
        title = a_tag.get_text(strip=True)
        detail_url = urljoin(resp.url, a_tag.get("href", ""))

        texts = [el.get_text(strip=True) for el in li.select("li")]
        notice_no = next((t for t in texts if _NOTICE_NO_RE.search(t)), "")
        date_str = next((t for t in texts if _DATE_CELL_RE.match(t)), "")
        post_date = None
        if date_str:
            try:
                post_date = dt.datetime.strptime(date_str, "%Y.%m.%d").date()
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
    # "bcd=file&msg_seq=420" 사이드바 링크가 모든 상세 페이지에 고정으로 붙어 있어
    # (실측 확인 — 이 공지와 무관한 전세임대 안내 링크) div.add_file 안으로 범위를
    # 좁혀야 한다.
    for a in soup.select("div.add_file a[href*='bbsMsgFileDown.do']"):
        name = a.get_text(strip=True)
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": urljoin(resp.url, a.get("href", "")), "ext": ext})
    return attachments
