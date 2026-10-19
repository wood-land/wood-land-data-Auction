"""
seongnam_board.py — 성남시청 게시판(/pm010301) 어댑터.

성남시에서 실측 확인했다(2026-09-28). 목록 행 제목 칸이 href="javascript:void();"
onclick="javascript:f_view('<id>')"뿐이라 href를 못 쓴다 — f_view()의 실제 구현이
"/pm010301/<id>"로 검색폼을 그대로 GET 제출하는 것을 확인해 그 경로를 직접 조립한다
(원래는 <form> 제출이지만 검색 조건이 비어 있으면 그냥 GET path만으로도 된다,
실측 확인). 페이지네이션은 히든필드 "curPage".

각 칸에 라벨용 <strong class="mobile-tit">번호</strong> 등이 텍스트 앞에 붙어 있어
(모바일 반응형 표시용) 라벨을 뗀 텍스트로 판별해야 한다.

첨부파일 다운로드는 eminwon_list.py와 같은 goDownLoad(...) 패턴이지만 첫 인자로
이벤트 객체(e)가 하나 더 있다(goDownLoad(e, user, sys, path)) — eminwon_list.py의
_GO_DOWNLOAD_RE를 이 변형까지 인식하도록 확장해 두고 그 fetch_attachments를
그대로 재사용한다(law.md 3-2 — 실제로 같다고 확인된 부분만 재사용).

City.boards 항목 형식: {"name": "고시공고"}
"""

import datetime as dt
import re
import ssl
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter

from cms_adapters.eminwon_list import fetch_attachments  # noqa: F401

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


class _LegacyTLSAdapter(HTTPAdapter):
    """암호화 스위트만 SECLEVEL=1로 완화한다(다른 지자체의 동해시 대응과 동일한
    조치). 인증서 검증 자체는 그대로 켜져 있다."""

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


# 성남시는 목록 사이트(www.seongnam.go.kr)와 첨부 다운로드 서버(eminwon.seongnam.go.kr)
# 둘 다 최신 OpenSSL 기본 보안수준의 암호화 스위트를 지원하지 않는다(실측:
# SSLV3_ALERT_HANDSHAKE_FAILURE, 2026-09-28) — eminwon.*은 접두어로 한 번에 잡는다.
_SECLEVEL_HOSTS = {"www.seongnam.go.kr"}
_SECLEVEL_PREFIX = "https://eminwon."


def prepare_session(session, city):
    """board_crawler.run_city가 지자체별 세션을 만든 직후 한 번 호출한다.
    fetch_attachments를 eminwon_list.py에서 그대로 가져다 쓰므로(이 파일 상단
    import 참고), 그 다운로드 서버(eminwon.seongnam.go.kr)용 TLS 완화도 여기서
    같이 걸어 둔다 — board_crawler는 city.adapter로 지정된 이 모듈의
    prepare_session만 호출하고 eminwon_list.py 것은 따로 안 부른다."""
    host = urlsplit(city.base_url).netloc
    if host in _SECLEVEL_HOSTS and not getattr(session, f"_legacy_tls_{host}", False):
        session.mount(f"https://{host}", _LegacyTLSAdapter())
        setattr(session, f"_legacy_tls_{host}", True)
    if not getattr(session, "_legacy_tls_eminwon_prefix", False):
        session.mount(_SECLEVEL_PREFIX, _LegacyTLSAdapter())
        session._legacy_tls_eminwon_prefix = True

_DATE_CELL_RE = re.compile(r"^\d{4}\.\d{1,2}\.\d{1,2}$")
_NOTICE_NO_RE = re.compile(r"(공고|고시)\s*제\s*\d{4}\s*[-–]\s*\d+\s*호")
_FVIEW_RE = re.compile(r"f_view\(\s*'(\d+)'\s*\)")
_LABEL_RE = re.compile(r"^[가-힣]{1,5}")  # 셀 맨 앞 라벨(strong.mobile-tit) 텍스트 조각


def _cell_text(td):
    label = td.find("strong", class_="mobile-tit")
    if label is not None:
        import copy

        td = copy.deepcopy(td)
        td.find("strong", class_="mobile-tit").decompose()
    return td.get_text(strip=True)


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(base_url, params={"curPage": page_index}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.select_one("table.board-table")
    if table is None:
        return []

    rows = []
    for tr in table.select("tbody tr"):
        a = None
        for cand in tr.find_all("a"):
            if _FVIEW_RE.search(cand.get("onclick", "")):
                a = cand
                break
        if a is None:
            continue
        m = _FVIEW_RE.search(a.get("onclick", ""))
        detail_url = urljoin(base_url if base_url.endswith("/") else base_url + "/", m.group(1))
        title = re.sub(r"\s+", " ", a.get_text(strip=True)).strip()

        texts = [_cell_text(td) for td in tr.find_all("td")]
        notice_no = next((t for t in texts if _NOTICE_NO_RE.search(t)), "")
        date_str = next((t for t in texts if _DATE_CELL_RE.match(t)), "")
        post_date = None
        if date_str:
            try:
                post_date = dt.datetime.strptime(date_str, "%Y.%m.%d").date()
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
