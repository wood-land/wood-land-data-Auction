"""
std_ezweb.py — 전자정부 표준프레임워크 계열 게시판(selectBbsNttList.do / selectBbsNttView.do /
downloadBbsFile.do) 어댑터.

원주시청을 포함해 6곳(원주시·보은군·제천시·양평군·횡성군·태백시·영월군)에서 실제로 URL을
열어 검증했다(2026-09-25). 같은 백엔드(URL 패턴)를 쓰지만 프론트엔드 스킨이 최소 2종류다:

  - p-table 스킨(원주시·보은군·제천시·양평군·횡성군): table.p-table, td.p-subject,
    첨부는 <a class="p-attach__link"> 안에 <span>파일명</span>, 날짜 "YYYY.MM.DD"
  - bbs_default 스킨(태백시·영월군): table.bbs_default, td.subject,
    첨부는 <a class="file_down..."> 옆 형제 <div>의 <span>파일명</span>, 날짜는
    "YYYY-MM-DD"(태백시) 또는 "YYYY.MM.DD"(영월군)

이 두 스킨은 selector를 순서대로 시도해 처리한다. 세 번째 스킨이 나오면(예: table도
td class도 안 맞음) 임의로 맞추지 말고 실제 페이지를 먼저 열어 확인한 뒤 selector를
추가한다 (law.md 3-2).

날짜/공고번호 칸의 "절대 위치"(tds[N])는 지자체마다 다르다 — 같은 p-table 스킨이라도
제천시처럼 부서·조회수·공고번호 칸 구성이 원주시와 다른 경우가 실제로 있었다
(2026-09-25 확인: 제천시는 날짜가 tds[3]이 아니라 tds[4]). 그래서 위치가 아니라
칸의 "내용 패턴"(날짜 형식 정규식 / "공고 제YYYY-N호" 형식 정규식)으로 찾는다.

City.boards 항목 형식: {"name": "공고", "bbsNo": 140, "key": 216}
"""

import copy
import datetime as dt
import re
import ssl
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

# 동해시(dh.go.kr)는 최신 OpenSSL 기본 보안수준의 암호화 스위트를 지원하지 않는다
# (실측: SSLV3_ALERT_HANDSHAKE_FAILURE). 암호화 스위트만 SECLEVEL=1로 완화하고
# 인증서 검증은 그대로 유지한다.
_SECLEVEL_HOSTS = {"dh.go.kr"}


class _LegacyTLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


# 철원군(www.cwg.go.kr)은 중간 인증서(RapidSSL TLS RSA CA G1)를 안 보내 체인을 못
# 만드는 것뿐이었다(실측 확인, 2026-09-26) — 발급기관 공개 배포처(AIA의 caIssuers
# URL)에서 받은 중간 인증서를 신뢰 목록에 추가해 해결했다. 검증을 끈 게 아니라
# 체인을 완성한 것이다.
_CWG_INTERMEDIATE_PEM = """-----BEGIN CERTIFICATE-----
MIIEszCCA5ugAwIBAgIQCyWUIs7ZgSoVoE6ZUooO+jANBgkqhkiG9w0BAQsFADBh
MQswCQYDVQQGEwJVUzEVMBMGA1UEChMMRGlnaUNlcnQgSW5jMRkwFwYDVQQLExB3
d3cuZGlnaWNlcnQuY29tMSAwHgYDVQQDExdEaWdpQ2VydCBHbG9iYWwgUm9vdCBH
MjAeFw0xNzExMDIxMjI0MzNaFw0yNzExMDIxMjI0MzNaMGAxCzAJBgNVBAYTAlVT
MRUwEwYDVQQKEwxEaWdpQ2VydCBJbmMxGTAXBgNVBAsTEHd3dy5kaWdpY2VydC5j
b20xHzAdBgNVBAMTFlJhcGlkU1NMIFRMUyBSU0EgQ0EgRzEwggEiMA0GCSqGSIb3
DQEBAQUAA4IBDwAwggEKAoIBAQC/uVklRBI1FuJdUEkFCuDL/I3aJQiaZ6aibRHj
ap/ap9zy1aYNrphe7YcaNwMoPsZvXDR+hNJOo9gbgOYVTPq8gXc84I75YKOHiVA4
NrJJQZ6p2sJQyqx60HkEIjzIN+1LQLfXTlpuznToOa1hyTD0yyitFyOYwURM+/CI
8FNFMpBhw22hpeAQkOOLmsqT5QZJYeik7qlvn8gfD+XdDnk3kkuuu0eG+vuyrSGr
5uX5LRhFWlv1zFQDch/EKmd163m6z/ycx/qLa9zyvILc7cQpb+k7TLra9WE17YPS
n9ANjG+ECo9PDW3N9lwhKQCNvw1gGoguyCQu7HE7BnW8eSSFAgMBAAGjggFmMIIB
YjAdBgNVHQ4EFgQUDNtsgkkPSmcKuBTuesRIUojrVjgwHwYDVR0jBBgwFoAUTiJU
IBiV5uNu5g/6+rkS7QYXjzkwDgYDVR0PAQH/BAQDAgGGMB0GA1UdJQQWMBQGCCsG
AQUFBwMBBggrBgEFBQcDAjASBgNVHRMBAf8ECDAGAQH/AgEAMDQGCCsGAQUFBwEB
BCgwJjAkBggrBgEFBQcwAYYYaHR0cDovL29jc3AuZGlnaWNlcnQuY29tMEIGA1Ud
HwQ7MDkwN6A1oDOGMWh0dHA6Ly9jcmwzLmRpZ2ljZXJ0LmNvbS9EaWdpQ2VydEds
b2JhbFJvb3RHMi5jcmwwYwYDVR0gBFwwWjA3BglghkgBhv1sAQEwKjAoBggrBgEF
BQcCARYcaHR0cHM6Ly93d3cuZGlnaWNlcnQuY29tL0NQUzALBglghkgBhv1sAQIw
CAYGZ4EMAQIBMAgGBmeBDAECAjANBgkqhkiG9w0BAQsFAAOCAQEAGUSlOb4K3Wtm
SlbmE50UYBHXM0SKXPqHMzk6XQUpCheF/4qU8aOhajsyRQFDV1ih/uPIg7YHRtFi
CTq4G+zb43X1T77nJgSOI9pq/TqCwtukZ7u9VLL3JAq3Wdy2moKLvvC8tVmRzkAe
0xQCkRKIjbBG80MSyDX/R4uYgj6ZiNT/Zg6GI6RofgqgpDdssLc0XIRQEotxIZcK
zP3pGJ9FCbMHmMLLyuBd+uCWvVcF2ogYAawufChS/PT61D9rqzPRS5I2uqa3tmIT
44JhJgWhBnFMb7AGQkvNq9KNS9dd3GWc17H/dXa1enoxzWjE0hBdFjxPhUb0W3wi
8o34/m8Fxw==
-----END CERTIFICATE-----
"""
_MISSING_CA_HOSTS = {"www.cwg.go.kr": _CWG_INTERMEDIATE_PEM}


class _MissingIntermediateCAAdapter(HTTPAdapter):
    def __init__(self, intermediate_pem, *args, **kwargs):
        self._intermediate_pem = intermediate_pem
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.load_verify_locations(cadata=self._intermediate_pem)
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def prepare_session(session, city):
    """board_crawler.run_city가 지자체별 세션을 만든 직후 한 번 호출한다."""
    host = urlsplit(city.base_url).netloc
    if host in _SECLEVEL_HOSTS and not getattr(session, f"_legacy_tls_{host}", False):
        session.mount(f"https://{host}", _LegacyTLSAdapter())
        setattr(session, f"_legacy_tls_{host}", True)
    if host in _MISSING_CA_HOSTS and not getattr(session, f"_ca_mounted_{host}", False):
        session.mount(f"https://{host}", _MissingIntermediateCAAdapter(_MISSING_CA_HOSTS[host]))
        setattr(session, f"_ca_mounted_{host}", True)

# 확인된 스킨들의 목록 테이블 selector (순서대로 시도). table.bbs_default_list는
# 산청군에서 실측 확인(2026-09-27) — bbs_default 스킨과 제목/첨부 마크업은 같고
# table class만 다르다.
_TABLE_SELECTORS = ["table.p-table", "table.bbs_default", "table.bbs_default_list"]
# 확인된 스킨들의 제목 셀 selector (순서대로 시도)
_SUBJECT_SELECTORS = ["td.p-subject", "td.subject"]
# 확인된 날짜 표기 형식 (순서대로 시도)
_DATE_FORMATS = ["%Y.%m.%d", "%Y-%m-%d"]
# 날짜 칸: 칸 전체가 "YYYY.MM.DD" 또는 "YYYY-MM-DD" 형식과 정확히 일치해야 인정한다
# (부분 일치로 하면 "2026-1841" 같은 공고번호 뒷부분과 헷갈릴 수 있다). 산청군은
# 끝에 마침표가 붙는다("2026.09.23.", 실측 확인) — 선택적 마침표를 허용한다.
_DATE_CELL_RE = re.compile(r"^\d{4}[.\-]\d{1,2}[.\-]\d{1,2}\.?$")
# 공고/고시번호 칸: "OO공고 제2026-123호" / "OO고시 제2026-123호" 형식
_NOTICE_NO_RE = re.compile(r"(공고|고시)\s*제\s*\d{4}\s*[-–]\s*\d+\s*호")
# 첨부파일명 칸을 찾을 때 "이게 진짜 파일명이다"로 인정하는 기준: 확장자로 끝남
_FILENAME_RE = re.compile(r"\.[A-Za-z0-9]{2,5}$")


def _find_date_cell(tds):
    for td in tds:
        text = td.get_text(strip=True)
        if _DATE_CELL_RE.match(text):
            return text
    return ""


def _find_notice_no(tds, subject_idx):
    for td in tds:
        text = td.get_text(strip=True)
        if _NOTICE_NO_RE.search(text):
            return text
    # 공고번호 칸을 못 찾으면(예: 원주시처럼 형식이 다름) 제목 바로 앞 칸으로 대체한다
    if subject_idx > 0:
        return tds[subject_idx - 1].get_text(strip=True)
    return ""


def _find_table(soup):
    for sel in _TABLE_SELECTORS:
        table = soup.select_one(sel)
        if table is not None:
            return table
    return None


def _find_subject_cell(tr):
    for sel in _SUBJECT_SELECTORS:
        td = tr.select_one(sel)
        if td is not None:
            return td
    return None


def _parse_post_date(date_str):
    date_str = date_str.rstrip(".")
    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def fetch_list_page(session, base_url, board, page_index, page_unit=50):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    list_url = urljoin(base_url, "selectBbsNttList.do")
    params = {
        "bbsNo": board["bbsNo"],
        "key": board["key"],
        "pageIndex": page_index,
        "pageUnit": page_unit,
        "searchCnd": "all",
    }
    resp = session.get(list_url, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    table = _find_table(soup)
    if table is None:
        return []
    rows = []
    for tr in table.select("tbody tr"):
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue
        subject_td = _find_subject_cell(tr)
        a_tag = subject_td.find("a") if subject_td else None
        if a_tag is None:
            continue
        # 철원군처럼 제목 <a> 안에 "핫이슈" 같은 배지 <span class="p-icon...">가
        # 섞여 있는 경우가 있어(실측 확인) 그 배지를 떼어내고 제목만 뽑는다.
        title_copy = copy.deepcopy(a_tag)
        for badge in title_copy.select("span.p-icon"):
            badge.decompose()
        title = title_copy.get_text(strip=True)
        title = re.sub(r"NEW$", "", title).strip()
        href = a_tag.get("href", "")
        detail_url = urljoin(resp.url, href)
        try:
            subject_idx = tds.index(subject_td)
        except ValueError:
            subject_idx = 1
        notice_no = _find_notice_no(tds, subject_idx)
        date_str = _find_date_cell(tds)
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


def _attachment_name(a):
    """첨부 링크 요소에서 실제 파일명을 찾는다. p-table 스킨은 <a> 안의 마지막 span이
    파일명이지만, bbs_default 스킨은 <a> 자체는 "다운로드" 같은 라벨이고 진짜 파일명은
    부모 <div> 안의 형제 <span>에 있다. 확장자로 끝나는 텍스트를 "진짜 파일명"으로 본다."""
    spans = a.find_all("span")
    if spans and _FILENAME_RE.search(spans[-1].get_text(strip=True)):
        return spans[-1].get_text(strip=True)
    parent = a.find_parent("div")
    if parent is not None:
        for sib in parent.find_all("span"):
            text = sib.get_text(strip=True)
            if _FILENAME_RE.search(text):
                return text
    return a.get_text(strip=True)


def fetch_attachments(session, detail_url):
    """상세 페이지의 첨부파일 [{"name", "url", "ext"}, ...] (다운로드는 하지 않음)."""
    resp = session.get(detail_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    attachments = []
    for a in soup.select("a[href*='downloadBbsFile']"):
        name = _attachment_name(a)
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append(
            {"name": name, "url": urljoin(resp.url, a.get("href", "")), "ext": ext}
        )
    return attachments
