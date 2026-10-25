"""
run_pc.py - 국내 IP PC 에서 실행('★PC수집_전체_더블클릭_v….bat' 더블클릭, 또는 이 파일만 실행).

GitHub Actions 러너(미국 IP)에서는 브이월드가 막혀(2026-10-25 확인) 선 도면(지형·지적 배경) 토지이용계획도를
연속지적도에 맞추지 못한다. 그런 사업은 review/ 에 '국내 IP PC 필요'로 남는데, 이 PC 에서 브이월드로 마저 처리한다.
  0) PC 이름 확인, 시작 전 점검(못 올린 커밋·충돌이면 중단)
  1) git pull (코드 저장소 = 이 폴더의 상위, DB 저장소 = ../wood-land-data-db 또는 WOOD_LAND_DB_DIR)
  2) python run_eiass.py --pages 3 --retry-review   (새 사업 + 'PC 대기' 사업. '사람 확인' 사업은 건너뛴다)
  3) DB 저장소의 eiass/ 만 커밋·푸시 (git add -A 를 쓰지 않는다). 실행 기록(eiass/pc_runs.jsonl)도 함께 올라간다
키: 환경변수 또는 500_local 폴더(core/keys.py). PC 두 대(PCwj, PCyw)가 동시에 돌지 않는 것이 전제다.
공통 부분(PC 이름·점검·기록)은 저장소 최상위의 pc_common.py 이며 gosi/run_blocked_local.py 와 같은 규칙이다.

  python run_pc.py            # 받기 -> 처리 -> 올리기
  python run_pc.py --no-git   # 시험: 처리만
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import pc_common  # noqa: E402
from core import store  # noqa: E402

VERSION = "v20261025"
JOB = "eiass"


def git(cwd, *args, check=True):
    print(">", "git", *args, f"({cwd.name})", flush=True)
    r = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, encoding="utf-8", errors="replace")
    if r.stdout.strip():
        print(r.stdout.strip())
    if r.returncode and check:
        print(r.stderr.strip()); raise SystemExit(f"git {' '.join(args)} 실패")
    return r


def _head(cwd):
    return pc_common.git_out(["rev-parse", "--short", "HEAD"], cwd)[1]


def _main(no_git, rec):
    db = store.DATA.parent
    runs_file = store.DATA / "pc_runs.jsonl"  # DB 저장소 eiass/ 안의 실행 기록(모든 PC 가 공유)
    print(f"===== 환경영향평가 PC 처리 {VERSION} =====")
    pc = pc_common.ensure_pc_name()
    if not pc:
        rec["result"] = "stopped: no pc name"
        return 2
    rec["pc"] = pc
    print(f"이 PC: {pc}")
    for old in pc_common.recent_records(runs_file, 3):
        print("  지난 기록: " + pc_common.summary(old))
    rec["stage"] = "check"
    if not (db / ".git").exists():
        print(f"DB 저장소가 없습니다: {db}\n  git clone https://github.com/wood-land/wood-land-data-db.git \"{HERE.parent / 'wood-land-data-db'}\"")
        rec["result"] = "stopped: no db repo"
        return 1
    if not no_git:
        if not pc_common.preflight([("코드 저장소", HERE.parent), ("DB 저장소", db)]):
            rec["result"] = "stopped: preflight (conflict or unpushed commits)"
            return 1
        rec["stage"] = "pull"
        git(HERE.parent, "pull", "--ff-only", check=False)
        if git(db, "status", "--porcelain", "eiass", check=False).stdout.strip():
            print("DB 저장소 eiass/ 에 올리지 않은 변경이 있어 먼저 커밋합니다")
        git(db, "pull", "--rebase", "--autostash")
        rec["heads"] = {"code": _head(HERE.parent), "db": _head(db)}
    rec["stage"] = "collect"
    rc = subprocess.call([sys.executable, str(HERE / "run_eiass.py"), "--pages", "3", "--retry-review"], cwd=HERE)
    rec["regions"]["eiass"] = {"status": "ok" if rc == 0 else f"exit {rc}"}
    done = "collected" if rc == 0 else f"collect failed (exit {rc})"
    if no_git:
        rec["result"] = done + " (no-git)"
        return rc
    rec["stage"] = "push"
    rec["result"] = done  # 이 줄이 DB 저장소에 올라간다(실패한 실행도 남긴다). push 성공 여부는 이 PC 의 로컬 기록에 남는다
    pc_common.append_record(runs_file, rec)
    git(db, "add", "eiass")
    if git(db, "diff", "--cached", "--quiet", check=False).returncode == 0:
        print("변경 없음"); rec["result"] = "ok (no change)" if rc == 0 else done; return rc
    git(db, "commit", "-m", f"eiass: 국내 IP PC 처리 결과 [{pc}]")
    for _ in range(5):
        if git(db, "pull", "--rebase", check=False).returncode == 0 and git(db, "push", check=False).returncode == 0:
            print("올리기 완료"); rec["result"] = "ok" if rc == 0 else done; return rc
    print("push 실패 - 나중에 다시 실행하세요"); rec["result"] = "push failed"; return 1


def main():
    rec = pc_common.new_record(pc_common.pc_name(), VERSION, JOB)
    try:
        return _main("--no-git" in sys.argv, rec)
    except BaseException as e:  # 어디서 죽었는지 남긴다
        rec["result"] = f"crashed: {type(e).__name__}: {str(e)[:150]}"
        raise
    finally:
        try:
            path = pc_common.local_record_path()
            if path:
                pc_common.append_record(path, rec)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
