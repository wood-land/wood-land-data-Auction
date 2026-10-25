"""
run_pc_all.py - 국내 IP PC 수집을 한 번에: 고시공고·공보(막힌 지자체) -> 환경영향평가(브이월드 선 도면).
'★PC수집_전체_더블클릭_v….bat' 이 이 파일을 실행한다. 둘은 각자의 실행기를 그대로 부르므로 하는 일은 따로 돌릴 때와 같다.

  1) PC 이름 확인(없으면 한 번 물어 저장) 2) 시작 전 점검(코드·DB 저장소: 못 올린 커밋·충돌) 3) 고시공고·공보 4) 환경영향평가
한쪽이 실패해도 다른 쪽은 계속 돈다. 마지막에 둘의 결과를 한 번에 보여 준다(0 = 정상).
Claude 앱 터미널 패널에서 돌리면 화면을 Claude 가 읽을 수 있다(운영 방식 2026-10-25).

  python run_pc_all.py             # 받기 -> 수집 -> 올리기 (둘 다)
  python run_pc_all.py --no-git    # 시험: git 은 건드리지 않고 수집만
  python run_pc_all.py --reread    # 고시공고·공보에서 이미 처리한 글도 7일 창 안이면 다시 읽는다
  python run_pc_all.py --only gosi | eiass
  python run_pc_all.py --no-venv   # 전용 가상환경(.venv-pc) 대신 지금 쓰는 파이썬으로

작업은 저장소 최상위의 전용 가상환경 .venv-pc 의 파이썬으로 돈다(처음 한 번 만들고 requirements 를 설치하므로 몇 분 걸린다).
"""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import pc_common  # noqa: E402

VERSION = "v20261025"
JOBS = {
    "gosi": ("고시공고·공보(막힌 지자체)", HERE / "gosi", "run_blocked_local.py", ("--no-git", "--reread")),
    "eiass": ("환경영향평가(브이월드 선 도면)", HERE / "eiass", "run_pc.py", ("--no-git",)),
}


def db_repo_dir():
    sys.path.insert(0, str(HERE / "gosi"))
    from core.paths import DB_REPO_DIR  # gosi 와 같은 규칙으로 DB 저장소 위치를 찾는다
    return Path(DB_REPO_DIR)


VENV = HERE / ".venv-pc"  # PC 수집 전용 가상환경(git 제외). 이 PC 의 다른 파이썬 작업(tensorflow 등)과 패키지 버전이 부딪치지 않게 따로 둔다


def venv_python():
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def ensure_venv():
    """전용 가상환경 파이썬 경로를 돌려준다(없으면 만든다). 만들지 못하면 지금 쓰는 파이썬으로 대신한다."""
    py = venv_python()
    if not py.exists():
        print(f"PC 수집 전용 가상환경을 만듭니다: {VENV}", flush=True)
        if subprocess.call([sys.executable, "-m", "venv", str(VENV)]) != 0 or not py.exists():
            print("[주의] 가상환경을 만들지 못해 지금 쓰는 파이썬으로 진행합니다.")
            return Path(sys.executable)
    return py


def ensure_requirements(cwd, env, python=None):
    """실행 전에 그 작업의 requirements.txt 를 맞춘다(이미 설치돼 있으면 금방 끝남). bat 이 하던 일을 터미널 패널 실행에서도 하게 한다."""
    req = Path(cwd) / "requirements.txt"
    if not req.is_file():
        return True
    rc = subprocess.call([str(python or sys.executable), "-m", "pip", "install", "-q", "--disable-pip-version-check", "-r", str(req)],
                         cwd=str(cwd), env=env)
    if rc != 0:
        print(f"[주의] {req} 설치에 실패했습니다(네트워크 확인). 이미 설치돼 있으면 그대로 진행합니다.")
    return rc == 0


def job_args(key, argv):
    return [a for a in argv if a in JOBS[key][3]]


def selected(argv):
    if "--only" in argv:
        i = argv.index("--only")
        want = argv[i + 1] if i + 1 < len(argv) else ""
        if want not in JOBS:
            raise SystemExit(f"--only 는 {' 또는 '.join(JOBS)} 중 하나여야 합니다")
        return [want]
    return list(JOBS)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    print(f"===== 국내 IP PC 수집 전체 {VERSION} =====")
    pc = pc_common.ensure_pc_name()
    if not pc:
        return 2
    print(f"이 PC: {pc}")
    if "--no-git" not in argv and not pc_common.preflight([("코드 저장소", HERE), ("DB 저장소", db_repo_dir())]):
        return 1
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", GOSI_PC_NAME=pc)
    python = Path(sys.executable) if "--no-venv" in argv else ensure_venv()
    print(f"파이썬: {python}")
    results = {}
    for key in selected(argv):
        label, cwd, script, _ = JOBS[key]
        print(f"\n########## {label} ##########", flush=True)
        ensure_requirements(cwd, env, python)
        results[key] = subprocess.call([str(python), "-u", script] + job_args(key, argv), cwd=str(cwd), env=env)
    print("\n========== 결과 ==========")
    for key, rc in results.items():
        print(f"  {JOBS[key][0]}: {'정상' if rc == 0 else f'문제 있음(코드 {rc}) - 위 메시지를 확인하세요'}")
    return 0 if all(rc == 0 for rc in results.values()) else 1


if __name__ == "__main__":
    code = main()
    print("\n끝났습니다. 창을 닫아도 됩니다.")
    sys.exit(code)
