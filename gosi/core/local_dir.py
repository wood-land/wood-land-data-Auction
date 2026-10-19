"""
core/local_dir.py - 이 PC 에만 두는 비밀 파일(API 키, 구글 서비스 계정 키, 시트 ID)이 있는 폴더(500_local)를 찾는다.

공개 저장소라 키·시트 ID 는 코드에 쓰지 않는다. 찾는 순서: 환경변수 GOSI_LOCAL_DIR -> 이 폴더의 `.local_dir` 파일(경로 한 줄, git 제외) -> 이 저장소의 상위 폴더들 중 '500_local' 이 있는 곳.
(Actions 에서는 환경변수/Secret 을 쓰므로 이 폴더가 없어도 된다.)
"""
import os
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def local_dir():
    env = os.environ.get("GOSI_LOCAL_DIR", "").strip()
    if env and Path(env).is_dir():
        return Path(env)
    pointer = _ROOT / ".local_dir"  # 저장소 밖 키 폴더를 가리키는 한 줄짜리 파일(git 제외). 크롤러 폴더가 키 폴더의 하위가 아닐 때 쓴다
    try:
        target = Path(pointer.read_text(encoding="utf-8").strip()) if pointer.is_file() else None
    except OSError:
        target = None
    if target and target.is_dir():
        return target
    for parent in _ROOT.parents:
        if (parent / "500_local").is_dir():
            return parent / "500_local"
    return None


def local_path(*parts):
    """500_local 아래 경로(폴더가 없으면 존재하지 않는 경로를 돌려준다 -> .exists() 가 False)."""
    base = local_dir()
    return (base or _ROOT / "_no_local_dir").joinpath(*parts)


def find_dirs(pattern, depth=2):
    """500_local 아래(깊이 depth 까지)에서 이름이 pattern(정규식, 대소문자 무시)에 맞는 폴더들. PC 마다 폴더 구성이 달라도 찾도록 훑는다
    (예: 500_local/100. Key 항목/101.kakao). 없으면 빈 리스트."""
    base = local_dir()
    out, level = [], [base] if base else []
    for _ in range(depth):
        nxt = []
        for d in level:
            try:
                subs = sorted(x for x in d.iterdir() if x.is_dir())
            except OSError:
                continue
            for x in subs:
                if re.search(pattern, x.name, re.I):
                    out.append(x)
                nxt.append(x)
        level = nxt
    return out


def find_file(folder_pattern, file_name):
    for d in find_dirs(folder_pattern):
        f = d / file_name
        if f.is_file():
            return f
    return local_path("_none_", file_name)  # 없는 경로(.exists() False)


def google_key_file():
    return find_file(r"google_credentials", "google_credentials_편집자.json")


def sheet_id():
    """수집 로그 시트 ID: 환경변수 GOOGLE_SHEET_ID -> 500_local 아래 google_credentials 폴더의 sheet_id.txt. 없으면 ''."""
    env = os.environ.get("GOOGLE_SHEET_ID", "").strip()
    if env:
        return env
    f = find_file(r"google_credentials", "sheet_id.txt")
    try:
        return f.read_text(encoding="utf-8").strip() if f.exists() else ""
    except OSError:
        return ""
