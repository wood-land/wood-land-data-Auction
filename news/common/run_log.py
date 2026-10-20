"""
common/run_log.py - 신문기사 수집 결과(통계)를 구글시트 탭에 이어 붙인다. 기사 본문·주소는 보내지 않는다.

탭(gosi 와 같은 시트의 새 탭):
  news_실행기록 : 단위(지역/묶음) 1회 실행에 1줄 - 언제, 얼마나 걸렸나, 성공/실패
  news_신문사별 : 신문사 1곳에 1줄 - 몇 건 저장했나, 검색 결과가 0건이거나 오류가 난 곳이 어디인가

환경변수: GOOGLE_SHEET_ID, GOOGLE_CREDENTIALS_EDITER(서비스 계정 JSON). 없으면 건너뛴다. 실패해도 수집은 멈추지 않는다.
실패/시간초과로 파이썬이 끝까지 못 돌았을 때는 워크플로가  python common/run_log.py --status 실패 --unit 단위  로 1줄만 남긴다.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

SHEETS = {
    "news_실행기록": ["기록시각(KST)", "단위", "지역", "수집기간(일)", "신문사수", "저장건수", "기사열람", "오류수",
                  "소요(분)", "상태", "실행링크"],
    "news_신문사별": ["기록시각(KST)", "단위", "신문사", "키워드수", "결과있는키워드", "페이지", "기사열람", "저장",
                  "블랙리스트제외", "보상무관제외", "오류", "소요(초)", "판정", "마지막오류"],
}


def _now():
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M")


def _run_link():
    rid, repo = os.environ.get("GITHUB_RUN_ID"), os.environ.get("GITHUB_REPOSITORY")
    return f"https://github.com/{repo}/actions/runs/{rid}" if rid and repo else ""


def verdict(s):
    """신문사 1곳의 판정: 검색 결과가 하나도 없으면 설정 문제, 오류만 있고 저장이 없으면 오류."""
    if s.keywords_total and s.keywords_with_results == 0:
        return "결과없음(점검필요)"
    if s.errors and s.errors >= max(3, s.keywords_total // 2):
        return "오류다수"
    if s.errors:
        return "일부오류"
    return "정상"


def build_rows(unit, region, days, stats, minutes, status):
    now = _now()
    sites = list(stats.values())
    run_row = [now, unit, region, days, len(sites), sum(s.saved for s in sites), sum(s.opened for s in sites),
               sum(s.errors for s in sites), round(minutes, 1), status, _run_link()]
    site_rows = [[now, unit, s.name, s.keywords_total, s.keywords_with_results, s.pages, s.opened, s.saved,
                  s.blacklist_skipped, s.irrelevant_skipped, s.errors, round(getattr(s, "seconds", 0.0), 1),
                  verdict(s), (s.failed or "")[:150]] for s in sites]
    return {"news_실행기록": [run_row], "news_신문사별": site_rows}


def _session():
    sheet_id = os.environ.get("GOOGLE_SHEET_ID", "").strip()
    if not sheet_id:
        return None, "GOOGLE_SHEET_ID 없음"
    raw = os.environ.get("GOOGLE_CREDENTIALS_EDITER", "").strip()
    if not raw:
        return None, "서비스 계정 키 없음"
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account
    creds = service_account.Credentials.from_service_account_info(
        json.loads(raw), scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return AuthorizedSession(creds), sheet_id


def send(rows_by_tab):
    """탭이 없으면 만들고 헤더를 쓴 뒤 행을 이어 붙인다. 실패해도 예외를 던지지 않는다."""
    try:
        sess, sheet_id = _session()
        if sess is None:
            print(f"[수집로그] 구글시트 건너뜀: {sheet_id}")
            return
        base = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
        meta = sess.get(base, params={"fields": "sheets.properties.title"}, timeout=30)
        meta.raise_for_status()
        have = {x["properties"]["title"] for x in meta.json().get("sheets", [])}
        sent = {}
        for tab, rows in rows_by_tab.items():
            if not rows:
                continue
            if tab not in have:
                r = sess.post(f"{base}:batchUpdate", timeout=30, json={"requests": [
                    {"addSheet": {"properties": {"title": tab, "gridProperties": {"frozenRowCount": 1}}}}]})
                r.raise_for_status()
                r = sess.put(f"{base}/values/{tab}!A1", params={"valueInputOption": "RAW"}, timeout=30,
                             json={"values": [SHEETS[tab]]})
                r.raise_for_status()
            for i in range(0, len(rows), 500):
                r = sess.post(f"{base}/values/{tab}!A1:append", timeout=60,
                              params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
                              json={"values": [[("" if v is None else v) for v in row] for row in rows[i:i + 500]]})
                r.raise_for_status()
            sent[tab] = len(rows)
        print(f"[수집로그] 구글시트 저장 {sent}")
    except Exception as e:  # 시트 때문에 수집이 멈추면 안 된다
        print(f"[경고] 구글시트 로그 저장 실패: {type(e).__name__}: {str(e)[:200]}")


def log_run(unit, region, days, stats, minutes, status="성공"):
    send(build_rows(unit, region, days, stats, minutes, status))


def main():
    ap = argparse.ArgumentParser(description="실패/시간초과 때 실행기록 1줄만 남긴다")
    ap.add_argument("--unit", required=True)
    ap.add_argument("--status", required=True)
    a = ap.parse_args()
    region = a.unit.split(":")[0]
    send({"news_실행기록": [[_now(), a.unit, region, "", "", "", "", "", "", a.status, _run_link()]]})


if __name__ == "__main__":
    sys.exit(main())
