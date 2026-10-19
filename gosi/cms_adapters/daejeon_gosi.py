"""
daejeon_gosi.py — 대전광역시청 "고시공고"(drh/drhGosiList.do / drhGosiView.do) 어댑터.

대전광역시청(www.daejeon.go.kr)에서 실측 확인했다(2026-09-28).

목록: GET drhGosiList.do?pageIndex=<P>&conifmstdt=<시작일>&conifmenddt=<종료일>. 날짜 범위를
안 주면 서버가 올해 1/1~12/31만 보여주므로 항상 "1년 전~오늘"을 실어 보낸다(연초에 지난해
공고가 잘리지 않게). 행은 table.board_table_list tbody tr, 칸은 고시공고 번호/제목/담당
부서/게재일자("YYYY.MM.DD"). 제목 링크는 drhGosiView.do?gosigbn=&sno=<sno>&... 인데
링크의 gosigbn이 비어 있다.

상세: gosigbn이 비어 있으면 "페이지가 잘못 요청되었습니다" 오류 페이지(HTTP 200)가 온다
(실측). 공고는 gosigbn=A, 고시는 gosigbn=N 이어야 열리고 목록에는 이 구분이 없어서(글
번호 대소로도 판별 불가) A, N, E, P 순으로 시도해 첫 정상 페이지를 쓴다. 정상 페이지는
오류 페이지(약 3KB)와 크기·내용으로 구분한다.

첨부: 상세의 <a href='javascript:fileDown("<filePath>")'>파일명(크기)</a>. 화면 JS는 폼을
POST(drhGosiFileDownload.do, filePath=<filePath>)하지만 같은 주소에 GET ?filePath=<filePath>
로도 원본이 내려오는 것을 실측 확인해(2026-09-28) 파일별 고유 GET 링크를 그대로 쓴다.

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

_GOSIGBN_CANDIDATES = ("A", "N", "E", "P")
_SNO_RE = re.compile(r"sno=(\d+)")
_FILEDOWN_RE = re.compile(r"fileDown\(\"(.*)\"\)")
_SIZE_SUFFIX_RE = re.compile(r"\s*\(\d+(?:\.\d+)?\s*[KMG]?B\)\s*$", re.I)
_DOWNLOAD_PATH = "/drh/drhGosiFileDownload.do"


def _parse_date(text):
    try:
        return dt.datetime.strptime(text.strip(), "%Y.%m.%d").date()
    except ValueError:
        return None


def _is_error_page(text):
    return "페이지가 잘못 요청" in text


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    today = dt.date.today()
    resp = session.get(
        base_url,
        params={
            "pageIndex": page_index,
            "conifmstdt": (today - dt.timedelta(days=365)).isoformat(),
            "conifmenddt": today.isoformat(),
        },
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for tr in soup.select("table.board_table_list tbody tr"):
        a_tag = tr.select_one("td.title a")
        num_td = tr.select_one("td.num")
        tds = tr.find_all("td")
        if a_tag is None or num_td is None or len(tds) < 4:
            continue
        date_str = tds[-1].get_text(strip=True)
        rows.append(
            {
                "board": board["name"],
                "notice_no": num_td.get_text(strip=True),
                "title": a_tag.get_text(" ", strip=True),
                "date": _parse_date(date_str),
                "date_str": date_str,
                "detail_url": urljoin(resp.url, a_tag.get("href", "")),
            }
        )
    return rows


def _fetch_detail(session, detail_url):
    """gosigbn을 A/N/E/P 순으로 바꿔 가며 정상 상세 페이지 응답을 찾는다(없으면 None)."""
    m = _SNO_RE.search(detail_url)
    if m is None:
        return None
    base = detail_url.split("?", 1)[0]
    for gosigbn in _GOSIGBN_CANDIDATES:
        resp = session.get(
            base, params={"gosigbn": gosigbn, "sno": m.group(1)}, headers=HEADERS, timeout=15
        )
        resp.raise_for_status()
        if not _is_error_page(resp.text):
            return resp
    return None


def fetch_attachments(session, detail_url):
    """상세 페이지의 첨부파일 [{"name","url","ext","_file_path"}, ...] (다운로드는 하지 않음)."""
    resp = _fetch_detail(session, detail_url)
    if resp is None:
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    download_url = urljoin(resp.url, _DOWNLOAD_PATH)
    attachments = []
    for a in soup.select("a[href^='javascript:fileDown']"):
        m = _FILEDOWN_RE.search(a.get("href", ""))
        if m is None:
            continue
        name = _SIZE_SUFFIX_RE.sub("", a.get_text(strip=True))
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": f"{download_url}?filePath={quote(m.group(1))}", "ext": ext})
    return attachments
