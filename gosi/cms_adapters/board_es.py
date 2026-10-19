"""
board_es.py — "board.es?mid=&bid=" 게시판(이지웹 계열, board.es act=view /
boardDownload.es) 어댑터.

광주광역시도시공사에서 실측 확인했다(2026-09-26). 목록/상세 모두 평범한 GET + 정적
<a href>(goView()의 onclick은 무시해도 된다 — href 자체가 이미 완성된 GET URL,
실측 확인). 날짜는 "YYYY.MM.DD"(점 구분).

서버가 중간 인증서를 안 보내(unable to get local issuer certificate, 실측 확인 —
가짜/자가서명 인증서가 아니라 체인이 빠진 것) 발급기관(GlobalSign) 공개 배포처에서
받은 중간 인증서(GlobalSign GCC R3 EV TLS CA 2025)를 신뢰 저장소에 추가해 완성한다
(검증을 끈 게 아니라 체인을 완성한 것).

상세: 첨부는 <div class="file"><ul class="list"><li><a href="/boardDownload.es?...">
파일명</a><span class="link"><a>다운로드</a><a>미리보기</a>...</span></li></ul></div>
구조라, li의 "직계 자식" <a>만 골라야 한다(안 그러면 다운로드/미리보기/바로듣기
버튼까지 같은 href로 중복 수집된다).

City.boards 항목 형식: {"name": "공고", "mid": "a10402000000", "bid": "0018"}
"""

import datetime as dt
import re
import ssl
from urllib.parse import urljoin

import certifi
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

_DATE_CELL_RE = re.compile(r"^\d{4}\.\d{1,2}\.\d{1,2}$")
_NOTICE_NO_RE = re.compile(r"(공고|고시)\s*제\s*\d{4}\s*[-–]\s*\d+\s*호")

# GlobalSign GCC R3 EV TLS CA 2025 — www.gmcc.co.kr이 응답에서 빠뜨리는 중간 인증서.
# http://secure.globalsign.com/cacert/gsgccr3evtlsca2025.crt (발급기관 공개 배포처)에서
# 받았다(2026-09-26). 루트(GlobalSign Root CA - R3)는 certifi 기본 번들에 이미 있다.
_GMCC_MISSING_INTERMEDIATE_PEM = """-----BEGIN CERTIFICATE-----
MIIElzCCA3+gAwIBAgIRAIPahmyfUtUakxi40OfAMWkwDQYJKoZIhvcNAQELBQAw
TDEgMB4GA1UECxMXR2xvYmFsU2lnbiBSb290IENBIC0gUjMxEzARBgNVBAoTCkds
b2JhbFNpZ24xEzARBgNVBAMTCkdsb2JhbFNpZ24wHhcNMjUwNzE2MDMwNTQ2WhcN
MjcwNzE2MDAwMDAwWjBTMQswCQYDVQQGEwJCRTEZMBcGA1UEChMQR2xvYmFsU2ln
biBudi1zYTEpMCcGA1UEAxMgR2xvYmFsU2lnbiBHQ0MgUjMgRVYgVExTIENBIDIw
MjUwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQDEG4l4CpUk556CyXIA
B3ihV2b8sWMNGwnW0wCpuaHHA5rlXpSWE1AD6r9hyGhQOrc45nPOj6Fvsqw8dFZw
FpAJzlk6FxhYP1ve8KPJvIpt6f5v28jOlzfs8c7dJ8ZmqKHB0Zj6RbAvA9vAl2A3
j0mu+ooXN3/QaFvVihDV/SRyOfFBlhPAsRk8y97tLPWx7/4YzfE6NSLKsU1yF+tf
BTttbaXTH/cWY/KQE3ZHTFRo6XouemjPBP9CDXeTR11tm37Bgn3QOj93FHdi1JJp
eNBGEOGvM8qhTV/77kDiUyOvsp4jZOhas6kIRn8nWK7fCPNdFJYi1Ctvd7gnQ1gB
lW71AgMBAAGjggFrMIIBZzAOBgNVHQ8BAf8EBAMCAYYwHQYDVR0lBBYwFAYIKwYB
BQUHAwEGCCsGAQUFBwMCMBIGA1UdEwEB/wQIMAYBAf8CAQAwHQYDVR0OBBYEFGMQ
f+QoM5r4R2BZUn5XEMdN+BcWMB8GA1UdIwQYMBaAFI/wS3+oLkUkrk1Q+mOai97i
3Ru8MHsGCCsGAQUFBwEBBG8wbTAuBggrBgEFBQcwAYYiaHR0cDovL29jc3AyLmds
b2JhbHNpZ24uY29tL3Jvb3RyMzA7BggrBgEFBQcwAoYvaHR0cDovL3NlY3VyZS5n
bG9iYWxzaWduLmNvbS9jYWNlcnQvcm9vdC1yMy5jcnQwNgYDVR0fBC8wLTAroCmg
J4YlaHR0cDovL2NybC5nbG9iYWxzaWduLmNvbS9yb290LXIzLmNybDAtBgNVHSAE
JjAkMAcGBWeBDAEBMAwGCisGAQQBoDIKAQEwCwYJKwYBBAGgMgEBMA0GCSqGSIb3
DQEBCwUAA4IBAQCtcTjIgw+tiW7E+sCTJ36nrC0IOxMpwE+nTaUG1xQJb+QE18vF
cPvEiqv8OonEBkQJFQ1N5YdDu9kydDYXBmIheYD9Z//TlUBnLL7HBje1ugplB0xE
jpU52q0XLxe6nHfeEKnslZ/Q/eDEsjZKxwF51SlGO6ap+09hfdbfMXDkTsfa+yXg
dIxZRCud0QEBTZAow0iCs3rf5wVALhhh2ePEwqxEm1LkUhvkJMLSCobYcJ+vXprK
JijbpPM602H1kqxNcD/nE7aCNm7g5GTaT04SCGYiQJ32r9mhx34peuYz05pY+AA3
aVB22PDvfoNyGZyClRtNt4KKg8dGJlYEhc3D
-----END CERTIFICATE-----"""


class _MissingIntermediateCAAdapter(HTTPAdapter):
    """인증서 검증은 그대로 켠 채, 빠진 중간 인증서만 신뢰 저장소에 추가한다."""

    def _build_ctx(self):
        ctx = ssl.create_default_context()
        ctx.load_verify_locations(cafile=certifi.where())
        ctx.load_verify_locations(cadata=_GMCC_MISSING_INTERMEDIATE_PEM)
        return ctx

    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = self._build_ctx()
        return super().init_poolmanager(*args, **kwargs)


def prepare_session(session, city):
    if not getattr(session, "_board_es_gmcc_mounted", False):
        session.mount("https://www.gmcc.co.kr", _MissingIntermediateCAAdapter())
        session._board_es_gmcc_mounted = True


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(
        base_url,
        params={"mid": board["mid"], "bid": board["bid"], "nPage": page_index},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for tr in soup.select("table tbody tr"):
        subject_td = tr.find("td", attrs={"aria-label": "제목"})
        a_tag = subject_td.find("a") if subject_td else None
        if a_tag is None:
            continue
        title = a_tag.get_text(strip=True)
        detail_url = urljoin(resp.url, a_tag.get("href", ""))

        tds = tr.find_all("td")
        texts = [td.get_text(strip=True) for td in tds]
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


def fetch_attachments(session, detail_url):
    """상세 페이지의 첨부파일 [{"name","url","ext"}, ...] (다운로드는 하지 않음)."""
    resp = session.get(detail_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    attachments = []
    # <li> 안에 같은 href가 3번(파일명 링크 + "다운로드"/"미리보기"/"바로듣기" 버튼) 나온다.
    # 파일명 링크만 class가 없고(버튼들은 class="btn_line") — 그걸로 구분한다.
    # (html.parser가 <img alt="..." onerror="...">를 닫힌 태그로 못 보고 뒤 형제를
    #  img 안에 중첩시키는 경우가 있어(실측 확인) li 직계 자식 selector는 못 믿는다.)
    for a_tag in soup.select("div.file ul.list li a[href*='boardDownload.es']:not(.btn_line)"):
        name = a_tag.get_text(strip=True)
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": urljoin(resp.url, a_tag.get("href", "")), "ext": ext})
    return attachments
