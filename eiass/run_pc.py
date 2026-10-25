"""
run_pc.py - 국내 IP PC 에서 실행('★PC_환경영향평가_더블클릭_v20261025.bat' 더블클릭).

GitHub Actions 러너(미국 IP)에서는 브이월드가 막혀(2026-10-25 확인) 선 도면(지형·지적 배경) 토지이용계획도를
연속지적도에 맞추지 못한다. 그런 사업은 review/ 에 '국내 IP PC 필요'로 남는데, 이 PC 에서 브이월드로 마저 처리한다.
  1) git pull (코드 저장소 = 이 폴더의 상위, DB 저장소 = ../wood-land-data-db 또는 WOOD_LAND_DB_DIR)
  2) python run_eiass.py --pages 3 --retry-review   (새 사업 + 'PC 대기' 사업. '사람 확인' 사업은 건너뛴다)
  3) DB 저장소의 eiass/ 만 커밋·푸시 (git add -A 를 쓰지 않는다)
키: 환경변수 또는 500_local 폴더(core/keys.py). PC 두 대(PCwj, PCyw)가 동시에 돌지 않는 것이 전제다.

  python run_pc.py            # 받기 -> 처리 -> 올리기
  python run_pc.py --no-git   # 시험: 처리만
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from core import store  # noqa: E402


def git(cwd, *args, check=True):
    print(">", "git", *args, f"({cwd.name})", flush=True)
    r = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, encoding="utf-8", errors="replace")
    if r.stdout.strip():
        print(r.stdout.strip())
    if r.returncode and check:
        print(r.stderr.strip()); raise SystemExit(f"git {' '.join(args)} 실패")
    return r


def main():
    no_git = "--no-git" in sys.argv
    db = store.DATA.parent
    if not (db / ".git").exists():
        print(f"DB 저장소가 없습니다: {db}\n  git clone https://github.com/wood-land/wood-land-data-db.git \"{HERE.parent.parent / 'wood-land-data-db'}\"")
        return 1
    if not no_git:
        git(HERE.parent, "pull", "--ff-only", check=False)
        if git(db, "status", "--porcelain", "eiass", check=False).stdout.strip():
            print("DB 저장소 eiass/ 에 올리지 않은 변경이 있어 먼저 커밋합니다")
        git(db, "pull", "--rebase", "--autostash")
    rc = subprocess.call([sys.executable, str(HERE / "run_eiass.py"), "--pages", "3", "--retry-review"], cwd=HERE)
    if no_git:
        return rc
    git(db, "add", "eiass")
    if git(db, "diff", "--cached", "--quiet", check=False).returncode == 0:
        print("변경 없음"); return rc
    git(db, "commit", "-m", "eiass: 국내 IP PC 처리 결과")
    for _ in range(5):
        if git(db, "pull", "--rebase", check=False).returncode == 0 and git(db, "push", check=False).returncode == 0:
            print("올리기 완료"); return rc
    print("push 실패 - 나중에 다시 실행하세요"); return 1


if __name__ == "__main__":
    sys.exit(main())
