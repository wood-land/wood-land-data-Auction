"""
notice_bbsgubun.py — "notice/notice.do?bbsgubun=" 게시판(setView/fn_egov_downFile 계열) 어댑터.

전북개발공사에서 실측 확인했다(2026-09-26). std_ezweb.py와 같은 전자정부
표준프레임워크 계열이지만 URL/파라미터 규칙이 다르다(selectBbsNttList.do가 아니라
notice.do?bbsgubun=<N>, 첨부 다운로드는 downloadBbsFile.do가 아니라
/cmm/fms/FileDown.do?atchFileId=<id>&fileSn=<n>) — 같은 "표준프레임워크"라는 것만으로
같은 어댑터를 쓸 수 없었다(law.md 3-2, URL 모양이 같다고 같은 백엔드라고 가정하지 않는다).

목록: GET notice.do?bbsgubun=<N>&pageIndex=<P> (실측 확인 — 화면의 onclick은 POST로
페이지를 넘기지만, 그냥 GET 쿼리스트링으로도 페이지별 내용이 실제로 달라진다).
제목 칸은 <td class="tdl"><a href="javascript:setView('<nttId>')">.

상세: 목록의 setView()는 JS로 <form name="frm">을 POST 제출한다 — GET으로는 상세
본문(첨부파일 등)이 나오지 않는다(실측 확인). 그래서 상세는 form의 hidden input
전체를 그대로 읽어 mode=view, nttId=<id>로 POST한다.

서버 TLS가 최신 클라이언트 기본 cipher와 handshake가 안 돼(SSLV3_ALERT_HANDSHAKE_FAILURE,
실측 확인) cipher suite를 완화한 어댑터(SECLEVEL=1)로 우회한다 — 인증서 검증 자체는
그대로 켜져 있다(검증을 끈 게 아니라 완화한 것뿐).

City.boards 항목 형식: {"name": "보상공고", "bbsgubun": "10"}
"""

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
_SETVIEW_RE = re.compile(r"setView\(\s*'([^']*)'\s*\)")
_DOWNFILE_RE = re.compile(r"fn_egov_downFile\(\s*'([^']*)'\s*,\s*'([^']*)'\s*\)")


class _LegacyTLSAdapter(HTTPAdapter):
    """cipher suite만 완화한다(SECLEVEL=1) — 인증서 검증은 그대로 켠다."""

    def _build_ctx(self):
        ctx = ssl.create_default_context()
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        return ctx

    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = self._build_ctx()
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        kwargs["ssl_context"] = self._build_ctx()
        return super().proxy_manager_for(*args, **kwargs)


def prepare_session(session, city):
    if not getattr(session, "_notice_bbsgubun_legacy_mounted", False):
        session.mount("https://", _LegacyTLSAdapter())
        session._notice_bbsgubun_legacy_mounted = True


def _form_fields(soup):
    """목록 페이지의 <form name="frm"> hidden input을 그대로 읽어 상세 POST에 재사용한다."""
    form = soup.find("form", {"name": "frm"})
    fields = {}
    if form is None:
        return fields
    for inp in form.find_all("input"):
        name = inp.get("name")
        if name:
            fields[name] = inp.get("value", "")
    return fields


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(
        base_url,
        params={"bbsgubun": board["bbsgubun"], "pageIndex": page_index},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    form_fields = _form_fields(soup)
    table = soup.find("table")
    if table is None:
        return []
    rows = []
    for tr in table.select("tbody tr"):
        subject_td = tr.find("td", class_="tdl")
        if subject_td is None:
            continue
        a_tag = subject_td.find("a")
        if a_tag is None:
            continue
        m = _SETVIEW_RE.search(a_tag.get("href", ""))
        if m is None:
            continue
        ntt_id = m.group(1)
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

        detail_url = f"{base_url}#notice_bbsgubun-nttId={ntt_id}"
        rows.append(
            {
                "board": board["name"],
                "notice_no": notice_no,
                "title": title,
                "date": post_date,
                "date_str": date_str,
                "detail_url": detail_url,
                "_ntt_id": ntt_id,
                "_form_fields": form_fields,
            }
        )
    return rows


def fetch_attachments(session, detail_url, _row=None):
    """상세 페이지의 첨부파일 [{"name","url","ext"}, ...] (다운로드는 하지 않음).

    detail_url은 진짜 열리는 URL이 아니라(POST 전용) fetch_list_page가 만든 합성 키다
    — board_crawler.py가 row 전체를 넘기지 않으므로, base_url과 nttId를 그 안에서
    복원해 form_fields 없이 최소 필드로 다시 POST한다."""
    base_url, ntt_id = detail_url.split("#notice_bbsgubun-nttId=")
    list_resp = session.get(base_url, headers=HEADERS, timeout=15)
    list_resp.raise_for_status()
    form_fields = _form_fields(BeautifulSoup(list_resp.text, "html.parser"))
    form_fields["nttId"] = ntt_id
    form_fields["mode"] = "view"

    resp = session.post(urljoin(list_resp.url, "notice.do"), data=form_fields, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    attachments = []
    for a in soup.find_all("a", href=re.compile(r"^javascript:fn_egov_downFile")):
        m = _DOWNFILE_RE.search(a.get("href", ""))
        if m is None:
            continue
        atch_file_id, file_sn = m.groups()
        name = a.get_text(strip=True)
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        url = urljoin(resp.url, f"/cmm/fms/FileDown.do?atchFileId={atch_file_id}&fileSn={file_sn}")
        attachments.append({"name": name, "url": url, "ext": ext})
    return attachments
