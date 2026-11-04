"""news-crawl 의 '오늘 돌 단위' 고르기 — 날짜가 아니라 '지난번에 어디까지 돌았는지' 기준으로 순환한다.

예전에는 날짜(toordinal) % 개수 로 골랐다. GitHub 예약 실행이 UTC 자정 너머로 밀리면 하루가 통째로 건너뛰어졌다
(2026-11-01 강원). 지금은 직전 예약 실행들의 작업 결과(crawl (단위): success/failure/cancelled)를 읽어
  - 성공이면 다음 단위
  - 실패·취소면 같은 단위를 한 번 더 (연속 2번 실패하면 막히지 않게 다음 단위)
로 간다. 실행 기록을 못 읽으면(권한·네트워크) 예전 날짜 방식으로 돌아간다.

단위 표기: "지역" / "지역:이름"(run_crawl.PART_GROUPS 의 묶음) / "지역:N/M"(활성 신문사를 M개로 번갈아 나눈 N번째)

사용(워크플로의 plan 작업): python plan_units.py --event "$EVENT" --inputs "$INPUT_REGIONS" --run-id "$RUN_ID" >> "$GITHUB_OUTPUT"
"""
import argparse
import datetime
import json
import re
import subprocess
import sys
from typing import List, Optional, Sequence, Tuple

# 하루에 한 단위, 한 바퀴 9일. 경기·인천은 아직 정기 수집에 넣지 않았다(수동 실행으로만).
UNITS = [
    "강원",
    "충청:충남",
    "충청:충북",
    "전라:전북",
    "전라:광주전남",
    "경남:1/2",
    "경남:2/2",
    "경북:1/2",
    "경북:2/2",
]
MAX_ATTEMPTS = 2          # 같은 단위가 이 횟수 연속으로 실패하면 건너뛰고 다음으로 간다
HISTORY_RUNS = 12         # 최근 예약 실행을 몇 개까지 읽을지
DONE = ("success", "failure", "cancelled", "timed_out")

History = Sequence[Tuple[str, str]]       # 오래된 것 -> 최신, (단위, 작업 결과)


def next_unit(history: History, units: Sequence[str] = UNITS, max_attempts: int = MAX_ATTEMPTS) -> Optional[str]:
    """직전 결과로 다음에 돌 단위를 정한다. 판단할 기록이 없으면 None(호출한 쪽이 날짜 방식으로 대신한다)."""
    rows = [(u, c) for u, c in history if c in DONE]
    if not rows:
        return None
    last_unit, last_result = rows[-1]
    if last_unit not in units:
        return None
    i = units.index(last_unit)
    if last_result == "success":
        return units[(i + 1) % len(units)]
    fails = 0
    for u, c in reversed(rows):
        if u != last_unit or c == "success":
            break
        fails += 1
    return last_unit if fails < max_attempts else units[(i + 1) % len(units)]


def by_date(today: datetime.date, units: Sequence[str] = UNITS) -> str:
    return units[today.toordinal() % len(units)]


def _gh_json(args: List[str]):
    out = subprocess.run(["gh"] + args, capture_output=True, text=True, encoding="utf-8", timeout=60, check=True).stdout
    return json.loads(out or "null")


def fetch_history(workflow: str = "news.yml", exclude_run_id: str = "", runs: int = HISTORY_RUNS) -> List[Tuple[str, str]]:
    """최근 '예약' 실행들에서 (단위, 결과) 를 오래된 순으로 모은다. 손으로 돌린 실행은 순환에 영향을 주지 않도록 뺀다."""
    listing = _gh_json(["run", "list", "--workflow", workflow, "--event", "schedule", "--status", "completed",
                        "--limit", str(runs), "--json", "databaseId,createdAt"])
    history: List[Tuple[str, str]] = []
    for run in sorted(listing, key=lambda r: r["createdAt"]):
        if str(run["databaseId"]) == str(exclude_run_id):
            continue
        jobs = _gh_json(["run", "view", str(run["databaseId"]), "--json", "jobs"])["jobs"]
        for job in sorted(jobs, key=lambda j: j.get("startedAt") or ""):
            m = re.match(r"crawl \((.+)\)$", job.get("name", ""))
            if m and job.get("conclusion"):
                history.append((m.group(1), job["conclusion"]))
    return history


def pick(event: str, inputs: str, history: Optional[History], today: datetime.date) -> List[str]:
    wanted = [x for x in inputs.replace(" ", "").split(",") if x]
    if wanted:                               # 수동 실행 + 지정: 그대로 (예: 충청:충남,강원)
        return wanted
    if event == "workflow_dispatch":         # 수동 실행 + 비움: 전체
        return list(UNITS)
    unit = next_unit(history) if history is not None else None
    return [unit or by_date(today)]          # 예약: 지난번 다음 차례 (기록이 없으면 날짜 방식)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--event", default="schedule")
    ap.add_argument("--inputs", default="")
    ap.add_argument("--run-id", default="")
    args = ap.parse_args()
    history = None
    if args.event == "schedule" and not args.inputs:
        try:
            history = fetch_history(exclude_run_id=args.run_id)
            print(f"[plan] 최근 예약 실행 기록: {history[-5:]}", file=sys.stderr)
        except Exception as e:                # 기록을 못 읽어도 오늘 수집은 돌아야 한다
            print(f"[plan] 실행 기록을 읽지 못해 날짜 방식으로 고릅니다: {type(e).__name__}: {e}", file=sys.stderr)
    regions = pick(args.event, args.inputs, history, datetime.date.today())
    print("regions=" + json.dumps(regions, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
