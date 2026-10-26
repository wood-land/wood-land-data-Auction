"""
core/pnu.py - 한국식 주소(소재지 + 지번) -> PNU(19자리) 변환.

기준: 500_local/52. 경공매 추출/211. Google to Auction_PNU_Geojson 26 1004.py 의
get_pnu_from_kakao_session 과 같은 방식(카카오 주소검색 b_code + 산여부 + 본번4 + 부번4)이다.
PNU = 법정동코드(10) + 대지(1)/산(2) + 본번(4) + 부번(4)

- 카카오 REST 키: 환경변수 KAKAO_REST_API_KEY (GitHub Actions 는 Secret) 또는
  500_local/103. kakao Api key/kakao api key.txt 또는 500_local/101.kakao/kakao.txt (키가 들어 있는 파일, git 제외 대상).
- 같은 질의는 캐시 DB(data/.cache/*.sqlite, git 제외)의 pnu_cache 표에 저장해 다시 호출하지 않는다(성공/확정 실패 모두).
- 카카오가 엉뚱한 번지를 돌려주면(질의한 본번·부번과 다름) 실패로 본다.
"""
import os
import re
import json
import time
from pathlib import Path

import requests

from core.local_dir import find_dirs

RESOLVER_VERSION = 7  # 7(2026-10-26): 면 빠진 리·읍면 오기재·시군 첫 글자 빠진 주소 보완(실패 캐시 라벨도 v4 로 올림) / 변환 규칙을 고칠 때 올린다 -> 이전 실패분(parcels_unresolved)을 한 번 전부 다시 시도
KAKAO_URL = "https://dapi.kakao.com/v2/local/search/address.json"

SIDO_FULL = {
    "서울": "서울특별시", "부산": "부산광역시", "대구": "대구광역시", "인천": "인천광역시", "광주": "광주광역시",
    "대전": "대전광역시", "울산": "울산광역시", "세종특별자치시": "세종특별자치시", "세종": "세종특별자치시",
    "경기": "경기도", "강원": "강원특별자치도", "충북": "충청북도", "충남": "충청남도", "전북": "전북특별자치도",
    "전남": "전라남도", "경북": "경상북도", "경남": "경상남도", "제주": "제주특별자치도",
}

JIBUN_RE = re.compile(r"(산)?\s*(\d+)(?:\s*-\s*(\d+))?")


_KEY_RE = re.compile(r"(?:KakaoAK\s+)?([0-9a-fA-F]{32})(?![0-9a-fA-F])")


def _key_from_file(path):
    try:
        m = _KEY_RE.search(Path(path).read_text(encoding="utf-8", errors="ignore")[:4000])
    except OSError:
        return ""
    return m.group(1) if m else ""


def load_key():
    """카카오 REST 키: 환경변수 KAKAO_REST_API_KEY -> 500_local 아래 이름에 'kakao'/'카카오'가 들어간 폴더의 파일.
    PC 마다 키 파일 이름이 달라도 찾도록 마지막에 폴더를 훑는다(키 파일은 git 에 올리지 않는다). 못 찾으면 ''."""
    key = os.environ.get("KAKAO_REST_API_KEY", "").strip()
    if key:
        return key
    for folder in find_dirs(r"kakao|카카오"):  # 500_local 아래(예: 100. Key 항목/101.kakao) 이름에 kakao/카카오 가 든 폴더의 파일
        for f in sorted(folder.iterdir()):
            key = _key_from_file(f) if f.is_file() else ""
            if key:
                return key
    return ""


def parse_jibun(jibun):
    """'산95-49' / '157-2' / '외95' -> (산여부 bool, 본번 int, 부번 int). 못 읽으면 None."""
    m = JIBUN_RE.search(jibun or "")
    if not m:
        return None
    return bool(m.group(1)), int(m.group(2)), int(m.group(3) or 0)


def build_query(sojaeji, jibun):
    sojaeji = (sojaeji or "").strip()
    jibun = (jibun or "").strip()
    if not sojaeji:
        return ""
    p = parse_jibun(jibun)
    if p is None:
        return ""  # 지번이 없으면 필지(PNU)를 만들 수 없다
    mountain, main, sub = p
    tail = f"{'산' if mountain else ''}{main}" + (f"-{sub}" if sub else "")
    # 소재지가 이미 지번으로 끝나면 그대로, 아니면 뒤에 붙인다
    if re.search(r"\d+(?:-\d+)?$", sojaeji):
        base = re.sub(r"\s*(산)?\s*\d+(?:-\d+)?$", "", sojaeji).strip()
        return f"{base} {tail}"
    return f"{sojaeji} {tail}"


_ALIAS_FILE = Path(__file__).with_name("place_aliases.json")  # 사용자가 확인한 지명 바로잡기: {"지자체": {"잘못 읽힌 이름": "정상 이름"}}
_NOT_PARCEL_RE = re.compile(r"합\s*계|소\s*계|\(\s*\d+\s*필지\s*\)|필지\s*\)|(?:로|일|월|년)\s*부터|^\s*\d+\s*$|사\s*용\s*기\s*간|평점산식|입찰가격")


def load_aliases():
    try:
        return json.loads(_ALIAS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def apply_aliases(sojaeji, city):
    """사용자가 확인한 지명 바로잡기(예: OCR 이 '화봉리'를 '화붕리'로 읽음)를 소재지의 단어 단위로 적용한다."""
    table = load_aliases().get(city or "") or {}
    if not table:
        return sojaeji
    return " ".join(table.get(w, w) for w in (sojaeji or "").split())


def region_agrees(sojaeji, region2):
    """소재지에 시·군·구 이름이 적혀 있으면 카카오 결과의 시군구(region_2depth_name)가 그것과 같아야 한다.
    카카오는 그 시군구에 없는 지번이면 비슷한 이름의 다른 지역(경기도 광주시 송정동 187 -> 이천시 송정동 187)을 돌려주는데,
    지번 숫자만 맞는다고 받으면 엉뚱한 지역의 PNU 가 저장된다(2026-10-27 감사에서 발견). 소재지에 시군구 이름이 없으면 확인할 게 없어 통과."""
    names = [w for w in (sojaeji or "").split()
             if re.fullmatch(r"[가-힣]{1,6}[시군구]", w) and not re.search(r"(특별시|광역시|특별자치시)$", w)]
    if not names or not region2:
        return True
    return all(re.sub(r"(특례시|[시군구])$", "", w) in region2 for w in names)


def repair_concat_sigun(sojaeji, context):
    """'경상북도 안동시 택시안중읍 학현리'처럼 시군 이름의 첫 글자가 빠진 채 읍·면에 붙은 단어('택시안중읍' = 평택시 안중읍)를
    게시글 제목·사업명(context)에 나온 이름('평택')으로 되살려 '평택시 안중읍 학현리' 로 바꾼다. 후보가 하나일 때만 고친다."""
    words = (sojaeji or "").split()
    for i, w in enumerate(words):
        m = re.fullmatch(r"([가-힣]{1,3}[시군])([가-힣]{2,3}[읍면])", w)
        if not m:
            continue
        pre = m.group(1)[:-1]
        hits = {c for c in re.findall(r"[가-힣]{2,4}", context or "") if c.endswith(pre) and len(c) > len(pre)}
        if len(hits) == 1:
            return " ".join([hits.pop() + m.group(1)[-1], m.group(2)] + words[i + 1:])
    return sojaeji


def looks_like_non_parcel(sojaeji):
    """소재지 칸에 합계·필지 수·기간 같은 말이 들어간 행 -> 필지가 아니다(표의 합계 행, 본문 문장 조각 등)."""
    return bool(_NOT_PARCEL_RE.search(sojaeji or ""))


class PnuResolver:
    def __init__(self, con, session=None):
        self.con = con
        self.session = session or requests.Session()
        self.key = load_key()
        self.stats = {"hit_cache": 0, "api": 0, "ok": 0, "fail": 0, "no_key": 0, "ai_call": 0, "ai_ok": 0}
        self._transient = False
        self.last_full = ""  # 직전 변환 성공 건의 정식 주소(시도 시군구 읍면 리 지번). 소재지가 깨졌어도 카카오가 바로잡은 값
        from core.ai_fix import AiFixer
        self.ai = AiFixer(self)
        con.execute(
            "CREATE TABLE IF NOT EXISTS cache.pnu_cache (query TEXT PRIMARY KEY, pnu TEXT, status TEXT, resolved_at TEXT, full TEXT)"
        )
        if "full" not in [r[1] for r in con.execute("PRAGMA cache.table_info(pnu_cache)")]:
            con.execute("ALTER TABLE cache.pnu_cache ADD COLUMN full TEXT")  # 예전 캐시 파일 호환

    def _call(self, query):
        data, state = self._call_raw(query)
        if state != "ok":
            self._transient = True  # 네트워크/인증 문제: 주소 탓이 아니므로 '영구 실패'로 보지 않는다
        return data, state

    def _call_raw(self, query):
        for attempt in range(3):
            try:
                r = self.session.get(KAKAO_URL, headers={"Authorization": f"KakaoAK {self.key}"},
                                     params={"query": query}, timeout=10)
                if r.status_code == 429:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                if r.status_code in (401, 403):
                    return None, "auth_error"  # 키 문제는 캐시하지 않는다
                r.raise_for_status()
                return r.json(), "ok"
            except requests.RequestException:
                time.sleep(1.0 * (attempt + 1))
        return None, "net_error"

    @staticmethod
    def _full_address(a, mountain, main, sub):
        """카카오 주소 문서 -> '제주특별자치도 서귀포시 안덕면 상창리 1995' 형태의 정식 주소.
        문서에 리만(또는 시군구가 틀리게) 적혀 있어도 카카오가 시도·시군구·읍면·리를 모두 채워 준다."""
        r1 = SIDO_FULL.get(a.get("region_1depth_name", ""), a.get("region_1depth_name", ""))
        parts = [r1, a.get("region_2depth_name", ""), a.get("region_3depth_name", "")]
        tail = f"{'산' if mountain else ''}{main}" + (f"-{sub}" if sub else "")
        return " ".join(x for x in parts + [tail] if x)

    @staticmethod
    def region_ok_for(sojaeji, full):
        """소재지에 적힌 시군구가 카카오 정식 주소('경기도 광주시 송정동 528-15')의 시군구 부분과 같은가(감사용)."""
        return region_agrees(sojaeji, " ".join(full.split()[:3]))

    @staticmethod
    def _match(doc, want):
        """카카오 문서 1건이 질의한 지번과 일치하면 (PNU, 시도, 시군구, 정식 주소) 아니면 None."""
        a = doc.get("address")
        if not a or not a.get("b_code"):
            return None
        mountain = a.get("mountain_yn") == "Y"
        try:
            main, sub = int(a.get("main_address_no") or 0), int(a.get("sub_address_no") or 0)
        except ValueError:
            return None
        if want and (want[0] != mountain or want[1] != main or want[2] != sub):
            return None
        pnu = f"{a['b_code'][:10]}{'2' if mountain else '1'}{main:04d}{sub:04d}"
        full = PnuResolver._full_address(a, mountain, main, sub)
        return pnu, a.get("region_1depth_name", ""), a.get("region_2depth_name", ""), full

    @staticmethod
    def _fallback_query(sojaeji, jibun):
        """시도·시군구가 틀리게 조립된 소재지(PDF 표 열 섞임: '종시연서면', 제주 '제주시 남원리'(실제는 서귀포시),
        부산 '연제구 금곡동'(실제는 북구) 등)에서 시군구를 버리고 시도 + 읍면동·리 + 지번만으로 질의를 만든다.
        읍면 이름은 끝 3글자(두 글자+읍/면)만 믿고, 앞에 붙은 잘못된 글자는 버린다. 시도는 남겨 후보를 좁힌다."""
        words = (sojaeji or "").split()
        eup = ri = ""
        for w in words:
            if re.fullmatch(r"[가-힣]{2,}[읍면]", w) or re.fullmatch(r"[가-힣0-9]{1,}동", w) and not eup:
                eup = w[-3:] if w[-1] in "읍면" and len(w) > 3 else w
            elif re.fullmatch(r"[가-힣0-9]+리", w) and len(w) >= 2:
                ri = w
        p = parse_jibun(jibun)
        if not ((eup or ri) and p):
            return ""
        sido = words[0] if words and re.search(r"(특별시|광역시|특별자치시|특별자치도|도)$", words[0]) else ""
        tail = f"{'산' if p[0] else ''}{p[1]}" + (f"-{p[2]}" if p[2] else "")
        return " ".join(x for x in (sido, eup, ri, tail) if x)

    def _abbrev_lookup(self, sojaeji, jibun, city, want):
        """'덕산 화상'(읍면 빠짐)·'마곡'(리 접미사 빠짐)처럼 축약된 소재지: 지자체(시·군·구) 이름을 앞에 붙이고
        읍/면 + 리(또는 리/동만)를 채워 질의한다. 소재지 끝에 지번이 붙어 있어도 떼고 본다."""
        base = re.sub(r"(?:\s+산?\s*\d+(?:-\d+)?)+$", "", (sojaeji or "").strip())  # '하빈 무등 1238 1238-2'(분할 전·후 지번이 붙음) -> '하빈 무등'
        words = base.split()
        if words and re.search(r"(특별시|광역시|특별자치시|특별자치도|도)$", words[0]):
            words = words[1:]  # '충청북도 단양군 당동' 처럼 시도·시군구가 이미 앞에 붙은 축약형(면이 빠진 리)
        if words and city and words[0] == city:
            words = words[1:]
        if not (1 <= len(words) <= 2) or not city or not city.endswith(("시", "군", "구")) or not want:
            return None
        if not all(re.fullmatch(r"[가-힣]{1,5}", w) for w in words):
            return None
        tail = f"{'산' if want[0] else ''}{want[1]}" + (f"-{want[2]}" if want[2] else "")
        if len(words) == 1:
            a = words[0]
            if a[-1] in "읍면리":
                return None
            if a[-1] == "동":  # '당동'(실제 당동리): 동으로 읽은 질의는 본 질의가 이미 했으므로 리 접미사만 더 시도한다
                queries = [f"{city} {a}리 {tail}"]
            else:
                queries = [f"{city} {a}리 {tail}", f"{city} {a}동 {tail}"]
        else:
            a, b = words
            if b.endswith("리") or a[-1] in "읍면동":
                return None
            queries = [f"{city} {a}{es} {b}{'' if es == '동' else '리'} {tail}" for es in ("읍", "면", "동")]
        for q in queries:
            data, state = self._call(q)
            self.stats["api"] += 1
            if state != "ok":
                return None
            for d in data.get("documents", []):
                m = self._match(d, want)
                if m:
                    self.last_full = m[3]
                    return m[0]
        return None

    def resolve(self, sojaeji, jibun, context="", city="", jimok=""):
        """-> PNU 19자리 문자열 또는 None.
        1차: 소재지+지번 그대로. 실패하면 2차: 읍면동·리·지번만으로 전국 검색해 지번이 일치하고 후보가 하나로 정해질 때만 인정
        (여러 지역에 같은 이름이 있으면 context(게시글 제목 등)에 나오는 시도·시군구로 가린다)."""
        sojaeji = apply_aliases(sojaeji, city)  # 사용자가 확인한 지명 바로잡기(place_aliases.json)
        query = build_query(sojaeji, jibun)
        if not query:
            self.stats["fail"] += 1
            return None
        row = self.con.execute("SELECT pnu, status, full FROM cache.pnu_cache WHERE query=?", (query,)).fetchone()
        if row and (row[0] and row[2] or row[1] == "no_match_v4"):  # 예전 실패 캐시(no_match)·정식 주소 없는 캐시는 다시 시도한다
            self.stats["hit_cache"] += 1
            self.stats["ok" if row[0] else "fail"] += 1
            self.last_full = row[2] or ""
            return row[0]
        if not self.key:
            self.stats["no_key"] += 1
            return None
        want = parse_jibun(jibun)
        data, state = self._call(query)
        self.stats["api"] += 1
        if state != "ok":
            self.stats["fail"] += 1
            return None  # 일시 오류는 캐시하지 않아 다음 실행에서 재시도
        pnu, status, full = None, "no_match_v4", ""
        for d in data.get("documents", []):
            m = self._match(d, want)
            if m and region_agrees(sojaeji, m[2]):
                pnu, status, full = m[0], "ok", m[3]
                break
        if not pnu:
            fixed = repair_concat_sigun(sojaeji, context)  # '택시안중읍'(실제 평택시 안중읍): 글자가 붙고 빠진 시군을 제목으로 되살린다
            if fixed != sojaeji:
                data_f, state_f = self._call(build_query(fixed, jibun))
                self.stats["api"] += 1
                if state_f == "ok":
                    for d in data_f.get("documents", []):
                        m = self._match(d, want)
                        if m:
                            pnu, status, full = m[0], "ok_repair", m[3]
                            break
        if not pnu:
            pnu = self._abbrev_lookup(sojaeji, jibun, city, want)
            if pnu:
                status, full = "ok_abbrev", self.last_full
        if not pnu:
            fq = self._fallback_query(sojaeji, jibun)
            if fq and fq != query:
                data2, state2 = self._call(fq)
                self.stats["api"] += 1
                if state2 != "ok":
                    self.stats["fail"] += 1
                    return None
                cands = {}
                for d in data2.get("documents", []):
                    m = self._match(d, want)
                    if m:
                        cands[m[0]] = m
                if len(cands) > 1:  # 같은 읍면·리 이름이 여러 곳 -> 제목/문맥에 나온 지역으로 가린다
                    ctx = f"{context} {city or ''}"  # 제목에 지역이 없어도 수집한 지자체(city)로 가린다('의정부동' 이 여러 곳일 때)
                    hit = [m for m in cands.values()
                           if any(x and re.sub(r"(특별자치시|특별자치도|광역시|특별시|도|시|군|구)$", "", x) in ctx
                                  for x in m[1:3])]
                    cands = {m[0]: m for m in hit} if len(hit) == 1 else {}
                if len(cands) == 1:
                    pnu = next(iter(cands))
                    if city and city.endswith(("시", "군")) and not region_agrees(city, cands[pnu][2]):
                        pnu = None  # 수집한 지자체(city)와 다른 시군의 같은 이름 동·리가 유일하다고 받으면 엉뚱한 지역이 된다
                    else:
                        status, full = "ok_fallback", cands[pnu][3]
        if not pnu:
            pnu = self._swap_eupmyeon(sojaeji, jibun, want)  # 읍·면 승격/개편으로 문서의 이름과 지금 이름이 다른 경우
            if pnu:
                status, full = "ok_swap", self.last_full
        if not pnu and re.search(r"[가-힣]\d동(?:\s|$)", sojaeji or ""):
            # 행정동 번호('남산3동')는 법정동('남산동')에 없다. 단, '대저2동'처럼 번호가 법정동 이름인 곳이 있어 원래 질의가 실패했을 때만 지운다
            stripped = re.sub(r"(?<=[가-힣])\d(?=동(?:\s|$))", "", sojaeji)
            data_s, state_s = self._call(build_query(stripped, jibun))
            self.stats["api"] += 1
            if state_s == "ok":
                for d in data_s.get("documents", []):
                    m = self._match(d, want)
                    if m and region_agrees(stripped, m[2]):
                        pnu, status, full = m[0], "ok_dongnum", m[3]
                        break
        if not pnu:
            pnu = self._ri_only_lookup(sojaeji, jibun, city, want)  # 읍·면이 틀리게 적힌 경우(시군 + 리 + 지번이 유일하게 맞을 때)
            if pnu:
                status, full = "ok_ri_only", self.last_full
        if not pnu and want and not want[0] and re.match(r"임", (jimok or "").strip()):
            # 지목이 임야(문서에 적힘)인데 지번에 '산'이 없다: 임야 대장 지번은 '산' 번호라 '산'을 붙여 다시 찾는다(카카오가 지번 일치를 확인)
            pnu = self.resolve(sojaeji, f"산{want[1]}" + (f"-{want[2]}" if want[2] else ""), context, city)
            if pnu:
                status, full = "ok_san", self.last_full
        self.last_full = full
        self.con.execute("INSERT OR REPLACE INTO cache.pnu_cache VALUES (?,?,?,datetime('now'),?)", (query, pnu, status, full))
        self.con.commit()
        self.stats["ok" if pnu else "fail"] += 1
        return pnu

    def _ri_only_lookup(self, sojaeji, jibun, city, want):
        """'공도읍 개정리'처럼 읍·면이 틀리게 적혔지만(실제 미양면 개정리) 시군 + 리 + 지번이 맞는 경우: 읍·면을 빼고 질의해
        리 이름과 지번(본번·부번·산)이 정확히 같은 후보가 단 하나일 때만 인정한다(같은 이름의 리가 여럿이면 포기)."""
        if not want:
            return None
        words = (sojaeji or "").split()
        ri = next((w for w in reversed(words) if re.fullmatch(r"[가-힣0-9]{1,6}리", w)), None)
        sigun = next((w for w in words if re.fullmatch(r"[가-힣]{1,5}[시군]", w)), None) or (city if city and city.endswith(("시", "군")) else None)
        if not ri or not sigun:
            return None
        tail = f"{'산' if want[0] else ''}{want[1]}" + (f"-{want[2]}" if want[2] else "")
        data, state = self._call(f"{sigun} {ri} {tail}")
        self.stats["api"] += 1
        if state != "ok":
            return None
        stem = re.sub(r"(시|군)$", "", sigun)
        cands = {}
        for d in data.get("documents", []):
            m = self._match(d, want)
            a = d.get("address") or {}
            if m and stem in m[2] and (a.get("region_3depth_name") or "").endswith(ri):
                cands[m[0]] = m
        if len(cands) == 1:
            m = next(iter(cands.values()))
            self.last_full = m[3]
            return m[0]
        return None

    def _swap_eupmyeon(self, sojaeji, jibun, want):
        """'일로면 망월리'처럼 읍·면만 바뀐 이름(면이 읍으로 승격된 경우 등)을 서로 바꿔 질의한다.
        리 이름과 지번(본번·부번·산)이 카카오 결과와 정확히 같을 때만 인정한다."""
        if not want:
            return None
        words = (sojaeji or "").split()
        for i, w in enumerate(words):
            if re.fullmatch(r"[가-힣]{2,4}[읍면]", w):
                other = w[:-1] + ("읍" if w.endswith("면") else "면")
                q = build_query(" ".join(words[:i] + [other] + words[i + 1:]), jibun)
                data, state = self._call(q)
                self.stats["api"] += 1
                if state != "ok":
                    return None
                for d in data.get("documents", []):
                    m = self._match(d, want)
                    if m:
                        self.last_full = m[3]
                        return m[0]
        return None
    def _from_ri_code(self, sojaeji, jibun, city):
        """카카오가 '리/동' 단위까지는 찾는데 그 안의 개별 지번은 지도 DB 에 없을 때(분할·신규 필지 등):
        리의 법정동코드(10자리) + 대지/산 + 본번 + 부번 으로 PNU 를 직접 만든다. 지번 존재는 확인된 것이 아니므로
        호출한 쪽이 verified=0 으로 표시한다. 리가 하나로 정해지고 지자체가 맞을 때만 인정한다."""
        want = parse_jibun(jibun)
        if not want:
            return None
        base = re.sub(r"\s*(산)?\s*\d+(?:-\d+)?$", "", (sojaeji or "").strip())
        words = base.split()
        if len(words) < 2 or not re.search(r"[가-힣0-9]{1,6}[리동가]$", words[-1]):
            return None
        stem = re.sub(r"(특별자치시|특별시|광역시|시|군|구)$", "", city or "")
        constrain = bool(city) and city.endswith(("시", "군", "구")) and len(stem) >= 2
        # 1차: 소재지 그대로. 2차: 시군구가 틀리게 적힌 경우(제주시 남원리 등)를 대비해 시도 + 읍면 + 리만으로
        alt = self._fallback_query(base, jibun)
        alt = re.sub(r"\s*(산)?\d+(?:-\d+)?$", "", alt).strip()
        for q, strict in ((base, True), (alt, False)):
            if not q or (q == base and not strict):
                continue
            data, state = self._call(q)
            self.stats["api"] += 1
            if state != "ok":
                return None
            codes, fulls = set(), {}
            for d in data.get("documents", []):
                a = d.get("address")
                if not a or len(a.get("b_code") or "") < 10 or not a.get("region_3depth_name", "").endswith(words[-1][-2:]):
                    continue
                if a.get("main_address_no"):
                    continue  # 리 단위 결과만(번지가 붙은 결과는 위 단계에서 이미 처리됨)
                if strict and constrain and stem not in a.get("region_2depth_name", ""):
                    continue
                codes.add(a["b_code"][:10])
                fulls[a["b_code"][:10]] = self._full_address(a, want[0], want[1], want[2])
            if len(codes) == 1:
                code = codes.pop()
                self.last_full = fulls[code]
                return f"{code}{'2' if want[0] else '1'}{want[1]:04d}{want[2]:04d}"
        return None

    def _ri_code_bare(self, sojaeji, jibun, city):
        """접미사가 빠진 리 이름('당동'=당동리, '양촌 임화'=양촌면 임화리)은 리 단위 질의를 못 만들어 리 코드 조립이 건너뛰어졌다.
        지자체(시·군) 이름을 앞에 붙이고 리·면 접미사를 채워 리 코드 조립(_from_ri_code)을 다시 시도한다. 리가 하나로 정해질 때만 인정."""
        if not city or not city.endswith(("시", "군")) or not parse_jibun(jibun):
            return None
        base = re.sub(r"\s*(산)?\s*\d+(?:-\d+)?$", "", (sojaeji or "").strip())
        words = base.split()
        if words and re.search(r"(특별시|광역시|특별자치시|특별자치도|도)$", words[0]):
            words = words[1:]
        if words and words[0] == city:
            words = words[1:]
        if not words or len(words) > 2 or not all(re.fullmatch(r"[가-힣]{1,5}", w) for w in words):
            return None
        if len(words) == 1:
            a = words[0]
            if a[-1] in "읍면리":
                return None
            variants = [f"{city} {a}리"]
        else:
            a, b = words
            if b.endswith("리") or a[-1] in "읍면동":
                return None
            variants = [f"{city} {a}{es} {b}리" for es in ("면", "읍")]
        for v in variants:
            pnu = self._from_ri_code(v, jibun, city)
            if pnu:
                return pnu
        return None

    def resolve_full(self, sojaeji, jibun, context="", city="", title="", project="", jimok=""):
        """-> (PNU 또는 None, 사유). 사유: ok / ok_ai / ok_ri(리 코드로 직접 조립, 지번 존재 미확인) / no_jibun / no_region(소재지 없음) / no_key / transient / no_match.
        규칙 변환이 모두 실패하면 DeepSeek 보정을 한 번 시도한다(카카오 검증을 통과한 것만 인정)."""
        self._transient = False
        self.last_full = ""
        if not re.search(r"[가-힣]", re.sub(r"(?:^|\s)산(?=\s*\d)", " ", sojaeji or "")) and parse_jibun(jibun):
            return None, "no_region"  # 소재지가 지번뿐(추출 단계 문제). 주소 변환으로는 고칠 수 없어 재시도 대상이 아니다
        if looks_like_non_parcel(sojaeji):
            return None, "not_parcel"  # '합 계 3'·'(2필지) 3'·'허가일로부터 10' 같은 필지가 아닌 행(재시도해도 같다)
        pnu = self.resolve(sojaeji, jibun, context, city, jimok)
        if pnu:
            return pnu, "ok"
        if not build_query(sojaeji, jibun):
            return None, "no_jibun"
        if not self.key:
            return None, "no_key"
        if self._transient:
            return None, "transient"
        if self.ai.enabled:
            pnu = self.ai.fix(sojaeji, jibun, city, title, project)
            if pnu:
                self.con.execute("INSERT OR REPLACE INTO cache.pnu_cache VALUES (?,?,?,datetime('now'),?)",
                                 (build_query(sojaeji, jibun), pnu, "ok_ai", self.last_full))
                self.con.commit()
                return pnu, "ok_ai"
            if self._transient:
                return None, "transient"
        pnu = self._from_ri_code(sojaeji, jibun, city) or self._ri_code_bare(sojaeji, jibun, city)
        if pnu:
            self.con.execute("INSERT OR REPLACE INTO cache.pnu_cache VALUES (?,?,?,datetime('now'),?)",
                             (build_query(sojaeji, jibun), pnu, "ok_ri", self.last_full))
            self.con.commit()
            return pnu, "ok_ri"
        if self._transient:
            return None, "transient"
        return None, "no_match"
