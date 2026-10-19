"""
mcee_board.py — 환경부 유역환경청 통합 게시판(mcee.go.kr, eGovFrame 계열) 어댑터.

금강·한강·낙동강·영산강유역환경청에서 실측 확인했다(2026-09-25). 보상맵 시트의
원래 URL(www.me.go.kr/<gg|hg|ndg|ysg>/web/index.do?menuId=...)은 전부 mcee.go.kr로
301 리다이렉트된다(requests가 자동으로 따라간다) — 같은 통합 포털을 유역청별로
경로만 다르게 쓰는 구조.

목록은 GET index.do?menuId=<M>&pagerOffset=<N*10>으로 그대로 페이지네이션된다
(list.do로 따로 안 가도 됨 — 실측 확인). 마크업은 <table>이 아니라
div.brd_body 아래 <ul>(행) > <li>(칸, class="size5p"/"title"/"size7p"/"size10p")
구조다. 제목 칸의 <a>에는 실제 상세/게시판 식별자(boardId·boardMasterId·menuId)가
전부 들어있어 하드코딩할 필요가 없다.

첨부파일 다운로드는 상세 페이지의 <a onclick="ajaxFileDownLoad(fileId,fileSeq)">를
파싱해 곧바로 POST /file/readDownloadFile.do (fileId+fileSeq)로 받는다 — JS가 먼저
호출하는 readDownloadFile4.do는 조회수 집계용으로 보여 생략해도 다운로드에는
지장이 없다(실측 확인). 사이트 경로 접두사(gg/hg/ndg/ysg)는 상세 URL 자체에서
가져와 쓴다.
"""

import datetime as dt
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

_AJAX_DOWNLOAD_RE = re.compile(r"ajaxFileDownLoad\(\s*'([^']*)'\s*,\s*'([^']*)'\s*\)")
_DATE_RE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    offset = (page_index - 1) * page_unit
    resp = session.get(base_url, params={"pagerOffset": offset}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    brd_body = soup.select_one("div.brd_body")
    if brd_body is None:
        return []
    rows = []
    for ul in brd_body.find_all("ul", recursive=False):
        title_li = ul.select_one("li.title")
        if title_li is None:
            continue
        a = title_li.find("a")
        if a is None or not a.get("href"):
            continue
        detail_url = urljoin(resp.url, a.get("href"))
        span = a.find("span", class_="ellipsis")
        text_el = span or a
        for icon in text_el.select(".brdIcon"):
            icon.decompose()
        title = re.sub(r"\s+", " ", text_el.get_text(strip=True)).strip()

        lis = ul.find_all("li", recursive=False)
        date_str = ""
        for li in lis:
            text = li.get_text(strip=True)
            if _DATE_RE.match(text):
                date_str = text
                break
        post_date = None
        if date_str:
            try:
                post_date = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                pass
        notice_no = lis[0].get_text(strip=True) if lis else ""
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
    """상세 페이지의 첨부파일 [{"name", "url", "ext"}, ...] (다운로드는 하지 않음)."""
    resp = session.get(detail_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    parts = urlsplit(resp.url)
    site_prefix = parts.path.split("/")[1] if len(parts.path.split("/")) > 1 else ""
    download_url = f"{parts.scheme}://{parts.netloc}/{site_prefix}/file/readDownloadFile.do"

    attachments = []
    for a in soup.find_all("a", href=True):
        m = _AJAX_DOWNLOAD_RE.search(a.get("onclick", "") + a.get("href", ""))
        if not m:
            continue
        file_id, file_seq = m.groups()
        name = re.sub(r"^[★\s]+", "", a.get_text(strip=True))
        name = re.sub(r"\s*\(\d+(\.\d+)?\s*[kKmM]?[bB]\)\s*$", "", name).strip()
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append(
            {
                "name": name,
                "url": f"{download_url}?fileId={file_id}&fileSeq={file_seq}",
                "ext": ext,
                "_dl_action": download_url,
                "_dl_data": {"fileId": file_id, "fileSeq": file_seq},
            }
        )
    return attachments


def download_attachment(session, attachment):
    resp = session.post(attachment["_dl_action"], data=attachment["_dl_data"], headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.content
