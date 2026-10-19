"""
jejusi_board.py — "information/intro/notice.do" 게시판(제주시청) 어댑터.

제주시에서 실측 확인했다(2026-09-26). JS 없이 평범한 GET + 정적 <table>
(사용자 CSV 노트의 "WAF로 직접 확인 불가"는 오판이었다 — 실제로는 그냥
서버 렌더링 페이지다, 진안군·거제시 등과 같은 패턴).

목록: GET information/intro/notice.do?currentPageNo=<P>,
<td class="title"><a href="?mode=detail&ancmnt_pbanc_mng_no=<id>&currentPageNo=1">.
고시공고번호는 <td class="number2">.

상세: 목록 href를 그대로 GET(상대경로). 첨부는
<a href="javascript:goDownLoad('user_file_nm','sys_file_nm','file_path')">파일명</a>
— goDownLoad()의 실제 JS 구현(문서 내 <script> 참고)이 그대로
eminwon.jejusi.go.kr의 GET FileDown.jsp를 호출하므로 그 URL을 직접 구성한다.

City.boards 항목 형식: {"name": "고시공고"}
"""

import datetime as dt
import re
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

_DATE_CELL_RE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")
_GODOWNLOAD_RE = re.compile(r"goDownLoad\(\s*'(.*)'\s*,\s*'(.*)'\s*,\s*'(.*)'\s*\)")
_FILEDOWN_BASE = "https://eminwon.jejusi.go.kr/emwp/jsp/ofr/FileDown.jsp"
_MGT_NO_RE = re.compile(r"ancmnt_pbanc_mng_no=(\d+)")


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(base_url, params={"currentPageNo": page_index}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    rows = []
    for tr in soup.select("div.board-list-default table tbody tr"):
        title_td = tr.find("td", class_="title")
        a_tag = title_td.find("a") if title_td else None
        if a_tag is None:
            continue
        title = re.sub(r"\s+", " ", a_tag.get_text(strip=True)).strip()
        # 원본 HTML이 href의 "&"를 "&amp;"로 이스케이프하지 않아(실측 확인)
        # bs4가 "&currentPageNo"를 "&curren;"(¤ 문자) 엔티티로 잘못 해석해
        # 쿼리스트링이 깨진다 — ancmnt_pbanc_mng_no만 뽑아 직접 URL을 구성한다.
        mgt_no_m = _MGT_NO_RE.search(a_tag.get("href", ""))
        if mgt_no_m is None:
            continue
        detail_url = urljoin(resp.url, f"?mode=detail&ancmnt_pbanc_mng_no={mgt_no_m.group(1)}&currentPageNo=1")

        notice_td = tr.find("td", class_="number2")
        notice_no = notice_td.get_text(strip=True) if notice_td else ""

        date_tds = tr.find_all("td", class_="date")
        date_str = ""
        for td in date_tds:
            text = td.get_text(strip=True)
            if _DATE_CELL_RE.match(text):
                date_str = text
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
    soup = BeautifulSoup(resp.text, "html.parser")
    attachments = []
    for a in soup.find_all("a", href=lambda v: bool(v) and v.startswith("javascript:goDownLoad(")):
        m = _GODOWNLOAD_RE.search(a.get("href", ""))
        if m is None:
            continue
        user_file_nm, sys_file_nm, file_path = m.groups()
        name = re.sub(r"\s+", " ", a.get_text(strip=True)).strip()
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        url = (
            f"{_FILEDOWN_BASE}?user_file_nm={quote(user_file_nm)}"
            f"&sys_file_nm={quote(sys_file_nm)}&file_path={quote(file_path)}"
        )
        attachments.append({"name": name, "url": url, "ext": ext})
    return attachments
