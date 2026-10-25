"""
detect_blocked.py - 수집 로그(구글시트)에서 GitHub Actions 가 반복해서 접속하지 못하는 지자체를 찾아, 이 PC(국내 IP)에서 되면
'막힌 지자체' 후보로 알려주고, 사용자가 승인하면 등록한다(core/blocked_sites_auto.json). 등록된 곳은 Actions 가 건너뛰고(--blocked skip) PC 수집 스크립트가 맡는다.

  python detect_blocked.py            # 후보만 보여준다(등록 안 함)
  python detect_blocked.py --apply    # PC 에서 접속되는 후보를 보여주고, 승인(y)하면 등록(★PC수집…bat 이 실행 때마다 이렇게 부른다)

판단 규칙(일시적인 실패를 막힌 곳으로 잘못 등록하지 않도록 보수적으로):
  1) 최근 WINDOW_DAYS 일 로그에서 연결 계열 오류(시간초과·연결 끊김·SSL·403/404/429/5xx)가 **서로 다른 날 MIN_FAIL_DAYS 번 이상**
  2) 같은 기간에 그 지자체를 정상으로 읽은 기록(게시판상태 '정상…', 문서처리의 다운로드 성공 행)이 **하나도 없음**
  3) **이 PC 에서 같은 게시판을 직접 열어 보니 됨** (PC 에서도 안 되면 사이트 문제라서 등록하지 않고 '점검 필요'로만 알린다)
이미 core/blocked_sites.py 의 수동 목록이나 자동 목록에 있는 곳은 건너뛴다.

시트를 읽으려면 서비스 계정 키(500_local/100. Google_credentials/google_credentials_편집자.json, git 제외)와 `pip install gspread` 가 필요하다.
키가 없는 PC 에서는 이 단계만 건너뛰고 수집은 그대로 된다.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
ROOT = Path(HERE).parent

from core.local_dir import google_key_file, sheet_id as local_sheet_id  # noqa: E402

KEY_FILE = google_key_file()  # 500_local/100. Google_credentials/ (저장소 밖). 시트 ID 는 환경변수 GOOGLE_SHEET_ID 또는 같은 폴더의 sheet_id.txt
WINDOW_DAYS = 14
MIN_FAIL_DAYS = 2
# 연결 계열 오류(사이트가 응답하지 않거나 끊거나 거부)
CONN_RE = re.compile(r"Timeout|timed out|ConnectionError|RemoteDisconnected|Max retries|SSLError|Connection aborted|"
                     r"HTTPError: (?:403|404|429|5\d\d)", re.I)
HOST_RE = re.compile(r"host='([^']+)'")


def _day(ts):
    try:
        return dt.datetime.strptime(str(ts)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def find_candidates(tabs, today=None, window=WINDOW_DAYS, min_days=MIN_FAIL_DAYS):
    """tabs: {탭 이름: [행 dict, ...]} (시트의 '{지역}_게시판상태', '{지역}_문서처리' 탭).
    반환: {(지역, 지자체): {"kinds": set, "days": set(날짜), "example": 오류 예, "hosts": set}} — 규칙 1)·2) 를 통과한 곳."""
    today = today or dt.date.today()
    cutoff = today - dt.timedelta(days=window)
    fail = defaultdict(lambda: {"kinds": set(), "days": set(), "example": "", "hosts": set()})
    ok = set()
    for tab, rows in tabs.items():
        region, _, sheet = tab.partition("_")
        if region.startswith("PC"):  # 이 PC 의 수집 로그(탭 이름 'PC…')는 Actions 가 막혔는지와 무관하다
            continue
        if sheet not in ("게시판상태", "문서처리"):
            continue
        for r in rows:
            day = _day(r.get("시각"))
            if day is None or day < cutoff:
                continue
            key = (region, (r.get("지자체") or "").strip())
            if not key[1]:
                continue
            if sheet == "게시판상태":
                status = r.get("상태", "")
                err = f"{r.get('오류', '')} {r.get('상세', '')}"
                if status.startswith("오류") and CONN_RE.search(err):
                    f = fail[key]
                    f["days"].add(day)
                    f["kinds"].add(r.get("종류") or "고시공고")
                    f["example"] = f["example"] or err.strip()[:80]
                    f["hosts"].update(HOST_RE.findall(err))
                elif status.startswith(("정상", "최근 게시물 없음")):
                    ok.add(key)
            else:  # 문서처리: 첨부 1개 = 1행
                code = r.get("원인코드", "")
                if code == "DL_FAIL":
                    err = r.get("상세", "")
                    if CONN_RE.search(err):
                        f = fail[key]
                        f["days"].add(day)
                        f["kinds"].add("첨부")
                        f["example"] = f["example"] or err.strip()[:80]
                        f["hosts"].update(HOST_RE.findall(err))
                else:
                    ok.add(key)  # 이 지자체의 문서를 읽은 적이 있다
    return {k: v for k, v in fail.items() if len(v["days"]) >= min_days and k not in ok}


def pc_can_read(region, city, info, log=print):
    """이 PC 에서 그 지자체의 실패했던 게시판을 직접 열어 본다. 하나라도 열리면 True(= 국내 IP 에서는 된다)."""
    import importlib

    import requests

    results = []
    kinds = info["kinds"]
    if "고시공고" in kinds:
        from run_gosigongo import discover_provinces
        from run_scheduled import REGION_PROVINCES

        P = discover_provinces()
        found = None
        for prov in REGION_PROVINCES.get(region, [region]):
            if prov in P:
                found = next((c for c in P[prov].CITIES if c.city == city), None) or found
        if found is not None:
            adapter = importlib.import_module(f"cms_adapters.{found.adapter}")
            s = requests.Session()
            if hasattr(adapter, "prepare_session"):
                adapter.prepare_session(s, found)
            try:
                adapter.fetch_list_page(s, found.base_url, found.boards[0], 1)
                results.append(("고시공고 목록", True, ""))
            except Exception as e:
                results.append(("고시공고 목록", False, f"{type(e).__name__}: {str(e)[:60]}"))
    gaz = [k for k in kinds if k not in ("고시공고", "첨부")]
    if gaz:
        import run_gazette as G
        from cms_adapters import gazette_generic as GG

        for b in G.load_boards(os.path.join(HERE, "output", "시군구_공보게시판_목록_new.xlsx")):
            if b["module"] == region and b["city"] == city:
                try:
                    GG.fetch_list_page(G.new_session(), b["url"], {"name": b["kind"]}, 1)
                    results.append((f"{b['kind']} 목록", True, ""))
                except Exception as e:
                    results.append((f"{b['kind']} 목록", False, f"{type(e).__name__}: {str(e)[:60]}"))
    if "첨부" in kinds:  # 첨부 다운로드 서버: 오류에 찍힌 호스트에 연결이 되는지만 본다(응답 코드는 무관)
        for host in sorted(info["hosts"]) or []:
            try:
                requests.get(f"https://{host}/", timeout=15, verify=False, headers={"User-Agent": "Mozilla/5.0"})
                results.append((f"첨부 서버 {host}", True, ""))
            except Exception as e:
                results.append((f"첨부 서버 {host}", False, f"{type(e).__name__}"))
    for name, good, why in results:
        log(f"      PC 시험 - {name}: {'열림' if good else '실패 ' + why}")
    return any(good for _, good, _ in results), bool(results)


def load_tabs(sheet_id=None):
    """시트의 '*_게시판상태', '*_문서처리' 탭을 {탭: [행 dict]} 로 읽는다. 못 읽으면 (None, 이유)."""
    try:
        import gspread
    except ImportError:
        return None, "gspread 가 없습니다(pip install gspread)"
    raw = os.environ.get("GOOGLE_CREDENTIALS_EDITER") or os.environ.get("GOOGLE_SA_KEY_JSON_ADMIN")
    try:
        if raw:
            gc = gspread.service_account_from_dict(json.loads(raw))
        elif KEY_FILE.exists():
            gc = gspread.service_account(filename=str(KEY_FILE))
        else:
            return None, f"서비스 계정 키가 없습니다({KEY_FILE.name})"
        sid = sheet_id or local_sheet_id()
        if not sid:
            return None, "시트 ID 가 없습니다(환경변수 GOOGLE_SHEET_ID 또는 500_local/100. Google_credentials/sheet_id.txt)"
        sh = gc.open_by_key(sid)
        tabs = {}
        for ws in sh.worksheets():
            if ws.title.endswith(("_게시판상태", "_문서처리")):
                values = ws.get_all_values()
                if values:
                    head = values[0]
                    tabs[ws.title] = [dict(zip(head, row)) for row in values[1:]]
        return tabs, ""
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:120]}"


def ask_console(prompt):
    """터미널에서 y/N 을 묻는다. 입력을 받을 수 없는 환경(자동 실행)이면 False — 승인 없이는 등록하지 않는다."""
    if not sys.stdin or not sys.stdin.isatty():
        return False
    try:
        return input(prompt).strip().lower() in ("y", "yes", "ㅛ", "예", "네")
    except EOFError:
        return False


def run(apply=False, confirm=None, log=print):
    """로그를 분석해 후보를 알려준다. apply=True 이고 PC 에서 접속되는 후보는 confirm(질문) 이 True 를 돌려줄 때만 등록한다
    (사용자 지시: 등록 전에 알림·승인). confirm 이 없으면 후보만 보여주고 등록하지 않는다.
    거절한 지자체는 7일 동안 다시 묻지 않는다. 반환: 새로 등록한 [(지역, 지자체)]."""
    from core import blocked_sites as B

    tabs, why = load_tabs()
    if tabs is None:
        log(f"[막힌 지자체 찾기] 건너뜀: {why}")
        return []
    already = {(r, c) for r, cs in B.all_blocked().items() for c in cs}
    cands = {k: v for k, v in find_candidates(tabs).items() if k not in already}
    for key in [k for k in cands if B.is_excluded_district(*k)]:
        del cands[key]  # 서울·부산·인천 자치구는 후보에서 영구 제외(묻지도 않는다)
    for key in [k for k in cands if B.is_metro_district(*k)]:
        del cands[key]  # 광역시 자치구는 후보에서 영구 제외(묻지도 않는다)
    if not cands:
        log(f"[막힌 지자체 찾기] 새 후보 없음(최근 {WINDOW_DAYS}일 로그, 서로 다른 {MIN_FAIL_DAYS}일 이상 실패 + 정상 기록 없음 기준)")
        return []
    added = []
    for (region, city), info in sorted(cands.items()):
        if B.recently_rejected(region, city):
            log(f"[막힌 지자체 후보] {region}/{city}: 최근 7일 안에 등록을 거절해서 건너뜁니다")
            continue
        days = ", ".join(sorted(d.strftime("%m-%d") for d in info["days"]))
        log(f"\n[막힌 지자체 후보] {region}/{city}: {'/'.join(sorted(info['kinds']))} 접속 오류 {len(info['days'])}일({days}) 예: {info['example']}")
        can, tried = pc_can_read(region, city, info, log)
        if not can:
            log(f"      -> {'PC 에서도 접속 실패' if tried else 'PC 에서 시험할 방법이 없음'}: 사이트 자체 문제일 수 있어 등록하지 않음(점검 필요)")
            continue
        if not apply or confirm is None:
            log(f"      -> PC 에서는 열림: 등록하려면 python detect_blocked.py --apply (또는 core/blocked_sites.py 에 \"{region}\": [\"{city}\"] 추가)")
            continue
        if confirm(f"      >>> {region}/{city} 를 '막힌 지자체'로 등록할까요? (등록하면 Actions 는 건너뛰고 이 PC 수집이 맡습니다) [y/N] "):
            B.register_auto(region, city, f"Actions 접속 오류 {len(info['days'])}일, PC 에서는 열림 - {info['example'][:50]}")
            added.append((region, city))
            log(f"      -> 등록했습니다: {region}/{city}")
        else:
            B.reject_auto(region, city)
            log("      -> 등록하지 않았습니다(7일 동안 다시 묻지 않습니다)")
    return added


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="수집 로그에서 Actions 가 반복해서 막히는 지자체를 찾는다")
    ap.add_argument("--apply", action="store_true", help="PC 에서 접속되는 후보를 물어보고 승인하면 core/blocked_sites_auto.json 에 등록")
    a = ap.parse_args()
    out = run(apply=a.apply, confirm=ask_console if a.apply else None)
    print(f"\n새로 등록: {out}" if a.apply else "\n(등록하지 않음)")
