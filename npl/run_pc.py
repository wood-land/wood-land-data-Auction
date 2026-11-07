# -*- coding: utf-8 -*-
"""run_pc.py - 국내 IP PC 에서 NPL 수집을 돌린다 (옥션원이 GitHub 서버 IP 를 403 으로 막아 PC 에서 실행).

  python run_pc.py                 # 전체 실행 (옥션원 NPL 목록 -> 두인 매칭 -> 두인 상세 -> 구글시트)
  python run_pc.py --max-detail 5  # 시험: 두인 상세는 5건만
  python run_pc.py --show          # 옥션원 브라우저 창을 띄워서 실행(막힐 때 눈으로 확인)

로그인 정보는 코드/저장소에 두지 않는다. 아래 순서로 찾는다(환경변수가 먼저).
  1) 이미 설정된 환경변수
  2) 환경변수 NPL_ENV_FILE 이 가리키는 파일, 없으면 D:\\npl_env.txt, C:\\npl_env.txt, 내 폴더\\npl_env.txt
     (한 줄에 KEY=값. 형식은 npl/npl_env.example.txt 참고. 이 파일은 git 저장소 밖에 둔다)
구글시트 서비스계정 키는 GOOGLE_SA_KEY_JSON 이 없으면 아래 후보 경로의 파일을 읽는다.
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

REQUIRED = ["SITE_DOMAIN", "SITE_LOGIN_ID", "SITE_LOGIN_PW", "TYPE_A_LABEL", "TYPE_B_LABEL",
            "GOOGLE_SHEET_ID", "A1_LOGIN_ID", "A1_LOGIN_PW"]
ENV_FILE_CANDIDATES = [
    os.environ.get("NPL_ENV_FILE", ""),
    r"D:\npl_env.txt", r"C:\npl_env.txt", str(Path.home() / "npl_env.txt"),
]
KEY_FILE_CANDIDATES = [
    os.environ.get("GOOGLE_CREDENTIALS_PATH", ""),
    r"D:\200_MU-MU_Auction\500_local\100. Google_credentials\google_credentials_편집자.json",
    r"C:\startcoding\100. Google_credentials\google_credentials_편집자.json",
    r"C:\Python\startcoding\100. google_credentials\google_credentials_편집자.json",
]


def load_env_file():
    for cand in ENV_FILE_CANDIDATES:
        if cand and os.path.isfile(cand):
            n = 0
            for line in open(cand, encoding="utf-8-sig"):
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                    v = v[1:-1]
                if k and k not in os.environ:   # 이미 설정된 환경변수가 우선
                    os.environ[k] = v
                    n += 1
            print(f"설정 파일 읽음: {cand} ({n}개)")
            return cand
    return None


def load_google_key():
    if os.environ.get("GOOGLE_SA_KEY_JSON"):
        return True
    for cand in KEY_FILE_CANDIDATES:
        if cand and os.path.isfile(cand):
            os.environ["GOOGLE_SA_KEY_JSON"] = open(cand, encoding="utf-8").read()
            print(f"구글 서비스계정 키 읽음: {cand}")
            return True
    return False


def main(argv):
    if "--max-detail" in argv:
        i = argv.index("--max-detail")
        os.environ["NPL_MAX_DETAIL"] = argv[i + 1] if i + 1 < len(argv) else "0"
    if "--show" in argv:
        os.environ["A1_HEADLESS"] = "0"
    os.environ.setdefault("TRIGGER_TYPE", "pc")
    os.environ.setdefault("PYTHONUTF8", "1")

    load_env_file()
    ok_key = load_google_key()
    missing = [k for k in REQUIRED if not os.environ.get(k)]
    if missing or not ok_key:
        print("필요한 설정이 없습니다:")
        for k in missing:
            print(f"  - {k}")
        if not ok_key:
            print("  - 구글 서비스계정 키 파일(google_credentials_편집자.json)을 찾지 못했습니다")
        print("npl/npl_env.example.txt 를 D:\\npl_env.txt 로 복사해 값을 채우세요(이 파일은 git 에 올리지 않는다).")
        return 2

    # auction/crawler.py 가 키를 /tmp/google_credentials.json 에 쓰므로(리눅스 기준) 윈도우에서도 그 폴더를 만들어 둔다
    os.makedirs("/tmp", exist_ok=True)

    sys.path.insert(0, str(HERE))
    import npl_crawler  # 환경변수를 다 채운 뒤에 불러와야 한다(두인 수집기가 import 때 읽음)
    return npl_crawler.main()


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass
    sys.exit(main(sys.argv[1:]))
