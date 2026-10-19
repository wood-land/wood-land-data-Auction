"""
saeol_gosi.py — "새올" 행정정보시스템 고시/공고 게시판(list.do/view.do) 공통 어댑터.

여러 지자체가 같은 벤더 시스템(같은 JS 함수 goDownload, 같은 다운로드 서버 패턴
"eminwon.<사이트도메인>/emwp/jsp/ofr/FileDown.jsp")을 쓰는 것을 실측으로 확인했다
(2026-09-25): 이천시·과천시·영천시·청도군·구미시·김천시·칠곡군·오산시·안동시·울주군·
평택시·안성시·의정부시 — 총 13곳.

의정부시(www.ui4u.go.kr)는 "SSL: CERTIFICATE_VERIFY_FAILED: unable to get local
issuer certificate" 오류가 났는데, 인증서 자체는 정상 발급된 것(Sectigo RSA OV
Secure Server CA)이고 서버가 중간 인증서를 안 보내 체인을 못 만드는 것뿐이었다.
그 중간 인증서를 발급기관 공개 배포처(AIA의 caIssuers URL)에서 받아 신뢰 목록에
추가해 해결했다 — 인증서 검증 자체를 끄는 게 아니라 체인을 완성한 것이다
(_MissingIntermediateCAAdapter).

목록 칸 클래스가 지자체마다 조금씩 다르다 — selector/날짜 형식을 순서대로 시도한다:
  - 제목: td.list_tit a / td.tit a(영천시) / td.gosi_tit a(안성시)
  - 날짜: td.list_date / td.date(영천시, "YYYYMMDD") / td.gosi_date(안성시)
  - 공고번호: class 없는 칸(대부분) / td.list_notice(평택시) / td.gosi_num(안성시)
상세 이동은 세 가지 방식이 섞여 있다:
  1. <a data-action="view.do?...">(대부분, onclick="req.post(this)"로 감싸져 있지만
     GET으로 그대로 열림 — 실측 확인)
  2. <a href="view.do?...">(안동시, JS 없이 바로 접근 가능)
  3. <a onclick="boardView(page, idx)">(안성시 — href/data-action이 아예 없다. idx로
     "…List.do"→"…View.do" + notAncmtMgtNo=idx 조합 URL을 직접 만든다)

첨부파일 다운로드 링크는 <a class="download">가 붙어있는 곳도 있고(이천시 등),
아예 class 없이 <a href="#" onclick="goDownload(...)">만 있는 곳도 있다(평택시,
안성시는 href="javascript:goDownload(...)" 자체). 그래서 class로 거르지 않고
페이지의 모든 <a>를 돌며 onclick과 href 양쪽에서 goDownload(...) 패턴을 찾는다
("미리보기" 버튼은 다른 함수(fn_egov_gosi_preview)라 안 걸린다.

다운로드 서버 URL은 "eminwon." + (목록/상세 URL의 도메인에서 www.를 뗀 값)으로
조립한다(전 지자체 공통 규칙, 실측 확인). 이 다운로드 서버들 중 일부(예: 이천시·
안동시)는 최신 OpenSSL 기본 보안수준의 암호화 스위트를 지원하지 않아
(SSLV3_ALERT_HANDSHAKE_FAILURE) 레거시 스위트를 허용하는 전용 어댑터로 접속해야
한다 — 문제없는 곳(칠곡군·김천시 등)에도 적용해 두 방식 모두 커버한다. 인증서
검증 자체는 그대로 유지한다(완화하는 건 암호화 스위트뿐).
"""

import datetime as dt
import re
import ssl
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlsplit, urlunsplit

import certifi
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

_SUBJECT_SELECTORS = ["td.list_tit a", "td.tit a", "td.gosi_tit a"]
_DATE_SELECTORS = ["td.list_date", "td.date", "td.gosi_date"]
_NOTICE_NO_SELECTORS = ["td.list_notice", "td.gosi_num"]
_DATE_FORMATS = ["%Y-%m-%d", "%Y%m%d", "%Y.%m.%d"]
_GO_DOWNLOAD_RE = re.compile(r"goDownload\(\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*\)")
_BOARD_VIEW_RE = re.compile(r"boardView\(\s*'[^']*'\s*,\s*'([^']*)'\s*\)")
# 문경시 등: onclick="gosiView('portal', 'list', '<mgtNo>', '<mId>', '1')"
# (실측 확인, 2026-09-26 — gosiView()의 실제 구현은 list.do를 view.do로 바꾸고
# mId/notAncmtMgtNo를 쿼리로 붙인다)
_GOSI_VIEW_RE = re.compile(r"gosiView\(\s*'([^']*)'\s*,\s*'[^']*'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*")
_DOWNLOAD_PREFIX = "https://eminwon."


# 의정부시(www.ui4u.go.kr, eminwon.ui4u.go.kr)가 체인에 빠뜨린 중간 인증서. 발급기관
# (Sectigo)의 공개 배포처(인증서 AIA 확장의 caIssuers URL: http://crt.sectigo.com/
# SectigoRSAOrganizationValidationSecureServerCA.crt)에서 받은 것 — 실제 서버
# 인증서는 정상 발급된 것이라 이 중간 인증서로 체인을 완성하면 검증이 통과한다
# (검증을 끄는 게 아니라 완성하는 것). eminwon.ui4u.go.kr는 이 문제에 더해
# 레거시 암호화 스위트 문제까지 겹쳐 있어(실측 확인) _LegacyTLSAdapter에 이
# 중간 인증서도 함께 실어 둔다(다른 eminwon.* 호스트에는 영향 없음 — 신뢰
# 목록에 인증서 하나를 더 추가하는 것뿐이라 다른 곳의 검증을 약화시키지 않는다).
_UI4U_MISSING_INTERMEDIATE_PEM = """-----BEGIN CERTIFICATE-----
MIIGGTCCBAGgAwIBAgIQE31TnKp8MamkM3AZaIR6jTANBgkqhkiG9w0BAQwFADCB
iDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCk5ldyBKZXJzZXkxFDASBgNVBAcTC0pl
cnNleSBDaXR5MR4wHAYDVQQKExVUaGUgVVNFUlRSVVNUIE5ldHdvcmsxLjAsBgNV
BAMTJVVTRVJUcnVzdCBSU0EgQ2VydGlmaWNhdGlvbiBBdXRob3JpdHkwHhcNMTgx
MTAyMDAwMDAwWhcNMzAxMjMxMjM1OTU5WjCBlTELMAkGA1UEBhMCR0IxGzAZBgNV
BAgTEkdyZWF0ZXIgTWFuY2hlc3RlcjEQMA4GA1UEBxMHU2FsZm9yZDEYMBYGA1UE
ChMPU2VjdGlnbyBMaW1pdGVkMT0wOwYDVQQDEzRTZWN0aWdvIFJTQSBPcmdhbml6
YXRpb24gVmFsaWRhdGlvbiBTZWN1cmUgU2VydmVyIENBMIIBIjANBgkqhkiG9w0B
AQEFAAOCAQ8AMIIBCgKCAQEAnJMCRkVKUkiS/FeN+S3qU76zLNXYqKXsW2kDwB0Q
9lkz3v4HSKjojHpnSvH1jcM3ZtAykffEnQRgxLVK4oOLp64m1F06XvjRFnG7ir1x
on3IzqJgJLBSoDpFUd54k2xiYPHkVpy3O/c8Vdjf1XoxfDV/ElFw4Sy+BKzL+k/h
fGVqwECn2XylY4QZ4ffK76q06Fha2ZnjJt+OErK43DOyNtoUHZZYQkBuCyKFHFEi
rsTIBkVtkuZntxkj5Ng2a4XQf8dS48+wdQHgibSov4o2TqPgbOuEQc6lL0giE5dQ
YkUeCaXMn2xXcEAG2yDoG9bzk4unMp63RBUJ16/9fAEc2wIDAQABo4IBbjCCAWow
HwYDVR0jBBgwFoAUU3m/WqorSs9UgOHYm8Cd8rIDZsswHQYDVR0OBBYEFBfZ1iUn
Z/kxwklD2TA2RIxsqU/rMA4GA1UdDwEB/wQEAwIBhjASBgNVHRMBAf8ECDAGAQH/
AgEAMB0GA1UdJQQWMBQGCCsGAQUFBwMBBggrBgEFBQcDAjAbBgNVHSAEFDASMAYG
BFUdIAAwCAYGZ4EMAQICMFAGA1UdHwRJMEcwRaBDoEGGP2h0dHA6Ly9jcmwudXNl
cnRydXN0LmNvbS9VU0VSVHJ1c3RSU0FDZXJ0aWZpY2F0aW9uQXV0aG9yaXR5LmNy
bDB2BggrBgEFBQcBAQRqMGgwPwYIKwYBBQUHMAKGM2h0dHA6Ly9jcnQudXNlcnRy
dXN0LmNvbS9VU0VSVHJ1c3RSU0FBZGRUcnVzdENBLmNydDAlBggrBgEFBQcwAYYZ
aHR0cDovL29jc3AudXNlcnRydXN0LmNvbTANBgkqhkiG9w0BAQwFAAOCAgEAThNA
lsnD5m5bwOO69Bfhrgkfyb/LDCUW8nNTs3Yat6tIBtbNAHwgRUNFbBZaGxNh10m6
pAKkrOjOzi3JKnSj3N6uq9BoNviRrzwB93fVC8+Xq+uH5xWo+jBaYXEgscBDxLmP
bYox6xU2JPti1Qucj+lmveZhUZeTth2HvbC1bP6mESkGYTQxMD0gJ3NR0N6Fg9N3
OSBGltqnxloWJ4Wyz04PToxcvr44APhL+XJ71PJ616IphdAEutNCLFGIUi7RPSRn
R+xVzBv0yjTqJsHe3cQhifa6ezIejpZehEU4z4CqN2mLYBd0FUiRnG3wTqN3yhsc
SPr5z0noX0+FCuKPkBurcEya67emP7SsXaRfz+bYipaQ908mgWB2XQ8kd5GzKjGf
FlqyXYwcKapInI5v03hAcNt37N3j0VcFcC3mSZiIBYRiBXBWdoY5TtMibx3+bfEO
s2LEPMvAhblhHrrhFYBZlAyuBbuMf1a+HNJav5fyakywxnB2sJCNwQs2uRHY1ihc
6k/+JLcYCpsM0MF8XPtpvcyiTcaQvKZN8rG61ppnW5YCUtCC+cQKXA0o4D/I+pWV
idWkvklsQLI+qGu41SWyxP7x09fn1txDAXYw+zuLXfdKiXyaNb78yvBXAfCNP6CH
MntHWpdLgtJmwsQt6j8k9Kf5qLnjatkYYaA7jBU=
-----END CERTIFICATE-----
"""


from cms_adapters.eminwon_list import _YEONGAM_INTERMEDIATE_PEM as _SECTIGO_DV_R36_PEM  # noqa: E402


class _LegacyTLSAdapter(HTTPAdapter):
    """eminwon.* 다운로드 서버 전용: 암호화 스위트를 SECLEVEL=1로 완화하고,
    기본 신뢰 저장소에 _UI4U_MISSING_INTERMEDIATE_PEM을 추가해 둔다(의정부시 다운로드
    서버가 체인을 안 보내는 문제 대응 — 다른 곳엔 영향 없음). 인증서 검증 자체는
    켜진 채로 유지한다(완화하는 건 암호화 스위트뿐, 신뢰 목록 추가는 검증을 채우는 것)."""

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context(cafile=certifi.where())
        ctx.load_verify_locations(cadata=_UI4U_MISSING_INTERMEDIATE_PEM)
        # 안동시 다운로드 서버(eminwon.andong.go.kr)는 Sectigo Public Server Authentication CA DV R36 을 보내지 않는다
        # (실측 2026-10-17: unable to get local issuer certificate). 영암군과 같은 인증서라 eminwon_list 것을 함께 신뢰 목록에 둔다.
        ctx.load_verify_locations(cadata=_SECTIGO_DV_R36_PEM)
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


class _MissingIntermediateCAAdapter(HTTPAdapter):
    """www.ui4u.go.kr(메인 사이트) 전용: 기본 신뢰 저장소 + 빠진 중간 인증서로 체인을
    완성한다. 인증서 검증은 그대로 켜져 있다(완화가 아니라 체인을 채우는 것)."""

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context(cafile=certifi.where())
        ctx.load_verify_locations(cadata=_UI4U_MISSING_INTERMEDIATE_PEM)
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


# www.ui4u.go.kr과 정확히 같은 빠진 중간 인증서(Sectigo RSA Organization Validation
# Secure Server CA)를 쓰는 사이트 목록 — 문경시(gbmg.go.kr)도 실측 확인(2026-09-26).
# 우연히 같은 CA 벤더를 쓰는 지자체가 더 있을 수 있어, 새 saeol_gosi 사이트에서
# "unable to get local issuer certificate" 오류가 나면 먼저 이 인증서로 시도해 본다.
_MISSING_CA_SITE_ROOTS = {"https://www.ui4u.go.kr", "https://www.gbmg.go.kr"}


def prepare_session(session, city):
    """board_crawler.run_city가 지자체별 세션을 만든 직후 한 번 호출한다.
    prefix가 "https://eminwon."이므로 어느 지자체의 다운로드 서버든 한 번의 mount로
    커버된다(session.mount는 URL 문자열 접두사로 매칭한다)."""
    if not getattr(session, "_saeol_legacy_mounted", False):
        session.mount(_DOWNLOAD_PREFIX, _LegacyTLSAdapter())
        session._saeol_legacy_mounted = True
    root = _site_root(city.base_url)
    if root in _MISSING_CA_SITE_ROOTS and not getattr(session, f"_ca_mounted_{root}", False):
        session.mount(root, _MissingIntermediateCAAdapter())
        setattr(session, f"_ca_mounted_{root}", True)


def _site_root(url):
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def _eminwon_host(url):
    netloc = urlsplit(url).netloc
    if netloc.startswith("www."):
        netloc = netloc[len("www."):]
    return "eminwon." + netloc


def _find_subject_link(tr):
    for sel in _SUBJECT_SELECTORS:
        a = tr.select_one(sel)
        if a is not None:
            return a
    # 알려진 class가 하나도 안 맞으면(의정부시는 td.taL) 그 행에서 <a>를 담은
    # 첫 번째 칸으로 대체한다 — eminwon_list.py와 같은 방식의 일반화.
    for td in tr.find_all("td"):
        a = td.find("a")
        if a is not None:
            return a
    return None


def _find_date_str(tr):
    for sel in _DATE_SELECTORS:
        td = tr.select_one(sel)
        if td is not None:
            return td.get_text(strip=True)
    return ""


def _parse_post_date(date_str):
    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def _find_notice_no(tr):
    for sel in _NOTICE_NO_SELECTORS:
        td = tr.select_one(sel)
        if td is not None:
            return td.get_text(" ", strip=True)
    notice_cell = tr.select_one("td:not([class])")
    return notice_cell.get_text(" ", strip=True) if notice_cell else ""


def _resolve_from_board_view(a, base_url):
    """안성시처럼 data-action/href 없이 onclick="boardView(page, idx)"만 있는 경우,
    idx로 "...List.do" -> "...View.do" + notAncmtMgtNo=idx 조합 URL을 직접 만든다."""
    m = _BOARD_VIEW_RE.search(a.get("onclick", ""))
    if not m:
        return None
    idx = m.group(1)
    parts = urlsplit(base_url)
    path = parts.path
    if "List.do" in path:
        view_path = path.replace("List.do", "View.do")
    elif "list.do" in path:
        view_path = path.replace("list.do", "view.do")
    else:
        return None
    query = dict(parse_qsl(parts.query))
    query["notAncmtMgtNo"] = idx
    return urlunsplit((parts.scheme, parts.netloc, view_path, urlencode(query), ""))


def _resolve_from_gosi_view(a, base_url):
    """문경시처럼 onclick="gosiView(siteCodeFull, formId, notAncmtMgtNo, mId, ...)"만
    있는 경우, list.do -> view.do로 바꾸고 mId/notAncmtMgtNo를 쿼리로 붙인다
    (gosiView()의 실제 JS 구현 참고, 2026-09-26 실측 확인)."""
    m = _GOSI_VIEW_RE.search(a.get("onclick", ""))
    if not m:
        return None
    site_code, mgt_no, mid = m.groups()
    parts = urlsplit(base_url)
    path = parts.path.replace("list.do", "view.do") if "list.do" in parts.path else None
    if path is None:
        return None
    query = urlencode({"mId": mid, "notAncmtMgtNo": mgt_no})
    return urlunsplit((parts.scheme, parts.netloc, path, query, ""))


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]
    base_url은 (mId/seCode/token까지 포함한) list.do 전체 URL이다."""
    resp = session.get(base_url, params={"page": page_index}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.select_one("table.bod_list") or soup.find("table")
    if table is None:
        return []
    rows = []
    for tr in table.select("tbody tr"):
        a = _find_subject_link(tr)
        if a is None:
            continue
        action = a.get("data-action") or a.get("href", "")
        if action and action not in ("#",) and not action.startswith("javascript:"):
            detail_url = urljoin(resp.url, action)
        else:
            detail_url = _resolve_from_board_view(a, base_url) or _resolve_from_gosi_view(a, base_url)
        if not detail_url:
            continue
        title = re.sub(r"\s+", " ", a.get_text(strip=True)).strip()
        date_str = _find_date_str(tr)
        post_date = _parse_post_date(date_str) if date_str else None
        notice_no = _find_notice_no(tr)
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
    """상세 페이지의 첨부파일 [{"name", "url", "ext"}, ...] (다운로드는 하지 않음).
    class="download"가 있는 곳도, 아예 없는 곳도 있어(평택시) class로 거르지 않고
    모든 <a>의 onclick/href 양쪽에서 goDownload(...) 패턴을 찾는다."""
    resp = session.get(detail_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    host = _eminwon_host(resp.url)
    attachments = []
    seen_urls = set()
    for a in soup.find_all("a"):
        text = a.get("onclick", "") + " " + a.get("href", "")
        m = _GO_DOWNLOAD_RE.search(text)
        if not m:
            continue
        user_name, sys_name, file_path = m.groups()
        url = (
            f"https://{host}/emwp/jsp/ofr/FileDown.jsp"
            f"?user_file_nm={quote(user_name)}&sys_file_nm={quote(sys_name)}"
            f"&file_path={quote(file_path)}"
        )
        if url in seen_urls:
            continue
        seen_urls.add(url)
        ext = user_name.rsplit(".", 1)[-1].lower() if "." in user_name else ""
        attachments.append({"name": user_name, "url": url, "ext": ext})
    return attachments
