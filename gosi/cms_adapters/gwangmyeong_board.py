"""
gwangmyeong_board.py — 광명시청 "openworks4" 계열 게시판(BD_selectNftcBbsList.do/
BD_selectNftcBbsDetail.do) 어댑터.

광명시에서 실측 확인했다(2026-09-27). 목록은 평범한 <table>이지만 제목 칸에 class
표식이 없고 <a href="javascript:void(0);" onclick="opDetail('<id>')">뿐이다 —
opDetail()의 실제 구현(페이지 인라인 스크립트)이 "BD_selectNftcBbsDetail.do?
q_nftcBbsCode=1001&q_nftcBbsMgtno=<id>&q_currPage=1"로 이동하는 것을 확인해 그 URL을
직접 조립한다. 페이지네이션은 "q_currPage".

첨부파일은 AJAX가 아니라 상세 페이지 자체의 인라인 <script> 안에 이미
"fileList.push({"sysFileNm":..,"fileNm":..,"filePath":..})" 형태의 JSON으로 박혀
있다(실측 확인) — 정규식으로 그대로 파싱한다. 다운로드는 <form id="fileDown"
method="post" action="https://eminwon.gm.go.kr/emwp/jsp/ofr/FileDownNew.jsp">로 POST
제출하는 화면이지만, 다른 eminwon 계열과 마찬가지로 같은 파라미터를 쿼리스트링으로
실은 GET도 그대로 받아준다(부여군 등에서 이미 확인된 패턴과 동일).

City.boards 항목 형식: {"name": "고시공고", "nftc_bbs_code": 1001}
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
_NOTICE_NO_RE = re.compile(r"(공고|고시)\s*제\s*\d{4}\s*[-–]\s*\d+\s*호")
_OPDETAIL_RE = re.compile(r"opDetail\(\s*'(\d+)'\s*\)")
_FILEPUSH_RE = re.compile(
    r'fileList\.push\(\s*\{\s*'
    r'"sysFileNm"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*'
    r'"fileNm"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*'
    r'"filePath"\s*:\s*"((?:[^"\\]|\\.)*)"',
    re.DOTALL,
)


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(
        base_url,
        params={"q_nftcBbsCode": board["nftc_bbs_code"], "q_currPage": page_index},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if table is None:
        return []

    rows = []
    for tr in table.select("tbody tr"):
        a = None
        for cand in tr.find_all("a"):
            if _OPDETAIL_RE.search(cand.get("onclick", "")):
                a = cand
                break
        if a is None:
            continue
        m = _OPDETAIL_RE.search(a.get("onclick", ""))
        detail_url = urljoin(
            resp.url,
            f"BD_selectNftcBbsDetail.do?q_nftcBbsCode={board['nftc_bbs_code']}"
            f"&q_nftcBbsMgtno={m.group(1)}&q_currPage=1",
        )
        title = re.sub(r"\s+", " ", a.get_text(strip=True)).strip()

        texts = [td.get_text(strip=True) for td in tr.find_all("td")]
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
    """상세 페이지의 첨부파일 [{"name","url","ext"}, ...] (다운로드는 하지 않음).
    fileList.push({...}) 인라인 스크립트에서 직접 파싱한다(AJAX 아님, 실측 확인)."""
    resp = session.get(detail_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    attachments = []
    for m in _FILEPUSH_RE.finditer(resp.text):
        sys_file_nm, file_nm, file_path = m.groups()
        if not file_nm:
            continue
        ext = file_nm.rsplit(".", 1)[-1].lower() if "." in file_nm else ""
        url = (
            "https://eminwon.gm.go.kr/emwp/jsp/ofr/FileDownNew.jsp"
            f"?user_file_nm={quote(file_nm)}&sys_file_nm={quote(sys_file_nm)}&file_path={quote(file_path)}"
        )
        attachments.append({"name": file_nm, "url": url, "ext": ext})
    return attachments
