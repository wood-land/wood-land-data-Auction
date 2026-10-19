"""
gwd_bulletin.py — "portal/bulletin/notification" 게시판(강원특별자치도청,
goPage()/egf 첨부 계열) 어댑터.

강원도청에서 실측 확인했다(2026-09-26). 화면은 <form name="mForm"> JS 제출
(goPage()/linkPage())을 쓰지만 그 form의 method가 실제로 GET이라(실측 확인)
articleSeq/pageIndex를 그냥 쿼리스트링으로 붙여도 그대로 열린다.

목록: GET portal/bulletin/notification?pageIndex=<P>, <td class="skinTb-sbj">
<a onclick="goPage(<articleSeq>); return false;">.

상세: GET portal/bulletin/notification?articleSeq=<id>. 첨부는
<a href="/egf/bp/common/front/<fileId>/download"><span class="icoFile..."></span> 파일명.ext</a>
— 아이콘 span은 텍스트가 없어 a.get_text()가 그대로 파일명이 된다.

City.boards 항목 형식: {"name": "고시공고"}
"""

import datetime as dt
import re
import ssl
from urllib.parse import urljoin, urlsplit

import certifi
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

# 인제군도 강원도청과 같은 "skinTb-data-resList" 플랫폼을 쓴다(실측 확인,
# 2026-09-26) — 다만 서버가 중간 인증서를 안 보낸다(Sectigo Public Server
# Authentication CA DV R36 누락). 발급기관 공개 배포처
# (http://crt.sectigo.com/SectigoPublicServerAuthenticationCADVR36.crt)에서 받았다.
# 속초시도 같은 발급기관의 같은 중간 인증서가 빠져 있다(실측 확인, 2026-09-28 —
# openssl s_client로 확인한 issuer가 인제군과 동일).
_INJE_MISSING_INTERMEDIATE_PEM = """-----BEGIN CERTIFICATE-----
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
-----END CERTIFICATE-----"""

_MISSING_CA_SITE_ROOTS = {"https://www.inje.go.kr", "https://www.sokcho.go.kr"}


class _MissingIntermediateCAAdapter(HTTPAdapter):
    """인증서 검증은 그대로 켠 채, 빠진 중간 인증서만 신뢰 저장소에 추가한다.

    속초시는 이 중간 인증서 누락에 더해 암호화 스위트도 최신 기본값을 지원하지
    않는다(실측 확인, 2026-09-28) — SECLEVEL=1 완화를 함께 적용한다. 인제군은
    이미 기본 스위트로 접속되던 곳이라 이 완화가 있어도(더 넓은 스위트를 허용할
    뿐이라) 영향이 없다."""

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context(cafile=certifi.where())
        ctx.load_verify_locations(cadata=_INJE_MISSING_INTERMEDIATE_PEM)
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def prepare_session(session, city):
    root = f"{urlsplit(city.base_url).scheme}://{urlsplit(city.base_url).netloc}"
    if root in _MISSING_CA_SITE_ROOTS and not getattr(session, f"_ca_mounted_{root}", False):
        session.mount(root, _MissingIntermediateCAAdapter())
        setattr(session, f"_ca_mounted_{root}", True)

_DATE_CELL_RE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")
_NOTICE_NO_RE = re.compile(r"(공고|고시)\s*제\s*\d{4}\s*[-–]\s*\d+\s*호")
_GOPAGE_RE = re.compile(r"goPage\(\s*(\d+)\s*\)")


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    resp = session.get(base_url, params={"pageIndex": page_index}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for tr in soup.select("table.skinTb tbody tr"):
        subject_td = tr.find("td", class_="skinTb-sbj")
        a_tag = subject_td.find("a") if subject_td else None
        if a_tag is None:
            continue
        # 강원도청/인제군은 onclick="goPage(<articleSeq>)"(숫자)뿐이지만, 평창군은
        # <a href="...?noticeMgrNo=..." onclick="goPage(this.href)">처럼 href
        # 자체가 이미 완성된 링크다(실측 확인, 2026-09-26) — href가 진짜 링크면
        # 그대로 쓰고, 아니면 goPage(숫자)에서 articleSeq를 뽑아 조립한다.
        href = a_tag.get("href", "")
        if href and href not in ("#", "#nolink", "javascript:void(0);") and not href.startswith("javascript:"):
            detail_url = urljoin(resp.url, href)
        else:
            m = _GOPAGE_RE.search(a_tag.get("onclick", ""))
            if m is not None:
                detail_url = f"{base_url}?articleSeq={m.group(1)}"
            else:
                # 속초시: href="#nolink"이고 data-key="<id>"를 JS가 hidden 필드
                # notAncmtMgtNo로 옮겨 폼을 제출한다(실측 확인, 2026-09-28) — 그
                # 필드명 그대로 GET 쿼리스트링을 붙여도 동일하게 열린다.
                data_key = a_tag.get("data-key")
                if not data_key:
                    continue
                detail_url = f"{base_url}?notAncmtMgtNo={data_key}"
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
    for div in soup.select("div.attachFile"):
        # 강원도청 등은 자체 "/egf/bp/common/front/<id>/download" GET 링크지만,
        # 속초시는 같은 div.attachFile 안에 eminwon.*.go.kr의 FileDown.jsp 완성된
        # GET 링크를 쓴다(실측 확인, 2026-09-28) — 둘 다 지원한다.
        a = div.find("a", href=re.compile(r"/download$")) or div.find("a", href=re.compile(r"FileDown"))
        if a is None:
            continue
        name = a.get_text(strip=True)
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": urljoin(resp.url, a.get("href", "")), "ext": ext})
    return attachments
