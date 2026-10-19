"""
run_blocked_local.py - PC 를 켤 때마다 실행('★PC수집_막힌지자체_더블클릭_v….bat' 더블클릭): 국내 IP 에서만 읽히는 게시판을 수집해 올린다.

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
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from core import blocked_sites as B  # noqa: E402
from core.paths import DB_REPO_DIR, DATA_DIR  # noqa: E402

DATA = str(DB_REPO_DIR)  # 비공개 DB 저장소(별도 git 저장소, 여러 크롤러 공용; 위치는 core/paths.py). 이 크롤러의 DB 는 그 안의 gosi/
DB_SUBDIR = "gosi"

VERSION = "v20261018"  # 배치 파일 이름의 버전과 맞춘다(이 스크립트를 고치면 둘 다 새 날짜로)
REGION_TIMEOUT = 30 * 60  # 지역 하나가 이 시간(초)을 넘기면 중단하고 다음으로 넘어간다(한 게시판이 오래 걸려도 전체가 멈추지 않게)
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
        print(f"\n[주의] [{label}] 올리기에 실패했습니다. 결과는 이 PC 에 커밋돼 있으니 다음 실행 때 다시 올라갑니다.")
        return False
    print(f"\n[{label}] 올리기 완료.")
    return True


def main(use_git=True):
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    print(f"===== 막힌 지자체 PC 수집 {VERSION} =====")
    from core.pnu import load_key
    if not load_key():
        print("\n[오류] 카카오 REST 키를 찾지 못했습니다. 주소를 PNU 로 바꿀 수 없어 수집을 시작하지 않습니다.\n"
              "  - 환경변수 KAKAO_REST_API_KEY 에 키를 넣거나,\n"
              "  - 500_local 아래 이름에 'kakao'(또는 '카카오')가 들어간 폴더에 키가 든 파일(.txt)을 두세요(git 에는 올리지 않습니다).")
        return 2
    if use_git and not os.path.isdir(os.path.join(DATA, ".git")):
        print("\n[오류] data/ 폴더가 비공개 DB 저장소가 아닙니다. 아래 명령으로 받아 두세요(한 번만):\n"
              f"  git clone {DB_REPO_URL} \"{DATA}\"")
        return 2
    if use_git:
        print("[1/4] 최신 코드·DB 받기")
        if run(["git", "pull", "--rebase", "--autostash"]) != 0 or run(["git", "pull", "--rebase", "--autostash"], DATA) != 0:
            print("\n[중단] git pull 에 실패했습니다. 위 메시지를 확인하세요(충돌이나 네트워크 문제). 아무것도 올리지 않았습니다.")
            return 1

    print("\n[2/4] 수집 로그(구글시트)에서 새로 막힌 지자체 찾기")
    try:
        import detect_blocked
        detect_blocked.run(apply=True, confirm=detect_blocked.ask_console)  # 후보는 물어보고 승인(y)해야 등록한다
    except Exception as e:  # 키가 없거나 시트를 못 읽어도 수집은 계속한다
        print(f"(건너뜀) {type(e).__name__}: {str(e)[:120]}")
    blocked = B.all_blocked()
    print("대상: " + " / ".join(f"{r}({', '.join(c)})" for r, c in blocked.items()))

    print("\n[3/4] 국내 IP 에서만 읽히는 게시판 수집")
    db_files = []
    for region in blocked:
        name = f"국내IP_{region}.sqlite"
        try:
            rc = subprocess.run([sys.executable, "-u", "run_scheduled.py", "--region", region, "--blocked", "only",
                                 "--db", str(DATA_DIR / name), "--log-prefix", "PC"],
                                cwd=HERE, env=env, timeout=REGION_TIMEOUT).returncode
            print(f"  -> {region}: {'완료' if rc == 0 else f'오류 종료(코드 {rc})'}")
        except subprocess.TimeoutExpired:
            print(f"  -> {region}: {REGION_TIMEOUT // 60}분을 넘겨 중단했습니다(그때까지 저장된 결과만 남습니다).")
        db_files.append(f"{DB_SUBDIR}/{name}")

    code_files = [os.path.relpath(str(f), HERE) for f in (B.AUTO_FILE, B.REJECTED_FILE) if f.exists()]
    # 등록 목록이 바뀌었으면 함께 올려야 Actions 가 그 지자체를 건너뛴다(거절 기록도 공유)
    if not use_git:
        print("\n--no-git: 결과 파일만 만들고 git 에는 올리지 않았습니다: " + ", ".join(db_files + code_files))
        return 0

    print("\n[4/4] 결과 올리기")
    ok_db = commit_push(DATA, db_files, "chore: 국내 IP 로컬 수집 결과 갱신 (막힌 게시판)", "DB 저장소")
    ok_code = commit_push(HERE, code_files, "chore: 막힌 지자체 목록 갱신 (자동 등록/거절)", "코드 저장소") if code_files else True
    return 0 if ok_db and ok_code else 1


if __name__ == "__main__":
    code = main(use_git="--no-git" not in sys.argv)
    print("\n끝났습니다. 창을 닫아도 됩니다.")
    sys.exit(code)
