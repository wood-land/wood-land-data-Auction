"""
namdong_board.py — "main/eminwon/eminwonAnnounceList.do" 게시판(인천 남동구) 어댑터.

남동구에서 실측 확인했다(2026-09-26). 목록/상세 모두 평범한 GET + 정적 <a href>
(JS 없음) — <table>이 아니라 <ul class="etcList"><li> 레이아웃이다. 페이지네이션
파라미터는 pgno(인천도시공사와 같은 패턴).

첨부는 href 자체가 이미 완성된 eminwon.namdong.go.kr FileDownNew.jsp GET URL이지만,
그 안의 user_file_nm 쿼리파라미터 값이 (밀양시·함안군과 달리) 암호화된 토큰이라
실제 파일명이 아니다(실측 확인) — eminwon_list.py의 일반 로직을 그대로 쓰면 안 되고,
링크 텍스트를 파일명으로 써야 한다.

목록: GET main/eminwon/eminwonAnnounceList.do?pgno=<P>, <li><p class="tit">
<a href="/main/eminwon/eminwonAnnounceDetail.do?mgt_no=<id>">.

City.boards 항목 형식: {"name": "고시공고"}
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

_DATE_RE = re.compile(r"작성일\s*:\s*(\d{4}-\d{1,2}-\d{1,2})")
_NOTICE_NO_RE = re.compile(r"(공고|고시)\s*제\s*\d{4}\s*[-–]\s*\d+\s*호")


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(base_url, params={"pgno": page_index}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for li in soup.select("div.board_list ul.etcList > li"):
        title_p = li.find("p", class_="tit")
        a_tag = title_p.find("a") if title_p else None
        if a_tag is None:
            continue
        title = a_tag.get_text(strip=True)
        detail_url = urljoin(resp.url, a_tag.get("href", ""))

        part_p = li.find("p", class_="part")
        notice_no = part_p.get_text(strip=True).strip("[]") if part_p else ""
        if not _NOTICE_NO_RE.search(notice_no):
            notice_no = ""
        info_text = li.get_text(" ", strip=True)
        m = _DATE_RE.search(info_text)
        date_str = m.group(1) if m else ""
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
    for a in soup.select("div.add_file a[href*='FileDown']"):
        # 링크 텍스트에 아이콘 alt와 파일명이 섞여 있을 수 있어(예: "pdf 파일명.pdf")
        # <img alt>를 뺀 순수 텍스트만 쓴다.
        name = re.sub(r"\s+", " ", a.get_text(strip=True)).strip()
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": urljoin(resp.url, a.get("href", "")), "ext": ext})
    return attachments
