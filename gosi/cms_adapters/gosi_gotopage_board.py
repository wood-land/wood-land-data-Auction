"""
gosi_gotopage_board.py — "?mode=V&mng_no=<id>" 상세 + "?GotoPage=<N>" 페이징 게시판
(충남 지역정보화 공통 스킨 계열) 어댑터.

계룡시(gyeryong.go.kr)·부여군(buyeo.go.kr)·영동군(yd21.go.kr)에서 실측 확인했다
(2026-09-27). 목록은 JS 없이 평범한 서버 렌더링 <table>이지만, 지자체마다 <td>
class 이름이 다르다(계룡시는 class="text-left", 부여군은 class="ta_l", 영동군은
class="title") — 그래서 class가 아니라 "href에 상세 id 파라미터가 있는 <a>"로
제목 칸을 찾는다. id 파라미터 이름도 계룡시/부여군은 mng_no, 영동군은 no로 갈려서
둘 다 인식한다. 날짜 칸도 class가 다르고("date"는 공통이지만 게재기간 칸도 같은
class를 쓰는 곳이 있어), 정확히 "YYYY-MM-DD" 전체와 일치하는 칸만 골라 게재기간
(범위) 칸을 자동으로 걸러낸다.

첨부파일 다운로드 방식이 지자체마다 갈린다(실측 확인):
  - 계룡시: <a href="/_prog/dn00/?file_id=<id>" title="파일명.ext 다운로드">
    형태의 이미 완성된 GET 링크. href를 그대로 쓰고 title에서 " 다운로드" 접미사를
    떼어 파일명으로 쓴다.
  - 영동군: <a href="?mode=D&no=<id>&file_id=<fid>" title="파일명.ext">
    형태의 이미 완성된 GET 링크(상세 페이지 전용 — 목록 행의 onclick="DownloadList(...)"
    JS는 무시하고, 상세 페이지에 이미 완성돼 있는 이 링크를 쓴다).
  - 부여군: <a onclick="fn_saeol_downFile('파일명','시스템파일명','경로')"> — JS
    구현(<사이트>/_prog/saeol_gosi/js/script.js)은 document.fileForm을 채워
    "https://eminwon.<도메인>/emwp/jsp/ofr/FileDown.jsp"로 <form method="post">
    제출하지만, 실측 결과 이 JSP는 같은 파라미터(user_file_nm/sys_file_nm/file_path)를
    쿼리스트링으로 실은 평범한 GET도 그대로 받아준다(다른 eminwon 계열 사이트와 동일한
    동작, 2026-09-27 실측: POST는 "지정한 파일을 찾을수 없습니다" 오류였지만 GET은
    정상적으로 파일을 내려받았다) — 그래서 POST 폼을 흉내 내지 않고 GET으로 통일한다.
    같은 스크립트의 fn_bbsGosi_downFile(...)은 자기 사이트의
    "/_prog/saeol_gosi/download.php"를 쓰는데, 이건 실측하지 못해 우선 같은 GET
    방식을 시도하도록 남겨 둔다(다른 지자체에서 나오면 재검증 필요).

City.boards 항목 형식: {"name": "고시공고"}
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


# 영동군(www.yd21.go.kr)은 최신 OpenSSL 기본 보안수준의 암호화 스위트를 지원하지
# 않는다(실측: SSLV3_ALERT_HANDSHAKE_FAILURE, 2026-09-27).
_SECLEVEL_HOSTS = {"www.yd21.go.kr"}


def prepare_session(session, city):
    """board_crawler.run_city가 지자체별 세션을 만든 직후 한 번 호출한다."""
    host = urlsplit(city.base_url).netloc
    if host in _SECLEVEL_HOSTS and not getattr(session, f"_legacy_tls_{host}", False):
        session.mount(f"https://{host}", _LegacyTLSAdapter())
        setattr(session, f"_legacy_tls_{host}", True)

_DATE_CELL_RE = re.compile(r"^\d{4}[.\-]\d{1,2}[.\-]\d{1,2}$")
# 금산군은 등록일 칸이 따로 없이 "게재기간" 범위(YYYY-MM-DD~YYYY-MM-DD)만 있다
# (실측 확인, 2026-09-28) — 시작일을 등록일 대신 쓴다.
_DATE_RANGE_RE = re.compile(r"^(\d{4}[.\-]\d{1,2}[.\-]\d{1,2})\s*~\s*\d{4}[.\-]\d{1,2}[.\-]\d{1,2}$")
_NOTICE_NO_RE = re.compile(r"(공고|고시)\s*제\s*\d{4}\s*[-–]\s*\d+\s*호")
_DETAIL_ID_RE = re.compile(r"[?&](mng_no|no)=([^&]+)")
_SAEOL_DOWNFILE_RE = re.compile(r"fn_saeol_downFile\(\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*\)")
_BBSGOSI_DOWNFILE_RE = re.compile(r"fn_bbsGosi_downFile\(\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*\)")
_DN00_RE = re.compile(r"/_prog/dn00/\?file_id=")
_MODE_D_RE = re.compile(r"\?mode=D&(?:amp;)?no=")


def _parse_post_date(date_str):
    for fmt in ("%Y-%m-%d", "%Y.%m.%d"):
        try:
            return dt.datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def _eminwon_host(url):
    netloc = urlsplit(url).netloc
    if netloc.startswith("www."):
        netloc = netloc[len("www."):]
    return "eminwon." + netloc


def _soup(resp):
    # 부여군(buyeo.go.kr) 등은 응답 헤더에 charset이 없어(Content-Type: text/html뿐)
    # requests가 기본값 ISO-8859-1로 잘못 추측한다 — 실제 페이지는 <meta charset="utf-8">
    # (실측 확인, 2026-09-27). apparent_encoding(콘텐츠 기반 추정)으로 바로잡는다.
    if resp.encoding is None or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding
    return BeautifulSoup(resp.text, "html.parser")


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(base_url, params={"GotoPage": page_index}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = _soup(resp)
    table = soup.find("table")
    if table is None:
        return []

    rows = []
    for tr in table.select("tbody tr"):
        a, m = None, None
        for cand in tr.find_all("a", href=True):
            found = _DETAIL_ID_RE.search(cand.get("href", ""))
            if found:
                a, m = cand, found
                break
        if a is None:
            continue
        detail_url = urljoin(resp.url, f"?mode=V&{m.group(1)}={m.group(2)}")
        title = re.sub(r"\s+", " ", a.get_text(strip=True)).strip()

        tds = tr.find_all("td")
        texts = [td.get_text(strip=True) for td in tds]
        notice_no = next((t for t in texts if _NOTICE_NO_RE.search(t)), "")
        date_str = next((t for t in texts if _DATE_CELL_RE.match(t)), "")
        if not date_str:
            range_match = next((_DATE_RANGE_RE.match(t) for t in texts if _DATE_RANGE_RE.match(t)), None)
            if range_match is not None:
                date_str = range_match.group(1)
        post_date = _parse_post_date(date_str) if date_str else None

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
    soup = _soup(resp)
    attachments = []

    # 금산군: <div class="ui bbs--view--file"><a href="/_prog/download/?...">
    # 완성된 GET 링크(실측 확인, 2026-09-28) — 링크 텍스트 자체가 이미 순수 파일명이다.
    for div in soup.select("div.bbs--view--file"):
        for a in div.select("a[href*='/_prog/download/']"):
            name = a.get_text(strip=True)
            if not name:
                continue
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            attachments.append({"name": name, "url": urljoin(resp.url, a.get("href", "")), "ext": ext})
    if attachments:
        return attachments

    # 계룡시: 완성된 GET 링크
    for a in soup.find_all("a", href=_DN00_RE):
        href = urljoin(resp.url, a.get("href", ""))
        title_attr = a.get("title", "")
        name = re.sub(r"\s*다운로드\s*$", "", title_attr).strip() or a.get_text(strip=True)
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": href, "ext": ext})
    if attachments:
        return attachments

    # 영동군: 완성된 GET 링크(?mode=D&no=<id>&file_id=<fid>), 파일명은 title 속성
    for a in soup.find_all("a", href=_MODE_D_RE):
        href = urljoin(resp.url, a.get("href", ""))
        name = (a.get("title", "") or a.get_text(strip=True)).strip()
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": href, "ext": ext})
    if attachments:
        return attachments

    # 부여군 등: fn_saeol_downFile(...) -> eminwon.<도메인>의 FileDown.jsp로 GET
    # (form은 POST를 쓰지만 실측 결과 GET 쿼리스트링도 그대로 받아준다 — 위 docstring 참고)
    host = _eminwon_host(resp.url)
    for a in soup.find_all("a"):
        text = a.get("onclick", "") + " " + a.get("href", "")
        m = _SAEOL_DOWNFILE_RE.search(text)
        if m:
            user_name, sys_name, file_path = m.groups()
            ext = user_name.rsplit(".", 1)[-1].lower() if "." in user_name else ""
            url = (
                f"https://{host}/emwp/jsp/ofr/FileDown.jsp"
                f"?user_file_nm={quote(user_name)}&sys_file_nm={quote(sys_name)}&file_path={quote(file_path)}"
            )
            attachments.append({"name": user_name, "url": url, "ext": ext})
            continue
        m = _BBSGOSI_DOWNFILE_RE.search(text)
        if m:
            user_name, sys_name, file_path = m.groups()
            ext = user_name.rsplit(".", 1)[-1].lower() if "." in user_name else ""
            url = urljoin(
                resp.url,
                "/_prog/saeol_gosi/download.php"
                f"?user_file_nm={quote(user_name)}&sys_file_nm={quote(sys_name)}&file_path={quote(file_path)}",
            )
            attachments.append({"name": user_name, "url": url, "ext": ext})
    return attachments
