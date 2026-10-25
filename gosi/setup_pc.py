"""
setup_pc.py - 새 PC(예: PCyw)를 PC 수집용으로 처음 한 번 준비한다. 여러 번 실행해도 안전하다(이미 된 것은 건너뜀).

  python setup_pc.py          # 코드 저장소를 받은 뒤 gosi 폴더에서 실행

하는 일:
  1) DB 저장소(wood-land-data-db)를 코드 저장소 최상위에 clone(없을 때만)하고, 코드 저장소 git 에서 제외 처리
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
    top = HERE.parent
    target = top / "wood-land-data-db"
    if (target / ".git").exists():
        print(f"이미 있음: {target}")
    else:
        rc = subprocess.run(["git", "clone", DB_REPO_URL, str(target)], cwd=top).returncode
        if rc != 0:
            print("[실패] clone 에 실패했습니다. GitHub 로그인(비공개 저장소 접근 권한)을 확인하세요.")
            return False
    exclude = top / ".git" / "info" / "exclude"
    try:
        text = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
        if "/wood-land-data-db/" not in text:
            exclude.parent.mkdir(parents=True, exist_ok=True)
            with open(exclude, "a", encoding="utf-8") as f:
                f.write(("\n" if text and not text.endswith("\n") else "") + "/wood-land-data-db/\n")
            print("코드 저장소 git 에서 제외 처리했습니다.")
    except OSError as e:
        print(f"(참고) 제외 처리를 못 했습니다: {e}")
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
