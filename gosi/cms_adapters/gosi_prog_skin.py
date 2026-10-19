"""
gosi_prog_skin.py — "prog/saeolGosi/.../list.do" 게시판(fn_search_detail/view 계열) 어댑터.

대전 중구·유성구·서구, 홍성군·서천군·예산군에서 실측 확인했다(2026-09-25) — 같은
"prog/saeolGosi" URL이라도 백엔드(NTIS eMinwon)는 같지만 프론트엔드 목록 마크업이
지자체마다 4가지로 갈렸다(law.md 3-2, URL 모양이 같다고 같은 마크업이라고 가정하지
않는다 — _find_mgt_no_and_title() 참고).

목록: <table>의 각 행에서 제목/공고관리번호를 4가지 방식 중 하나로 찾는다
(_find_mgt_no_and_title 참고). 어느 방식이든 결국 같은 view.do?notAncmtMgtNo=<id>
로 귀결된다(실측 확인) — GET으로 그대로 열린다(JS의 document.폼.submit()은 POST지만
GET으로도 동일하게 열림).

첨부파일: <form name="fileForm">의 action이 이미 채워져 있는 곳도 있고(대전 중구·
홍성군: "https://eminwon.<도메인>/emwp/jsp/ofr/FileDown.jsp"), 정적 action은
비어 있고 JS(fn_egov_downFile)가 클릭 시점에 jQuery로 동적으로 채우는 곳도 있다
(대전 유성구) — 두 경우 모두 결국 같은 eminwon.<도메인> 규칙으로 귀결되어, action이
비어 있으면 그 규칙으로 대체한다. 파일명은 이중 인코딩한다
(encodeURI(encodeURIComponent(fileNm))) — 그대로 재현하지 않으면 서버가 파일을
못 찾는다.
"""

import datetime as dt
import re
import ssl
from urllib.parse import quote, urljoin, urlsplit

from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


class _LegacyTLSAdapter(HTTPAdapter):
    """암호화 스위트만 SECLEVEL=1로 완화한다(std_ezweb.py의 동해시 대응과 동일한
    조치). 인증서 검증 자체는 그대로 켜져 있다."""

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


# 강원 고성군(gwgs.go.kr)은 최신 OpenSSL 기본 보안수준의 암호화 스위트를 지원하지
# 않는다(실측: SSLV3_ALERT_HANDSHAKE_FAILURE, 2026-09-28).
_SECLEVEL_HOSTS = {"www.gwgs.go.kr"}


def prepare_session(session, city):
    """board_crawler.run_city가 지자체별 세션을 만든 직후 한 번 호출한다."""
    host = urlsplit(city.base_url).netloc
    if host in _SECLEVEL_HOSTS and not getattr(session, f"_legacy_tls_{host}", False):
        session.mount(f"https://{host}", _LegacyTLSAdapter())
        setattr(session, f"_legacy_tls_{host}", True)

_DETAIL_RE = re.compile(r"fn_search_(?:detail|view)\(\s*'([^']*)'\s*\)")
_NOTICE_NO_RE = re.compile(r"(공고|고시)\s*제\s*\d{4}\s*[-–]\s*\d+\s*호")
_DATE_CELL_RE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")
_DOWN_FILE_RE = re.compile(r"fn_egov_downFile\(\s*'(.*)'\s*,\s*'(.*)'\s*,\s*'(.*)'\s*\)")


def _eminwon_host(url):
    netloc = urlsplit(url).netloc
    if netloc.startswith("www."):
        netloc = netloc[len("www."):]
    return "eminwon." + netloc


def _double_encode(text):
    """JS의 encodeURI(encodeURIComponent(text))를 그대로 재현한다."""
    first = quote(text, safe="-_.!~*'()")
    return first.replace("%", "%25")


def _find_mgt_no_and_title(tr):
    """행에서 (공고관리번호, 제목)을 찾는다. 네 가지 마크업을 모두 지원한다:
    1. <a onclick="fn_search_detail/view('<id>')">제목</a> (대전 중구·유성구·홍성군)
    2. <td data-key-no="<id>"><button class="button_view"><strong class=
       "bbs-subject-txt">제목</strong></button></td> (대전 서구)
    3. <a data-not-ancmt-mgt-no="<id>">제목</a> (서천군)
    4. <button class="button_view" data-list-no="<id>"><strong class=
       "bbs-subject-txt">제목</strong></button> (예산군 — 전부 실측 확인)"""
    a = tr.find("a", onclick=lambda v: bool(v) and _DETAIL_RE.search(v))
    if a is not None:
        m = _DETAIL_RE.search(a.get("onclick", ""))
        title = re.sub(r"\s+", " ", a.get_text(strip=True)).strip()
        return m.group(1), title

    key_td = tr.find(lambda t: t.name == "td" and t.get("data-key-no"))
    if key_td is not None:
        title_el = key_td.select_one(".bbs-subject-txt") or key_td.find("button")
        title = re.sub(r"\s+", " ", title_el.get_text(strip=True)).strip() if title_el else ""
        return key_td.get("data-key-no"), title

    mgt_a = tr.find(lambda t: t.name == "a" and t.get("data-not-ancmt-mgt-no"))
    if mgt_a is not None:
        title = re.sub(r"\s+", " ", mgt_a.get_text(strip=True)).strip()
        return mgt_a.get("data-not-ancmt-mgt-no"), title

    list_no_btn = tr.find(lambda t: t.name == "button" and t.get("data-list-no"))
    if list_no_btn is not None:
        title_el = list_no_btn.select_one(".bbs-subject-txt") or list_no_btn
        title = re.sub(r"\s+", " ", title_el.get_text(strip=True)).strip()
        return list_no_btn.get("data-list-no"), title

    # 천안시: onclick/data 속성 없이 <td class="subject"><a href=".../view.do?
    # notAncmtMgtNo=<id>">제목</a></td>처럼 href 자체가 이미 완성된 링크다(실측
    # 확인, 2026-09-28) — 페이지 안에 fn_search_view() 정의는 있지만 실제로는
    # 어디서도 호출되지 않는 죽은 코드였다.
    href_a = tr.find("a", href=lambda v: bool(v) and "notAncmtMgtNo=" in v)
    if href_a is not None:
        m = re.search(r"notAncmtMgtNo=(\w+)", href_a.get("href", ""))
        if m is not None:
            title = re.sub(r"\s+", " ", href_a.get_text(strip=True)).strip()
            return m.group(1), title

    return None


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(base_url, params={"pageIndex": page_index}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if table is None:
        return []
    rows = []
    for tr in table.find_all("tr"):
        found = _find_mgt_no_and_title(tr)
        if found is None:
            continue
        mgt_no, title = found

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

        parts = urlsplit(base_url)
        view_path = parts.path.rsplit("/", 1)[0] + "/view.do"
        detail_url = urljoin(resp.url, f"{view_path}?notAncmtMgtNo={mgt_no}")
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
    """상세 페이지의 첨부파일 [{"name","url","ext","_dl_action","_dl_data"}, ...] (다운로드는 하지 않음)."""
    resp = session.get(detail_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    form = soup.find("form", {"name": "fileForm"})
    if form is None:
        return []
    raw_action = form.get("action") or ""
    # 일부 사이트(대전 유성구)는 정적 action이 비어 있고 JS가 클릭 시점에
    # fn_egov_downFile 안에서 동적으로 세팅한다(실측 확인, 2026-09-25) — 그 경우
    # eminwon.<도메인>/emwp/jsp/ofr/FileDown.jsp 로 대체한다(saeol_gosi와 같은 규칙).
    action = urljoin(resp.url, raw_action) if raw_action else f"https://{_eminwon_host(resp.url)}/emwp/jsp/ofr/FileDown.jsp"

    attachments = []
    for a in soup.find_all("a"):
        m = _DOWN_FILE_RE.search(a.get("href", "") + a.get("onclick", ""))
        if not m:
            continue
        user_name, sys_name, file_path = m.groups()
        ext = user_name.rsplit(".", 1)[-1].lower() if "." in user_name else ""
        post_data = {
            "user_file_nm": _double_encode(user_name),
            "sys_file_nm": sys_name,
            "file_path": file_path,
        }
        attachments.append(
            {"name": user_name, "url": action, "ext": ext, "_dl_action": action, "_dl_data": post_data}
        )
    return attachments


def download_attachment(session, attachment):
    resp = session.post(attachment["_dl_action"], data=attachment["_dl_data"], headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.content
