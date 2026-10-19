"""
chungbuk_do_board.py — 충청북도청 "고시/공고"(selectGosiPblancList.do) 어댑터.

충청북도청(www.chungbuk.go.kr)에서 실측 확인했다(2026-09-28). 목록/상세 모두 평범한
GET + 정적 <a href>(JS 없음). 같은 도의 시·군(보은군 등)이 쓰는 selectBbsNttList.do
(std_ezweb 계열)와 달리 "고시공고 전용" 화면(selectGosiPblancList.do / View.do)이라
목록 칸 구성(구분 / 고시·공고 번호 / 제목 / 의뢰부서 / 게재일자)이 다르다.

목록: GET selectGosiPblancList.do?key=<key>&pageIndex=<P>&pageUnit=10, 행은
table.p-table tbody tr, 제목은 <td class="p-subject"><a href="./selectGosiPblancView.do?...">,
게재일은 <time datetime="YYYY-MM-DD">.

상세: 목록의 href를 그대로 GET. 첨부는 <div class="attach__item"> 안에
<span class="text"><em>파일명</em></span> + <a class="attach_btn down" href="https://sido.
chungbuk.go.kr/citynet/jsp/cmm/attach/download.jsp?...">(완성된 GET 링크, 세션 불필요).
같은 div의 "미리보기" 링크(a.preview)는 원본 파일이 아니라서 쓰지 않는다.

City.boards 항목 형식: {"name": "고시공고", "key": 422}
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
    resp = session.get(
        base_url,
        params={"key": board["key"], "pageIndex": page_index, "pageUnit": page_unit},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for tr in soup.select("table.p-table tbody tr"):
        subject_td = tr.find("td", class_="p-subject")
        a_tag = subject_td.find("a") if subject_td else None
        if a_tag is None:
            continue
        tds = tr.find_all("td")
        kind = tds[0].get_text(strip=True)  # "고시" / "공고"
        number = tds[1].get_text(strip=True)  # "2026-1378"
        time_el = tr.find("time")
        date_str = (time_el.get("datetime") or time_el.get_text(strip=True)) if time_el else ""
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
    for item in soup.select("div.attach__item"):
        a = item.select_one("a.attach_btn.down")
        name_el = item.select_one("span.text em")
        if a is None or name_el is None:
            continue
        name = name_el.get_text(strip=True)
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": urljoin(resp.url, a.get("href", "")), "ext": ext})
    return attachments
