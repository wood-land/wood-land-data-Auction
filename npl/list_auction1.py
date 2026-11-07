# -*- coding: utf-8 -*-
"""
옥션원(auction1.co.kr) 부실채권(NPL) 목록 수집 모듈 (v1, 2026-11-07) - npl_crawler.py 가 collect_npl_rows() 를 호출

[이 파일의 역할]
- 옥션원 NPL 탭 목록만 수집한다(사건번호 목록). 옥션원 상세페이지는 서비스 지역 제한이
  있어 크롤링하지 않는다.
- 단독 실행하면 구글 시트 "NPL_YYYYMMDD" 탭 + 로컬 xlsx 로 저장한다.
- 상세 내역은 '03_2. 옥션원 NPL 두인연계 상세 26 1107_v1.py' 가 이 파일의
  collect_npl_rows() 를 불러와 두인경매에서 추출한다.

[화면 구조 조사 결과 - 사이트가 바뀌면 여기를 먼저 확인]
1) 검색 페이지 /auction/ca_npl.php (form#fm_aulist). 필드명 고정:
   s_class, state, ju_price1/2(만원), bi_price1/2(만원), next_biddate1/2, scale, order,
   npl_key(보유회사 전체), npl_* (회사별)
2) 결과 #auct_list 의 tr/td id·class 는 로드마다 무작위 -> input[name=ck_pid] 가 든 tr 을 행으로 잡고
   td 위치로 읽는다. td[2]사건번호/종류, [3]소재지, [4]가격, [5]진행상태, [6]매각기일, [7]조회수.
3) 페이지 이동: div.pagn a 링크의 start=오프셋.
4) 목록에는 법원명이 없다 -> 두인 매칭은 사건번호 + 감정가/매각기일/소재지로 한다.

로그인: 환경변수 A1_LOGIN_ID / A1_LOGIN_PW
필요 패키지: pip install selenium gspread google-auth openpyxl
"""

import os
import re
import sys
import time
import math
from datetime import datetime, date, timedelta

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, UnexpectedAlertPresentException,
    NoAlertPresentException,
)

try:
    import gspread
except ImportError:
    gspread = None

try:
    from openpyxl import Workbook
except ImportError:
    Workbook = None


# ============================== 설정 ==============================
SITE_BASE = "https://www.auction1.co.kr"
LOGIN_URL = f"{SITE_BASE}/common/login_box.php"
NPL_SEARCH_URL = f"{SITE_BASE}/auction/ca_npl.php"
DETAIL_URL_FMT = f"{SITE_BASE}/auction/ca_view.php?product_id={{pid}}"

LOGIN_ID = os.environ.get("A1_LOGIN_ID", "").strip()
LOGIN_PW = os.environ.get("A1_LOGIN_PW", "").strip()

GOOGLE_SHEETS_ENABLED = False   # 저장은 npl_crawler.py 가 한다(이 파일은 목록 수집 전용)
GOOGLE_SHEET_ID = ""
GOOGLE_SHEET_SHARE_EMAIL = ""
GOOGLE_CREDENTIALS_PATH_CANDIDATES = [
    "C:/startcoding/100. Google_credentials/google_credentials_편집자.json",
    "C:/Python/startcoding/100. google_credentials/google_credentials_편집자.json",
]
TAB_PREFIX = "NPL_"
WEEKEND_WEEKDAY = 5             # 5=토요일
TAB_RETENTION_WEEKS = 8

SAVE_LOCAL_XLSX = False
SAVE_DIR = "D:/"

DAYS_AHEAD = 60
S_CLASS_TEXT = "토지"            # "" 또는 "전체보기" = 전체
STATE_TEXT = "진행물건"
JU_PRICE_MIN_MANWON = ""
JU_PRICE_MAX_MANWON = "50000"   # 만원 단위, 50000 = 5억
BI_PRICE_MIN_MANWON = ""
BI_PRICE_MAX_MANWON = ""
LIST_SCALE = "100"
ORDER_TEXT = "매각기일↑"
MAX_PAGES = 200

TAG_NPL_HOLDER = True
NPL_HOLDERS = [
    ("npl_woori", "대신AMC"), ("npl_kpmg", "파빌리온자산관리"), ("npl_uamco", "연합자산관리"),
    ("npl_nonghyup", "농협자산관리"), ("npl_kdf", "(주)화인자산관리"), ("npl_jone", "제이원자산관리"),
    ("npl_ptamc", "파인트리AMC"), ("npl_lbamc", "리베AMC"), ("npl_mai", "코레이트자산운용"),
    ("npl_hanafni", "하나에프앤아이"), ("npl_igisam", "이지스자산운용"), ("npl_mginfo", "MG신용정보"),
    ("npl_wooricredit", "우리신용정보"), ("npl_koryo", "고려신용정보"), ("npl_shci", "신한신용정보"),
    ("npl_woorifni", "우리금융F&I"), ("npl_etcamc", "자산관리"), ("npl_etc", "기타"),
]

HEADLESS = os.environ.get("A1_HEADLESS", "1") != "0"   # run_pc.py --show 이면 창을 띄운다
PAGE_DELAY_SEC = 1.5

HEADERS = [
    "사건번호", "물번", "물건종류", "소재지", "면적정보", "특이사항",
    "감정가", "최저가", "최저가율", "평당가", "진행상태", "유찰횟수",
    "매각기일", "매각시간", "입찰D-day", "조회수", "보유회사", "product_id", "상세페이지", "수집일시",
]
PRICE_COLS = ("감정가", "최저가")
# =================================================================


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def this_weekend(d: date) -> date:
    monday = d - timedelta(days=d.weekday())
    return monday + timedelta(days=WEEKEND_WEEKDAY)


def tab_name_for(d: date = None) -> str:
    return f"{TAB_PREFIX}{this_weekend(d or date.today()):%Y%m%d}"


# ------------------------------------------------------------------ 브라우저
def get_driver():
    opts = Options()
    if HEADLESS:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--lang=ko-KR")
    opts.add_argument("--no-sandbox")              # GitHub Actions(리눅스) 필수
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    # 러너에 미리 깔린 chromedriver 는 시스템 Chrome 과 버전이 맞는다(두인 수집기와 같은 방식).
    # setup-chrome 이 받은 최신 Chrome(CHROME_BIN)은 드라이버와 버전이 달라 마지막 수단으로만 쓴다.
    for cand in ("/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
                 "/usr/bin/chromium-browser", "/usr/bin/chromium", os.environ.get("CHROME_BIN", "")):
        if cand and os.path.exists(cand):
            opts.binary_location = cand
            break
    opts.add_experimental_option("excludeSwitches", ["enable-logging"])
    return webdriver.Chrome(service=Service(), options=opts)


def dismiss_alert(driver):
    try:
        a = driver.switch_to.alert
        txt = a.text
        a.accept()
        log(f"알림창 닫음: {txt}")
        return txt
    except NoAlertPresentException:
        return None
    except Exception:
        return None


def is_logged_in(driver):
    try:
        return "로그아웃" in driver.find_element(By.TAG_NAME, "body").text
    except Exception:
        return False


def login(driver):
    if not LOGIN_ID or not LOGIN_PW:
        raise RuntimeError("로그인 정보가 없습니다. 환경변수 A1_LOGIN_ID / A1_LOGIN_PW 를 설정하세요.")
    driver.get(LOGIN_URL)
    wait = WebDriverWait(driver, 20)
    id_el = wait.until(EC.element_to_be_clickable((By.ID, "client_id")))
    id_el.clear()
    id_el.send_keys(LOGIN_ID)
    try:
        driver.find_element(By.ID, "pw_Dummy").click()
    except NoSuchElementException:
        pass
    pw_el = wait.until(EC.visibility_of_element_located((By.ID, "passwd")))
    pw_el.send_keys(LOGIN_PW)
    pw_el.send_keys(Keys.ENTER)
    time.sleep(3)
    dismiss_alert(driver)
    log(f"로그인 시도 후 URL={driver.current_url} 로그아웃표시={is_logged_in(driver)}")

    driver.get(NPL_SEARCH_URL)
    try:
        wait.until(EC.presence_of_element_located((By.ID, "fm_aulist")))
    except TimeoutException:
        txt = ""
        try:
            txt = re.sub(r"\s+", " ", driver.find_element(By.TAG_NAME, "body").text)[:400]
        except Exception:
            pass
        raise RuntimeError(f"NPL 검색 화면을 열지 못함: URL={driver.current_url} 제목={driver.title!r} "
                           f"로그아웃표시={is_logged_in(driver)} 본문={txt!r}")
    if not is_logged_in(driver):
        raise RuntimeError("로그인 실패로 보입니다 (페이지에 '로그아웃'이 없음). 아이디/비밀번호를 확인하세요.")
    log("옥션원 로그인 완료")


# ------------------------------------------------------------------ 검색 조건
def _set_text(driver, name, value):
    driver.execute_script(
        "var e=document.getElementsByName(arguments[0])[0];"
        "if(e){e.value=arguments[1];e.dispatchEvent(new Event('change',{bubbles:true}));}",
        name, value or "")


def _select_text(driver, name, text):
    if not text:
        return
    try:
        Select(driver.find_element(By.NAME, name)).select_by_visible_text(text)
    except NoSuchElementException:
        log(f"경고: '{name}' 에서 '{text}' 옵션을 찾지 못해 기본값으로 둡니다.")


def _set_npl_holder(driver, holder_name):
    driver.execute_script(
        "var target=arguments[0];"
        "document.querySelectorAll('#fm_aulist input[type=checkbox][name^=\"npl_\"]').forEach(function(c){"
        "  c.checked = target ? (c.name===target) : (c.name==='npl_key');"
        "});", holder_name)


def run_search(driver, start_date, end_date, holder_name=None):
    driver.get(NPL_SEARCH_URL)
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "fm_aulist")))
    dismiss_alert(driver)

    _select_text(driver, "s_class", S_CLASS_TEXT)
    _select_text(driver, "state", STATE_TEXT)
    _set_text(driver, "ju_price1", JU_PRICE_MIN_MANWON)
    _set_text(driver, "ju_price2", JU_PRICE_MAX_MANWON)
    _set_text(driver, "bi_price1", BI_PRICE_MIN_MANWON)
    _set_text(driver, "bi_price2", BI_PRICE_MAX_MANWON)
    _set_text(driver, "next_biddate1", start_date)
    _set_text(driver, "next_biddate2", end_date)
    _select_text(driver, "scale", LIST_SCALE)
    _select_text(driver, "order", ORDER_TEXT)
    _set_npl_holder(driver, holder_name)

    btn = driver.find_element(By.XPATH, "//form[@id='fm_aulist']//input[@value='검색']")
    driver.execute_script("arguments[0].click();", btn)
    try:
        WebDriverWait(driver, 30).until(
            lambda d: re.search(r"물건수\s*:\s*[\d,]+\s*건", d.find_element(By.TAG_NAME, "body").text))
    except UnexpectedAlertPresentException:
        dismiss_alert(driver)
    except TimeoutException:
        log("경고: 검색 결과(물건수)를 확인하지 못했습니다.")
    return get_total_count(driver)


def get_total_count(driver):
    try:
        m = re.search(r"물건수\s*:\s*([\d,]+)\s*건", driver.find_element(By.TAG_NAME, "body").text)
        return int(m.group(1).replace(",", "")) if m else 0
    except Exception:
        return 0


# ------------------------------------------------------------------ 목록 읽기
JS_READ_ROWS = r"""
var out=[];
document.querySelectorAll('#auct_list input[name="ck_pid"]').forEach(function(inp){
  var tr=inp.closest('tr'); if(!tr) return;
  var cells=Array.prototype.map.call(tr.cells, function(c){
    return c.innerText.split('\n').map(function(s){return s.trim();}).filter(Boolean);
  });
  out.push({pid: inp.value, cells: cells});
});
return out;
"""


def wait_rows_loaded(driver, expected, timeout=40):
    end = time.time() + timeout
    last, stable_since = -1, time.time()
    while time.time() < end:
        n = len(driver.find_elements(By.CSS_SELECTOR, "#auct_list input[name='ck_pid']"))
        if expected and n >= expected:
            return n
        if n != last:
            last, stable_since = n, time.time()
        elif n > 0 and time.time() - stable_since > 2.0:
            return n
        time.sleep(0.4)
    return last


def _to_int(s):
    s = re.sub(r"[^\d]", "", s or "")
    return int(s) if s else None


def parse_row(pid, cells, collected_at):
    def cell(i):
        return cells[i] if i < len(cells) else []

    c2, c3, c4, c5, c6, c7 = cell(2), cell(3), cell(4), cell(5), cell(6), cell(7)

    case_raw = c2[0] if c2 else ""
    m = re.match(r"([\d]+-[\d]+)\s*(?:\((\d+)\))?", case_raw)
    사건번호 = m.group(1) if m else case_raw
    물번 = m.group(2) if (m and m.group(2)) else ""
    물건종류 = c2[1] if len(c2) > 1 else ""

    소재지 = c3[0] if c3 else ""
    rest = c3[1:]
    면적정보 = rest[0].strip("[]") if rest and re.search(r"㎡|평", rest[0]) else ""
    특이사항 = " ".join(x.strip("[]") for x in (rest[1:] if 면적정보 else rest))

    nums = [x for x in c4 if re.fullmatch(r"[\d,]+", x)]
    감정가 = _to_int(nums[0]) if len(nums) > 0 else None
    최저가 = _to_int(nums[1]) if len(nums) > 1 else None
    평당가 = next((x for x in c4 if "평당" in x), "")

    진행상태 = c5[0] if c5 else ""
    최저가율 = next((x.strip("()") for x in c5 if "%" in x), "")
    mm = re.search(r"유찰\s*(\d+)\s*회", " ".join(c5))
    유찰횟수 = int(mm.group(1)) if mm else 0

    md = re.search(r"(\d{4})\.(\d{2})\.(\d{2})", " ".join(c6))
    매각기일 = f"{md.group(1)}-{md.group(2)}-{md.group(3)}" if md else ""
    mt = re.search(r"\((\d{1,2}:\d{2})\)", " ".join(c6))
    매각시간 = mt.group(1) if mt else ""
    dday = next((x for x in c6 if "일전" in x or "당일" in x), "")
    조회수 = _to_int(c7[0]) if c7 else None

    return {
        "사건번호": 사건번호, "물번": 물번, "물건종류": 물건종류, "소재지": 소재지,
        "면적정보": 면적정보, "특이사항": 특이사항, "감정가": 감정가, "최저가": 최저가,
        "최저가율": 최저가율, "평당가": 평당가, "진행상태": 진행상태, "유찰횟수": 유찰횟수,
        "매각기일": 매각기일, "매각시간": 매각시간, "입찰D-day": dday, "조회수": 조회수,
        "보유회사": "", "product_id": pid, "상세페이지": DETAIL_URL_FMT.format(pid=pid),
        "수집일시": collected_at,
    }


def _page_href(driver, offset):
    href = driver.execute_script("var a=document.querySelector('.pagn a'); return a ? a.href : null;")
    if not href:
        return None
    if re.search(r"[?&]start=", href):
        return re.sub(r"([?&]start=)\d*", rf"\g<1>{offset}", href)
    return href + ("&" if "?" in href else "?") + f"start={offset}"


def crawl_all_pages(driver, total, collected_at, label=""):
    rows = {}
    if total <= 0:
        return rows
    scale = int(LIST_SCALE)
    pages = min(math.ceil(total / scale), MAX_PAGES)
    prev_first = None
    for p in range(pages):
        offset = p * scale
        if p > 0:
            href = _page_href(driver, offset)
            if not href:
                log(f"{label} 페이지 링크를 찾지 못해 {p}페이지에서 중단")
                break
            time.sleep(PAGE_DELAY_SEC)
            driver.get(href)
            dismiss_alert(driver)
        expected = min(scale, total - offset)
        n = wait_rows_loaded(driver, expected)
        data = driver.execute_script(JS_READ_ROWS) or []
        if not data:
            log(f"{label} {p + 1}페이지: 행이 없습니다. 중단")
            break
        if prev_first is not None and data[0]["pid"] == prev_first:
            log(f"{label} {p + 1}페이지: 이전 페이지와 같은 목록 - 페이지 이동 실패로 보고 중단")
            break
        prev_first = data[0]["pid"]
        for d in data:
            rows.setdefault(d["pid"], parse_row(d["pid"], d["cells"], collected_at))
        log(f"{label} {p + 1}/{pages}페이지: {len(data)}행 (누적 {len(rows)}/{total})")
        if n < expected:
            log(f"  경고: 예상 {expected}행 중 {n}행만 로드됨")
    return rows


# ------------------------------------------------------------------ 구글 시트
def credentials_path():
    for p in GOOGLE_CREDENTIALS_PATH_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


def open_spreadsheet():
    if not GOOGLE_SHEETS_ENABLED:
        return None
    if gspread is None:
        log("[구글시트] gspread 미설치 - 건너뜀")
        return None
    cred = credentials_path()
    if not cred:
        log("[구글시트] 서비스 계정 키 파일을 찾지 못해 건너뜀")
        return None
    gc = gspread.service_account(filename=cred)
    if GOOGLE_SHEET_ID:
        return gc.open_by_key(GOOGLE_SHEET_ID.strip())
    sh = gc.create("옥션원_NPL")
    log(f"[구글시트] 새 스프레드시트 생성: {sh.url}  <- GOOGLE_SHEET_ID 에 이 ID를 넣어두세요")
    if GOOGLE_SHEET_SHARE_EMAIL:
        sh.share(GOOGLE_SHEET_SHARE_EMAIL, perm_type="user", role="writer")
    return sh


def write_to_gsheet(sh, tab_name, values, headers=None, price_cols=PRICE_COLS):
    headers = headers or HEADERS
    try:
        ws = sh.worksheet(tab_name)
        ws.clear()
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=tab_name, rows=max(len(values) + 10, 100), cols=len(headers) + 2)
    if ws.row_count < len(values):
        ws.add_rows(len(values) - ws.row_count + 10)
    if ws.col_count < len(headers):
        ws.add_cols(len(headers) - ws.col_count + 2)
    ws.update(values=values, range_name="A1", value_input_option="USER_ENTERED")
    try:
        ws.freeze(rows=1)
        ws.format("1:1", {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.9, "green": 0.93, "blue": 0.98}})
        for col_name in price_cols:
            if col_name not in headers:
                continue
            ci = headers.index(col_name) + 1
            letter = gspread.utils.rowcol_to_a1(1, ci).rstrip("1")
            ws.format(f"{letter}2:{letter}", {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}})
    except Exception as e:
        log(f"[구글시트] 서식 적용 실패(데이터는 저장됨): {e}")
    log(f"[구글시트] '{tab_name}' 탭에 {len(values) - 1}행 저장 완료")
    return ws


def cleanup_old_tabs(sh, keep_weeks):
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


# ------------------------------------------------------------------ 로컬 백업
def save_local_xlsx(tab_name, values, headers=None, price_cols=PRICE_COLS):
    if not SAVE_LOCAL_XLSX or Workbook is None:
        return
    headers = headers or HEADERS
    folder = SAVE_DIR if os.path.isdir(SAVE_DIR) else os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(folder, f"{tab_name}.xlsx")
    wb = Workbook()
    ws = wb.active
    ws.title = tab_name[:31]
    for r in values:
        ws.append(r)
    for col_name in price_cols:
        if col_name not in headers:
            continue
        ci = headers.index(col_name) + 1
        for row in ws.iter_rows(min_row=2, min_col=ci, max_col=ci):
            row[0].number_format = "#,##0"
    wb.save(path)
    log(f"로컬 백업 저장: {path}")


# ------------------------------------------------------------------ 수집 본체
def collect_npl_rows():
    """옥션원 NPL 목록을 수집해 정렬된 dict 리스트로 반환한다."""
    today = date.today()
    start_date = today.strftime("%Y-%m-%d")
    end_date = (today + timedelta(days=DAYS_AHEAD)).strftime("%Y-%m-%d")
    collected_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    log(f"=== 옥션원 NPL 목록 수집: 매각기일 {start_date} ~ {end_date} ===")

    driver = get_driver()
    try:
        login(driver)
        total = run_search(driver, start_date, end_date, holder_name=None)
        log(f"검색 결과(보유회사 전체): {total}건")
        rows = crawl_all_pages(driver, total, collected_at, label="[전체]")

        if TAG_NPL_HOLDER and rows:
            holder_map = {}
            for field, name in NPL_HOLDERS:
                cnt = run_search(driver, start_date, end_date, holder_name=field)
                if cnt == 0:
                    continue
                sub = crawl_all_pages(driver, cnt, collected_at, label=f"[{name}]")
                for pid, r in sub.items():
                    holder_map.setdefault(pid, []).append(name)
                    rows.setdefault(pid, r)
            for pid, names in holder_map.items():
                rows[pid]["보유회사"] = ", ".join(names)
            log(f"보유회사 태깅 완료: {len(holder_map)}/{len(rows)}건")

        if total and len(rows) < total:
            log(f"경고: 검색 결과 {total}건 중 {len(rows)}건만 수집됨")
    finally:
        driver.quit()

    return sorted(rows.values(), key=lambda r: (r["매각기일"], r["사건번호"], int(r["물번"] or 0)))


def save_list(ordered, sh=None):
    tab_name = tab_name_for()
    values = [HEADERS] + [[("" if r[h] is None else r[h]) for h in HEADERS] for r in ordered]
    save_local_xlsx(tab_name, values)
    if sh is not None:
        write_to_gsheet(sh, tab_name, values)
        cleanup_old_tabs(sh, TAB_RETENTION_WEEKS)


def main():
    ordered = collect_npl_rows()
    save_list(ordered, open_spreadsheet())
    log(f"=== 완료: {len(ordered)}건 ===")
    return 0 if ordered else 1


if __name__ == "__main__":
    sys.exit(main())
