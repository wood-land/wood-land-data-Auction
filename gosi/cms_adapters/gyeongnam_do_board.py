"""
gyeongnam_do_board.py — 경상남도청 "고시공고"(index.gyeong?menuCd=DOM_...135003009001) 어댑터.

경상남도청(www.gyeongnam.go.kr)에서 실측 확인했다(2026-09-28). 목록/상세 모두 평범한
GET + 정적 <a href>(JS 없음). 경남의 시·군(창원시 등)이나 이지사이트 계열(board/list.
gyeong?boardId=)과는 다른, "고시공고" 전용 모듈(mode=view&sno=&gosiGbn=)이다.

목록: GET index.gyeong?menuCd=<menuCd>&page=<P>&pageLine=10&conIfmStdt=<시작일>&
conIfmEnddt=<종료일>. 날짜 범위 파라미터를 안 주면 서버가 최근 3개월만 보여주므로 항상
"1년 전 ~ 오늘"을 실어 보낸다(충청남도청 어댑터와 같은 처리). 행은 table.A-13 tbody tr,
제목은 <td class="title"><a>, 번호는 td.num 2번째, 게재일은 td.date("YYYY-MM-DD").

상세: 목록의 href를 그대로 GET. 첨부는 <span class="attach_1"><a class="file"
href="/index.gyeong?contentsSid=...&fn=<파일명>"> — 평범한 GET으로 원본이 내려온다.

City.boards 항목 형식: {"name": "고시공고", "menu_cd": "DOM_000000135003009001"}
"""

import datetime as dt
from urllib.parse import urljoin

from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


def _parse_date(text):
    try:
        return dt.datetime.strptime(text.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    today = dt.date.today()
    resp = session.get(
        base_url,
        params={
            "menuCd": board["menu_cd"],
            "conIfmStdt": (today - dt.timedelta(days=365)).isoformat(),
            "conIfmEnddt": today.isoformat(),
            "pageLine": page_unit,
            "page": page_index,
        },
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for tr in soup.select("table.A-13 tbody tr"):
        title_td = tr.find("td", class_="title")
        a_tag = title_td.find("a") if title_td else None
        if a_tag is None:
            continue
        nums = [td.get_text(strip=True) for td in tr.find_all("td", class_="num")]
        kind, number = (nums + ["", ""])[:2]  # "공고" / "2026-1496"
        date_td = tr.find("td", class_="date")
        date_str = date_td.get_text(strip=True) if date_td else ""
        rows.append(
            {
                "board": board["name"],
                "notice_no": f"{kind} 제{number}호" if kind and number else "",
                "title": a_tag.get_text(strip=True),
                "date": _parse_date(date_str),
                "date_str": date_str,
                "detail_url": urljoin(resp.url, a_tag.get("href", "")),
            }
        )
    return rows


def fetch_attachments(session, detail_url):
    """상세 페이지의 첨부파일 [{"name","url","ext"}, ...] (다운로드는 하지 않음)."""
    resp = session.get(detail_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    attachments = []
    for a in soup.select("span.attach_1 a.file[href*='fn=']"):
        name = a.get_text(strip=True)
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": urljoin(resp.url, a.get("href", "")), "ext": ext})
    return attachments
