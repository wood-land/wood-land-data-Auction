"""
gazette_generic.py — 시보·군보·도보·구보·공보 게시판 범용 어댑터(휴리스틱).

지자체마다 공보 게시판 마크업이 달라 어댑터를 하나씩 쓰면 수백 개가 된다. 공보 게시판은
대부분 "번호 / 제목(제N호) / 첨부 / 등록일" 형태의 목록이라, 마크업 대신 내용으로 판별한다:
  - 행: table tr 중 날짜가 있는 것, 없으면 페이지 전체에서 "날짜 또는 제N호"를 가진 가장 안쪽
    요소(li/div/article/dl 등 — 카드형 목록 포함)
  - 날짜가 없는 목록(e-book형: 제N호만 있음)은 date=None 으로 돌려주고, run_gazette.py 가
    최신순 앞쪽 몇 건만 쓴다(목록이 최신순이라는 가정)
  - 제목 링크: 행 안의 첫 번째 "파일이 아닌" <a href>. href가 #/javascript: 뿐이고 onclick이
    fn_view('123') 같은 함수 호출이면, 페이지 안의 그 함수 정의(폼 action + 파라미터)를 읽어
    상세 주소를 재구성한다(resolve_js_link)
  - 첨부: 주소나 글자에 확장자(.pdf/.hwp/...)가 있거나, 글자가 PDF/HWP/다운로드이거나, 주소가
    download/fileDown 계열, 또는 eGov 표준 fn_egov_downFile(atchFileId, fileSn)
  - 페이지 이동: 목록의 숫자 링크(2,3,...)를 그대로 따라간다(파라미터 이름을 추측하지 않는다)
못 읽는 경우는 rows가 비거나 detail_url이 비어 run_gazette.py 가 '수동 확인 필요'로 표시한다.

City 형식이 아니라 run_gazette.py 가 board = {"name": "시보"} 와 base_url 만 넘겨 쓴다.
"""

import datetime as dt
import re
from urllib.parse import parse_qs, unquote, urlencode, urljoin, urlsplit

from bs4 import BeautifulSoup

from core import http_fetch

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

DATE_RE = re.compile(r"(20\d{2})\s*[-./]\s*(\d{1,2})\s*[-./]\s*(\d{1,2})|(20\d{2})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일")
ISSUE_RE = re.compile(r"(?:제|(?:시보|공보|군보|도보|구보)\s?)\s?(\d{2,5})\s?호")  # '시보 1150호'처럼 제 없이 간행물 이름 뒤에 붙는 호수도 읽는다(보령시)
EXT_RE = re.compile(r"\.(pdf|hwpx|hwp|docx?|xlsx?|zip)(?![a-z])", re.I)
FILEISH_HREF_RE = re.compile(r"download|filedown|/file/|fileid|atchfile|attach|getfile|filedownload|filedown", re.I)
FILEISH_TEXT_RE = re.compile(r"pdf|hwp|다운로드|내려받기|첨부", re.I)
SKIP_TEXT_RE = re.compile(r"^(처음|이전|다음|마지막|목록|검색|first|prev|next|last)$", re.I)
# 본문 첨부 링크 뒤의 크기 표기 "(7,098kb)" — 이런 표기가 있으면 푸터의 무관한 파일을 걸러내는 데 쓴다
SIZE_RE = re.compile(r"\(\s*[\d,.]+\s*(?:kb|mb|k|m|bytes?)\s*\)", re.I)
EGOV_DOWN_RE = re.compile(r"fn_egov_downFile\(\s*'([^']*)'\s*,\s*'?(\d*)'?\s*\)")

# base_url -> {page_no: url}, detail_url -> [attachment, ...]  (목록에서 본 첨부를 상세 조회 때 재사용)
_PAGE_MAP = {}
_LIST_FILES = {}


def _parse_date(text):
    m = DATE_RE.search(text or "")
    if not m:
        return None
    g = [x for x in m.groups() if x]
    try:
        return dt.date(int(g[0]), int(g[1]), int(g[2]))
    except ValueError:
        return None


_JS_FILE_PATH_RE = re.compile(r"""\(\s*['"]([^'"]+\.(?:pdf|hwpx?|docx?))['"]""", re.I)
VIEWER_RE = re.compile(r"viewer|synap|미리보기|바로보기|뷰어|preview|convert", re.I)


def _is_file_anchor(a):
    href = (a.get("href", "") or "").strip()
    text = a.get_text(" ", strip=True)
    js = _anchor_js(a)  # href="#" + onclick="fn_egov_downFile(...)" 형태도 첨부 링크로 본다
    if js and _JS_FILE_PATH_RE.search(js):  # pdfview('/thumbnail/eBook/x.pdf') 처럼 인자가 곧 파일 경로(글자가 "바로보기"여도 파일)
        return True
    if VIEWER_RE.search(href) or VIEWER_RE.search(text):
        return False
    if js:
        return bool(re.search(r"down|file", js, re.I)) and not VIEWER_RE.search(js)
    if href.lower().startswith("javascript"):
        return False
    if href.startswith("#") or href.lower().startswith(("mailto", "tel:")):
        return False
    return bool(EXT_RE.search(href) or EXT_RE.search(text) or FILEISH_HREF_RE.search(href) or FILEISH_TEXT_RE.search(text))


def _file_name(a, url):
    text = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
    text = re.sub(r"\s*(다운로드|내려받기|바로보기|미리보기|다운)\s*$", "", text).strip()
    if text and EXT_RE.search(text):
        return text
    title = (a.get("title") or "").strip()
    if title and EXT_RE.search(title):
        return re.sub(r"\s*(다운로드|내려받기)\s*$", "", title).strip()
    return text or (url.rsplit("/", 1)[-1][:60])


def _attachment(a, base, html=None, soup=None):
    href = (a.get("href", "") or "").strip()
    js = _anchor_js(a)
    if js:
        href = js if js.lower().startswith("javascript") else "javascript:" + js
    url = ""
    pm = _JS_FILE_PATH_RE.search(href) if href.lower().startswith("javascript") else None
    if pm:
        url = urljoin(base, pm.group(1))
    elif href.lower().startswith("javascript"):
        if html:
            url = resolve_js_link(html, soup, base, href)
        m = EGOV_DOWN_RE.search(href)
        if not url and m:  # eGovFrame 표준 경로(사이트가 다른 경로를 쓰면 위 해석이 먼저 적용된다)
            url = urljoin(base, "/cmm/fms/FileDown.do") + "?" + urlencode({"atchFileId": m.group(1), "fileSn": m.group(2) or "0"})
    else:
        url = urljoin(base, href)
    name = _file_name(a, url)
    m2 = EXT_RE.search(name) or EXT_RE.search(url)
    sized = bool(SIZE_RE.search(a.get_text(" ", strip=True)))
    ext = m2.group(1).lower() if m2 else ""
    if not ext and re.search(r"pdf", (a.get("title") or "") + a.get_text(" ", strip=True), re.I):
        ext = "pdf"  # 주소·글자에 확장자가 없어도 'PDF 로 받아 보실 수 있습니다' 같은 안내가 있으면 PDF 로 본다(보령시 시보; 받은 뒤 형식은 내용으로 다시 판별한다)
    return {"name": name, "url": url, "ext": ext, "sized": sized}


def _containers(soup):
    """목록 행 후보. 표(tr)가 우선, 없으면 '날짜 또는 제N호'를 가진 가장 안쪽 요소."""
    rows = soup.select("table tbody tr") or soup.select("table tr")
    rows = [r for r in rows if DATE_RE.search(r.get_text(" ", strip=True)) or ISSUE_RE.search(r.get_text(" ", strip=True))]
    if len(rows) >= 2:
        return rows
    cands = []
    for el in soup.find_all(["li", "div", "article", "dl", "section", "p"]):
        t = el.get_text(" ", strip=True)
        if len(t) > 500 or len(t) < 8:
            continue
        if ISSUE_RE.search(t) or DATE_RE.search(t):
            cands.append(el)
    inner = []
    for el in cands:
        if any(ch is not el and ch in cands for ch in el.find_all(["li", "div", "article", "dl", "section", "p"])):
            continue
        inner.append(el)
    # 제N호(또는 날짜)가 서로 다른 요소가 2개 이상일 때만 목록으로 인정
    return inner if len(inner) >= 2 else []


def _has_title_link(el):
    return any(
        (not _is_file_anchor(a)) and (a.get("onclick") or (a.get("href") or "").strip() not in ("", "#"))
        for a in el.find_all("a")
    )


def _widen(el):
    """카드형 목록에서 날짜만 든 안쪽 요소는 제목 링크가 없다 — 링크가 나올 때까지(최대 3단계) 부모로 올라간다.
    부모에 날짜가 둘 이상이면(다른 항목까지 포함) 멈춘다."""
    for _ in range(3):
        if _has_title_link(el):
            return el
        parent = el.parent
        if parent is None:
            return el
        if len(DATE_RE.findall(parent.get_text(" ", strip=True))) > 1:
            return el
        el = parent
    return el


def _build_page_map(soup, base):
    """목록 페이지의 숫자 페이지 링크 -> {페이지번호: URL}"""
    pages = {}
    for a in soup.find_all("a", href=True):
        t = a.get_text(strip=True)
        h = a["href"].strip()
        if t.isdigit() and 2 <= int(t) <= 30 and not h.lower().startswith(("javascript", "#")):
            if re.search(r"page|pageIndex|currPage|pageNo|nPage|cpage|start", h, re.I):
                pages.setdefault(int(t), urljoin(base, h))
    return pages


# ---------------------------------------------------------------- JS 링크 해석
def _split_args(s):
    return [(m.group(1) if m.group(1) is not None else m.group(2) if m.group(2) is not None else m.group(3).strip())
            for m in re.finditer(r"""'([^']*)'|"([^"]*)"|([^,\s'"][^,]*)""", s)]


def _brace_body(text, start):
    depth, i = 0, start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:i]
        i += 1
    return text[start + 1:start + 600]


def _find_function(html, name):
    m = re.search(r"(?:function\s+" + re.escape(name) + r"|" + re.escape(name) + r"\s*[:=]\s*function)\s*\(([^)]*)\)\s*\{", html)
    if not m:
        return None
    return [p.strip() for p in m.group(1).split(",") if p.strip()], _brace_body(html, m.end() - 1)


def _first_arg(expr):
    """window.open("url"+x, "name") 처럼 뒤에 인자가 더 붙은 식에서 첫 인자만 남긴다(따옴표 밖 쉼표 기준)."""
    q, out = "", []
    for ch in expr:
        if q:
            if ch == q:
                q = ""
        elif ch in "'\"":
            q = ch
        elif ch == ",":
            break
        out.append(ch)
    return "".join(out)


def _eval_expr(expr, env, lenient=False):
    """'"/a/b.do?idx=" + idx' 같은 단순 문자열 이음식 계산. 모르는 식별자가 있으면 None
    (lenient=True면 빈 문자열로 본다 — 검색어처럼 폼에서 읽는 선택 값용)."""
    out = []
    for piece in re.split(r"\+", expr.strip()):
        piece = piece.strip()
        m = re.fullmatch(r"""(['"])(.*?)\1""", piece)
        if m:
            out.append(m.group(2))
        elif piece in env:
            out.append(env[piece])
        elif piece == "concatBoardParams":  # yh 계열 CMS의 도우미: 폼에 없는 bIdx/ptIdx 를 쿼리로 잇는다
            out.append("&bIdx=%s&ptIdx=%s" % (env.get("bIdx", ""), env.get("ptIdx", "")))
        elif lenient:
            out.append("")
        else:
            return None
    return "".join(out)


def _page_env(html):
    """페이지의 설정 객체(var yh = {"mId": "..", "siteCodeFull": "..", "contextPath": ""})를 식 계산용 환경으로."""
    env = {"window.G_CONTEXT_PATH": ""}
    m = re.search(r"var\s+yh\s*=\s*\{(.{0,1500}?)\}\s*;", html, re.S)
    if m:
        for k, v in re.findall(r"[\"'](\w+)[\"']\s*:\s*[\"']([^\"']*)[\"']", m.group(1)):
            env["yh." + k] = v
    return env


_JS_CACHE = {}
_SKIP_JS_RE = re.compile(r"jquery|bootstrap|slick|swiper|kakao|weather|moment|chart|ckeditor|masonry|bxslider|migrate|datepicker|ie-checker|lazy|popup|banner|sns\.js", re.I)


def _external_js(session, html, base):
    """같은 도메인의 외부 스크립트 텍스트를 이어 붙여 돌려준다(함수 정의가 외부 JS에 있는 사이트용). 주소별 캐시."""
    host = urlsplit(base).netloc
    texts = []
    for src in re.findall(r"""<script[^>]+src=["']([^"']+)["']""", html)[:40]:
        u = urljoin(base, src)
        if urlsplit(u).netloc != host or _SKIP_JS_RE.search(u):
            continue
        if u not in _JS_CACHE:
            try:
                r = session.get(u, headers=HEADERS, timeout=30)
                _JS_CACHE[u] = r.text[:400_000] if r.status_code == 200 and "html" not in r.headers.get("content-type", "") else ""
            except Exception:
                _JS_CACHE[u] = ""
        texts.append(_JS_CACHE[u])
    return "\n".join(texts)


def _find_method(text, obj, name):
    """var obj = { name: function (...) {...} } 형태의 객체 메서드."""
    m0 = re.search(r"\b" + re.escape(obj) + r"\s*=\s*\{", text)
    if not m0:
        return None
    m = re.search(re.escape(name) + r"\s*[:=]\s*function\s*\(([^)]*)\)\s*\{", text[m0.end():])
    if not m:
        return None
    start = m0.end() + m.end() - 1
    return [p.strip() for p in m.group(1).split(",") if p.strip()], _brace_body(text, start)


def _anchor_js(a):
    """링크가 실행하는 JS: href가 javascript:호출이면 그것, 아니면(href="#"/javascript:;) onclick."""
    href = (a.get("href") or "").strip()
    if href.lower().startswith("javascript") and re.search(r"\w\s*\(", href[11:]) and "void(" not in href:
        return href
    return (a.get("onclick") or "").strip()


def _form_defaults(soup, form_id):
    form = soup.find("form", id=form_id) or soup.find("form", attrs={"name": form_id})
    if form is None:
        return {}
    return {i.get("name"): i.get("value", "") for i in form.find_all("input") if i.get("name")}


def resolve_js_link(html, soup, base_url, onclick):
    """onclick='fn_view("123")' -> 상세 URL. 못 풀면 ''."""
    m = re.match(r"\s*(?:javascript:)?\s*([\w.$]+)\s*\((.*)\)\s*;?\s*(?:return\s+false\s*;?)?\s*$", onclick or "", re.S)
    if not m:
        return ""
    dotted = m.group(1).split(".")
    fname = dotted[-1]
    args = _split_args(m.group(2))
    if dotted[-2:] == ["file", "download"] and args:
        # yhLib 계열: 함수 본문이 verifiedURL(...)/삼항식이라 일반 해석이 안 되지만 열리는 주소는 고정이다
        return urljoin(base_url, "/common/file/download.do") + "?" + urlencode(
            {"atchFileId": args[0], "fileSn": args[1] if len(args) > 1 else ""}
        )
    fn = (_find_method(html, dotted[0], fname) if len(dotted) > 1 else None) or _find_function(html, fname)
    if fn is None:
        return ""
    params, body = fn
    env = dict(zip(params, args))
    env.update({k: v for k, v in _page_env(html).items() if k not in env})
    # 식은 따옴표 문자열(안에 ';' ')' 가 있어도 됨)과 식별자를 '+'로 이은 것 — 예: "/a/b.do;jsessionid=X?id="+id+"&n="+n
    _tok = r"""(?:"[^"\n]*"|'[^'\n]*'|[\w.$]+)"""
    _chain = _tok + r"""(?:\s*\+\s*""" + _tok + r""")*"""
    # 지역 변수: var boardView = "/a/view.do?idx=" + idx;  (뒤에서 location.href = boardView 로 쓰이는 경우)
    for lname, lexpr in re.findall(r"""(?:var|let|const)\s+(\w+)\s*=\s*(""" + _chain + r""")\s*;""", body):
        lv = _eval_expr(lexpr, env)
        if lv is not None:
            env.setdefault(lname, lv)
    am = re.search(
        r"""(?:\.action\s*=|\baction\s*=|location(?:\.href)?\s*=|window\.open\(|setUrl\(|pageFormSubmit\(\s*[\w.$]+\s*,|\.attr\(\s*['"]action['"]\s*,)\s*(""" + _chain + r""")""",
        body,
    )
    fm = re.search(r"""getElementById\(\s*['"](\w+)['"]\)|document\.(\w+)\.action|\$\(\s*['"]#(\w+)['"]\s*\)""", body)
    form, form_id = None, None
    if fm and soup is not None:
        form_id = next(g for g in fm.groups() if g)
        form = soup.find("form", id=form_id) or soup.find("form", attrs={"name": form_id})
    action = None
    if am:
        expr = _first_arg(am.group(1))
        action = _eval_expr(expr, env) or _eval_expr(expr, env, lenient=True)
    if not action and form is not None and form.get("action"):
        action = form["action"]  # 함수는 폼 값만 채우고 submit 하는 사이트(양양군 등): 폼 자체의 action 을 쓴다
    if not action:
        return ""
    q = {}
    if form is not None:
        q.update(_form_defaults(soup, form_id))
    for name, var in re.findall(r"\.(\w+)\.value\s*=\s*(\w+)", body):
        if var in env:
            q[name] = env[var]
    for name, var in re.findall(r"""\$\(\s*['"]#?(\w+)['"]\s*\)\.val\(\s*(\w+)\s*\)""", body):
        if var in env:
            q[name] = env[var]
    for name, var in re.findall(r"""\[name=['"]?(\w+)['"]?\]["']\)\.val\(\s*(\w+)\s*\)""", body):
        if var in env:  # $("input[name=bbs_seq]").val(x) / form.find("[name=boardNo]").val(x)
            q[name] = env[var]
    url = urljoin(base_url, action)
    if q:
        url += ("&" if "?" in url else "?") + urlencode({k: v for k, v in q.items() if v is not None})
    return url


def _yh_inline_post_url(a, soup, base):
    """yhLib.inline.post(this): 앵커의 data-req-form-id 폼 action + data-req-get-p-<키>=<값> 들을 쿼리로 잇는다."""
    form = soup.find("form", id=a.get("data-req-form-id") or "viewForm")
    if form is None or not form.get("action"):
        return ""
    q = {k[len("data-req-get-p-"):]: v for k, v in a.attrs.items() if k.startswith("data-req-get-p-")}
    url = urljoin(base, form["action"])
    return url + ("&" if "?" in url else "?") + urlencode(q) if q else url


_SCRIPT_RE = re.compile(r"<script[^>]*>(.*?)</script>", re.S | re.I)
_BARE_REDIRECT_RE = re.compile(
    r"""^\s*(?:window\.|top\.|document\.)?location(?:\.href)?\s*=\s*['"]([^'"]+)['"]\s*;?\s*$"""
    r"""|^\s*(?:window\.|top\.)?location\.replace\(\s*['"]([^'"]+)['"]\s*\)\s*;?\s*$""")


def _bare_js_redirect(html):
    """HTML 안에 '이것 하나만 실행하는' 스크립트(location.href='…' 한 줄)가 있으면 그 주소. 없으면 ''.
    함수 안·조건 안의 이동(function f(){location.href=…})은 이 규칙에 걸리지 않는다(스크립트 본문이 그 한 문장뿐일 때만)."""
    for body in _SCRIPT_RE.findall(html):
        body = re.sub(r"//<!\[CDATA\[|//\]\]>", "", body)
        body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)  # 블록 주석
        body = re.sub(r"^[ \t]*//[^\r\n]*$", "", body, flags=re.M)  # 줄 주석(한 줄만 지운다)
        m = _BARE_REDIRECT_RE.match(body)
        if m:
            return m.group(1) or m.group(2)
    return ""


def _get(session, url):
    """GET 하고, 페이지에 '무조건 다른 주소로 보내는 스크립트'(location.href='…' 한 줄)가 있으면 그 주소로 이어서 간다(최대 2번).
    울릉군 군보 상세는 ?cmd=2 가 메뉴까지 담은 페이지 위쪽에 <script>location.href='?cmd=258&...'</script> 를 두어, 브라우저는 곧바로
    cmd=258(첨부가 있는 글보기)로 가지만 requests 는 스크립트를 실행하지 않아 첨부가 없다고 읽었다(2026-10-25 실측)."""
    def once(u):
        r = session.get(u, headers=HEADERS, timeout=60)
        r.raise_for_status()
        return r

    resp = http_fetch.retry_call(lambda: once(url))  # 502 등 일시 오류는 다시 받는다(2026-10-25 나주시 시보 502)
    for _ in range(2):
        if "html" not in resp.headers.get("content-type", "html"):
            break
        target = _bare_js_redirect(resp.text)
        nxt = urljoin(resp.url, target) if target else ""
        if not nxt or nxt == resp.url:
            break
        resp = http_fetch.retry_call(lambda n=nxt: once(n))
    return resp


_OPEN_URL_RE = re.compile(r"""window\.open\(\s*['"]([^'"]+)['"]""")


def _ebook_card_rows(soup, base, board):
    """이미지 카드형 전자 간행물 목록(영양군 전자군보): 카드마다 제목(.tit)과 다운로드 버튼(onclick="window.open('/…/file_download/…pdf')")만 있고
    날짜가 없다. 다른 방식으로 행을 못 찾았을 때만 쓴다. 미리보기(preview) 버튼은 제외한다."""
    rows = []
    for el in soup.find_all(attrs={"onclick": True}):
        m = _OPEN_URL_RE.search(el.get("onclick") or "")
        if not m or re.search(r"preview", m.group(1), re.I):
            continue
        url = m.group(1).replace("&amp;", "&")
        if not (EXT_RE.search(url) or FILEISH_HREF_RE.search(url) or "file_download" in url):
            continue
        title, card = "", el
        for _ in range(4):
            card = card.parent
            if card is None:
                break
            t = card.select_one(".tit")
            if t:
                title = re.sub(r"\s*새글\s*$", "", re.sub(r"\s+", " ", t.get_text(" ", strip=True)))
                break
        if not title:
            continue
        full = urljoin(base, url)
        name = unquote(urlsplit(full).path.rsplit("/", 1)[-1])
        ext = EXT_RE.search(name)
        att = {"name": name, "url": full, "ext": ext.group(1).lower() if ext else "pdf", "sized": False}
        _LIST_FILES[full] = [att]
        iss = ISSUE_RE.search(title)
        rows.append({"board": board["name"], "notice_no": iss.group(0) if iss else "", "title": title, "date": None,
                     "date_str": "", "detail_url": full})
    return rows


# 쪽 번호 링크(?page=2, goPage(2)). 호수만 제목으로 쓰는 게시판(경상남도청 '2834')의 상세 링크와 구별한다
_PAGER_HREF_RE = re.compile(r"(?:^|[?&])(?:page|pageno|pageindex|cpage|curpage|currentpage|pagenum)=\d+|gopage|fn_?page|movepage", re.I)


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    if page_index == 1:
        url = base_url
    else:
        url = _PAGE_MAP.get(base_url, {}).get(page_index)
        if not url:
            return []
    resp = _get(session, url)
    if resp.encoding in (None, "ISO-8859-1"):
        resp.encoding = resp.apparent_encoding
    soup = BeautifulSoup(resp.text, "html.parser")
    if page_index == 1:
        _PAGE_MAP[base_url] = _build_page_map(soup, resp.url)
    page_js = resp.text + "\n" + _external_js(session, resp.text, resp.url)  # JS 함수 정의가 외부 파일에 있는 사이트용
    rows = []
    for c in [x if x.name == "tr" else _widen(x) for x in _containers(soup)]:  # 표의 행(tr)은 이미 한 글이다 - 넓히면 표 전체(다른 호 첨부까지)가 한 글이 된다(통영시 공보)
        text = re.sub(r"\s+", " ", c.get_text(" ", strip=True))
        date = _parse_date(text)
        title_a, files, viewer_a = None, [], None
        for a in c.find_all("a"):
            if _is_file_anchor(a):
                files.append(_attachment(a, resp.url, page_js, soup))
                continue
            if title_a is None and a.get_text(strip=True) and not SKIP_TEXT_RE.match(a.get_text(strip=True)):
                href = (a.get("href") or "").strip()
                if (href and not href.lower().startswith(("javascript", "#", "mailto", "tel:"))) or a.get("onclick") or href.lower().startswith("javascript"):
                    if VIEWER_RE.search(a.get_text(" ", strip=True)) or VIEWER_RE.search(href) or VIEWER_RE.search(_anchor_js(a)):
                        viewer_a = viewer_a or a  # '바로 보기' 같은 뷰어 링크는 제목 후보에서 뒤로 미룬다
                    else:
                        title_a = a
        if title_a is None and not files and viewer_a is not None:
            title_a = viewer_a  # 첨부 링크가 따로 없을 때만 뷰어 링크를 상세로 쓴다
        if title_a is not None:
            title = re.sub(r"\s+", " ", title_a.get_text(" ", strip=True))
        elif files:  # 제목 링크가 없고 첨부만 있으면 카드의 제목 요소, 없으면 첨부 이름(크기 표기 제외)을 제목으로 쓴다
            head = next((h for h in c.select("th, p") if ISSUE_RE.search(h.get_text(" ", strip=True))), None) or c.select_one("[class*=title], strong, h3, h4, h5")  # 호수가 든 th/p(통영·보령)를 먼저
            head_text = re.sub(r"\s+", " ", head.get_text(" ", strip=True)) if head else ""
            title = head_text or re.sub(r"\s*\[[\d.,]+\s*[KMGkmg]?B\]\s*$", "", files[0]["name"]).strip() or text[:80]
        else:
            title = text[:80]
        if title_a is not None and re.fullmatch(r"[\d\s]{1,4}|[<>«»‹›]+", title) and _PAGER_HREF_RE.search(title_a.get("href") or ""):
            continue  # 쪽 번호('2')·이전/다음 화살표 링크는 글이 아니다(무안군보 목록 아래 쪽 번호 줄이 오늘 날짜와 함께 글처럼 읽혔다)
        if date is None:  # 날짜가 목록 글자에 없고 첨부 파일명에만 있는 사이트(무안군보: 군보 1702호(2026. 10. 19.).pdf)
            for f in files:
                date = _parse_date(unquote(f["url"]))
                if date is not None:
                    break
        m = ISSUE_RE.search(title) or ISSUE_RE.search(text)
        if date is None and not m:
            continue
        detail_url = ""
        if title_a is not None:
            href = (title_a.get("href") or "").strip()
            if href and not href.lower().startswith(("javascript", "#", "mailto", "tel:")):
                detail_url = urljoin(resp.url, href)
            elif _anchor_js(title_a).startswith("yhLib.inline.post"):
                detail_url = _yh_inline_post_url(title_a, soup, resp.url)
            else:
                detail_url = resolve_js_link(page_js, soup, resp.url, _anchor_js(title_a) or title_a.get("onclick") or href)
        for i, f in enumerate(files):  # 목록 행의 첨부에도 미리보기 주소를 붙여 둔다(목록 페이지 안의 함수 정의 사용)
            f["preview_url"] = _pair_preview(f, [], i, page_js, resp.url)
        if detail_url and files:
            _LIST_FILES[detail_url] = files
        elif not detail_url and files:
            detail_url = files[0]["url"]  # 목록에 파일 링크만 있는 사이트: 파일 링크를 상세 대신 쓴다
            _LIST_FILES[detail_url] = files
        rows.append(
            {
                "board": board["name"],
                "notice_no": m.group(0) if m else "",
                "title": title,
                "date": date,
                "date_str": date.isoformat() if date else "",
                "detail_url": detail_url,
            }
        )
    if not rows:
        rows = _ebook_card_rows(soup, resp.url, board)
    return rows


def fetch_attachments(session, detail_url):
    """첨부파일 [{"name","url","ext"}, ...] — 목록에서 본 첨부 + 상세 페이지의 첨부(다운로드는 하지 않음)."""
    found = list(_LIST_FILES.get(detail_url, []))
    seen = {a["url"] for a in found}
    if not detail_url:
        return _with_default_previews(found)
    if found and found[0]["url"] == detail_url:
        return _with_default_previews(found)
    try:
        resp = _get(session, detail_url)
    except Exception:  # noqa: BLE001 - 상세 페이지가 500 등으로 안 열려도 목록에서 이미 본 첨부가 있으면 그걸 쓴다
        if found:
            return _with_default_previews(found)
        raise
    ctype = resp.headers.get("content-type", "")
    if "html" not in ctype and "text" not in ctype:
        return found or [{"name": detail_url.rsplit("/", 1)[-1], "url": detail_url, "ext": ""}]
    if resp.encoding in (None, "ISO-8859-1"):
        resp.encoding = resp.apparent_encoding
    soup = BeautifulSoup(resp.text, "html.parser")
    page_js = resp.text + "\n" + _external_js(session, resp.text, resp.url)
    for a in soup.find_all("a"):
        if _is_file_anchor(a):
            att = _attachment(a, resp.url, page_js, soup)
            if att["url"] not in seen and not re.search(r"privacy|개인정보|policy", att["name"] + att["url"], re.I):
                seen.add(att["url"])
                found.append(att)
    if any(a.get("sized") for a in found):  # 크기 표기가 있는 첨부만 본문 첨부로 본다(푸터의 전화번호부 등 제외)
        found = [a for a in found if a.get("sized")]
    viewers = _collect_viewers(soup, resp.url, page_js)
    for i, att in enumerate(found):
        att["preview_url"] = _pair_preview(att, viewers, i, page_js, resp.url)
    return found


def _with_default_previews(found):
    """목록에서만 본 첨부(상세 조회 없이 반환하는 경로)에도 미리보기 주소를 붙인다."""
    for i, att in enumerate(found):
        if not att.get("preview_url"):
            att["preview_url"] = _pair_preview(att, [], i)
    return found


PREVIEW_RE = re.compile(r"미리보기|바로보기|convert|viewer|preview|synap", re.I)
_FID_RE = re.compile(r"(FILE_\d+)['\"]?\s*,?\s*['\"]?(\d*)")


def _collect_viewers(soup, base, html):
    """페이지의 미리보기 링크 -> [{"url","fid","sn"}]. JS 링크(fn_egov_convertFile('FILE_..','0') 등)는 페이지 안
    함수 정의로 실제 주소를 복원한다(사이트마다 뷰어가 다르다: Synap FileViewer.do, 한컴 hancomViewer.do 등)."""
    out = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text(" ", strip=True)
        if not (PREVIEW_RE.search(href) or PREVIEW_RE.search(text)) or href.startswith("#"):
            continue
        if href.lower().startswith("javascript"):
            url = resolve_js_link(html, soup, base, href)
            m = _FID_RE.search(href)
            fid, sn = (m.group(1), m.group(2) or "0") if m else ("", "")
        else:
            url = urljoin(base, href)
            q = parse_qs(urlsplit(url).query)
            fid = (q.get("atchFileId") or [""])[0]
            sn = (q.get("fileSn") or ["0"])[0]
        if url:
            out.append({"url": url, "fid": fid, "sn": sn})
    return out


def _page_preview_url(fid, sn, html, base):
    """페이지 안에 미리보기 함수(filePreview, fn_egov_convertFile 등)가 정의돼 있으면 그 함수가 여는 주소를 복원한다."""
    if not html:
        return ""
    for name in ("filePreview", "fn_egov_convertFile", "fn_egov_viewFile", "fnPreview", "fn_preview"):
        if _find_function(html, name):
            url = resolve_js_link(html, None, base, f"javascript:{name}('{fid}','{sn}')")
            if url:
                return url
    return ""


def _pair_preview(att, viewers, index, html="", base=""):
    """첨부 1개에 대응하는 미리보기 주소. atchFileId+fileSn 이 같은 링크를 우선하고, 없으면 같은 순번의 링크,
    그래도 없고 첨부가 eGov 표준 파일이면 표준 경로(/synapsoft/FileViewer.do)를 시도용으로 만든다."""
    q = parse_qs(urlsplit(att["url"]).query)
    fid = (q.get("atchFileId") or [""])[0]
    sn = (q.get("fileSn") or ["0"])[0]
    if fid:
        for v in viewers:
            if v["fid"] == fid and v["sn"] == sn:
                return v["url"]
    if not fid and index < len(viewers):
        return viewers[index]["url"]
    if fid:
        page_url = _page_preview_url(fid, sn, html, base or att["url"])
        if page_url:
            return page_url
        return urljoin(att["url"], "/synapsoft/FileViewer.do") + "?" + urlencode({"atchFileId": fid, "fileSn": sn, "fileName": ""})
    return ""
