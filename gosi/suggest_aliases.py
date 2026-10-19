"""
suggest_aliases.py - PNU 로 못 바꾼 주소(parcels_unresolved) 중 OCR 오인식으로 보이는 지명(리·동)의 정상 이름 후보를 찾아 보여준다.

카카오 REST API 에는 지도 화면 같은 연관검색어(자동완성)가 없다. 대신 OCR 이 자주 틀리는 모음·받침 한 글자만 바꾼 이름들을
카카오 주소검색으로 확인한다(같은 시군구 + 바꾼 이름 + 문서의 지번). 지번까지 정확히 일치한 이름만 후보가 된다.
후보는 사람이 확인한 뒤 core/place_aliases.json 에 등록한다(자동으로 쓰지 않는다: 지번이 작으면 우연히 일치할 수 있다).

  python suggest_aliases.py                # data/gosi/*.sqlite 전체
  python suggest_aliases.py 충남 전남        # 지역 DB 이름만
"""
import glob
import os
import re
import sqlite3
import sys
from collections import defaultdict

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from core.paths import DATA_DIR  # noqa: E402
from core.pnu import KAKAO_URL, PnuResolver, load_key, parse_jibun  # noqa: E402

# 초성/중성/종성 번호(유니코드 한글 음절 분해). OCR 이 잘 혼동하는 같은 계열끼리만 바꾼다.
VOWEL_SETS = [{8, 13, 12, 17, 18}, {4, 6, 0, 2, 20}, {1, 5, 3, 7, 20}]  # ㅗㅜㅛㅠㅡ / ㅓㅕㅏㅑㅣ / ㅐㅔㅒㅖㅣ
INITIAL_SETS = [{7, 17, 6}, {0, 15, 1}, {3, 16, 2}, {9, 12, 14}]  # ㅂㅍㅁ / ㄱㅋㄲ / ㄷㅌㄸ / ㅅㅈㅊ
FINALS = (0, 1, 4, 8, 16, 17, 21)  # 없음 ㄱ ㄴ ㄹ ㅁ ㅂ ㅇ


def _split(ch):
    n = ord(ch) - 0xAC00
    return n // 588, (n % 588) // 28, n % 28


def _join(l, v, t):
    return chr(0xAC00 + l * 588 + v * 28 + t)


def syllable_variants(ch):
    if not "가" <= ch <= "힣":
        return set()
    l, v, t = _split(ch)
    out = set()
    for vs in VOWEL_SETS:
        if v in vs:
            out |= {_join(l, x, t) for x in vs if x != v}
    for ls in INITIAL_SETS:
        if l in ls:
            out |= {_join(x, v, t) for x in ls if x != l}
    out |= {_join(l, v, x) for x in FINALS if x != t}
    out.discard(ch)
    return out


def name_variants(name):
    """접미사(리·동·가)를 뺀 이름에서 한 글자만 바꾼 후보들(한 글자 이름은 제외)."""
    stem, suffix = name[:-1], name[-1]
    if len(stem) < 2:
        return []
    return sorted({stem[:i] + v + stem[i + 1:] + suffix for i, ch in enumerate(stem) for v in syllable_variants(ch)})


def kakao_exact(session, key, query, want):
    try:
        data = session.get(KAKAO_URL, headers={"Authorization": f"KakaoAK {key}"}, params={"query": query}, timeout=10).json()
    except (requests.RequestException, ValueError):
        return None
    for d in data.get("documents", []):
        if PnuResolver._match(d, want):
            return d["address"]["address_name"]
    return None


def main(argv):
    key = load_key()
    if not key:
        print("카카오 키가 없습니다(환경변수 KAKAO_REST_API_KEY 또는 500_local 아래 kakao 폴더).")
        return 2
    wanted = set(argv)
    groups = defaultdict(list)  # (지자체, 시도 시군구 앞부분, 이름) -> [지번...]
    for path in sorted(glob.glob(str(DATA_DIR / "*.sqlite"))):
        if wanted and os.path.basename(path)[:-7] not in wanted:
            continue
        con = sqlite3.connect(path)
        try:
            rows = con.execute("SELECT sojaeji, jibun, city FROM parcels_unresolved WHERE reason='no_match'").fetchall()
        except sqlite3.Error:
            continue
        for soj, jibun, city in rows:
            base = re.sub(r"(?:\s+산?\s*\d+(?:-\d+)?)+$", "", (soj or "").strip())
            words = base.split()
            if len(words) >= 2 and re.fullmatch(r"[가-힣0-9]{2,6}[리동]", words[-1]) and parse_jibun(jibun):
                groups[(city, " ".join(words[:-1]), words[-1])].append(jibun)
    session = requests.Session()
    found = {}
    for (city, prefix, name), jibuns in sorted(groups.items()):
        jibuns = sorted(set(jibuns))[:6]
        # 이름 그대로 지번이 하나라도 맞으면 이름 문제가 아니다
        if any(kakao_exact(session, key, f"{prefix} {name} {j}", parse_jibun(j)) for j in jibuns):
            continue
        for cand in name_variants(name):
            hits = [j for j in jibuns if kakao_exact(session, key, f"{prefix} {cand} {j}", parse_jibun(j))]
            if hits:
                found.setdefault((city, name), []).append((cand, len(hits), len(jibuns)))
    if not found:
        print("후보 없음(이름만 한 글자 틀린 경우는 찾지 못했습니다).")
    for (city, name), cands in found.items():
        for cand, n, total in sorted(cands, key=lambda x: -x[1]):
            print(f"{city}: {name} -> {cand}   (지번 {n}/{total}건 일치)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
