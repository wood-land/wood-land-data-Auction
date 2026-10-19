"""
ish_board.py — "lay2/program/.../list.do?multi_itm_seq=" 게시판(sh서울주택도시공사
CMS, getDetailView/이노릭스 계열) 어댑터.

sh서울주택도시공사에서 실측 확인했다(2026-09-26). 목록은 GET으로 그대로 재현되지만
(getDetailView()는 <form name="mainform"> POST 제출), 상세는 POST가 필요하다
(GET으로는 페이지가 다르게 렌더링됨, 실측 확인).

첨부파일은 "이노릭스"(Innorix) 라는 자체 다운로드 클라이언트 UI를 쓰지만, 실제로는
JS 변수 initParam.downList(JSON, brdId/seq/fileTp/fileSeq/oriFileNm)를 읽어
`/com/file/innoFD.do?brdId=<>&seq=<>&fileTp=<>&fileSeq=<>` 로 평범한 GET 스트리밍
다운로드를 한다(innorix.config.js의 downloadType:"stream" 분기, 실측 확인 —
플러그인 설치 없이 그대로 GET된다).

City.boards 항목 형식: {"name": "공고", "multi_itm_seq": "32"}
"""

import datetime as dt
import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

_DATE_CELL_RE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")
_NOTICE_NO_RE = re.compile(r"(공고|고시)\s*제\s*\d{4}\s*[-–]\s*\d+\s*호")
_GETDETAIL_RE = re.compile(r"getDetailView\(\s*'([^']*)'\s*\)")
_DOWNLIST_RE = re.compile(r"initParam\.downList\s*=\s*(\[.*?\])\s*;")


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    list_url = base_url.replace("view.do", "list.do")
    resp = session.get(
        list_url,
        params={"multi_itm_seq": board["multi_itm_seq"], "page": page_index},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for tr in soup.select("table tbody tr"):
        a_tag = tr.find("a", onclick=lambda v: bool(v) and _GETDETAIL_RE.search(v))
        if a_tag is None:
            continue
        m = _GETDETAIL_RE.search(a_tag.get("onclick", ""))
        seq = m.group(1)
        title = a_tag.get_text(strip=True)

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

        detail_url = f"{list_url.rsplit('/', 1)[0]}/view.do#ish-seq={seq}&multi_itm_seq={board['multi_itm_seq']}"
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

    detail_url은 (POST 전용이라) 합성 키다 — view.do 경로와 seq/multi_itm_seq를
    복원해 POST로 상세를 연 뒤, initParam.downList JS 변수를 파싱한다."""
    view_url, frag = detail_url.split("#ish-seq=")
    seq, multi_itm_seq = frag.split("&multi_itm_seq=")
    data = {
        "page": "1",
        "seq": seq,
        "itm_seq_1": "0",
        "multi_itm_seq": multi_itm_seq,
        "multi_itm_seqsStr": "",
        "isRecrnoti": "",
    }
    resp = session.post(view_url, data=data, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    m = _DOWNLIST_RE.search(resp.text)
    if m is None:
        return []
    down_list = json.loads(m.group(1))

    root = view_url.split("/main/", 1)[0]
    down_url = urljoin(root, "/com/file/innoFD.do")
    attachments = []
    for item in down_list:
        name = item.get("oriFileNm", "")
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        url = (
            f"{down_url}?brdId={item.get('brdId', '')}&seq={item.get('seq', '')}"
            f"&fileTp={item.get('fileTp', '')}&fileSeq={item.get('fileSeq', '')}"
        )
        attachments.append({"name": name, "url": url, "ext": ext})
    return attachments
