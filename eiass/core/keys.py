"""
core/keys.py - API 키 찾기. 환경변수가 먼저, 없으면 PC 의 500_local 폴더(git 제외)에서 찾는다.
  VWORLD_API_KEY      : 500_local 아래 이름에 vworld/브이월드 가 든 폴더의 파일(XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX 형식)
  KAKAO_REST_API_KEY  : 500_local 아래 이름에 kakao/카카오 가 든 폴더의 파일(32자리)
500_local 위치: 환경변수 GOSI_LOCAL_DIR -> eiass/.local_dir 또는 gosi/.local_dir -> 상위 폴더들 중 '500_local' (gosi/core/local_dir.py 와 같은 규칙)
"""
import os
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "VWORLD_API_KEY": (r"vworld|브이월드", re.compile(r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}")),
    "KAKAO_REST_API_KEY": (r"kakao|카카오", re.compile(r"(?<![0-9A-Fa-f])[0-9a-fA-F]{32}(?![0-9A-Fa-f])")),
}


def _local_dir():
    env = os.environ.get("GOSI_LOCAL_DIR", "").strip()
    if env and Path(env).is_dir():
        return Path(env)
    # gosi 와 같은 '.local_dir'(키 폴더 경로 한 줄, git 제외) 파일: eiass/ 또는 옆 gosi/ 폴더
    for pointer in (_ROOT / ".local_dir", _ROOT.parent / "gosi" / ".local_dir"):
        try:
            t = Path(pointer.read_text(encoding="utf-8").strip()) if pointer.is_file() else None
        except OSError:
            t = None
        if t and t.is_dir():
            return t
    for parent in _ROOT.parents:
        if (parent / "500_local").is_dir():
            return parent / "500_local"
    return None


def load(name):
    v = os.environ.get(name, "").strip()
    if v:
        return v
    base = _local_dir()
    if not base or name not in PATTERNS:
        return ""
    pat, rx = PATTERNS[name]
    level = [base]
    for _ in range(3):
        nxt = []
        for d in level:
            try:
                subs = sorted(x for x in d.iterdir() if x.is_dir())
            except OSError:
                continue
            for x in subs:
                nxt.append(x)
                if re.search(pat, x.name, re.I):
                    for f in sorted(x.iterdir()):
                        if f.is_file() and f.stat().st_size < 20000:
                            m = rx.search(f.read_text(encoding="utf-8", errors="ignore"))
                            if m:
                                os.environ[name] = m.group(0)
                                return m.group(0)
        level = nxt
    return ""
