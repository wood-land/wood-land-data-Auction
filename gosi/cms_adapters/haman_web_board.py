"""
haman_web_board.py — "<번호>/<번호>.web?amode=view&..." 게시판(함안군 등,
list1f1t3i1 스킨) 어댑터.

함안군에서 실측 확인했다(2026-09-26). 목록/상세 모두 평범한 GET + 정적 <a href>
(JS 없음) — <table>이 아니라 <ul class="lst1"><li class="li1"> 레이아웃이다.
첨부는 밀양시와 똑같은 GET 방식(이미 완성된 eminwon.*.go.kr FileDown.jsp GET URL)
이라 eminwon_list.py의 fetch_attachments를 그대로 가져다 쓴다(law.md 3-2 — 목록
마크업은 다르지만 실제로 같다고 확인된 첨부 다운로드 부분만 재사용한다).

목록: GET <path>.web?cpage=<P>, <li class="li1"><a href="?amode=view&<id 파라미터>&">
<strong class="t1">제목</strong><i class="wrap1t3"><span class="t3">고시번호 : ...</span>
<span class="t3">등록일 : YYYY-MM-DD</span>...</i></a>. id 파라미터 이름은 함안군·거제·
창녕·하동·진주·김해·합천·남해·통영은 not_ancmt_mgt_no=, 사천·삼척은 mgtNo=로 갈린다
(실측 확인, 2026-09-28) — 그래서 공통으로 항상 붙는 "amode=view"로 항목을 찾는다.

사천·삼척은 span.t3에 "등록일 : " 라벨 없이 날짜 하나만 담겨 있고(예: "2026-09-23"),
고시번호도 span.t3가 아니라 제목 앞에 "[사천시 공고 제2026-1506호]"처럼 대괄호로
붙어 나온다(실측 확인, 2026-09-28) — 라벨 있는 형식을 먼저 찾고 없으면 "그 칸
전체가 날짜뿐인" 형식으로, 고시번호도 span.t3에서 못 찾으면 제목 텍스트에서 찾는다.

City.boards 항목 형식: {"name": "고시공고"}
"""

import datetime as dt
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from cms_adapters.eminwon_list import fetch_attachments  # noqa: F401

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

_DATE_RE = re.compile(r"등록일\s*:\s*(\d{4}-\d{1,2}-\d{1,2})")
_PLAIN_DATE_RE = re.compile(r"^(\d{4}-\d{1,2}-\d{1,2})$")
_NOTICE_NO_RE = re.compile(r"(공고|고시)\s*제\s*\d{4}\s*[-–]\s*\d+\s*호")


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(base_url, params={"cpage": page_index}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for li in soup.select("ul.lst1 > li.li1"):
        a_tag = li.find("a", href=re.compile(r"amode=view"))
        if a_tag is None:
            continue
        title_el = a_tag.select_one("strong.t1")
        title = title_el.get_text(strip=True) if title_el else a_tag.get_text(strip=True)
        detail_url = urljoin(resp.url, a_tag.get("href", ""))

        meta_texts = [span.get_text(strip=True) for span in a_tag.select("span.t3")]
        notice_no = next((t for t in meta_texts if _NOTICE_NO_RE.search(t)), "")
        if not notice_no:
            m_no = _NOTICE_NO_RE.search(title)
            notice_no = m_no.group(0) if m_no else ""
        date_str = ""
        for t in meta_texts:
            m = _DATE_RE.search(t)
            if m:
                date_str = m.group(1)
                break
        if not date_str:
            for t in meta_texts:
                m = _PLAIN_DATE_RE.match(t)
                if m:
                    date_str = m.group(1)
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
