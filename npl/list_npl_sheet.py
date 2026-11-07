# -*- coding: utf-8 -*-
"""
옥션원(auction1.co.kr) 부실채권(NPL) 물건 목록 추출 -> 구글시트 'NPL_YYYYMMDD' (GitHub Actions 실행용 사본. 로컬판: 200_MU-MU_Auction 500_local/52. 경공매 추출/03_3, v1, 2026-11-07)

[참고한 코드] 다운로드한 auction1-crawler.zip / auction1_crawler.py (GitHub Actions용 requests 방식)
  - 크롬(Selenium) 없이 requests + BeautifulSoup 만으로 수집한다. 가볍고 빠르다.
    (03_1 Selenium 방식은 화면 구조가 바뀌면 깨지기 쉬워, 이 파일을 기본 수집기로 쓴다)
  - 로그인은 POST (MemberLoginController.php?action=member_login), 목록은 GET /auction/ca_list.php
    * start=오프셋, scale=100, 응답 인코딩 EUC-KR(cp949)
    * NPL 화면 = page_code=121010 & npl_key=1
    * class/id 는 요청마다 무작위로 바뀌므로 고정 class(addr, auct_class_name, no)와 td 위치로만 읽는다
    * 로그인하지 않으면 목록 행이 나오지 않는다

[이 파일에서 바꾼 점]
  - 설정은 환경변수 + 파일 상단 상수. 로컬 PC 용(GitHub Actions/Secrets 아님).
  - 매각기일 N일 이내 / 감정가 상한 은 목록을 받은 뒤 이 쪽에서 걸러낸다(서버 필터 이름이 확실치 않아 안전하게).
  - 결과 dict 는 03_1 과 같은 키(사건번호, 물번, 소재지, 감정가, 매각기일 ...)라서
    '03_2. 옥션원 NPL 두인연계 상세' 가 그대로 이 목록을 받아 쓴다(보유회사 태깅은 아직 없음 - 빈칸).
  - 구글시트 탭 'NPL_YYYYMMDD'(YYYYMMDD = 이번 주 토요일). 직전 탭과 비교해 '이전대비=신규' 표시.
  - 실행 기록은 'NPL_로그_목록' 탭에 한 줄씩 남긴다(실패해도 남김).
  - 수집이 사이트 표시 건수의 98% 미만이면 시트는 건드리지 않는다(기존 탭 보호).

[환경변수]
  AUCTION1_ID / AUCTION1_PW  (또는 A1_LOGIN_ID / A1_LOGIN_PW)   없으면 '500_local/103. 두인경매, 옥션원 key/옥션원.txt' 를 읽음
  GOOGLE_SHEET_ID            없으면 NPL_SHEET_ID(10vK5WyeAV...) 사용
  GOOGLE_CREDENTIALS_PATH    없으면 아래 후보 경로에서 찾음
  CATEGORY_GROUPS            commercial,land (기본 둘 다) / land / commercial
  DAYS_AHEAD                 매각기일 오늘~N일 이내만 (기본 60, 0 이면 제한 없음)
  JU_PRICE_MIN_MANWON / JU_PRICE_MAX_MANWON   감정가 하한/상한(만원). 기본 20000(2억) ~ 150000(15억)

필요 패키지: pip install requests beautifulsoup4 lxml openpyxl gspread google-auth
"""

import csv
import os
import random
import re
import sys
import time
from datetime import datetime, date, timedelta, timezone

import requests
from bs4 import BeautifulSoup

try:
    import gspread
except ImportError:
    gspread = None
try:
    from openpyxl import Workbook
except ImportError:
    Workbook = None
try:
    import lxml  # noqa: F401
    HTML_PARSER = "lxml"
except ImportError:
    HTML_PARSER = "html.parser"

# ============================== 설정 ==============================
KST = timezone(timedelta(hours=9))
SITE = "https://www.auction1.co.kr"
LOGIN_URL = f"{SITE}/controller/Auth/MemberLoginController.php?action=member_login"
LIST_URL = f"{SITE}/auction/ca_list.php"
DETAIL_URL_FMT = f"{SITE}/auction/ca_view.php?product_id={{pid}}"

HERE = os.path.dirname(os.path.abspath(__file__))
# 로그인 정보 파일(이 PC 의 500_local 아래, git 에 올리지 않는다): 'ID: 아이디' / 'P.W : 비밀번호' 형식
KEY_FILE_CANDIDATES = [
    os.environ.get("AUCTION1_KEY_FILE", ""),
    os.path.join(os.path.dirname(HERE), "103. 두인경매, 옥션원 key", "옥션원.txt"),
]


def _read_key_file():
    for path in KEY_FILE_CANDIDATES:
        if path and os.path.isfile(path):
            try:
                txt = open(path, encoding="utf-8-sig", errors="replace").read()
            except OSError:
                continue
            mi = re.search(r"^\s*(?:\S+\s+)?(?:ID|아이디)\s*[:：]\s*(\S+)", txt, re.I | re.M)
            mp = re.search(r"^\s*(?:\S+\s+)?(?:P\.?\s*W\.?|PW|패스워드|비밀번호)\s*[:：]\s*(\S+)", txt, re.I | re.M)
            if mi and mp:
                return mi.group(1), mp.group(1), path
    return "", "", ""


# 환경변수가 있으면 그것이 우선, 없으면 로그인 정보 파일
LOGIN_ID = (os.environ.get("AUCTION1_ID") or os.environ.get("A1_LOGIN_ID") or "").strip()
LOGIN_PW = (os.environ.get("AUCTION1_PW") or os.environ.get("A1_LOGIN_PW") or "").strip()
if not (LOGIN_ID and LOGIN_PW):
    LOGIN_ID, LOGIN_PW, _KEY_SRC = _read_key_file()
GOOGLE_CREDENTIALS_PATH_CANDIDATES = [
    os.environ.get("GOOGLE_CREDENTIALS_PATH", ""),
    os.path.join(os.path.dirname(HERE), "100. Google_credentials", "google_credentials_편집자.json"),
    "C:/startcoding/100. Google_credentials/google_credentials_편집자.json",
    "C:/Python/startcoding/100. google_credentials/google_credentials_편집자.json",
]
GOOGLE_SHEETS_ENABLED = True


def _resolve_sheet_id():
    # NPL 전용 스프레드시트(2026-11-07 지정). 환경변수로 바꿀 수 있다.
    return os.environ.get("GOOGLE_SHEET_ID", "").strip() or NPL_SHEET_ID


NPL_SHEET_ID = "10vK5WyeAVoDJFdMAAGAteH_oxi__2jYaz18b2uq94JQ"
GOOGLE_SHEET_ID = _resolve_sheet_id()
TAB_PREFIX = "NPL_"
WEEKEND_WEEKDAY = 5                      # 5 = 토요일
TAB_RETENTION_WEEKS = 8
LOG_TAB = "NPL_로그_목록"
SAVE_LOCAL_XLSX = os.environ.get("SAVE_LOCAL_XLSX", "0") == "1"   # Actions 에서는 저장하지 않음
SAVE_DIR = "D:/"                         # 없으면 이 스크립트 폴더

CATEGORY_GROUPS = [g.strip() for g in (os.environ.get("CATEGORY_GROUPS") or "commercial,land").split(",") if g.strip()]
DAYS_AHEAD = int(os.environ.get("DAYS_AHEAD") or 60)
JU_PRICE_MIN_MANWON = (os.environ.get("JU_PRICE_MIN_MANWON") or "20000").strip()    # 감정가 하한 2억
JU_PRICE_MAX_MANWON = (os.environ.get("JU_PRICE_MAX_MANWON") or "150000").strip()   # 감정가 상한 15억
MAX_PAGES = 200
PAGE_SIZE = 100                          # scale: 20~100
PAGE_DELAY = (1.5, 3.0)                  # 페이지 요청 사이 대기(초) - 서버 부하 방지
REQUEST_RETRY = 3
STATE_IN_PROGRESS = "1,2,17,18"          # 진행물건
ORDER = "num1,num2,p_num,product_id ASC"  # 사건번호 순 - 페이지 넘기는 동안 순서 고정
COMPLETE_RATIO = 0.98                    # 사이트 표시 건수 대비 이 비율 이상이면 '완료'

S_CLASS_GROUPS = {   # select#s_class 그룹 값 (사이트 HTML 그대로)
    "commercial": "4,5,19,6,21,13,27,16,30,15,18,22,26,20,28,44,51,52,53,54",   # 상업용및업무용
    "land": "9,10,11,12,14,7,24,33,45,46,47,48,49,50,34,35,36,37,42",            # 토지
}

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# 03_1 / 03_2 와 같은 키 + 물건내역/신건여부/이전대비
HEADERS = [
    "사건번호", "물번", "물건종류", "소재지", "물건내역", "특이사항",
    "감정가", "최저가", "최저가율", "진행상태", "유찰횟수",
    "매각기일", "매각시간", "신건여부", "이전대비", "보유회사", "product_id", "상세페이지", "수집일시",
]
PRICE_COLS = ("감정가", "최저가")
LOG_HEADERS = [
    "실행시각(KST)", "결과", "대상탭", "사이트표시건수", "수집건수", "조건통과건수",
    "시트기록행수", "비교탭", "신규", "사라짐(매각/취하 추정)", "소요시간(분)", "비고",
]
# ===================================================================


def log(msg):
    print(f"[{datetime.now(KST):%H:%M:%S}] {msg}", flush=True)


def this_weekend(d: date) -> date:
    return d - timedelta(days=d.weekday()) + timedelta(days=WEEKEND_WEEKDAY)


def tab_name_for(d: date = None) -> str:
    return f"{TAB_PREFIX}{this_weekend(d or date.today()):%Y%m%d}"


# ------------------------------------------------------------------ 사이트 접속
def decode(resp):
    return resp.content.decode("cp949", errors="replace")   # 옥션원은 EUC-KR


def build_session():
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "ko-KR,ko;q=0.9", "Referer": f"{SITE}/"})
    return s


def login(session):
    if not LOGIN_ID or not LOGIN_PW:
        raise RuntimeError("로그인 정보가 없습니다. '103. 두인경매, 옥션원 key/옥션원.txt'(ID: / P.W :) 또는 환경변수 AUCTION1_ID / AUCTION1_PW 를 확인하세요.")
    session.get(f"{SITE}/", timeout=30)    # 초기 쿠키
    data = {"client_id": LOGIN_ID, "passwd": LOGIN_PW, "popup": "", "partner_id": "",
            "ref_popup": f"{SITE}/", "redirect_url": ""}
    r = session.post(LOGIN_URL, data=data, timeout=30, allow_redirects=True)
    html = decode(r)
    if "로그아웃" not in html:
        html = decode(session.get(f"{SITE}/", timeout=30))
    if "로그아웃" not in html:
        m = re.search(r"alert\(['\"]([^'\"]{1,120})", decode(r))
        raise RuntimeError(f"로그인 실패: {m.group(1) if m else '응답에서 로그아웃 버튼을 찾지 못함'}")
    log("옥션원 로그인 성공")


def build_params(s_class, start):
    p = {
        "search_fm_off": "1", "state": STATE_IN_PROGRESS, "s_class": s_class, "power_flag": "0",
        "sido": "0", "gugun": "0", "dong": "0", "am_cnt": "0",
        "order": ORDER, "scale": str(PAGE_SIZE), "ck_photo": "0", "search_mode": "1", "start": str(start),
        "npl_key": "1", "page_code": "121010",      # 부실채권(NPL) 검색 화면
    }
    return p


def fetch_list_page(session, s_class, start):
    last_err = None
    for attempt in range(1, REQUEST_RETRY + 1):
        try:
            r = session.get(LIST_URL, params=build_params(s_class, start), timeout=60)
            r.raise_for_status()
            return decode(r)
        except Exception as e:
            last_err = e
            wait = 5 * attempt
            log(f"  요청 실패({attempt}/{REQUEST_RETRY}): {e} - {wait}초 후 재시도")
            time.sleep(wait)
    raise RuntimeError(f"목록 요청 반복 실패 (start={start}): {last_err}")


# ------------------------------------------------------------------ 파싱
def _text(el):
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el else ""


def _to_int(s):
    digits = re.sub(r"[^\d]", "", s or "")
    return int(digits) if digits else None


def parse_total(html):
    m = re.search(r"total_record=(\d+)", html)
    return int(m.group(1)) if m else None


def parse_rows(html):
    soup = BeautifulSoup(html, HTML_PARSER)
    items = []
    for chk in soup.select("input[name=ck_pid]"):
        tr = chk.find_parent("tr")
        if tr is None:
            continue
        try:
            items.append(parse_row(tr, chk.get("value", "")))
        except Exception as e:
            log(f"  행 파싱 실패(물건ID {chk.get('value')}): {e}")
    return items


def parse_row(tr, pid):
    tds = tr.find_all("td", recursive=False)

    cls_el = tr.select_one(".auct_class_name")
    case_box = tr.select_one("div.no") or (cls_el.find_parent("td") if cls_el else None)
    case_txt = _text(case_box)
    m = re.search(r"(\d{2,4}\s*-\s*\d+)", case_txt)
    case_no = m.group(1).replace(" ", "") if m else case_txt
    m2 = re.search(r"\((\d+)\)", case_txt)
    item_no = m2.group(1) if m2 else ""
    kind = _text(cls_el)

    addr_el = tr.select_one("div.addr")
    address = _text(addr_el)
    detail, note = "", ""
    if addr_el is not None:
        sibs = list(addr_el.find_next_siblings("div"))
        if sibs:
            detail = _text(sibs[0])
        if len(sibs) > 1:
            note = " ".join(_text(d) for d in sibs[1:])
    addr_td = addr_el.find_parent("td") if addr_el is not None else None
    idx = tds.index(addr_td) if addr_td in tds else None

    def td_at(offset):
        if idx is None or idx + offset >= len(tds):
            return None
        return tds[idx + offset]

    price_td = td_at(1)
    prices = [_text(d) for d in price_td.find_all("div", recursive=False)] if price_td else []
    appraisal = _to_int(prices[0]) if len(prices) > 0 else None
    minimum = _to_int(prices[1]) if len(prices) > 1 else None

    stat_txt = _text(td_at(2))
    m3 = re.search(r"유찰\s*(\d+)\s*회", stat_txt)
    fail_cnt = int(m3.group(1)) if m3 else 0
    m4 = re.search(r"\((\d+(?:\.\d+)?)\s*%\)", stat_txt)
    rate = m4.group(1) if m4 else ""
    status = re.sub(r"\s*\(\d+(?:\.\d+)?\s*%\)", "", stat_txt).strip()

    date_txt = _text(td_at(3))
    m5 = re.search(r"(\d{4})\.(\d{2})\.(\d{2})", date_txt)
    m6 = re.search(r"\((\d{1,2}:\d{2})\)", date_txt)

    return {
        "사건번호": case_no, "물번": item_no, "물건종류": kind, "소재지": address,
        "물건내역": detail, "특이사항": note,
        "감정가": appraisal, "최저가": minimum,
        "최저가율": f"{rate}%" if rate else "", "진행상태": status, "유찰횟수": fail_cnt,
        "매각기일": f"{m5.group(1)}-{m5.group(2)}-{m5.group(3)}" if m5 else "",
        "매각시간": m6.group(1) if m6 else "",
        "신건여부": "신건" if fail_cnt == 0 else "", "이전대비": "",
        "보유회사": "", "product_id": str(pid), "상세페이지": DETAIL_URL_FMT.format(pid=pid), "수집일시": "",
    }


# ------------------------------------------------------------------ 수집
def crawl(session):
    s_class = ",".join(S_CLASS_GROUPS[g] for g in CATEGORY_GROUPS)
    log(f"수집 시작 - 부실채권(NPL) 화면, 물건종류: {CATEGORY_GROUPS}, 진행물건")
    results, seen, total = [], set(), None
    start, page = 0, 0
    while page < MAX_PAGES:
        page += 1
        html = fetch_list_page(session, s_class, start)
        if total is None:
            total = parse_total(html)
            log(f"검색 결과 총 {total}건 (페이지당 {PAGE_SIZE}건)")
        rows = parse_rows(html)
        if not rows:
            if page == 1 and "로그아웃" not in html:
                raise RuntimeError("목록이 비어 있습니다 - 로그인 세션이 유지되지 않았거나 접근이 거부되었습니다.")
            break
        new = 0
        for r in rows:
            if r["product_id"] in seen:
                continue
            seen.add(r["product_id"])
            results.append(r)
            new += 1
        log(f"  {page}페이지 (start={start}): {len(rows)}행, 신규 {new}건, 누적 {len(results)}건")
        start += PAGE_SIZE
        if total is not None and start >= total:
            break
        time.sleep(random.uniform(*PAGE_DELAY))
    complete = total is not None and len(results) >= total * COMPLETE_RATIO
    log(f"수집 종료: {len(results)}건 / 사이트 표시 {total}건 -> {'완료' if complete else '불완전'}")
    return results, total, complete


def apply_filters(items):
    """매각기일 오늘~DAYS_AHEAD일, 감정가 상한 (둘 다 비어 있으면 그대로)."""
    out = items
    if DAYS_AHEAD > 0:
        today = date.today()
        last = (today + timedelta(days=DAYS_AHEAD)).isoformat()
        out = [r for r in out if r["매각기일"] and today.isoformat() <= r["매각기일"] <= last]
    if JU_PRICE_MIN_MANWON.isdigit():
        floor = int(JU_PRICE_MIN_MANWON) * 10000
        out = [r for r in out if r["감정가"] is not None and r["감정가"] >= floor]
    if JU_PRICE_MAX_MANWON.isdigit():
        cap = int(JU_PRICE_MAX_MANWON) * 10000
        out = [r for r in out if r["감정가"] is not None and r["감정가"] <= cap]
    return out


# ------------------------------------------------------------------ 구글시트 / 로컬 저장
def credentials_path():
    for p in GOOGLE_CREDENTIALS_PATH_CANDIDATES:
        if p and os.path.exists(p):
            return p
    return None


def open_spreadsheet():
    if not GOOGLE_SHEETS_ENABLED:
        return None
    if gspread is None:
        log("[구글시트] gspread 미설치 - 건너뜀")
        return None
    if not GOOGLE_SHEET_ID:
        log("[구글시트] 스프레드시트 ID 를 찾지 못해 건너뜀(GOOGLE_SHEET_ID 환경변수)")
        return None
    cred = credentials_path()
    if not cred:
        log("[구글시트] 서비스 계정 키 파일을 찾지 못해 건너뜀")
        return None
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        return gspread.service_account(filename=cred, scopes=scopes).open_by_key(GOOGLE_SHEET_ID)
    except Exception as e:
        log(f"[구글시트] 연결 실패: {e}")
        return None


def write_to_gsheet(sh, tab_name, values, headers=None, price_cols=PRICE_COLS):
    headers = headers or HEADERS
    n_rows, n_cols = len(values), len(headers)
    try:
        ws = sh.worksheet(tab_name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=tab_name, rows=n_rows + 10, cols=n_cols + 2)
        log(f"[구글시트] 새 탭 생성: {tab_name}")
    if ws.row_count < n_rows + 10 or ws.col_count < n_cols + 2:
        ws.resize(rows=max(ws.row_count, n_rows + 10), cols=max(ws.col_count, n_cols + 2))
    ws.clear()
    ws.update(values=values, range_name="A1", value_input_option="USER_ENTERED")   # A1 고정(열 밀림 방지)
    try:
        ws.freeze(rows=1)
        ws.format("1:1", {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.9, "green": 0.93, "blue": 0.98}})
        for name in price_cols:
            if name in headers:
                col = gspread.utils.rowcol_to_a1(1, headers.index(name) + 1).rstrip("1")
                ws.format(f"{col}2:{col}", {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}})
    except Exception as e:
        log(f"[구글시트] 서식 적용 실패(데이터는 저장됨): {e}")
    try:
        after = len(ws.col_values(1))
        log(f"[검증] {'일치' if after == n_rows else '불일치'} - 기록 {n_rows}행 / 실제 {after}행")
        return after
    except Exception as e:
        log(f"[검증] 행 수 확인 실패: {e}")
        return None


def cleanup_old_tabs(sh, keep_weeks=TAB_RETENTION_WEEKS):
    if not keep_weeks:
        return
    cutoff = this_weekend(date.today()) - timedelta(weeks=keep_weeks - 1)
    pat = re.compile(rf"^{re.escape(TAB_PREFIX)}(\d{{8}})(?:_상세)?$")
    for ws in sh.worksheets():
        m = pat.match(ws.title)
        if not m:
            continue
        try:
            d = datetime.strptime(m.group(1), "%Y%m%d").date()
        except ValueError:
            continue
        if d < cutoff and len(sh.worksheets()) > 1:
            sh.del_worksheet(ws)
            log(f"[구글시트] 오래된 탭 삭제: {ws.title}")


def previous_tab_ids(sh, current_title):
    pat = re.compile(rf"^{re.escape(TAB_PREFIX)}\d{{8}}$")
    titles = sorted([w.title for w in sh.worksheets() if pat.match(w.title) and w.title != current_title], reverse=True)
    if not titles:
        return "", set()
    ws = sh.worksheet(titles[0])
    try:
        values = ws.get_all_values()
    except Exception:
        return titles[0], set()
    if not values or "product_id" not in values[0]:
        return titles[0], set()
    i = values[0].index("product_id")
    return titles[0], {r[i] for r in values[1:] if len(r) > i and r[i]}


def append_log(sh, entry):
    if sh is None:
        return
    try:
        try:
            ws = sh.worksheet(LOG_TAB)
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title=LOG_TAB, rows=1000, cols=len(LOG_HEADERS) + 2)
            ws.update(values=[LOG_HEADERS], range_name="A1")
        if not ws.row_values(1):
            ws.update(values=[LOG_HEADERS], range_name="A1")
        ws.append_row([entry.get(h, "") for h in LOG_HEADERS], value_input_option="RAW", table_range="A1")
    except Exception as e:
        log(f"[{LOG_TAB}] 기록 실패(치명적이지 않음): {e}")


def save_local_xlsx(tab_name, values, headers=None, price_cols=PRICE_COLS):
    if not SAVE_LOCAL_XLSX:
        return
    headers = headers or HEADERS
    folder = SAVE_DIR if os.path.isdir(SAVE_DIR) else HERE
    base = os.path.join(folder, tab_name)
    with open(base + ".csv", "w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerows(values)
    log(f"로컬 CSV 저장: {base}.csv")
    if Workbook is None:
        return
    wb = Workbook()
    ws = wb.active
    ws.title = tab_name[:31]
    for r in values:
        ws.append(r)
    for name in price_cols:
        if name in headers:
            ci = headers.index(name) + 1
            for (cell,) in ws.iter_rows(min_row=2, min_col=ci, max_col=ci):
                cell.number_format = "#,##0"
    ws.freeze_panes = "A2"
    wb.save(base + ".xlsx")
    log(f"로컬 XLSX 저장: {base}.xlsx")


# ------------------------------------------------------------------ 외부(03_2)에서 쓰는 진입점
def collect_npl_rows():
    """로그인 -> 수집 -> 조건 필터 -> 03_1 과 같은 키의 dict 리스트(매각기일·사건번호 순)."""
    session = build_session()
    login(session)
    items, total, complete = crawl(session)
    if not complete:
        log("경고: 수집이 불완전합니다(사이트 표시 건수 미달).")
    collected_at = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    items = apply_filters(items)
    for r in items:
        r["수집일시"] = collected_at
    log(f"조건(매각기일 {DAYS_AHEAD}일 이내, 감정가 {JU_PRICE_MIN_MANWON or '-'}~{JU_PRICE_MAX_MANWON or '-'}만원) 통과: {len(items)}건")
    return sorted(items, key=lambda r: (r["매각기일"], r["사건번호"], int(r["물번"] or 0)))


# ------------------------------------------------------------------ main
def main():
    t0 = time.monotonic()
    now = datetime.now(KST)
    tab = tab_name_for()
    sh = open_spreadsheet()
    entry = {"실행시각(KST)": now.strftime("%Y-%m-%d %H:%M"), "대상탭": tab}
    note = []
    result, code = "실패", 1
    try:
        session = build_session()
        login(session)
        raw, total, complete = crawl(session)
        entry["사이트표시건수"], entry["수집건수"] = total if total is not None else "", len(raw)
        collected_at = now.strftime("%Y-%m-%d %H:%M")
        items = apply_filters(raw)
        for r in items:
            r["수집일시"] = collected_at
        items.sort(key=lambda r: (r["매각기일"], r["사건번호"], int(r["물번"] or 0)))
        entry["조건통과건수"] = len(items)

        prev_title, prev_ids = ("", set())
        if sh is not None:
            prev_title, prev_ids = previous_tab_ids(sh, tab)
        cur_ids = {r["product_id"] for r in items}
        if prev_ids:
            for r in items:
                r["이전대비"] = "" if r["product_id"] in prev_ids else "신규"
        entry["비교탭"] = prev_title
        entry["신규"] = sum(1 for r in items if r["이전대비"] == "신규") if prev_ids else ""
        entry["사라짐(매각/취하 추정)"] = len(prev_ids - cur_ids) if prev_ids else ""

        values = [HEADERS] + [[("" if r[h] is None else r[h]) for h in HEADERS] for r in items]
        save_local_xlsx(tab, values)

        if sh is None:
            result, code = "구글시트 미사용(로컬만 저장)", 0
        elif not complete:
            result, code = "수집 불완전 - 시트 기록 안 함", 1
            note.append("사이트 표시 건수 대비 수집이 부족해 기존 시트를 건드리지 않음")
        elif not items:
            result, code = "0건 - 시트 기록 안 함", 1
        else:
            written = write_to_gsheet(sh, tab, values)
            entry["시트기록행수"] = written if written is not None else ""
            cleanup_old_tabs(sh)
            result, code = ("성공", 0) if written == len(values) else ("행수 불일치", 1)
        log(f"완료: 수집 {len(raw)}건 -> 조건통과 {len(items)}건 / 결과: {result}")
    except Exception as e:
        note.append(f"{type(e).__name__}: {str(e)[:200]}")
        log(f"오류: {e}")
    entry["결과"] = result
    entry["소요시간(분)"] = round((time.monotonic() - t0) / 60, 1)
    entry["비고"] = " | ".join(note)
    append_log(sh, entry)
    return code


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass
    sys.exit(main())
