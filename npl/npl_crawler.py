# -*- coding: utf-8 -*-
"""옥션원 NPL 목록 -> 두인 시트 매칭 -> 두인 상세(필지/지분/등기부/채권) -> 구글시트 'NPL_YYYYMMDD_상세'.

흐름
 1) list_auction1.collect_npl_rows(): 옥션원 NPL 탭 목록(사건번호). 옥션원 상세는 보지 않는다.
 2) 두인 구글시트 주차 탭(YYYYMMDD_Wxx_data / _manual_data / _경공매물건)에서 사건번호 -> tid 색인.
 3) matching.match_one(): 연도+번호 후보를 감정가/매각기일/소재지 점수로 확인.
 4) 매칭된 물건만 두인 상세페이지 방문:
      - auction/crawler.py fetch_detail_info(): 필지별 주소, 참고사항, 지분 여부, 토지등기 요약(지분)
      - registry.fetch_registry_history_info(): 입찰이력, 근저당/청구금액, 채권원금, 연체이자, 채권행사권리금액
 5) 'NPL_YYYYMMDD_상세' 탭(YYYYMMDD = 이번 주 토요일)에 저장. 필지가 여러 개면 필지마다 한 행.
    앞 19열은 두인 주차 탭과 같고 AC열(29열)이 토지등기 요약이라 PNU/QGIS 단계가 그대로 이어받는다.
 6) 'NPL_로그' 탭에 실행 1회당 한 줄 기록(성공/실패와 무관하게 마지막에 반드시 기록).

환경변수: SITE_DOMAIN SITE_LOGIN_ID SITE_LOGIN_PW GOOGLE_SHEET_ID GOOGLE_SA_KEY_JSON (두인, auction.yml 과 동일)
          A1_LOGIN_ID A1_LOGIN_PW (옥션원)
          선택: NPL_MAX_DETAIL(시험용 상세 상한), NPL_DEADLINE_MINUTES, TRIGGER_TYPE
"""
import os
import re
import sys
import time
import traceback
from datetime import datetime, timedelta, date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import gspread  # noqa: E402

import dooin_base as dc  # noqa: E402
import list_auction1 as a1  # noqa: E402
import matching  # noqa: E402
import registry  # noqa: E402

TAB_PREFIX = "NPL_"
DETAIL_SUFFIX = "_상세"
LOG_TAB = "NPL_로그"
RETENTION_WEEKS = 8
INDEX_TABS_MAX = 4
INDEX_TAB_PATTERNS = [
    re.compile(r"^(\d{8})_W\d{2}_data$"),
    re.compile(r"^(\d{8})_manual_data$"),
    re.compile(r"^(\d{8})_W\d{2}_경공매물건$"),
]
MAX_DETAIL = int(os.environ.get("NPL_MAX_DETAIL", "0") or 0)              # 0 = 제한 없음
DEADLINE_MIN = float(os.environ.get("NPL_DEADLINE_MINUTES", "150") or 0)   # 넘으면 상세 추출을 멈추고 저장
AC_COL = dc.AC_COL                                                         # 29: 토지등기 요약

EXTRA_HEADERS = [  # 두인 19열 뒤 ~ AB열(28열) 까지 9열
    "매칭상태", "매칭점수", "보유회사", "옥션원 사건번호", "물번", "product_id", "옥션원 상세페이지", "tid", "두인 탭",
]
REGISTRY_HEADERS = [  # AD열(30열) ~
    "개시결정", "토지면적(상세)", "건물면적(상세)", "입찰진행내용",
    "등기부_근저당권설정(말소기준포함)", "근저당권_합계금액", "채권원금",
    "등기부_청구금액", "유동화전문_청구금액",
    "기준일(입찰기일+60일)", "이자 연체일수", "예상연체이자", "채권행사권리금액",
]
LOG_HEADERS = [
    "실행시각(KST)", "트리거", "대상탭", "결과", "옥션원_수집건수", "두인색인_건수", "매칭", "미매칭",
    "상세성공", "상세실패", "출력행수", "소요시간(분)", "마감도달", "비고",
]


def kst_now():
    return datetime.utcnow() + timedelta(hours=9)


def log(msg):
    print(f"[{kst_now():%H:%M:%S}] {msg}", flush=True)


def header_row():
    h = list(dc.TEMPLATE_HEADERS) + EXTRA_HEADERS
    assert len(h) == AC_COL - 1, (len(h), AC_COL)
    h.append("토지등기_요약(지분물건만, 임시)")
    return h + REGISTRY_HEADERS


# ------------------------------------------------------------------ 시트
def build_index(sh):
    tabs = []
    for ws in sh.worksheets():
        for p in INDEX_TAB_PATTERNS:
            m = p.match(ws.title)
            if m:
                tabs.append((m.group(1), ws))
                break
    tabs.sort(key=lambda t: t[0], reverse=True)
    tabs = tabs[:INDEX_TABS_MAX]
    log(f"두인 시트 탭 {len(tabs)}개 읽기: {[w.title for _, w in tabs]}")
    index, seen = {}, set()
    for _, ws in tabs:
        try:
            n = matching.add_tab_to_index(index, seen, ws.get_all_values(), ws.title)
            log(f"  '{ws.title}': tid {n}건 색인")
        except Exception as e:
            log(f"  '{ws.title}' 읽기 실패: {e}")
    return index, len(seen)


def this_saturday(d: date) -> date:
    return d - timedelta(days=d.weekday()) + timedelta(days=5)


def write_detail_tab(sh, tab, values):
    try:
        ws = sh.worksheet(tab)
        ws.clear()
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=tab, rows=max(len(values) + 20, 100), cols=len(values[0]) + 2)
    need_r, need_c = len(values) + 10, len(values[0]) + 2
    if ws.row_count < need_r or ws.col_count < need_c:
        ws.resize(rows=max(ws.row_count, need_r), cols=max(ws.col_count, need_c))
    ws.update(values=values, range_name="A1", value_input_option="USER_ENTERED")
    try:
        ws.freeze(rows=1)
        ws.format("1:1", {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.9, "green": 0.93, "blue": 0.98}})
    except Exception as e:
        log(f"서식 적용 실패(데이터는 저장됨): {e}")
    log(f"'{tab}' 탭에 {len(values) - 1}행 저장")
    return ws


def cleanup_old_tabs(sh):
    cutoff = this_saturday(kst_now().date()) - timedelta(weeks=RETENTION_WEEKS - 1)
    pat = re.compile(rf"^{TAB_PREFIX}(\d{{8}}){DETAIL_SUFFIX}$")
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
            log(f"오래된 탭 삭제: {ws.title}")


def append_log(sh, entry: dict):
    """실행 요약 한 줄을 NPL_로그 탭에 추가한다. 실패해도 예외를 밖으로 내보내지 않는다."""
    if sh is None:
        log("로그 탭에 기록하지 못함(스프레드시트 연결 없음): " + str(entry))
        return
    try:
        try:
            ws = sh.worksheet(LOG_TAB)
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title=LOG_TAB, rows=1000, cols=len(LOG_HEADERS) + 2)
            ws.update(values=[LOG_HEADERS], range_name="A1")
            ws.freeze(rows=1)
        if not ws.row_values(1):
            ws.update(values=[LOG_HEADERS], range_name="A1")
        ws.append_row([entry.get(h, "") for h in LOG_HEADERS], value_input_option="RAW", table_range="A1")
        log(f"[{LOG_TAB}] 기록: 결과={entry.get('결과')} 매칭={entry.get('매칭')}/{entry.get('옥션원_수집건수')}")
    except Exception as e:
        log(f"[{LOG_TAB}] 기록 실패: {e}")


# ------------------------------------------------------------------ 행 만들기
def make_rows(r, cand, score, status, parcels, notes, ac_summary, jibun, reg):
    """옥션원 1건 -> 시트 행 1개 이상(필지가 여러 개면 필지마다 한 행)."""
    tmpl = dc.TEMPLATE_HEADERS
    base = cand["base"] if cand else {}
    values = {h: base.get(h, "") for h in tmpl}
    if not cand:   # 미매칭: 옥션원 값으로 채워 다음 단계(주소 -> PNU)가 돌게 한다
        values[tmpl[0]] = "NPL"
        values["사건번호"] = r["사건번호"] + (f" ({r['물번']})" if r["물번"] else "")
        values["주소"] = r["소재지"]
        values["참고사항"] = r["특이사항"] or "-"
        values["용도"] = r["물건종류"]
        values["진행상태"] = r["진행상태"]
        values["최저가율"] = r["최저가율"]
        values["최저가"] = r["최저가"]
        values["감평가"] = r["감정가"]
        values["입찰일"] = f"{r['매각기일']} {r['매각시간']}".strip()
        values["상세페이지"] = r["상세페이지"]
    base_addr = values.get("주소", "")

    if notes:
        old = values.get("참고사항", "")
        values["참고사항"] = f"{old}\n\n{notes}" if old and old != "-" else notes
    if jibun:
        values["지분 여부"] = jibun
    elif "지분" in str(values.get("참고사항", "")):
        values["지분 여부"] = "지분"

    reg = reg or {}
    extras = [status, score, r["보유회사"], r["사건번호"], r["물번"], r["product_id"],
              r["상세페이지"], cand["tid"] if cand else "", cand["tab"] if cand else ""]
    regvals = [reg.get("개시결정", ""), reg.get("토지면적", ""), reg.get("건물면적", ""),
               reg.get("입찰진행내용", ""), reg.get("등기부_근저당", ""), reg.get("근저당권_합계금액"),
               reg.get("채권원금"), reg.get("등기부_청구금액"), reg.get("유동화전문_청구금액"),
               reg.get("기준일(입찰기일+60일)", ""), reg.get("이자 연체일수"), reg.get("예상연체이자"),
               reg.get("채권행사권리금액")]

    addrs = parcels if len(parcels) >= 2 else [parcels[0] if parcels else base_addr]
    out = []
    for addr in addrs:
        vals = dict(values)
        vals["필지별 주소"] = addr
        row = [vals.get(h, "") for h in tmpl] + extras + [ac_summary or ""] + regvals
        out.append(["" if v is None else v for v in row])
    return out


# ------------------------------------------------------------------ 메인
def run(stats):
    t0 = time.monotonic()
    sh = dc.get_google_spreadsheet()
    stats["sh"] = sh
    if sh is None:
        raise RuntimeError("구글 스프레드시트에 연결하지 못했습니다(GOOGLE_SHEET_ID / 서비스 계정 키 확인).")

    rows = a1.collect_npl_rows()
    stats["옥션원_수집건수"] = len(rows)
    if not rows:
        raise RuntimeError("옥션원 NPL 수집 결과가 0건입니다(로그인/사이트 구조 확인).")

    index, n_idx = build_index(sh)
    stats["두인색인_건수"] = n_idx

    matched, unmatched = [], []
    for r in rows:
        cand, score = matching.match_one(r, index)
        (matched if cand else unmatched).append((r, cand, score))
    stats["매칭"], stats["미매칭"] = len(matched), len(unmatched)
    log(f"매칭 {len(matched)} / 미매칭 {len(unmatched)} / 옥션원 {len(rows)}")
    if unmatched:
        sample = [f"{r['사건번호']}({r['물번']}) {r['감정가']}원 {r['매각기일']}" for r, _, _ in unmatched[:8]]
        stats["notes"].append("미매칭 예: " + "; ".join(sample))

    targets = matched[:MAX_DETAIL] if MAX_DETAIL else matched
    details = {}
    if targets:
        driver = dc.get_driver()
        try:
            driver.get(dc.BASE_URL)
            dc.wait_for_list(driver)
            time.sleep(1)
            if not dc.login(driver, dc.LOGIN_ID, dc.LOGIN_PW):
                raise RuntimeError("두인 로그인 실패 - 상세 추출 불가")
            time.sleep(1)
            session = dc.build_requests_session(driver)
            for n, (r, cand, _) in enumerate(targets, 1):
                if DEADLINE_MIN and (time.monotonic() - t0) / 60 >= DEADLINE_MIN:
                    stats["마감도달"] = "Y"
                    log("마감 시각 도달 - 남은 물건은 상세 없이 저장합니다.")
                    break
                tid = cand["tid"]
                log(f"[상세 {n}/{len(targets)}] {r['사건번호']} tid={tid}")
                try:
                    parcels, notes, ac, jibun = dc.fetch_detail_info(
                        driver, session, tid, cand["chk"], cand["tot"], cand["base"].get("주소", ""))
                    reg = registry.fetch_registry_history_info(driver, tid, cand["chk"], cand["tot"])
                    details[tid] = (parcels, notes, ac, jibun, reg)
                    stats["상세성공"] += 1
                except Exception as e:
                    stats["상세실패"] += 1
                    log(f"  상세 추출 오류: {e}")
                    stats["notes"].append(f"상세오류 {r['사건번호']}: {str(e)[:80]}")
        finally:
            try:
                driver.quit()
            except Exception:
                pass

    out = []
    for r, cand, score in matched:
        d = details.get(cand["tid"])
        if d:
            out += make_rows(r, cand, score, "매칭", d[0], d[1], d[2], d[3], d[4])
        else:
            out += make_rows(r, cand, score, "매칭(상세없음)", [], "", "", "", None)
    for r, _, score in unmatched:
        out += make_rows(r, None, score, "미매칭", [], "", "", "", None)

    tab = f"{TAB_PREFIX}{this_saturday(kst_now().date()):%Y%m%d}{DETAIL_SUFFIX}"
    stats["대상탭"], stats["출력행수"] = tab, len(out)
    write_detail_tab(sh, tab, [header_row()] + out)
    cleanup_old_tabs(sh)


def main():
    t0 = time.monotonic()
    stats = {"상세성공": 0, "상세실패": 0, "마감도달": "", "notes": [], "sh": None}
    err = None
    try:
        run(stats)
    except BaseException as e:      # 실패해도 로그는 반드시 남긴다
        err = e
        traceback.print_exc()
        stats["notes"].append(f"오류: {type(e).__name__}: {str(e)[:200]}")
    elapsed = (time.monotonic() - t0) / 60
    if err is not None:
        result = "실패"
    elif stats["상세실패"] or stats["마감도달"]:
        result = "부분성공"
    else:
        result = "성공"
    entry = {
        "실행시각(KST)": kst_now().strftime("%Y-%m-%d %H:%M:%S"),
        "트리거": os.environ.get("TRIGGER_TYPE", "manual"),
        "대상탭": stats.get("대상탭", ""), "결과": result,
        "옥션원_수집건수": stats.get("옥션원_수집건수", ""), "두인색인_건수": stats.get("두인색인_건수", ""),
        "매칭": stats.get("매칭", ""), "미매칭": stats.get("미매칭", ""),
        "상세성공": stats["상세성공"], "상세실패": stats["상세실패"],
        "출력행수": stats.get("출력행수", ""), "소요시간(분)": round(elapsed, 1),
        "마감도달": stats["마감도달"], "비고": " | ".join(n for n in stats["notes"] if n)[:1500],
    }
    sh = stats["sh"]
    if sh is None:
        try:
            sh = dc.get_google_spreadsheet()
        except Exception:
            sh = None
    append_log(sh, entry)
    return 1 if err is not None else 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass
    sys.exit(main())
