"""
core/pc_runlog.py - PC 수집 실행 기록(누가·언제·어디까지·결과). 문제가 생겼을 때 어느 PC 가 무엇을 했는지 이 기록으로 추적한다.

한 번 실행에 한 줄(JSON)을 덧붙인다(.jsonl, 텍스트라 git 에서 읽기 쉽다).
  - 수집까지 간 실행: DB 저장소의 gosi/pc_runs.jsonl 에 적어 결과 DB 와 함께 올린다 -> 다른 PC 에서도 pull 하면 보인다.
  - 시작 전에 멈춘 실행(점검 실패·pull 실패 등): 저장소를 건드리면 다음 pull 과 충돌할 수 있어 이 PC 의 500_local/pc_runs_local.jsonl 에만 남긴다.
"""
import json
import socket
import sys
from datetime import datetime


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def new_record(pc, version):
    return {"pc": pc, "host": socket.gethostname(), "version": version, "python": sys.version.split()[0],
            "started": now(), "stage": "start", "result": "running", "regions": {}, "notes": []}


def append(path, rec):
    rec = dict(rec, ended=now())
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def recent(path, n=3):
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines[-n:]:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def summary(rec):
    regions = rec.get("regions") or {}
    bad = [r for r, v in regions.items() if v.get("status") != "ok"]
    tail = f", 문제 지역: {', '.join(bad)}" if bad else ""
    return f"{rec.get('pc')} {str(rec.get('started', ''))[:16].replace('T', ' ')} -> {rec.get('result')} (단계: {rec.get('stage')}{tail})"
