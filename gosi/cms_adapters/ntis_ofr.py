"""
ntis_ofr.py — "NTIS eMinwon 고시공고"(OfrNotAncmtL.jsp / OfrNotAncmtLSub.jsp) 공통 어댑터.

행정안전부 표준 eMinwon 시스템(페이지 안의 jndinm=OfrNotAncmtEJB, context=NTIS 필드로
식별됨)을 쓰는 지자체 공통 어댑터. 정읍시·익산시·광주남구에서 실측 확인했다(2026-09-25).

이 시스템은 목록/상세 모두 순수 GET이 아니라, 페이지에 있는 <form name="form1">의
숨은 필드값을 그대로 들고 고정된 액션 URL(/emwp/gov/mogaha/ntis/web/ofr/action/
OfrAction.do)로 POST해야 실제 데이터가 나온다 — GET만 하면 "전체게시물:0개"만
나온다(실측 확인). 사이트마다 숨은 필드 구성이 조금씩 다르므로(정읍시엔 있는 필드가
익산시엔 없는 등) 필드를 하드코딩하지 않고 그 페이지에서 읽은 값을 그대로 재사용하고
method/methodnm/pageIndex만 바꾼다.

목록 결과 마크업도 지자체마다 갈린다: 정읍시·익산시는 <table summary="...">인데,
광주남구는 <div class="dbody"> 안에 행마다 <ul>, 칸마다 <li class="col02/title/
col04...">인 완전히 다른 레이아웃이다 — 그래서 _raw_items_from_table/_div 두 경로를
모두 시도한다. (광주남구는 원래 보상맵 시트의 URL이 깨져 있었는데, 사용자가 실제
게시판 URL을 다시 알려줘서 이 iframe 뒤에 있는 게 같은 NTIS 백엔드임을 확인했다.)

첨부파일 다운로드는 상세 페이지의 <a href="javascript:goDownLoad(a,b,c)">에서 세 값을
그대로 꺼내 쓰는데, goDownLoad()의 실제 구현이 지자체마다 다르다(2026-09-25 실측):
  - 정읍시: <form name="nnn">이 가리키는 액션(FileDownNew.jsp)으로 POST(신버전)
  - 익산시: /emwp/jsp/ofr/FileDown.jsp 로 GET, 값은 encodeURI로만 인코딩(구버전 —
    페이지 안에 "(2011.08.02)수정 전/후" 주석이 남아있어 옛 방식임을 알 수 있다)
GET으로 바로 못 받는 경우가 있어(POST 방식) core.board_crawler의 download_attachment
확장 지점을 쓴다. attachment dict에 담아 둔 _dl_method/_dl_action/_dl_data 로 재구성한다.

detail_url은 이 시스템에 진짜 GET URL이 없어서(POST 상태 기반) base_url 뒤에
"#ntis-mgtno=<id>"를 붙인 값으로 대신한다 — fetch_attachments가 이를 다시 풀어서
base_url을 재조회한 뒤 상세 조회 POST를 만든다.
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

_ACTION_PATH = "/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do"
_SEARCH_DETAIL_RE = re.compile(r"searchDetail\('([^']*)'\)")
# 연수구: onclick/searchDetail() 없이 href 자체가 이미 완성된 OfrAction.do GET
# 링크다(실측 확인, 2026-09-27) — not_ancmt_mgt_no 쿼리파라미터에서 바로 id를 읽는다.
_MGT_NO_HREF_RE = re.compile(r"not_ancmt_mgt_no=(\d+)")
_GO_DOWNLOAD_RE = re.compile(r"goDownLoad\('(.*)'\s*,\s*'(.*)'\s*,\s*'(.*)'\)")
# 논산시는 "YYYY.MM.DD" 점 형식을 쓴다(실측 확인, 2026-09-27) — 기존 대시 형식과
# 함께 지원한다.
_DATE_CELL_RE = re.compile(r"^\d{4}[.\-]\d{1,2}[.\-]\d{1,2}$")
_NOTICE_NO_RE = re.compile(r"(공고|고시)\s*제\s*\d{4}\s*[-–]\s*\d+\s*호")
_DETAIL_MARKER = "#ntis-mgtno="


def _search_detail_match(tag):
    """searchDetail('<id>')를 onclick 또는 href(논산시, 실측 확인 2026-09-27) 양쪽에서 찾고,
    없으면 href 자체가 완성된 OfrAction.do 링크인 경우(연수구, 실측 확인 2026-09-27)
    not_ancmt_mgt_no= 값을 찾는다 — 항상 group(1)에 id가 오도록 통일한다."""
    return (
        _SEARCH_DETAIL_RE.search(tag.get("onclick", ""))
        or _SEARCH_DETAIL_RE.search(tag.get("href", ""))
        or _MGT_NO_HREF_RE.search(tag.get("href", ""))
    )


def _is_search_detail_tag(tag):
    return tag.name in ("a", "td") and _search_detail_match(tag) is not None


# 순창군(eminwon.sunchang.go.kr)은 중간 인증서(RapidSSL TLS RSA CA G1)를 안 보내
# 체인을 못 만든다(실측 확인, 2026-09-28) — 철원군(std_ezweb.py)에서 이미 검증된
# 것과 같은 발급기관 공개 배포 인증서를 재사용한다. 검증을 끈 게 아니라 체인을
# 완성한 것이다.
_RAPIDSSL_INTERMEDIATE_PEM = """-----BEGIN CERTIFICATE-----
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
-----END CERTIFICATE-----"""
_MISSING_CA_HOSTS = {"eminwon.sunchang.go.kr": _RAPIDSSL_INTERMEDIATE_PEM}


class _LegacyTLSAdapter(HTTPAdapter):
    """일부 eminwon.*.go.kr 서버가 최신 OpenSSL 기본 보안수준의 암호화 스위트를
    지원하지 않는다(실측: 익산시, SSLV3_ALERT_HANDSHAKE_FAILURE). 암호화 스위트만
    SECLEVEL=1로 완화하고 인증서 검증(cert_verify)은 그대로 상속해 유지한다.
    extra_cadata가 있으면(순창군) 빠진 중간 인증서도 함께 신뢰 목록에 추가한다."""

    def __init__(self, extra_cadata=None, *args, **kwargs):
        self._extra_cadata = extra_cadata
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        if self._extra_cadata:
            ctx.load_verify_locations(cadata=self._extra_cadata)
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def _site_root(url):
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def prepare_session(session, city):
    """base_url 도메인 자체가 eminwon.*.go.kr 서브도메인인 지자체를 위해 레거시
    TLS를 방어적으로 mount해 둔다(필요 없는 곳엔 그냥 영향이 없다)."""
    if not hasattr(session, "_ntis_legacy_mounted"):
        session._ntis_legacy_mounted = set()
    root = _site_root(city.base_url)
    if root not in session._ntis_legacy_mounted:
        host = urlsplit(city.base_url).netloc
        session.mount(root, _LegacyTLSAdapter(_MISSING_CA_HOSTS.get(host)))
        session._ntis_legacy_mounted.add(root)


def _form_fields(session, url, form_name):
    resp = session.get(url, headers=HEADERS, timeout=40)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    form = soup.find("form", {"name": form_name})
    if form is None:
        return None, soup, resp
    fields = {inp.get("name"): (inp.get("value") or "") for inp in form.find_all("input") if inp.get("name")}
    return fields, soup, resp


def _raw_items_from_table(soup):
    """목록이 <table>로 온 경우(정읍시·익산시·부산진구·진안군) ->
    [(mgt_no, notice_no, title, date_str), ...] / 없으면 None.

    정읍시·익산시는 <table summary="...">이지만 부산진구는 summary 속성이 아예
    없는 평범한 <table>이다(실측 확인, 2026-09-26) — summary 유무로 테이블을
    고르지 않고, 행 안에 searchDetail()이 있는지(내용 패턴)로 진짜 목록 테이블을
    찾는다(law.md 3-2). 진안군은 그게 <a>가 아니라 <td>에 onclick으로 직접 걸려
    있어(실측 확인) <a> 한정 검색으로는 테이블 자체를 못 찾는다 — <a>/<td> 모두
    후보로 본다. 논산시는 onclick이 아니라 href="javaScript:searchDetail(...)"
    형태라(실측 확인, 2026-09-27) onclick/href 둘 다 검사한다."""
    # 정읍시는 목록 테이블이 페이징 등을 감싸는 바깥 <table> 안에 중첩돼 있어
    # (실측 확인), "onclick 패턴이 있는 첫 테이블"만으로 고르면 그 바깥 wrapper를
    # 잘못 고를 수 있다 — 중첩 <table>이 없는(leaf) 테이블만 후보로 삼는다.
    list_table = None
    for t in soup.find_all("table"):
        if t.find("table") is not None:
            continue
        if t.find(_is_search_detail_tag) is not None:
            list_table = t
            break
    if list_table is None:
        return None

    # 제목/고시공고번호 칸의 위치를 <th> 헤더 텍스트로 먼저 파악해 둔다. 진안군은
    # "번호"/"고시공고번호"/"제목" 칸 전부가 같은 형태의 onclick을 갖고 있어(실측
    # 확인) onclick 유무만으로는 칸을 구분할 수 없다 — 헤더가 있으면 그 열 번호를
    # 그대로 쓰고, 헤더가 없는 변형이면 예전 방식(가장 긴 텍스트)으로 대체한다.
    title_idx = None
    notice_idx = None
    for tr in list_table.find_all("tr"):
        ths = tr.find_all("th")
        if not ths:
            continue
        header_texts = [th.get_text(strip=True) for th in ths]
        for i, text in enumerate(header_texts):
            if "제목" in text:
                title_idx = i
            if "공고번호" in text:
                notice_idx = i
        # 논산시는 thead가 "번호"칸까지 전부 <th>로 세지만(실측 확인, 2026-09-27),
        # 데이터 행은 번호 칸만 <th>고 나머지가 <td>라 <td>만 세면 한 칸씩 밀린다
        # (예: 헤더 index 2 "제목"인데 데이터 <td>로는 index 1) — 실제 데이터 행의
        # <td> 개수와 비교해 그 차이만큼 인덱스를 보정한다.
        sample_row = next(
            (r for r in list_table.find_all("tr") if r.find(_is_search_detail_tag) is not None), None
        )
        if sample_row is not None:
            offset = len(header_texts) - len(sample_row.find_all("td"))
            if offset > 0:
                if title_idx is not None:
                    title_idx -= offset
                if notice_idx is not None:
                    notice_idx -= offset
        break

    items = []
    for tr in list_table.find_all("tr"):
        el = tr.find(_is_search_detail_tag)
        if el is None:
            continue
        m = _search_detail_match(el)
        tds = tr.find_all("td")
        if len(tds) < 4:
            continue
        texts = [re.sub(r"\s+", " ", td.get_text(strip=True)).strip() for td in tds]

        if title_idx is not None and title_idx < len(texts):
            title = texts[title_idx]
        else:
            # 정읍시는 "번호" 칸도 title 칸과 같은 searchDetail() onclick을 가진
            # <a>로 감싸져 있어(실측 확인) 첫 후보만 보면 번호를 제목으로 잘못
            # 집는다 — 숫자만이거나 공고번호 형식인 후보는 제외하고 가장 긴
            # 텍스트를 제목으로 본다.
            candidates = [c for c in tr.find_all(["a", "td"]) if _is_search_detail_tag(c)]
            text_candidates = [c.get_text(strip=True) for c in candidates]
            title_pool = [t for t in text_candidates if t and not t.isdigit() and not _NOTICE_NO_RE.search(t)]
            title = max(title_pool, key=len) if title_pool else next((t for t in text_candidates if t), "")

        # 고시공고번호 칸이 없는 지자체(부산진구)도 있어(실측 확인), 헤더로 못
        # 찾으면 공고/고시번호 형식(제YYYY-N호)에 맞는 칸이 있을 때만 쓴다.
        if notice_idx is not None and notice_idx < len(texts):
            notice_no = texts[notice_idx]
        else:
            notice_no = next((t for t in texts if _NOTICE_NO_RE.search(t)), "")
        date_str = next((t for t in texts if _DATE_CELL_RE.match(t)), "")
        items.append((m.group(1), notice_no, title, date_str))
    return items


def _raw_items_from_div(soup):
    """목록이 <div class="dbody"><ul>(행)<li>(칸)로 온 경우(광주남구) ->
    [(mgt_no, notice_no, title, date_str), ...] / 없으면 None"""
    dbody = soup.select_one("div.dbody")
    if dbody is None:
        return None
    items = []
    for ul in dbody.find_all("ul", recursive=False):
        a = ul.find("a", onclick=True)
        if a is None:
            continue
        m = _SEARCH_DETAIL_RE.search(a.get("onclick", ""))
        if not m:
            continue
        notice_li = ul.select_one('li[class*="col02"]')
        title_li = ul.select_one('li[class*="title"]')
        date_li = ul.select_one('li[class*="col04"]')
        notice_no = notice_li.get_text(strip=True) if notice_li else ""
        title = re.sub(r"\s+", " ", title_li.get_text(strip=True)).strip() if title_li else ""
        date_str = date_li.get_text(strip=True) if date_li else ""
        items.append((m.group(1), notice_no, title, date_str))
    return items


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]
    지자체마다 마크업이 <table>(정읍시·익산시) 또는 <div>/<ul>/<li>(광주남구)로 갈린다."""
    # 대부분은 <form name="form1">이지만 기장군은 <form name="form">이다(실측
    # 확인, 2026-09-26) — 폼 이름 자체가 다른 배포판이 있어 둘 다 시도한다.
    fields, _soup, _resp = _form_fields(session, base_url, "form1")
    if fields is None:
        fields, _soup, _resp = _form_fields(session, base_url, "form")
    if fields is None:
        return []
    fields["method"] = "selectListOfrNotAncmt"
    fields["methodnm"] = "selectListOfrNotAncmtHomepage"
    fields["pageIndex"] = str(page_index)
    fields["ofr_pageSize"] = str(page_unit)
    resp = session.post(_site_root(base_url) + _ACTION_PATH, data=fields, headers=HEADERS, timeout=40)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    raw_items = _raw_items_from_table(soup)
    if raw_items is None:
        raw_items = _raw_items_from_div(soup)
    if not raw_items:
        return []

    rows = []
    for mgt_no, notice_no, title, date_str in raw_items:
        post_date = None
        if date_str:
            try:
                post_date = dt.datetime.strptime(date_str.replace(".", "-"), "%Y-%m-%d").date()
            except ValueError:
                pass
        rows.append(
            {
                "board": board["name"],
                "notice_no": notice_no,
                "title": title,
                "date": post_date,
                "date_str": date_str,
                "detail_url": base_url + _DETAIL_MARKER + mgt_no,
            }
        )
    return rows


def fetch_attachments(session, detail_url):
    """상세 페이지의 첨부파일 [{"name","url","ext","_dl_method","_dl_action","_dl_data"}, ...]
    (다운로드는 하지 않음). url은 참고용 표시값일 뿐이고, 실제 다운로드는
    download_attachment()가 _dl_* 필드로 재구성한다(POST/GET 방식이 지자체마다 다름)."""
    base_url, marker, mgt_no = detail_url.partition(_DETAIL_MARKER)
    if not marker:
        return []
    # 기장군·연수구처럼 <form name="form1">이 아니라 <form name="form">인 변형도
    # 있어(실측 확인) fetch_list_page와 같은 순서로 둘 다 시도한다.
    fields, _soup, _resp = _form_fields(session, base_url, "form1")
    if fields is None:
        fields, _soup, _resp = _form_fields(session, base_url, "form")
    if fields is None:
        return []
    fields["method"] = "selectOfrNotAncmt"
    fields["methodnm"] = "selectOfrNotAncmtRegst"
    fields["not_ancmt_mgt_no"] = mgt_no
    resp = session.post(_site_root(base_url) + _ACTION_PATH, data=fields, headers=HEADERS, timeout=40)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    down_form = soup.find("form", {"name": "nnn"})
    down_action, down_fields = None, None
    if down_form is not None:
        down_action = urljoin(resp.url, down_form.get("action", ""))
        down_fields = {
            inp.get("name"): (inp.get("value") or "") for inp in down_form.find_all("input") if inp.get("name")
        }

    attachments = []
    for a in soup.find_all("a", href=re.compile(r"^javascript:goDownLoad\(")):
        m = _GO_DOWNLOAD_RE.search(a.get("href", ""))
        if not m:
            continue
        user_name, sys_name, file_path = m.groups()
        ext = user_name.rsplit(".", 1)[-1].lower() if "." in user_name else ""
        if down_form is not None:
            # 신버전: <form name="nnn">이 가리키는 액션으로 POST (예: 정읍시)
            post_data = dict(down_fields)
            post_data["user_file_nm"] = user_name
            post_data["sys_file_nm"] = sys_name
            post_data["file_path"] = file_path
            attachments.append(
                {
                    "name": user_name,
                    "url": down_action,
                    "ext": ext,
                    "_dl_method": "POST",
                    "_dl_action": down_action,
                    "_dl_data": post_data,
                }
            )
        else:
            # 구버전: FileDown.jsp로 GET (예: 익산시)
            get_url = (
                _site_root(base_url) + "/emwp/jsp/ofr/FileDown.jsp"
                f"?user_file_nm={quote(user_name)}&sys_file_nm={quote(sys_name)}&file_path={quote(file_path)}"
            )
            attachments.append(
                {"name": user_name, "url": get_url, "ext": ext, "_dl_method": "GET", "_dl_action": get_url}
            )
    return attachments


def download_attachment(session, attachment):
    if attachment.get("_dl_method") == "POST":
        resp = session.post(
            attachment["_dl_action"], data=attachment.get("_dl_data", {}), headers=HEADERS, timeout=30
        )
    else:
        resp = session.get(attachment["_dl_action"], headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.content
