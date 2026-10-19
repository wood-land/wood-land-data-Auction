"""
chungnam_do_board.py — "cnportal/province/province/list.do" 게시판(충청남도청) 어댑터.

충청남도청에서 실측 확인했다(2026-09-26). 뒷단은 인천광역시청과 같은
SAPGosiBizProcess.do(minwon.chungnam.go.kr)이지만, 화면 자체는 이 cnportal
프론트가 감싸고 있고 view.do/download.jsp로 직접 GET된다(law.md 3-2 — 뒷단이
같다고 프론트 마크업까지 같다고 가정하지 않고 별도 어댑터로 뒀다).

검색 폼이 날짜범위(sdate/edate)를 필수로 요구한다(JS fnSearch()의 alert 확인) —
GET에 안 실어도 서버가 기본값으로 응답은 하지만, 안전하게 "오늘로부터 1년 전 ~ 오늘"을
항상 실어 보낸다.

목록: GET list.do?menuNo=500487&pageIndex=<P>&sdate=<1년전>&edate=<오늘>,
<td class="td-subj"><a href="view.do?nttId=<id>&menuNo=500487&pageIndex=1">.

상세: GET view.do?nttId=<id>&menuNo=500487&pageIndex=1. 첨부는
<li>파일명<a class="ico_file" href="https://minwon.chungnam.go.kr/.../download.jsp?...">
내려받기</a>...</li> — 파일명은 li의 첫 텍스트 노드에 있다(내려받기/미리보기/미리듣기
링크와 섞이지 않게 li.contents[0]만 취한다).

City.boards 항목 형식: {"name": "고시공고", "menu_no": "500487"}
"""

import datetime as dt
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString

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
    today = dt.date.today()
    start = today - dt.timedelta(days=365)
    list_url = base_url.replace("view.do", "list.do")
    resp = session.get(
        list_url,
        params={
            "menuNo": board["menu_no"],
            "pageIndex": page_index,
            "sdate": start.isoformat(),
            "edate": today.isoformat(),
        },
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for tr in soup.select("table tbody tr"):
        subject_td = tr.find("td", class_="td-subj")
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
    for a in soup.select("ul.view-file-list li a.ico_file"):
        li = a.find_parent("li")
        first_text = next((c for c in li.contents if isinstance(c, NavigableString) and c.strip()), None)
        name = first_text.strip() if first_text else a.get_text(strip=True)
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": urljoin(resp.url, a.get("href", "")), "ext": ext})
    return attachments
