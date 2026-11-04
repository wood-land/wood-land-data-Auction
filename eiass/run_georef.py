"""
run_georef.py - QGIS 지리참조자로 저장한 기준점을 DB 에 반영하고 올린다(더블클릭용 바로가기: '★지리참조_반영_더블클릭.bat').

사람이 하는 일은 QGIS 에서 전체 도면(check Plz/{코드}_{대표지번}_도면.png)에 점을 찍고 '저장'하는 것뿐이다.
QGIS 가 그림 옆에 만드는 '..._도면.png.points' 를 이 스크립트가 찾아서(이름 바꿀 필요 없음)
  1) DB 저장소 받기  2) run_manual.py 로 검증·확정  3) DB 저장소 eiass/ 커밋·푸시
를 한 번에 한다. 확정하지 못한 사업은 사유를 화면과 이슈에 남긴다. 전체 수집(run_pc.py)과 달리 몇십 초면 끝난다.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from core import store  # noqa: E402


def git(cwd, *args):
    r = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, encoding="utf-8", errors="replace")
    return r


def main():
    db = store.DATA.parent
    if not (db / ".git").exists():
        print(f"DB 저장소를 찾지 못했습니다: {db}"); return 1
    print("1) DB 저장소 받기")
    r = git(db, "pull", "--rebase", "--autostash")
    print("  " + (r.stdout.strip().splitlines() or ["완료"])[-1] if r.returncode == 0 else "  받기 실패: " + r.stderr.strip()[:200])
    if r.returncode != 0:
        return 1
    print("2) 기준점 반영 (run_manual.py)")
    subprocess.call([sys.executable, str(HERE / "run_manual.py")], cwd=HERE)
    print("3) DB 저장소 올리기")
    git(db, "add", "eiass")
    if git(db, "diff", "--cached", "--quiet").returncode == 0:
        print("  올릴 변경이 없습니다(점이 없거나 이미 처리됨)"); return 0
    git(db, "commit", "-m", "eiass: 사람이 지리참조한 기준점 반영 (run_georef.py)")
    for _ in range(5):
        if git(db, "pull", "--rebase").returncode == 0 and git(db, "push").returncode == 0:
            print("  올리기 완료"); return 0
    print("  올리기 실패 - 잠시 뒤 다시 실행하세요"); return 1


if __name__ == "__main__":
    sys.exit(main())
