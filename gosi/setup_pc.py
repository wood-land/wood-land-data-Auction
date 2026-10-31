"""
setup_pc.py - 새 PC(예: PCyw)를 PC 수집용으로 처음 한 번 준비한다. 여러 번 실행해도 안전하다(이미 된 것은 건너뜀).

  python setup_pc.py          # 코드 저장소를 받은 뒤 gosi 폴더에서 실행

하는 일:
  1) DB 저장소(wood-land-data-db)를 코드 저장소 옆 폴더(D:/wood-land-data-db)에 clone(없을 때만)하고, 환경변수 WOOD_LAND_DB_DIR 로 위치를 알려 둔다
  2) 500_local 폴더 위치를 찾고(상위 폴더 중 500_local, 또는 .local_dir), 카카오 키·구글 키·시트 ID 가 보이는지 점검
  3) 이 PC 의 이름(PCwj / PCyw ...)이 없으면 물어서 500_local/pc_name.txt 에 저장
키 파일은 git 에 없으므로 이 스크립트가 만들어 주지 못한다(다른 PC 에서 500_local 안의 해당 폴더를 직접 복사).
"""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from core import local_dir  # noqa: E402

DB_REPO_URL = "https://github.com/wood-land/wood-land-data-db.git"


def step(msg):
    print(f"\n== {msg}")


def clone_db():
    """DB 저장소는 한 곳(코드 저장소 옆 D:/wood-land-data-db)에만 둔다. WOOD_LAND_DB_DIR 이 이미 있으면 그 위치를 쓴다."""
    env = os.environ.get("WOOD_LAND_DB_DIR", "").strip()
    target = Path(env) if env else HERE.parent.parent / "wood-land-data-db"
    legacy = HERE.parent / "wood-land-data-db"      # 예전 방식(코드 폴더 안)
    if legacy.exists() and legacy.resolve() != target.resolve():
        print(f"(주의) 예전 방식의 DB 폴더가 있습니다: {legacy}"
              f"\n       수집 결과가 {target} 와 갈라지지 않게, 올리지 않은 변경이 없으면 이 폴더는 지우세요.")
    if (target / ".git").exists():
        print(f"이미 있음: {target}")
    else:
        rc = subprocess.run(["git", "clone", DB_REPO_URL, str(target)], cwd=str(target.parent)).returncode
        if rc != 0:
            print("[실패] clone 에 실패했습니다. GitHub 로그인(비공개 저장소 접근 권한)을 확인하세요.")
            return False
    if not env:
        os.environ["WOOD_LAND_DB_DIR"] = str(target)
        if sys.platform == "win32":
            rc = subprocess.run(["setx", "WOOD_LAND_DB_DIR", str(target)], capture_output=True).returncode
            print(f"환경변수 WOOD_LAND_DB_DIR={target} 을 저장했습니다(새로 여는 터미널부터 적용)." if rc == 0
                  else f"(참고) 환경변수를 저장하지 못했습니다. 직접: setx WOOD_LAND_DB_DIR " + chr(34) + str(target) + chr(34))
    return True


def vworld_key_found():
    """eiass/core/keys.py 와 같은 규칙: 환경변수 VWORLD_API_KEY, 또는 500_local 아래 이름에 vworld/브이월드 가 든 폴더의 키 파일."""
    import re
    if os.environ.get("VWORLD_API_KEY", "").strip():
        return True
    pat = re.compile(r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}")
    for folder in local_dir.find_dirs(r"vworld|브이월드"):
        for f in folder.rglob("*"):
            try:
                if f.is_file() and pat.search(f.read_text(encoding="utf-8", errors="ignore")):
                    return True
            except OSError:
                continue
    return False


def tesseract_ok():
    from core.gazette_extractor import TESSERACT
    try:
        out = subprocess.run([TESSERACT, "--list-langs"], capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return "kor" in out.split()


def check_local():
    base = local_dir.local_dir()
    if not base:
        print("[없음] 500_local 폴더를 찾지 못했습니다. 다른 PC 의 500_local 을 이 저장소의 상위 폴더에 복사하거나,\n"
              f"       {HERE}\\.local_dir 파일에 500_local 경로 한 줄을 적으세요.")
        return False
    print(f"500_local: {base}")
    from core.pnu import load_key
    from core.ai_fix import load_key as deepseek_key
    ok = True
    for label, found in (("카카오 REST 키", bool(load_key())),
                         ("DeepSeek 키(AI 주소 보정)", bool(deepseek_key())),
                         ("브이월드 키(환경영향평가 선 도면)", vworld_key_found()),
                         ("구글 서비스 계정 키", local_dir.google_key_file().exists()),
                         ("로그 시트 ID", bool(local_dir.sheet_id())),
                         ("Tesseract OCR + 한글(kor) 데이터(스캔 PDF 읽기)", tesseract_ok())):
        print(f"  [{'OK' if found else '없음'}] {label}")
        ok = ok and found
    if not ok:
        print("  없는 항목은 다른 PC 의 500_local 안 해당 폴더(예: kakao, google_credentials)를 복사해 오세요.")
    return ok


def ensure_name():
    name = local_dir.pc_name()
    if name:
        print(f"PC 이름: {name}")
        return True
    if local_dir.local_dir() is None:
        return False
    ans = input("이 PC 의 이름을 입력하세요 (예: PCyw): ").strip()
    if local_dir.save_pc_name(ans):
        print(f"저장했습니다: {ans}")
        return True
    print("[오류] 이름 형식이 맞지 않습니다(영문·숫자·한글 2~20자).")
    return False


if __name__ == "__main__":
    results = []
    step("1) DB 저장소")
    results.append(clone_db())
    step("2) 500_local 과 키")
    results.append(check_local())
    step("3) PC 이름")
    results.append(ensure_name())
    print("\n" + ("준비 완료. ★PC수집_…bat 을 더블클릭하면 됩니다." if all(results) else "위 [없음]/[실패] 항목을 해결한 뒤 다시 실행하세요."))
    sys.exit(0 if all(results) else 1)
