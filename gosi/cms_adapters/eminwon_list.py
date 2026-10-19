"""
eminwon_list.py — "eMinwon/고시" 목록(selectEminwonList.do / selectGosiList.do /
selectGosiNttList.do — 전부 같은 프레임워크의 다른 모듈 이름) 공통 어댑터.

원주시 계열 BBS 게시판(cms_adapters/std_ezweb.py)과는 다른 모듈이다. CSS 클래스
(table.p-table)는 같은 프레임워크를 공유하지만, 열 구성이 지자체마다 다르다
(2026-09-25 실측: 홍천군은 공고번호/제목이 분리된 td.p-subject 칸 2개 + 열람기간 칸,
포천시는 통합된 td.p-subject 칸 1개, 음성군은 class 자체가 없이 순수 <a> 태그만,
연천군·하남시·동두천시·구리시·가평군은 "subject"/"p-subject" 등 제각각) — 그래서
class가 아니라 내용 패턴으로 판별한다:
  - 제목 칸: "그 행에서 <a> 태그를 담고 있는 첫 번째 칸"
  - 공고번호: "OO공고 제YYYY-N호"/"OO고시 제YYYY-N호" 패턴에 맞는 칸을 먼저 찾고,
    없으면 제목 칸 바로 앞 칸으로 대체(부정확할 수 있음 — 정보용)
  - 날짜: "YYYY-MM-DD" 또는 압축형 "YYYYMMDD"에 정확히 일치하는 칸(게재기간처럼
    범위가 있는 칸은 정확히 일치하지 않아 자동으로 걸러진다)

첨부파일 링크는 <a href="https://eminwon.<도메인 또는 별도 파일서버>/emwp/jsp/ofr/
FileDown.jsp?user_file_nm=...&sys_file_nm=...&file_path=..."> 형태의 이미 완성된
절대 URL이다(포천시는 도메인이 자기 사이트가 아니라 eminwon.pcs21.net — 공유 파일
서버로 추정). 대부분 saeol_gosi처럼 JS(goDownload) 파싱이 필요 없다 — href를 그대로
쓰고, 파일명은 링크 텍스트 대신 훨씬 안정적인 user_file_nm 쿼리 파라미터에서 읽는다
(포천시는 링크 글자가 "다운로드"뿐이라 텍스트로는 파일명을 알 수 없다). 일부
지자체는 href가 완성된 링크가 아니라 <a href="javascript:goDownLoad(a,b,c)">뿐인데,
이때도 goDownLoad의 실제 구현이 또 갈린다(ntis_ofr.py와 같은 문제):
  - 밀양시: GET, 값이 encodeURI로만 인코딩된 실제 파일명 -> eminwon.<도메인> 조립
  - 보령시: <form name="nnn">이 가리키는 액션(FileDownNew.jsp)으로 POST, 값은
    암호화된 토큰이라 파일명은 링크 텍스트에서 읽어야 한다
그래서 이 경우엔 먼저 페이지에 <form name="nnn">이 있는지로 방식을 가르고, core.
board_crawler의 download_attachment 확장 지점으로 POST를 처리한다.

제목 칸 판별은 class에 "title"이 들어간 칸을 최우선으로 본다(인천 제물포구는
첨부파일 아이콘 칸에도 빈 텍스트 <a>가 있어 "마지막 <a> 칸" 규칙만으로는 그 칸을
잘못 집는다 — 실측 확인, 2026-09-25). 인천 제물포구는 사이트 인증서 체인에 중간
인증서가 빠져 있었는데, 발급기관(Thawte/DigiCert) 공개 배포처에서 받은 중간
인증서로 체인을 완성해 해결했다(검증을 끄는 게 아니라 완성하는 것).
"""

import copy
import datetime as dt
import re
import ssl
from urllib.parse import parse_qsl, quote, unquote, urlencode, urljoin, urlsplit

import certifi
from requests.adapters import HTTPAdapter

from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

_DATE_FORMATS = ["%Y-%m-%d", "%Y.%m.%d", "%Y%m%d"]
_DATE_CELL_RE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$|^\d{4}\.\d{1,2}\.\d{1,2}$|^\d{8}$")
_NOTICE_NO_RE = re.compile(r"(공고|고시)\s*제\s*\d{4}\s*[-–]\s*\d+\s*호")
# 성남시는 goDownLoad(e, user, sys, path)처럼 앞에 이벤트 인자가 하나 더 있다
# (실측 확인, 2026-09-28) — 있어도 없어도 매칭되게 선택적으로 둔다.
_GO_DOWNLOAD_RE = re.compile(r"goDownLoad\(\s*(?:[A-Za-z_]\w*\s*,\s*)?'(.*)'\s*,\s*'(.*)'\s*,\s*'(.*)'\)")
# 장흥군: <button onclick="window.open('https://eminwon.<도메인>/.../FileDown.jsp?...', '_blank')">
_WINDOW_OPEN_FILEDOWN_RE = re.compile(r"window\.open\('([^']*FileDown[^']*)'")
# goDownLoad(...)의 첫 인자가 암호화 토큰이 아니라 평문 실제 파일명인지 판별
# (확장자로 끝나는지로 판단, 영양군 등)
_FILENAME_LIKE_RE = re.compile(r"\.[A-Za-z0-9]{2,5}$")
# 곡성군·구례군: 제목 <a href="#" onclick="javaScript:searchDetail('<id>')">인
# eGovFramework 계열 게시판(실측 확인, 2026-09-28) — href가 "#"라 그대로 쓰면 상세
# 페이지가 아니라 목록 페이지 자신을 다시 가리키게 된다. 실제 이동은 JS가
# document.<폼이름>.action을 GosiView.do로 바꾼 뒤 그 폼(hidden 필드 전부 포함,
# method="get")을 submit하는 방식이라, 그 hidden 필드 값 그대로에 not_ancmt_mgt_no만
# 바꿔서 GosiView.do로 GET하면 동일한 상세 URL을 만들 수 있다.
_SEARCH_DETAIL_ONCLICK_RE = re.compile(r"searchDetail\('(\d+)'\)")
_FORM_ACTION_OVERRIDE_RE = re.compile(r"\.action\s*=\s*[\"']([^\"']+)[\"']")
_JSESSIONID_RE = re.compile(r";jsessionid=[^?&]*")
# 구례군: function searchDetail(not_ancmt_mgt_no) { location.href = '/board/GosiView.do
# ?...고정 쿼리' + '&not_ancmt_mgt_no=' + not_ancmt_mgt_no; } — 고정 쿼리 문자열만 뽑아
# 뒤에 not_ancmt_mgt_no=<id>만 붙이면 동일한 URL이 된다(searchDetail() 함수 본문
# 안에서만 찾으므로 페이지의 다른 location.href 대입과 섞이지 않는다).
_LOCATION_HREF_RE = re.compile(r"location\.href\s*=\s*'([^']+)'")

# 인천 제물포구(icdonggu.go.kr)가 체인에 빠뜨린 중간 인증서. 발급기관(Thawte/
# DigiCert)의 공개 배포처(인증서 AIA 확장의 caIssuers URL: http://cacerts.thawte.com/
# ThawteTLSRSACAG1.crt)에서 받은 것 — 실제 서버 인증서는 정상 발급된 것이라 이
# 중간 인증서로 체인을 완성하면 검증이 통과한다(검증을 끄는 게 아니라 완성하는 것).
_ICDONGGU_MISSING_INTERMEDIATE_PEM = """-----BEGIN CERTIFICATE-----
MIIEizCCA3OgAwIBAgIQCQ7oxd5b+mLSri/3CXxIVzANBgkqhkiG9w0BAQsFADBh
MQswCQYDVQQGEwJVUzEVMBMGA1UEChMMRGlnaUNlcnQgSW5jMRkwFwYDVQQLExB3
d3cuZGlnaWNlcnQuY29tMSAwHgYDVQQDExdEaWdpQ2VydCBHbG9iYWwgUm9vdCBH
MjAeFw0xNzExMDIxMjI0MjVaFw0yNzExMDIxMjI0MjVaMF4xCzAJBgNVBAYTAlVT
MRUwEwYDVQQKEwxEaWdpQ2VydCBJbmMxGTAXBgNVBAsTEHd3dy5kaWdpY2VydC5j
b20xHTAbBgNVBAMTFFRoYXd0ZSBUTFMgUlNBIENBIEcxMIIBIjANBgkqhkiG9w0B
AQEFAAOCAQ8AMIIBCgKCAQEAxjngmPhVetC0b/ozbYJdzOBUA1sMog47030cAP+P
23ANUN8grXECL8NhDEF4F1R9tL0wY0mczHaR0a7lYanlxtwWo1s2uGnnyDs6mOCs
66ew2w3YETr6Tb14xgjpu1gGFtAeewaikO9Fud8hxGJTSwn8xeNkfKVWpD2L4vFN
36FNgxeilK6aE4ykgGAzNlokTp6hNOLAYpDySdLAPKzuJSQ7JCEZ6O+SDKywIdXL
oMTnpxuBKGSG88NWTo3CHCOGmQECia2yqdPDjgLqnEiYNjwQL8uMqj8rOvlMgviB
cHA7xty+7/uYLN6ZS7Vq1/F/lVhVOf5ej6jZdmB85szFbQIDAQABo4IBQDCCATww
HQYDVR0OBBYEFKWM/jLM6w8s1BnGCLgAJIhdw8W3MB8GA1UdIwQYMBaAFE4iVCAY
lebjbuYP+vq5Eu0GF485MA4GA1UdDwEB/wQEAwIBhjAdBgNVHSUEFjAUBggrBgEF
BQcDAQYIKwYBBQUHAwIwEgYDVR0TAQH/BAgwBgEB/wIBADA0BggrBgEFBQcBAQQo
MCYwJAYIKwYBBQUHMAGGGGh0dHA6Ly9vY3NwLmRpZ2ljZXJ0LmNvbTBCBgNVHR8E
OzA5MDegNaAzhjFodHRwOi8vY3JsMy5kaWdpY2VydC5jb20vRGlnaUNlcnRHbG9i
YWxSb290RzIuY3JsMD0GA1UdIAQ2MDQwMgYEVR0gADAqMCgGCCsGAQUFBwIBFhxo
dHRwczovL3d3dy5kaWdpY2VydC5jb20vQ1BTMA0GCSqGSIb3DQEBCwUAA4IBAQC6
km0KA4sTb2VYpEBm/uL2HL/pZX9B7L/hbJ4NcoBe7V56oCnt7aeIo8sMjCRWTCWZ
D1dY0+2KZOC1dKj8d1VXXAtnjytDDuPPf6/iow0mYQTO/GAg/MLyL6CDm3FzDB8V
tsH/aeMgP6pgD1XQqz+haDnfnJTKBuxhcpnx3Adbleue/QnPf1hHYa8L+Rv8Pi5U
h4V9FwHOfphdMXOxi14OqmsiTbc5cOs9/uukH+YVsuFdWTna6IVw1qh+tEtyH16R
vmi7pkqyZYULOPMIE7avrljVVBZuikwARtY8tCVV6Pp9l3VeagBqb2ffgqNJt3C0
TYNYQI+BXG1R1cABlold
-----END CERTIFICATE-----
"""


class _MissingIntermediateCAAdapter(HTTPAdapter):
    """기본 신뢰 저장소 + 빠진 중간 인증서로 체인을 완성한다. 인증서 검증은 그대로
    켜져 있다(완화가 아니라 체인을 채우는 것)."""

    def __init__(self, intermediate_pem, *args, **kwargs):
        self._intermediate_pem = intermediate_pem
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context(cafile=certifi.where())
        ctx.load_verify_locations(cadata=self._intermediate_pem)
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


# 영암군(www.yeongam.go.kr)이 빠뜨린 중간 인증서(Sectigo Public Server
# Authentication CA DV R36) — 발급기관 공개 배포처(AIA의 caIssuers URL:
# http://crt.sectigo.com/SectigoPublicServerAuthenticationCADVR36.crt)에서 받은
# 것(실측 확인, 2026-09-28).
_YEONGAM_INTERMEDIATE_PEM = """-----BEGIN CERTIFICATE-----
MIIGTDCCBDSgAwIBAgIQOXpmzCdWNi4NqofKbqvjsTANBgkqhkiG9w0BAQwFADBf
MQswCQYDVQQGEwJHQjEYMBYGA1UEChMPU2VjdGlnbyBMaW1pdGVkMTYwNAYDVQQD
Ey1TZWN0aWdvIFB1YmxpYyBTZXJ2ZXIgQXV0aGVudGljYXRpb24gUm9vdCBSNDYw
HhcNMjEwMzIyMDAwMDAwWhcNMzYwMzIxMjM1OTU5WjBgMQswCQYDVQQGEwJHQjEY
MBYGA1UEChMPU2VjdGlnbyBMaW1pdGVkMTcwNQYDVQQDEy5TZWN0aWdvIFB1Ymxp
YyBTZXJ2ZXIgQXV0aGVudGljYXRpb24gQ0EgRFYgUjM2MIIBojANBgkqhkiG9w0B
AQEFAAOCAY8AMIIBigKCAYEAljZf2HIz7+SPUPQCQObZYcrxLTHYdf1ZtMRe7Yeq
RPSwygz16qJ9cAWtWNTcuICc++p8Dct7zNGxCpqmEtqifO7NvuB5dEVexXn9RFFH
12Hm+NtPRQgXIFjx6MSJcNWuVO3XGE57L1mHlcQYj+g4hny90aFh2SCZCDEVkAja
EMMfYPKuCjHuuF+bzHFb/9gV8P9+ekcHENF2nR1efGWSKwnfG5RawlkaQDpRtZTm
M64TIsv/r7cyFO4nSjs1jLdXYdz5q3a4L0NoabZfbdxVb+CUEHfB0bpulZQtH1Rv
38e/lIdP7OTTIlZh6OYL6NhxP8So0/sht/4J9mqIGxRFc0/pC8suja+wcIUna0HB
pXKfXTKpzgis+zmXDL06ASJf5E4A2/m+Hp6b84sfPAwQ766rI65mh50S0Di9E3Pn
2WcaJc+PILsBmYpgtmgWTR9eV9otfKRUBfzHUHcVgarub/XluEpRlTtZudU5xbFN
xx/DgMrXLUAPaI60fZ6wA+PTAgMBAAGjggGBMIIBfTAfBgNVHSMEGDAWgBRWc1hk
lfmSGrASKgRieaFAFYghSTAdBgNVHQ4EFgQUaMASFhgOr872h6YyV6NGUV3LBycw
DgYDVR0PAQH/BAQDAgGGMBIGA1UdEwEB/wQIMAYBAf8CAQAwHQYDVR0lBBYwFAYI
KwYBBQUHAwEGCCsGAQUFBwMCMBsGA1UdIAQUMBIwBgYEVR0gADAIBgZngQwBAgEw
VAYDVR0fBE0wSzBJoEegRYZDaHR0cDovL2NybC5zZWN0aWdvLmNvbS9TZWN0aWdv
UHVibGljU2VydmVyQXV0aGVudGljYXRpb25Sb290UjQ2LmNybDCBhAYIKwYBBQUH
AQEEeDB2ME8GCCsGAQUFBzAChkNodHRwOi8vY3J0LnNlY3RpZ28uY29tL1NlY3Rp
Z29QdWJsaWNTZXJ2ZXJBdXRoZW50aWNhdGlvblJvb3RSNDYucDdjMCMGCCsGAQUF
BzABhhdodHRwOi8vb2NzcC5zZWN0aWdvLmNvbTANBgkqhkiG9w0BAQwFAAOCAgEA
YtOC9Fy+TqECFw40IospI92kLGgoSZGPOSQXMBqmsGWZUQ7rux7cj1du6d9rD6C8
ze1B2eQjkrGkIL/OF1s7vSmgYVafsRoZd/IHUrkoQvX8FZwUsmPu7amgBfaY3g+d
q1x0jNGKb6I6Bzdl6LgMD9qxp+3i7GQOnd9J8LFSietY6Z4jUBzVoOoz8iAU84OF
h2HhAuiPw1ai0VnY38RTI+8kepGWVfGxfBWzwH9uIjeooIeaosVFvE8cmYUB4TSH
5dUyD0jHct2+8ceKEtIoFU/FfHq/mDaVnvcDCZXtIgitdMFQdMZaVehmObyhRdDD
4NQCs0gaI9AAgFj4L9QtkARzhQLNyRf87Kln+YU0lgCGr9HLg3rGO8q+Y4ppLsOd
unQZ6ZxPNGIfOApbPVf5hCe58EZwiWdHIMn9lPP6+F404y8NNugbQixBber+x536
WrZhFZLjEkhp7fFXf9r32rNPfb74X/U90Bdy4lzp3+X1ukh1BuMxA/EEhDoTOS3l
7ABvc7BYSQubQ2490OcdkIzUh3ZwDrakMVrbaTxUM2p24N6dB+ns2zptWCva6jzW
r8IWKIMxzxLPv5Kt3ePKcUdvkBU/smqujSczTzzSjIoR5QqQA6lN1ZRSnuHIWCvh
JEltkYnTAH41QJ6SAWO66GrrUESwN/cgZzL4JLEqz1Y=
-----END CERTIFICATE-----
"""

# 제물포구와 정확히 같은 빠진 중간 인증서(Thawte TLS RSA CA G1)를 쓰는 사이트
# 목록 — 곡성군(gokseong.go.kr)도 실측 확인(2026-09-26, 같은 CA 벤더를 쓰는
# 지자체가 우연히 더 있는 것으로 보인다).
_MISSING_CA_HOSTS = {
    "www.icdonggu.go.kr": _ICDONGGU_MISSING_INTERMEDIATE_PEM,
    "www.gokseong.go.kr": _ICDONGGU_MISSING_INTERMEDIATE_PEM,
    "www.yeongam.go.kr": _YEONGAM_INTERMEDIATE_PEM,
}


class _LegacyTLSAdapter(HTTPAdapter):
    """암호화 스위트만 SECLEVEL=1로 완화한다(std_ezweb.py의 동해시 대응과 동일한
    조치). 인증서 검증 자체는 그대로 켜져 있다."""

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


# 강릉시(www.gn.go.kr)는 최신 OpenSSL 기본 보안수준의 암호화 스위트를 지원하지
# 않는다(실측: SSLV3_ALERT_HANDSHAKE_FAILURE, 2026-09-27) — 목록 사이트만 해당하고
# 첨부 다운로드 서버(eminwon.gangneung.go.kr)는 정상 TLS라 별도로 영향받지 않는다.
# 의성군은 반대 경우다: 목록 사이트(www.usc.go.kr)는 정상인데, download.do가
# 리다이렉트하는 첨부 다운로드 서버(eminwon.uiseong.go.kr)가 같은 핸드셰이크
# 실패를 낸다(실측 확인, 2026-09-28) — 그래서 city.base_url에 호스트명이 나타나는지로
# 거는 게 아니라 무조건 마운트한다(다운로드 서버 호스트는 목록 사이트와 다를 수 있다).
# 청주시 첨부 다운로드 서버(eminwon.cheongju.go.kr)도 같다(실측 2026-10-17: 기본 설정은 SSLV3_ALERT_HANDSHAKE_FAILURE,
# SECLEVEL=1 이면 HTTP 200). 이 때문에 청주시 첨부가 '형식 불일치(UNSUPPORTED)'로 기록되던 문제의 마지막 원인이었다.
_SECLEVEL_HOSTS = {"www.gn.go.kr", "eminwon.uiseong.go.kr", "eminwon.cheongju.go.kr"}

# 강릉시 첨부 다운로드 서버(eminwon.gangneung.go.kr)는 영암군과 같은 중간 인증서(Sectigo Public Server Authentication CA DV R36)를
# 서버가 보내지 않는다(실측 2026-10-17: unable to get local issuer certificate). 발급기관 공개 인증서(AIA caIssuers)를 채워
# 검증은 그대로 켜 둔 채 체인만 완성한다. 목록 사이트와 호스트가 달라 base_url 과 무관하게 마운트한다.
_DOWNLOAD_SERVER_CA_HOSTS = {"eminwon.gangneung.go.kr": _YEONGAM_INTERMEDIATE_PEM}


def prepare_session(session, city):
    """board_crawler.run_city가 지자체별 세션을 만든 직후 한 번 호출한다."""
    for host, pem in _MISSING_CA_HOSTS.items():
        if host in city.base_url and not getattr(session, f"_ca_mounted_{host}", False):
            session.mount(f"https://{host}", _MissingIntermediateCAAdapter(pem))
            setattr(session, f"_ca_mounted_{host}", True)
    for host, pem in _DOWNLOAD_SERVER_CA_HOSTS.items():
        if not getattr(session, f"_ca_mounted_{host}", False):
            session.mount(f"https://{host}", _MissingIntermediateCAAdapter(pem))
            setattr(session, f"_ca_mounted_{host}", True)
    for host in _SECLEVEL_HOSTS:
        if not getattr(session, f"_legacy_tls_{host}", False):
            session.mount(f"https://{host}", _LegacyTLSAdapter())
            setattr(session, f"_legacy_tls_{host}", True)


def _find_subject_cell(tds):
    """제목 칸을 판별한다. 우선순위:
    1. class에 "title"이 들어간 칸(강화군·옹진군·제물포구 등 실측 확인) — 제물포구는
       첨부파일 아이콘 칸에도 빈 텍스트 <a>가 있어 "마지막 <a> 칸" 규칙만으로는
       틀린 칸을 집는다. 아산시는 이 class="title" 칸이 두 개다(공고번호 칸도
       "title", 진짜 제목 칸은 "title alignLeft") — 클래스가 여러 개(더 구체적)인
       칸을 우선한다(실측 확인, 2026-09-27).
    2. 없으면 <a>를 담은 마지막 칸(강화군·옹진군처럼 공고번호 칸에도 같은 링크가
       중복으로 걸려 있는 경우 제목 칸이 보통 더 뒤에 있다).
    3. 그래도 없으면 <a>를 담은 첫 칸(대부분의 다른 사이트)."""
    title_candidates = [
        td for td in tds if any("title" in c for c in (td.get("class") or [])) and td.find("a") is not None
    ]
    if title_candidates:
        multi_class = [td for td in title_candidates if len(td.get("class") or []) > 1]
        return multi_class[0] if multi_class else title_candidates[0]
    candidate = None
    for td in tds:
        if td.find("a") is not None:
            candidate = td
    return candidate


def _cell_text(td):
    """칸의 텍스트를 뽑되, 라벨용 <b class="mtitle">칸이름</b>(남원시 등, 실측 확인
    2026-09-27)이 있으면 떼어낸다 — 안 떼면 "등록일2026-09-23"처럼 라벨이 날짜/
    공고번호 앞에 그대로 붙어 정규식이 못 알아본다."""
    label = td.find("b", class_="mtitle")
    if label is not None:
        td = copy.deepcopy(td)
        td.find("b", class_="mtitle").decompose()
    return td.get_text(strip=True)


def _find_notice_no(tds, subject_idx):
    for td in tds:
        text = _cell_text(td)
        if _NOTICE_NO_RE.search(text):
            return text
    return _cell_text(tds[subject_idx - 1]) if subject_idx > 0 else ""


def _find_date_str(tds):
    for td in tds:
        text = _cell_text(td)
        if _DATE_CELL_RE.match(text):
            return text
    return ""


def _parse_post_date(date_str):
    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]
    base_url은 (key 등 지자체별 파라미터를 포함한) selectEminwonList.do 전체 URL이다.
    페이지네이션 파라미터 이름이 지자체마다 다르다(대부분 pageIndex, 강화군·옹진군
    계열은 pgno, 목포시는 page, 군위군은 pageNo, 아산시는 대문자 PageNo, 부천시는
    currentpage, 예천군은 p, 영덕군(워드프레스 kboard)은 pageid — 쿼리 파라미터
    이름은 대소문자를 구분한다, 실측 확인, 2026-09-25/27/28). 안 쓰는 파라미터는
    서버가 그냥 무시하니 다 같이 보낸다. 영덕군은 base_url 자체에 이미 쿼리
    파라미터 page_id=763(게시판 고유 ID, kboard 플러그인 규약)이 들어있는데, 이건
    페이지 번호가 아니라 게시판 식별자라 페이지네이션과 무관하다 — 페이지 번호는
    별도 파라미터 pageid(밑줄 없음)로 넘어간다(실측 확인, 2026-09-28)."""
    resp = session.get(
        base_url,
        params={
            "pageIndex": page_index,
            "pgno": page_index,
            "page": page_index,
            "pageNo": page_index,
            "PageNo": page_index,
            "currentpage": page_index,
            "p": page_index,
            "pageid": page_index,
            "pageUnit": page_unit,
        },
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.select_one("table.p-table") or soup.find("table")
    if table is None:
        return []

    # searchDetail(id) 방식(곡성군·구례군)을 쓰는 페이지인지 미리 한 번만 확인해 둔다.
    # eGovFramework 계열 공통 관용구지만 실제 구현이 두 갈래다:
    #   - 곡성군: document.<폼이름>.action을 GosiView.do로 바꾼 뒤 그 폼(hidden 필드
    #     전부, method="get")을 submit — 폼 hidden 필드 값 그대로 + not_ancmt_mgt_no만
    #     바꿔서 재구성한다.
    #   - 구례군: location.href = '<GosiView.do?...고정 쿼리>' + '&not_ancmt_mgt_no=' + id
    #     처럼 URL 조각을 문자열로 바로 조립 — 그 고정 쿼리 뒤에 not_ancmt_mgt_no만
    #     붙이면 된다(폼 hidden 필드 불필요).
    detail_action, detail_fields = None, None
    location_href_prefix = None
    # 페이지 전체가 아니라 searchDetail() 함수 본문 안에서만 찾는다 — 페이지 다른
    # 곳(상단 검색창 등)의 무관한 ".action = ..." 대입에 잘못 걸리는 걸 막는다
    # (구례군 실측 확인, 2026-09-28: 페이지 전체 검색은 엉뚱한 폼을 집었다).
    fn_match = re.search(r"function\s+searchDetail\b[^{]*\{(.*?)\n\}", resp.text, re.DOTALL)
    fn_body = fn_match.group(1) if fn_match else ""
    mgt_no_form = next(
        (f for f in soup.find_all("form") if f.find("input", {"name": "not_ancmt_mgt_no"}) is not None), None
    )
    if mgt_no_form is not None:
        m = _FORM_ACTION_OVERRIDE_RE.search(fn_body)
        if m:
            detail_action = urljoin(resp.url, _JSESSIONID_RE.sub("", m.group(1)))
            detail_fields = {
                inp.get("name"): (inp.get("value") or "")
                for inp in mgt_no_form.find_all("input")
                if inp.get("name")
            }
    if detail_action is None:
        m = _LOCATION_HREF_RE.search(fn_body)
        if m:
            location_href_prefix = urljoin(resp.url, m.group(1))

    rows = []
    for tr in table.select("tbody tr"):
        tds = tr.find_all("td")
        subject_td = _find_subject_cell(tds)
        if subject_td is None:
            continue
        a = subject_td.find("a")
        href = a.get("href", "")
        detail_url = None
        if href and href != "#" and not href.lower().startswith("javascript:"):
            detail_url = urljoin(resp.url, href)
        else:
            m = _SEARCH_DETAIL_ONCLICK_RE.search(href + a.get("onclick", ""))
            if m and detail_action is not None:
                fields = dict(detail_fields)
                fields["not_ancmt_mgt_no"] = m.group(1)
                detail_url = detail_action + "?" + urlencode(fields)
            elif m and location_href_prefix is not None:
                sep = "&" if "?" in location_href_prefix else "?"
                detail_url = f"{location_href_prefix}{sep}not_ancmt_mgt_no={m.group(1)}"
        if not detail_url:
            continue
        title = re.sub(r"\s+", " ", a.get_text(strip=True)).strip()
        try:
            subject_idx = tds.index(subject_td)
        except ValueError:
            subject_idx = 0
        notice_no = _find_notice_no(tds, subject_idx)
        date_str = _find_date_str(tds)
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


def _eminwon_host(url):
    netloc = urlsplit(url).netloc
    if netloc.startswith("www."):
        netloc = netloc[len("www."):]
    return "eminwon." + netloc


def fetch_attachments(session, detail_url):
    """상세 페이지의 첨부파일 [{"name", "url", "ext"}, ...] (다운로드는 하지 않음)."""
    resp = session.get(detail_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    attachments = []
    # href*='FileDown'는 남원시의 "전체다운" 링크(href="javascript:allFileDown(...)")도
    # 부분문자열로 걸려버려(실측 확인, 2026-09-27) javascript: 스킴은 제외한다 —
    # 진짜 완성된 다운로드 링크는 항상 실제 URL이다.
    for a in soup.select("a[href*='FileDown']"):
        raw_href = a.get("href", "")
        if raw_href.startswith("javascript:"):
            continue
        href = urljoin(resp.url, raw_href)
        query = dict(parse_qsl(urlsplit(href).query))
        name = unquote(query.get("user_file_nm", "")) or a.get_text(strip=True)
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": href, "ext": ext})
    if attachments:
        return attachments

    # 김포시: href가 아니라 data-user-file-nm/data-sys-file-nm/data-file-path 속성에
    # 값이 있고, 클릭 시 JS가 그걸로 FileDown.jsp GET href를 조립한다(실측 확인,
    # 2026-09-28) — 클릭 이벤트 없이 속성값만 바로 읽어 같은 URL을 만든다.
    for a in soup.select("a.ntfc_file_down[data-user-file-nm]"):
        user_name = a.get("data-user-file-nm", "")
        sys_name = a.get("data-sys-file-nm", "")
        file_path = a.get("data-file-path", "")
        if not user_name:
            continue
        ext = user_name.rsplit(".", 1)[-1].lower() if "." in user_name else ""
        url = (
            f"https://{_eminwon_host(resp.url)}/emwp/jsp/ofr/FileDown.jsp"
            f"?user_file_nm={quote(user_name)}&sys_file_nm={quote(sys_name)}&file_path={quote(file_path)}"
        )
        attachments.append({"name": user_name, "url": url, "ext": ext})
    if attachments:
        return attachments

    # 장흥군: href가 아니라 <button onclick="window.open('...FileDown.jsp?...')">에
    # 완성된 URL이 들어있다(실측 확인, 2026-09-27).
    for btn in soup.find_all(["button", "a"], onclick=_WINDOW_OPEN_FILEDOWN_RE):
        m = _WINDOW_OPEN_FILEDOWN_RE.search(btn.get("onclick", ""))
        href = urljoin(resp.url, m.group(1))
        query = dict(parse_qsl(urlsplit(href).query))
        name = unquote(query.get("user_file_nm", "")) or btn.get_text(strip=True)
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": href, "ext": ext})
    if attachments:
        return attachments

    # 남원시: <a href="download.do?boardUid=&postUid=&atchFileUid=">파일명.ext</a>
    # (완성된 GET 링크, 링크 텍스트 자체가 파일명 — 같은 href를 가리키는 "다운로드"
    # 라벨 링크가 하나 더 있어(class="btn_down") 중복 제거한다. 실측 확인, 2026-09-27).
    seen_download_urls = set()
    for a in soup.select("a[href*='download.do']"):
        href = urljoin(resp.url, a.get("href", ""))
        name = re.sub(r"\s+", " ", a.get_text(strip=True)).strip()
        if not name or "." not in name or href in seen_download_urls:
            continue
        seen_download_urls.add(href)
        ext = name.rsplit(".", 1)[-1].lower()
        attachments.append({"name": name, "url": href, "ext": ext})
    if attachments:
        return attachments

    # 진도군: <a href="/doc/dataDown.jsp?...">완성된 GET 링크(실측 확인, 2026-09-27).
    # 같은 <li> 안의 앞선 <a><em>파일명</em></a>에서 진짜 파일명을 읽는다 —
    # goDownload(...) 링크는 주석 처리돼 죽어 있고 dataDown.jsp가 실제 다운로드다.
    for a in soup.select("a.down[href*='dataDown.jsp']"):
        href = urljoin(resp.url, a.get("href", ""))
        em = a.find_previous_sibling("a")
        name = em.find("em").get_text(strip=True) if em and em.find("em") else a.get_text(strip=True)
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": href, "ext": ext})
    if attachments:
        return attachments

    # 영덕군(워드프레스 kboard): <a href="https://www.yd.go.kr/?action=kboard_file_download
    # &uid=<글번호>&file=file1">실제파일명.ext</a> — 이미 완성된 GET 링크고 링크 텍스트가
    # 그대로 실제 파일명이다(실측 확인, 2026-09-28). 단, Referer 헤더 없이 요청하면
    # 세션 쿠키가 있어도 에러 페이지(362바이트 text/html)를 돌려준다 — 상세 페이지
    # URL을 Referer로 같이 보내야 진짜 파일이 내려온다(실측 확인).
    for a in soup.select("a[href*='kboard_file_download']"):
        href = urljoin(resp.url, a.get("href", ""))
        name = re.sub(r"\s+", " ", a.get_text(strip=True)).strip()
        if not name or "." not in name:
            continue
        ext = name.rsplit(".", 1)[-1].lower()
        attachments.append({"name": name, "url": href, "ext": ext, "_referer": resp.url})
    if attachments:
        return attachments

    # href가 javascript:goDownLoad(...)뿐인 경우 — 먼저 POST 방식인지 확인. 폼 이름은
    # 보통 "nnn"이지만 순천시는 "form1"이다(실측 확인, 2026-09-28) — 이름이 아니라
    # user_file_nm/sys_file_nm/file_path 세 hidden 필드를 다 가진 폼인지로 판별한다.
    down_form = next(
        (
            f
            for f in soup.find_all("form")
            if f.find("input", {"name": "user_file_nm"}) is not None
            and f.find("input", {"name": "sys_file_nm"}) is not None
            and f.find("input", {"name": "file_path"}) is not None
        ),
        None,
    )
    down_action, down_fields = None, None
    if down_form is not None:
        down_action = urljoin(resp.url, down_form.get("action", ""))
        if not down_form.get("action"):
            # 청주시: 폼에 action 이 없고 goDownLoad() JS 가 'f.action = "https://eminwon.cheongju.go.kr/emwp/jsp/ofr/FileDown.jsp"' 로
            # 넣어 제출한다(실측 2026-10-17). action 이 비었다고 상세 페이지 주소로 POST 하면 HTML 이 내려와 '형식 불일치'로 기록된다.
            js_action = re.search(r"function\s+goDownLoad\s*\([^)]*\)\s*\{[^}]*?\.action\s*=\s*[\"']([^\"']+)[\"']", resp.text)
            if js_action:
                down_action = urljoin(resp.url, js_action.group(1))
        down_fields = {
            inp.get("name"): (inp.get("value") or "") for inp in down_form.find_all("input") if inp.get("name")
        }
    else:
        host = _eminwon_host(resp.url)

    # 곡성군은 같은 goDownLoad(...) 인자를 가리키는 <a> 2개가 늘 붙어 있다(실측
    # 확인, 2026-09-28) — 하나는 진짜 파일명이 텍스트고, 바로 옆 <div class=
    # "inner_btn"> 안 것은 라벨이 "다운로드"뿐인 중복 버튼이다. 인자 3개(토큰)가
    # 같으면 같은 파일이므로 처음 나온 것만 남긴다(문서 순서상 진짜 파일명 쪽이 항상
    # 먼저 나온다).
    seen_godownload_args = set()
    for a in soup.find_all(["a", "button"]):
        m = _GO_DOWNLOAD_RE.search(a.get("href", "") + a.get("onclick", ""))
        if not m:
            continue
        if m.groups() in seen_godownload_args:
            continue
        seen_godownload_args.add(m.groups())
        user_name, sys_name, file_path = m.groups()
        if down_form is not None:
            # POST 방식이라도 지자체마다 첫 인자(user_file_nm)의 의미가 다르다:
            # 보령시는 암호화된 토큰이라 링크 텍스트를 진짜 파일명으로 써야 하고,
            # 영양군은 첫 인자 자체가 이미 실제 파일명(확장자 포함 평문)이라 버튼
            # 텍스트("다운로드" 같은 라벨만 있음)를 쓰면 안 된다(실측 확인, 2026-09-28)
            # — 확장자로 끝나면 평문 파일명으로 보고 그대로 쓰고, 아니면 기존처럼
            # 링크/버튼 텍스트로 대체한다.
            if _FILENAME_LIKE_RE.search(user_name):
                display_name = user_name
            else:
                display_name = re.sub(r"\s+", " ", a.get_text(strip=True)).strip() or user_name
                # 영암군은 링크 텍스트 자체가 "파일명.ext 다운로드"처럼 라벨이 그대로
                # 붙어 있다(실측 확인, 2026-09-28) — 확장자 뒤에 붙은 라벨만 뗀다.
                display_name = re.sub(r"(\.[A-Za-z0-9]{2,5})\s*다운로드$", r"\1", display_name)
            post_data = dict(down_fields)
            post_data["user_file_nm"] = user_name
            post_data["sys_file_nm"] = sys_name
            post_data["file_path"] = file_path
            ext = display_name.rsplit(".", 1)[-1].lower() if "." in display_name else ""
            attachments.append(
                {
                    "name": display_name,
                    "url": down_action,
                    "ext": ext,
                    "_dl_method": "POST",
                    "_dl_action": down_action,
                    "_dl_data": post_data,
                }
            )
        else:
            # GET 방식: 토큰 자체가 실제 파일명이다(밀양시)
            url = (
                f"https://{host}/emwp/jsp/ofr/FileDown.jsp"
                f"?user_file_nm={quote(user_name)}&sys_file_nm={quote(sys_name)}&file_path={quote(file_path)}"
            )
            ext = user_name.rsplit(".", 1)[-1].lower() if "." in user_name else ""
            attachments.append({"name": user_name, "url": url, "ext": ext})
    return attachments


def download_attachment(session, attachment):
    if attachment.get("_dl_method") == "POST":
        resp = session.post(
            attachment["_dl_action"], data=attachment.get("_dl_data", {}), headers=HEADERS, timeout=30
        )
    else:
        headers = HEADERS
        if attachment.get("_referer"):
            headers = {**HEADERS, "Referer": attachment["_referer"]}
        resp = session.get(attachment["url"], headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.content
