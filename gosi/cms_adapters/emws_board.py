"""
emws_board.py — "main/emwsWebList.do"/"emwsWebView.do" 게시판(안양시 등,
"EMWS eminwon-web" 계열) 어댑터.

안양시에서 실측 확인했다(2026-09-26). 사이트 자체가 레거시 암호화 스위트만
지원해(실측: SSLV3_ALERT_HANDSHAKE_FAILURE) 익산시와 같은 방식으로 SECLEVEL만
완화하고 인증서 검증은 그대로 유지한다(검증을 끈 게 아니라 완성한 것).

목록: GET main/emwsWebList.do?key=<key>&searchGosiSe=<코드>&pageIndex=<P>,
<table class="p-table"><td class="text_left"><a href="./emwsWebView.do?...
&regiNo=<id>&...">제목</a>. 고시공고번호 칸은 같은 행의 앞쪽 <td>.

상세: 목록 href를 그대로 GET(상대경로). 첨부는
<a href="/downloadGosiFile.do?regiNo=<id>&sfn=<file>"><span class="p-icon...">
hwpx 파일</span>실제파일명.ext<i .../></a> — 앞의 아이콘 <span>을 떼어내야
실제 파일명만 남는다(실측 확인, ansan_bbs.py의 같은 문제와 유사).

City.boards 항목 형식: {"name": "고시공고", "key": "4101", "search_gosi_se": "01,03,04"}
"""

import copy
import datetime as dt
import re
import ssl
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

_DATE_CELL_RE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")
_NOTICE_NO_RE = re.compile(r"(공고|고시)\s*제\s*\d{4}\s*[-–]\s*\d+\s*호")


class _LegacyTLSAdapter(HTTPAdapter):
    """안양시 서버가 최신 OpenSSL 기본 보안수준의 암호화 스위트를 지원하지 않는다
    (실측: SSLV3_ALERT_HANDSHAKE_FAILURE). 암호화 스위트만 SECLEVEL=1로 완화하고
    인증서 검증(cert_verify)은 그대로 상속해 유지한다."""

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def prepare_session(session, city):
    if not getattr(session, "_emws_legacy_mounted", False):
        session.mount("https://", _LegacyTLSAdapter())
        session._emws_legacy_mounted = True


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(
        base_url,
        params={"key": board["key"], "searchGosiSe": board["search_gosi_se"], "pageIndex": page_index},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    rows = []
    for tr in soup.select("table.p-table tbody tr"):
        tds = tr.find_all("td")
        if len(tds) < 4:
            continue
        a_tag = tds[1].find("a")
        if a_tag is None:
            continue
        title = re.sub(r"\s+", " ", a_tag.get_text(strip=True)).strip()
        detail_url = urljoin(resp.url, a_tag.get("href", ""))

        texts = [re.sub(r"\s+", " ", td.get_text(strip=True)).strip() for td in tds]
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
    for a in soup.select("a[href*='/downloadGosiFile.do']"):
        a_copy = copy.deepcopy(a)
        icon_span = a_copy.find("span")
        if icon_span is not None:
            icon_span.extract()
        name = re.sub(r"\s+", " ", a_copy.get_text(strip=True)).strip()
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": urljoin(resp.url, a.get("href", "")), "ext": ext})
    return attachments
