"""
pc_common.py - 국내 IP PC 실행기(gosi/run_blocked_local.py, eiass/run_pc.py, run_pc_all.py)가 함께 쓰는 공통 부분.

  - PC 이름(PCwj / PCyw): 환경변수 GOSI_PC_NAME -> 500_local/pc_name.txt. 없으면 처음 한 번 물어 저장한다.
  - 시작 전 점검: 못 올린 커밋이 있으면 먼저 올리고, 충돌·rebase 중단 상태면 수집하지 않는다.
  - 실행 기록: 한 번 실행에 한 줄(JSON). 수집까지 간 실행은 DB 저장소의 파일에, 시작 전에 멈춘 실행은 이 PC 의 500_local 에만 남긴다.
PC 두 대가 서로 다른 시간에 도는 것이 전제다(동시에 돌지 않는다). gosi/core/local_dir.py·pc_runlog.py 와 같은 규칙이다
(gosi 와 eiass 는 각자 core 패키지를 가져서 한쪽 것을 다른 쪽에서 가져다 쓸 수 없어, 공통 부분을 이 파일 하나에 둔다).
"""
import json
import os
import re
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PC_NAME_RE = re.compile(r"^[A-Za-z0-9가-힣_-]{2,20}$")  # 시트 탭 이름·커밋 메시지에 그대로 쓰므로 공백·특수문자는 막는다


# ---- 500_local 위치와 PC 이름 ----
def local_dir():
    env = os.environ.get("GOSI_LOCAL_DIR", "").strip()
    if env and Path(env).is_dir():
        return Path(env)
    for pointer in (ROOT / "gosi" / ".local_dir", ROOT / "eiass" / ".local_dir"):
        try:
            target = Path(pointer.read_text(encoding="utf-8").strip()) if pointer.is_file() else None
        except OSError:
            target = None
        if target and target.is_dir():
            return target
    for parent in ROOT.parents:
        if (parent / "500_local").is_dir():
            return parent / "500_local"
    return None


def pc_name():
    name = os.environ.get("GOSI_PC_NAME", "").strip()
    if not name:
        base = local_dir()
        try:
            f = base / "pc_name.txt" if base else None
            name = f.read_text(encoding="utf-8").strip() if f and f.is_file() else ""
        except OSError:
            name = ""
    return name if PC_NAME_RE.match(name) else ""


def save_pc_name(name):
    base = local_dir()
    if not base or not PC_NAME_RE.match(name or ""):
        return False
    try:
        (base / "pc_name.txt").write_text(name + "\n", encoding="utf-8")
        return True
    except OSError:
        return False


def ensure_pc_name(ask=input, interactive=None):
    """이 PC 이름을 돌려준다. 없으면 콘솔에서 한 번 물어 저장한다. 끝내 못 정하면 ''."""
    name = pc_name()
    if name:
        return name
    if interactive is None:
        interactive = bool(sys.stdin) and sys.stdin.isatty()
    if not interactive:
        print("\n[오류] 이 PC 의 이름을 모릅니다. 환경변수 GOSI_PC_NAME 을 넣거나 500_local/pc_name.txt 에 한 줄로 적으세요(예: PCwj).")
        return ""
    ans = ask("\n이 PC 의 이름을 입력하세요 (영문·숫자·한글 2~20자, 예: PCwj 또는 PCyw): ").strip()
    if save_pc_name(ans):
        print(f"저장했습니다: 500_local/pc_name.txt = {ans}  (이 PC 에서는 다음부터 묻지 않습니다)")
        return ans
    print("[오류] 이름 형식이 맞지 않거나 500_local 폴더를 찾지 못해 저장하지 못했습니다.")
    return ""


# ---- 시작 전 점검 ----
def git_out(args, cwd):
    p = subprocess.run(["git"] + args, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "").strip()


def git_problems(cwd, git=git_out, exists=os.path.exists):
    """cwd 저장소가 '다음 수집을 시작해도 되는 상태'인지 확인한다. -> (막힌 이유 리스트, 아직 못 올린 커밋 수)."""
    stuck = []
    for name in ("rebase-merge", "rebase-apply", "MERGE_HEAD"):
        rc, path = git(["rev-parse", "--git-path", name], cwd)
        if rc == 0 and path and exists(path if os.path.isabs(path) else os.path.join(str(cwd), path)):
            stuck.append(f"git 이 '{name}' 상태로 멈춰 있습니다(이전 pull/합치기가 끝나지 않음)")
    rc, out = git(["diff", "--name-only", "--diff-filter=U"], cwd)
    if rc == 0 and out:
        stuck.append("충돌이 풀리지 않은 파일이 있습니다: " + ", ".join(out.splitlines()[:5]))
    rc, out = git(["rev-list", "--count", "@{u}..HEAD"], cwd)
    unpushed = int(out) if rc == 0 and out.isdigit() else 0
    return stuck, unpushed


# DB 저장소에서 PC 수집이 만드는 파일(이 경로의 변경만 있을 때 버리고 원격 최신으로 맞춰도 된다)
PC_OUTPUT_PREFIXES = ("gosi/국내IP_", "gosi/pc_runs.jsonl", "eiass/")


def recover_db_repo(cwd, git=git_out):
    """DB 저장소가 충돌·push 실패로 막혔을 때, 이 PC 의 수집 결과(PC_OUTPUT_PREFIXES)만 걸려 있으면 그것을 버리고 원격 최신으로 맞춘다.
    PC 결과는 7일 창에서 다시 수집하면 되는 파생 데이터이고, sqlite 는 이진 파일이라 합칠 수 없어 이 방법이 가장 안전하다
    (버린 글은 원격 DB 의 '처리한 글' 기록에 없으므로 이번 실행에서 다시 수집된다). 다른 변경이 섞여 있으면 손대지 않고 False."""
    git(["rebase", "--abort"], cwd)  # 해당 상태가 아니면 실패하지만 무시한다
    git(["merge", "--abort"], cwd)
    rc, _ = git(["fetch"], cwd)
    if rc != 0:
        return False
    rc, committed = git(["-c", "core.quotepath=false", "diff", "--name-only", "@{u}...HEAD"], cwd)
    rc2, dirty = git(["-c", "core.quotepath=false", "status", "--porcelain"], cwd)
    if rc != 0 or rc2 != 0:
        return False
    names = [n.strip().strip('"') for n in committed.splitlines() if n.strip()]
    names += [ln[3:].strip().strip('"') for ln in dirty.splitlines() if ln.strip()]
    if any(not n.startswith(PC_OUTPUT_PREFIXES) for n in names):
        return False
    return git(["reset", "--hard", "@{u}"], cwd)[0] == 0


def preflight(repos, git=git_out, push=None, recover=("DB 저장소",)):
    """repos: [(이름, 경로), ...]. 문제가 있으면 안내를 출력하고 False(수집하지 않음). 못 올린 커밋은 먼저 올려 본다.
    recover 에 든 저장소(DB 저장소)는 충돌·push 실패 시 이 PC 의 수집 결과만 버리고 원격 최신으로 맞춘 뒤 계속한다
    (다른 PC 가 먼저 올린 결과와 이 PC 의 올리지 못한 결과가 같은 sqlite 를 고쳐 부딪친 경우 등)."""
    push = push or (lambda cwd: subprocess.run(["git", "push"], cwd=str(cwd)).returncode == 0)

    def recovered(label, cwd, why):
        if label in recover and recover_db_repo(cwd, git):
            print(f"[복구] {label}: {why} -> 이 PC 의 올리지 못한 수집 결과를 버리고 원격 최신으로 맞췄습니다(그 글들은 이번에 다시 수집됩니다).")
            return True
        return False

    for label, cwd in repos:
        stuck, unpushed = git_problems(cwd, git)
        if stuck:
            if recovered(label, cwd, "pull/합치기가 끝나지 않았거나 충돌이 남아 있음"):
                continue
            print(f"\n[중단] {label}({cwd}) 상태가 이상합니다. 수집하지 않고 끝냅니다:")
            for s in stuck:
                print("  - " + s)
            print("  해결: 그 폴더에서 `git status` 를 보고 충돌을 푼 뒤(또는 `git rebase --abort`) 다시 실행하세요.")
            return False
        if unpushed:
            print(f"\n[알림] {label}에 아직 올리지 못한 커밋 {unpushed}개가 있습니다(이전 실행의 push 실패). 먼저 올립니다.")
            if not push(cwd):
                if recovered(label, cwd, "올리지 못한 커밋이 원격과 부딪침"):
                    continue
                print("[중단] 올리지 못했습니다. 그대로 수집하면 다른 PC 와 DB 가 갈라집니다. 네트워크·권한을 확인하고 다시 실행하세요.")
                return False
    return True


# ---- 실행 기록 ----
def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def new_record(pc, version, job):
    return {"job": job, "pc": pc, "host": socket.gethostname(), "version": version, "python": sys.version.split()[0],
            "started": now(), "stage": "start", "result": "running", "regions": {}, "notes": []}


def append_record(path, rec):
    rec = dict(rec, ended=now())
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def recent_records(path, n=3):
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
    return f"{rec.get('pc')} {str(rec.get('started', ''))[:16].replace('T', ' ')} -> {rec.get('result')} (단계: {rec.get('stage')})"


def local_record_path():
    base = local_dir()
    return Path(base) / "pc_runs_local.jsonl" if base else None
