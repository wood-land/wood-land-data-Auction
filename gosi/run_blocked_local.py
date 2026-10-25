"""
run_blocked_local.py - PC 를 켤 때마다 실행('★PC수집_전체_더블클릭_v….bat'(저장소 최상위, 환경영향평가와 함께) 더블클릭 또는 이 파일만 실행): 국내 IP 에서만 읽히는 게시판을 수집해 올린다.

GitHub 호스티드 러너(미국 IP)에서는 core/blocked_sites.py 의 게시판이 막혀서(history/15 7절), 그곳만 이 PC 에서 수집한다.
  1) git pull(코드·DB 두 저장소)  2) 로그 분석으로 새로 막힌 지자체 등록  3) 막힌 게시판만 수집(run_scheduled.py --blocked only)
  4) 결과 DB 는 DB 저장소(data/)에, 자동 등록 목록은 코드 저장소에 커밋·푸시

저장소가 둘이다(2026-10-18 분리): 코드는 공개 저장소(이 폴더), 수집 결과 DB 는 비공개 저장소이며 옆 폴더(../wood-land-data-db, 없으면 이 폴더의 data/)에 따로 받아 둔다.
  git clone https://github.com/wood-land/wood-land-data-db.git ../wood-land-data-db   (또는 환경변수 WOOD_LAND_DB_DIR 로 위치 지정)
결과는 지역 DB(data/gosi/{지역}.sqlite)가 아니라 별도 파일 data/gosi/국내IP_{지역}.sqlite 에 저장한다. Actions 가 같은 지역 DB 를 계속
커밋하므로, 같은 파일을 둘이 고치면 sqlite(이진 파일)는 합칠 수 없어 충돌한다. 파일이 다르면 충돌이 없다.
이 스크립트가 올리는 것은 data/gosi/국내IP_*.sqlite(DB 저장소)와 자동 등록 목록(core/blocked_sites_auto.json, 코드 저장소)뿐이다(git add -A 를 쓰지 않는다).
수집 전에 detect_blocked.py 로 로그를 분석해, Actions 가 반복해서 막히고 이 PC 에서는 되는 지자체를 자동 등록한다(키가 없으면 건너뜀).

  python run_blocked_local.py            # 받기 -> 수집 -> 올리기
  python run_blocked_local.py --no-git   # 시험용: 수집만 하고 git 은 건드리지 않는다
  python run_blocked_local.py --reread   # 이미 처리한 글도 7일 창 안이면 다시 읽는다(AI 오류 등으로 빈 결과가 남았을 때)

PC 가 두 대(PCwj, PCyw)이고 서로 다른 시간에 도는 것이 전제다(동시에 돌지 않는다). 그래서 PC 별 DB 파일 분리는 필요 없고, 같은 국내IP_*.sqlite 를
순서대로 받고(pull) 수집하고 올린다(push). 시작 전 점검(preflight)이 '못 올린 커밋'·'충돌로 멈춘 상태'를 걸러낸다. PC 이름은
500_local/pc_name.txt(한 줄, git 제외)나 환경변수 GOSI_PC_NAME 이며, 없으면 처음 한 번 물어본다.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from core import blocked_sites as B  # noqa: E402
from core import local_dir  # noqa: E402
from core import pc_runlog  # noqa: E402
from core.paths import DB_REPO_DIR, DATA_DIR  # noqa: E402

DATA = str(DB_REPO_DIR)  # 비공개 DB 저장소(별도 git 저장소, 여러 크롤러 공용; 위치는 core/paths.py). 이 크롤러의 DB 는 그 안의 gosi/
DB_SUBDIR = "gosi"

VERSION = "v20261025"  # 배치 파일 이름의 버전과 맞춘다(이 스크립트를 고치면 둘 다 새 날짜로)
REGION_TIMEOUT = 30 * 60  # 지역 하나가 이 시간(초)을 넘기면 중단하고 다음으로 넘어간다(한 게시판이 오래 걸려도 전체가 멈추지 않게)
RUNS_FILE = Path(DATA) / DB_SUBDIR / "pc_runs.jsonl"  # 실행 기록(DB 저장소, 모든 PC 가 공유)
DB_REPO_URL = "https://github.com/wood-land/wood-land-data-db.git"


def run(args, cwd=HERE):
    print("\n$ " + " ".join(args), flush=True)
    return subprocess.run(args, cwd=cwd).returncode


def has_changes(cwd, paths):
    return subprocess.run(["git", "diff", "--cached", "--quiet", "--"] + paths, cwd=cwd).returncode != 0


def commit_push(cwd, paths, message, label):
    """cwd 저장소에서 paths 만 커밋·푸시한다. 성공(또는 올릴 것 없음) True."""
    run(["git", "add", "--"] + paths, cwd)
    if not has_changes(cwd, paths):
        print(f"[{label}] 변경된 결과가 없어 올릴 것이 없습니다.")
        return True
    run(["git", "commit", "-m", message, "--"] + paths, cwd)
    if run(["git", "push"], cwd) != 0:  # 그 사이 다른 커밋이 올라온 경우: 받아서 다시 올린다(파일이 달라 충돌 없음)
        if run(["git", "pull", "--rebase", "--autostash"], cwd) == 0 and run(["git", "push"], cwd) == 0:
            print(f"\n[{label}] 올리기 완료(재시도).")
            return True
        print(f"\n[주의] [{label}] 올리기에 실패했습니다. 결과는 이 PC 에만 커밋돼 있습니다 - 다른 PC 가 돌기 전에 다시 실행해(시작할 때 먼저 올립니다) 올려 두세요.")
        return False
    print(f"\n[{label}] 올리기 완료.")
    return True


def _git_out(args, cwd):
    p = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "").strip()


def git_problems(cwd, git=_git_out, exists=os.path.exists):
    """cwd 저장소가 '다음 수집을 시작해도 되는 상태'인지 확인한다. -> (막힌 이유 리스트, 아직 못 올린 커밋 수).
    PC 가 두 대(집·회사)이고 서로 다른 시간에 도는 것이 전제라, 위험은 '한 PC 의 push 실패로 결과가 그 PC 에만 남은 채 다른 PC 가 옛 DB 로
    이어서 수집하는 것'과 'pull 중 충돌이 난 채로 남은 상태' 뿐이다. 둘 다 시작 전에 걸러낸다."""
    stuck = []
    for name in ("rebase-merge", "rebase-apply", "MERGE_HEAD"):
        rc, path = git(["rev-parse", "--git-path", name], cwd)
        if rc == 0 and path and exists(path if os.path.isabs(path) else os.path.join(cwd, path)):
            stuck.append(f"git 이 '{name}' 상태로 멈춰 있습니다(이전 pull/합치기가 끝나지 않음)")
    rc, out = git(["diff", "--name-only", "--diff-filter=U"], cwd)
    if rc == 0 and out:
        stuck.append("충돌이 풀리지 않은 파일이 있습니다: " + ", ".join(out.splitlines()[:5]))
    rc, out = git(["rev-list", "--count", "@{u}..HEAD"], cwd)
    unpushed = int(out) if rc == 0 and out.isdigit() else 0
    return stuck, unpushed


def preflight(use_git, git=_git_out, push=None):
    """수집을 시작하기 전 점검. 문제가 있으면 안내를 출력하고 False(수집하지 않음). 못 올린 커밋은 먼저 올려 본다."""
    if not use_git:
        return True
    push = push or (lambda cwd: run(["git", "push"], cwd) == 0)
    for label, cwd in (("코드 저장소", HERE), ("DB 저장소", DATA)):
        stuck, unpushed = git_problems(cwd, git)
        if stuck:
            print(f"\n[중단] {label}({cwd}) 상태가 이상합니다. 수집하지 않고 끝냅니다:")
            for s in stuck:
                print("  - " + s)
            print("  해결: 그 폴더에서 `git status` 를 보고 충돌을 푼 뒤(또는 `git rebase --abort`) 다시 실행하세요.")
            return False
        if unpushed:
            print(f"\n[알림] {label}에 아직 올리지 못한 커밋 {unpushed}개가 있습니다(이전 실행의 push 실패). 먼저 올립니다.")
            if not push(cwd):
                print(f"[중단] 올리지 못했습니다. 그대로 수집하면 다른 PC 와 DB 가 갈라집니다. 네트워크·권한을 확인하고 다시 실행하세요.")
                return False
    return True


def ensure_pc_name(ask=input, interactive=None):
    """이 PC 이름(PCwj / PCyw 등)을 돌려준다. 없으면 콘솔에서 한 번 물어 500_local/pc_name.txt 에 저장한다. 끝내 못 정하면 ''."""
    name = local_dir.pc_name()
    if name:
        return name
    if interactive is None:
        interactive = bool(sys.stdin) and sys.stdin.isatty()
    if not interactive:
        print("\n[오류] 이 PC 의 이름을 모릅니다. 환경변수 GOSI_PC_NAME 을 넣거나 500_local/pc_name.txt 에 한 줄로 적으세요(예: PCwj).")
        return ""
    ans = ask("\n이 PC 의 이름을 입력하세요 (영문·숫자·한글 2~20자, 예: PCwj 또는 PCyw): ").strip()
    if local_dir.save_pc_name(ans):
        print(f"저장했습니다: 500_local/pc_name.txt = {ans}  (이 PC 에서는 다음부터 묻지 않습니다)")
        return ans
    print("[오류] 이름 형식이 맞지 않거나 500_local 폴더를 찾지 못해 저장하지 못했습니다.")
    return ""


def _main(use_git, rec, reread=False):
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    print(f"===== 막힌 지자체 PC 수집 {VERSION} =====")
    pc = ensure_pc_name()
    if not pc:
        rec["result"] = "stopped: no pc name"
        return 2
    rec["pc"] = pc
    print(f"이 PC: {pc}  (수집 로그 시트 탭 이름 앞에 '{pc}' 가 붙습니다)")
    for old in pc_runlog.recent(RUNS_FILE, 3):
        print("  지난 기록: " + pc_runlog.summary(old))
    from core.pnu import load_key
    rec["stage"] = "check"
    if not load_key():
        rec["result"] = "stopped: no kakao key"
        print("\n[오류] 카카오 REST 키를 찾지 못했습니다. 주소를 PNU 로 바꿀 수 없어 수집을 시작하지 않습니다.\n"
              "  - 환경변수 KAKAO_REST_API_KEY 에 키를 넣거나,\n"
              "  - 500_local 아래 이름에 'kakao'(또는 '카카오')가 들어간 폴더에 키가 든 파일(.txt)을 두세요(git 에는 올리지 않습니다).")
        return 2
    if use_git and not os.path.isdir(os.path.join(DATA, ".git")):
        print("\n[오류] data/ 폴더가 비공개 DB 저장소가 아닙니다. 아래 명령으로 받아 두세요(한 번만):\n"
              f"  git clone {DB_REPO_URL} \"{DATA}\"")
        return 2
    if not preflight(use_git):
        rec["result"] = "stopped: preflight (conflict or unpushed commits)"
        return 1
    if use_git:
        print("[1/4] 최신 코드·DB 받기")
        rec["stage"] = "pull"
        if run(["git", "pull", "--rebase", "--autostash"]) != 0 or run(["git", "pull", "--rebase", "--autostash"], DATA) != 0:
            print("\n[중단] git pull 에 실패했습니다. 위 메시지를 확인하세요(충돌이나 네트워크 문제). 아무것도 올리지 않았습니다.")
            rec["result"] = "stopped: git pull failed"
            return 1
        rec["heads"] = {"code": _git_out(["rev-parse", "--short", "HEAD"], HERE)[1],
                        "db": _git_out(["rev-parse", "--short", "HEAD"], DATA)[1]}

    rec["stage"] = "detect"
    print("\n[2/4] 수집 로그(구글시트)에서 새로 막힌 지자체 찾기")
    try:
        import detect_blocked
        detect_blocked.run(apply=True, confirm=detect_blocked.ask_console)  # 후보는 물어보고 승인(y)해야 등록한다
    except Exception as e:  # 키가 없거나 시트를 못 읽어도 수집은 계속한다
        print(f"(건너뜀) {type(e).__name__}: {str(e)[:120]}")
        rec["notes"].append(f"detect_blocked skipped: {type(e).__name__}")
    blocked = B.all_blocked()
    print("대상: " + " / ".join(f"{r}({', '.join(c)})" for r, c in blocked.items()))

    print("\n[3/4] 국내 IP 에서만 읽히는 게시판 수집")
    rec["stage"] = "collect"
    rec["targets"] = {r: list(c) for r, c in blocked.items()}
    db_files = []
    for region in blocked:
        t0 = time.time()
        status = "ok"
        name = f"국내IP_{region}.sqlite"
        try:
            rc = subprocess.run([sys.executable, "-u", "run_scheduled.py", "--region", region, "--blocked", "only",
                                 "--db", str(DATA_DIR / name), "--log-prefix", pc] + (["--reread"] if reread else []),
                                cwd=HERE, env=env, timeout=REGION_TIMEOUT).returncode
            print(f"  -> {region}: {'완료' if rc == 0 else f'오류 종료(코드 {rc})'}")
            status = "ok" if rc == 0 else f"exit {rc}"
        except subprocess.TimeoutExpired:
            print(f"  -> {region}: {REGION_TIMEOUT // 60}분을 넘겨 중단했습니다(그때까지 저장된 결과만 남습니다).")
            status = "timeout"
        rec["regions"][region] = {"status": status, "minutes": round((time.time() - t0) / 60, 1)}
        db_files.append(f"{DB_SUBDIR}/{name}")

    code_files = [os.path.relpath(str(f), HERE) for f in (B.AUTO_FILE, B.REJECTED_FILE) if f.exists()]
    # 등록 목록이 바뀌었으면 함께 올려야 Actions 가 그 지자체를 건너뛴다(거절 기록도 공유)
    if not use_git:
        rec["result"] = "collected (no-git)"
        print("\n--no-git: 결과 파일만 만들고 git 에는 올리지 않았습니다: " + ", ".join(db_files + code_files))
        return 0

    print("\n[4/4] 결과 올리기")
    rec["stage"] = "push"
    rec["result"] = "collected"  # 이 줄이 DB 저장소에 올라간다. push 성공 여부는 이 PC 의 로컬 기록에 남는다
    pc_runlog.append(RUNS_FILE, rec)
    db_files.append(f"{DB_SUBDIR}/{RUNS_FILE.name}")
    ok_db = commit_push(DATA, db_files, f"chore: 국내 IP 로컬 수집 결과 갱신 (막힌 게시판) [{pc}]", "DB 저장소")
    ok_code = commit_push(HERE, code_files, f"chore: 막힌 지자체 목록 갱신 (자동 등록/거절) [{pc}]", "코드 저장소") if code_files else True
    rec["result"] = "ok" if ok_db and ok_code else "push failed"
    return 0 if ok_db and ok_code else 1


def main(use_git=True, reread=False):
    rec = pc_runlog.new_record(local_dir.pc_name(), VERSION)
    try:
        return _main(use_git, rec, reread)
    except BaseException as e:  # 어디서 죽었는지 남긴다
        rec["result"] = f"crashed: {type(e).__name__}: {str(e)[:150]}"
        raise
    finally:
        try:
            base = local_dir.local_dir()
            if base:
                pc_runlog.append(Path(base) / "pc_runs_local.jsonl", rec)
        except OSError:
            pass


if __name__ == "__main__":
    code = main(use_git="--no-git" not in sys.argv, reread="--reread" in sys.argv)
    print("\n끝났습니다. 창을 닫아도 됩니다.")
    sys.exit(code)
