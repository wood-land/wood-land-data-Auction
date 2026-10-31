# -*- coding: utf-8 -*-
"""
common/pnu_resolver.py - 기사 내 주소 완성, 19자리 PNU 발급(Kakao/VWorld), SQLite 저장 파이프라인

기능:
1. 불완전 주소('지정면 신평리 400' 등)를 주소 자체 > 신문사/지역힌트 > 읍·면 사전 > 기사 본문 순으로 단서를 써서
   온전한 한국식 표준 주소로 복원한다. (시군구가 불확실하면 후보를 여러 개 만들어 차례로 조회한다)
2. Kakao Local API 및 VWorld Geocoder API를 호출하여 19자리 토지 고유번호(PNU) 및 좌표를 얻는다.
   응답 필지의 지번(본번·부번·산 여부)과 시군구가 요청과 같은지 확인하므로, 비슷한 다른 필지가 잘못 채택되지 않는다.
3. 중복 API 호출 방지를 위한 SQLite 캐시와 영구 저장소(articles, article_addresses)를 관리한다.
   - 성공은 계속 캐시, 실패(NOT_FOUND)는 주소 완성 로직 버전(NEWS_RESOLVER_VERSION)이 같고 30일 이내일 때만 재사용한다.
   - 일시 오류(ERROR)는 캐시하지 않는다.

주소에 어떤 근거로 시군구를 붙였는지는 basis 컬럼에 남긴다.
  explicit(주소에 적혀 있음) / hint(신문사·지역힌트) / eupmyeon(읍·면 사전) / context(기사 본문 추정)
  / province(시·도 + 읍·면 이름만으로 조회: 시군구를 응답에서 확인)
  → eupmyeon·context·province 는 시군구를 추정한 것이므로, 정확도가 중요한 용도에서는 거를 수 있다.
시·도도 시군구도 알 수 없는 주소는 조회하지 않는다(동명 지역의 엉뚱한 필지가 채택되는 것을 막기 위함).
"""

import hashlib
import os
import re
import sqlite3
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple
import requests

from common.admin_names import (  # noqa: F401  (다른 모듈이 예전처럼 pnu_resolver 에서 가져다 쓸 수 있게 다시 내보낸다)
    AMBIGUOUS_SIGUNGU, EUP_MYEON_MAP, GENERAL_GU_PARENT, METRO_GU_MAP, NON_PLACE_DONGRI,
    PROVINCE_STANDARDIZATION, SHORT_SIGUNGU_MAP, SHORT_TO_SIGUNGU, SIGUNGU_TO_PROVINCE,
    PROVINCE_SHORT, VALID_SIGUNGU_NAMES, _AMBIGUOUS_GU, is_place_eupmyeon,
)

# API 엔드포인트 및 인증 키 (퍼블릭 리포이므로 키는 환경변수 / GitHub Secrets 로만 받는다)
KAKAO_URL = "https://dapi.kakao.com/v2/local/search/address.json"
VWORLD_URL = "http://api.vworld.kr/req/address"

# 주소 완성 로직 버전: 로직을 고쳐 실패 캐시를 다시 시도해야 할 때 올린다.
NEWS_RESOLVER_VERSION = 2
NOT_FOUND_TTL_DAYS = 30        # NOT_FOUND 캐시를 믿는 기간
MAX_CANDIDATES = 5             # 주소 1건당 조회해 볼 후보 주소의 최대 개수
CONTEXT_CHARS = 600            # 시군구 단서를 찾을 기사 본문 길이


def _kakao_key() -> str:
    return os.environ.get("KAKAO_REST_API_KEY", "")


def _vworld_key() -> str:
    return os.environ.get("VWORLD_API_KEY", "")


if not _kakao_key() or not _vworld_key():
    print("[경고] KAKAO_REST_API_KEY / VWORLD_API_KEY 환경변수가 없습니다. PNU 발급이 실패할 수 있습니다.")


def build_context(title: str = "", body: str = "") -> str:
    """시군구 단서를 찾는 기사 문맥 (제목 + 본문 앞부분). 정제 단계와 PNU 단계가 같은 문맥을 쓰도록 한 곳에서 만든다."""
    return f"{title or ''} {(body or '')[:CONTEXT_CHARS]}".strip()


@dataclass
class PNUResult:
    raw_address: str
    completed_address: str
    pnu: Optional[str]
    source: str          # 'kakao' | 'vworld' | 'cache(...)' | 'none'
    status: str          # 'SUCCESS' | 'NOT_FOUND' | 'ERROR'
    x: Optional[float] = None
    y: Optional[float] = None
    standard_name: str = ""
    error_message: str = ""
    basis: str = ""      # 시군구를 정한 근거: explicit | hint | eupmyeon | context | province


def extract_numbers_and_mountain(addr: str) -> Tuple[str, str, str]:
    """주소 문자열에서 본번(4자리), 부번(4자리), 산구분('1'|'2') 추출"""
    mountain = "1"
    parts = re.split(r"(\d+-\d+|\d+)", addr or "")
    parts = [p.strip() for p in parts if p and p.strip()]
    if parts and re.match(r"\d+-\d+|\d+", parts[-1]):
        main_part = parts[-1]
        if "-" in main_part:
            main_no, sub_no = main_part.split("-", 1)
            sub_no = sub_no.zfill(4)
        else:
            main_no = main_part
            sub_no = "0000"
        main_no = main_no.zfill(4)
        if len(parts) > 1 and parts[-2].endswith("산"):
            mountain = "2"
        return main_no, sub_no, mountain
    return "0000", "0000", mountain


# ============================ 주소 해석 ============================
@dataclass
class ParsedAddress:
    prov: str = ""                                   # 주소에 적힌 시·도 (표준 명칭)
    sg: List[str] = field(default_factory=list)      # 주소에 적힌 시·군·구 (예: ['포항시', '북구'])
    eup: str = ""                                    # 읍/면
    dongri: str = ""                                 # 동/리 (또는 '3가')
    mountain: bool = False
    main: int = 0
    sub: int = 0
    junk: List[str] = field(default_factory=list)    # 주소 앞에 섞인 지명 아닌 낱말 ('사업지구' 등)

    @property
    def lot_text(self) -> str:
        num = f"{self.main}-{self.sub}" if self.sub else f"{self.main}"
        return f"산 {num}" if self.mountain else num


def _normalize_address(raw: str) -> str:
    a = re.sub(r"\s+", " ", raw or "").strip()
    a = re.sub(r"\s*번지\s*$", "", a)
    a = re.sub(r"(?<=[동리가])(?=\d)", " ", a)        # '원계리388' -> '원계리 388'
    a = re.sub(r"(\d)\s*-\s*(\d)", r"\1-\2", a)
    return a


def parse_address(raw: str) -> Optional[ParsedAddress]:
    """기사에서 뽑은 주소 문자열을 구성 요소로 나눈다. 동/리 + 지번이 없으면 None (주소가 아닌 것)."""
    a = _normalize_address(raw)
    m = re.search(r"(산\s*)?(\d{1,4})(?:-(\d{1,4}))?$", a)
    if not m:
        return None
    parsed = ParsedAddress(mountain=bool(m.group(1)), main=int(m.group(2)), sub=int(m.group(3) or 0))
    toks = a[:m.start()].split()
    if not toks:
        return None
    last = toks[-1]
    if not (re.fullmatch(r"[가-힣]+(?:동|리)", last) or re.fullmatch(r"[가-힣]+\d가", last)):
        return None
    if last in NON_PLACE_DONGRI:
        return None
    parsed.dongri = last
    toks = toks[:-1]
    if toks and is_place_eupmyeon(toks[-1]):
        parsed.eup = toks.pop()
    for i, t in enumerate(toks):
        if t == "광주시" and i + 1 < len(toks) and toks[i + 1] in METRO_GU_MAP["광주광역시"]:
            t = "광주광역시"          # '광주시 북구 일곡동' 의 광주시는 경기도 광주시가 아니라 광주광역시
        if t in PROVINCE_STANDARDIZATION and not parsed.sg:
            parsed.prov = PROVINCE_STANDARDIZATION[t]
        elif t in VALID_SIGUNGU_NAMES and len(parsed.sg) < 2:
            parsed.sg.append(t)
        else:
            parsed.junk.append(t)
    return parsed


def parse_hint(*texts: str) -> Tuple[str, List[str]]:
    """지역힌트(예: '충청 충남 천안', '함양군', '경상남도')에서 (시·도, [시·군·구...]) 를 뽑는다."""
    prov = ""
    sg: List[str] = []
    for w in re.split(r"[\s,/·|;]+", " ".join(t for t in texts if t)):
        if not w:
            continue
        if w in PROVINCE_STANDARDIZATION:
            prov = prov or PROVINCE_STANDARDIZATION[w]
        elif w in VALID_SIGUNGU_NAMES:
            sg.append(w)
        elif w in SHORT_TO_SIGUNGU:
            sg.append(SHORT_TO_SIGUNGU[w])
    return prov, sg


def _province_of(sgg: str, prefer: str = "") -> str:
    """시/군의 시·도. 이름이 겹치는 시/군(고성군 등)은 prefer(다른 단서의 시·도)와 맞는 쪽을 고른다."""
    names = AMBIGUOUS_SIGUNGU.get(sgg) or ([SIGUNGU_TO_PROVINCE[sgg]] if sgg in SIGUNGU_TO_PROVINCE else [])
    if not names:
        return ""
    return prefer if prefer in names else names[0]


def _metro_of_gu(gu: str) -> str:
    owners = [p for p, gus in METRO_GU_MAP.items() if gu in gus]
    return owners[0] if len(owners) == 1 else ""


def _normalize_chain(chain: List[str], prov_pref: str, hint_sg: List[str]) -> Tuple[List[str], str]:
    """시군구 목록을 '시 [구]' 형태로 바로잡고 시·도를 정한다."""
    first = chain[0]
    if first[-1] in "시군":
        return chain, _province_of(first, prov_pref)
    # 구 이름만 있는 경우
    if len(chain) == 1:
        gu = first
        if gu in GENERAL_GU_PARENT and gu not in _AMBIGUOUS_GU:          # 의창구 -> 창원시 의창구
            parent = GENERAL_GU_PARENT[gu]
            return [parent, gu], _province_of(parent, prov_pref)
        if gu in _AMBIGUOUS_GU and ("포항시" in hint_sg or prov_pref == "경상북도"):   # 포항 남구/북구
            return ["포항시", gu], "경상북도"
        if prov_pref in METRO_GU_MAP and gu in METRO_GU_MAP[prov_pref]:
            return chain, prov_pref
        return chain, _metro_of_gu(gu) or prov_pref
    return chain, prov_pref


def _hint_chain(hint_sg: List[str]) -> List[str]:
    """지역힌트의 시군구 목록에서 '시/군 [구]' 하나를 고른다."""
    for i, name in enumerate(hint_sg):
        if name[-1] in "시군":
            nxt = hint_sg[i + 1] if i + 1 < len(hint_sg) else ""
            return [name, nxt] if nxt and nxt[-1] == "구" else [name]
    return [hint_sg[0]] if hint_sg else []


_SI_GUN_NAMES = sorted((n for n in VALID_SIGUNGU_NAMES if n[-1] in "시군"), key=len, reverse=True)


def context_sigungu(context: str, prov: str = "") -> List[Tuple[str, List[str]]]:
    """기사 문맥에 나온 시·군·구 이름을 (많이 나온 순, 먼저 나온 순) 으로 돌려준다. [(시·도, [시군구])]
    '집중호우시'처럼 지명이 아닌 낱말이 시로 끝나는 경우는 이름 사전으로 걸러진다."""
    if not context:
        return []
    ranked: List[Tuple[int, int, str]] = []
    for name in _SI_GUN_NAMES:
        hits = [m.start() for m in re.finditer(r"(?<![가-힣])" + re.escape(name), context)]
        if not hits:
            continue
        names = AMBIGUOUS_SIGUNGU.get(name) or [SIGUNGU_TO_PROVINCE.get(name, "")]
        if prov and prov not in names:
            continue
        if name == "광주시" and prov == "광주광역시":      # 광주광역시 기사의 '광주시'는 광주광역시 자신 (경기 광주시 아님)
            continue
        ranked.append((-len(hits), hits[0], name))
    ranked.sort()
    out: List[Tuple[str, List[str]]] = [(_province_of(n, prov), [n]) for _, _, n in ranked]
    if not out and prov in METRO_GU_MAP:             # 광역시: 문맥에 나온 구
        gus = []
        for gu in METRO_GU_MAP[prov]:
            hits = [m.start() for m in re.finditer(r"(?<![가-힣])" + re.escape(gu), context)]
            if hits:
                gus.append((-len(hits), hits[0], gu))
        out = [(prov, [gu]) for _, _, gu in sorted(gus)]
    return out


def _assemble(prov: str, chain: List[str], eup: str, dongri: str, lot: str) -> str:
    return re.sub(r"\s+", " ", " ".join(x for x in [prov, *chain, eup, dongri, lot] if x)).strip()


def complete_korean_address_candidates(raw_addr: str, area_hint: str = "", paper: str = "",
                                       default_area: str = "", context_text: str = "",
                                       max_candidates: int = MAX_CANDIDATES) -> List[Tuple[str, str]]:
    """불완전 주소를 조회용 표준 주소 후보로 만든다. [(완성주소, 근거)] 가장 믿을 만한 것이 앞.
    주소가 아닌 것(동/리 + 지번이 없음)이면 빈 목록.

    시군구를 정하는 우선순위
      1. 주소 자체에 적힌 시·군·구 (다른 단서와 충돌해도 이것을 믿는다: '포항시 북구'는 대구 힌트가 있어도 경북)
      2. 신문사 기본지역·지역힌트의 시·군·구
      3. 읍·면 이름 사전 (주소/힌트에 시·도가 있으면 그것과 맞을 때만)
      4. 기사 문맥에 가장 많이 나온 시·군·구 (여러 개면 차례로 후보)
    """
    p = parse_address(raw_addr)
    if p is None:
        return []
    hprov, hsg = parse_hint(default_area, area_hint)
    prov_pref = p.prov or hprov
    plans: List[Tuple[str, List[str], str]] = []      # (시·도, 시군구, 근거)

    if p.sg:                                                          # 1. 주소에 명시
        chain, prov = _normalize_chain(list(p.sg), prov_pref, hsg)
        plans.append((prov or prov_pref, chain, "explicit"))
    else:
        hchain = _hint_chain(hsg)                                     # 2. 힌트
        if hchain:
            chain, prov = _normalize_chain(hchain, prov_pref, hsg)
            if not (p.prov and prov and p.prov != prov):             # 주소의 시·도와 힌트 시군구의 시·도가 다르면 힌트를 버린다
                plans.append((prov or prov_pref, chain, "hint"))

    known_prov = prov_pref or (plans[0][0] if plans else "")
    if not p.sg:                                                      # 3, 4. 추정 후보 (주소에 시군구가 없을 때만)
        have = {tuple(pl[1]) for pl in plans}
        em = EUP_MYEON_MAP.get(p.eup)
        if em and (not known_prov or em[0] == known_prov) and tuple(em[1].split()) not in have:
            plans.append((em[0], em[1].split(), "eupmyeon"))
            have.add(tuple(em[1].split()))
        for prov, chain in context_sigungu(context_text, known_prov):
            if tuple(chain) not in have:
                plans.append((prov or known_prov, chain, "context"))
                have.add(tuple(chain))

    out: List[Tuple[str, str]] = []
    seen = set()

    def add(addr: str, basis: str):
        if addr not in seen:
            seen.add(addr)
            out.append((addr, basis))

    for prov, chain, basis in plans:
        add(_assemble(prov, chain, p.eup, p.dongri, p.lot_text), basis)
    # 마지막 대안: 시군구를 빼고 '시·도 + 읍/면 + 동/리 + 지번' 으로 조회. 힌트의 시군구가 틀렸을 때(예: 진주신문에 실린
    # 의령군 궁류면) 읍/면 이름이 시군구를 알려 준다. 읍/면을 빼고 시군구만으로 조회하는 대안은 두지 않는다 —
    # 다른 읍/면의 같은 이름 리가 우연히 같은 지번이면 엉뚱한 필지를 채택하게 된다.
    if known_prov and p.eup and not p.sg:
        add(_assemble(known_prov, [], p.eup, p.dongri, p.lot_text), "province")
    if not out and known_prov:                                        # 시·도만 아는 경우 (예: 경남일보)
        add(_assemble(known_prov, [], "", p.dongri, p.lot_text), "province")
    return out[:max_candidates]               # 시·도도 시군구도 모르면 빈 목록 (조회하지 않는다)


def complete_korean_address(raw_addr: str, area_hint: str = "", paper: str = "",
                            default_area: str = "", context_text: str = "") -> str:
    """기사 내 축약/불완전 주소('영동읍 계산리 583-11번지' 등)를 표준 주소로 완성 (가장 믿을 만한 후보 1개).
    주소가 아니면 빈 문자열."""
    cands = complete_korean_address_candidates(raw_addr, area_hint, paper, default_area, context_text)
    return cands[0][0] if cands else ""


# ============================ 지번 검증 / API 호출 ============================
@dataclass
class LotExpect:
    """요청한 필지. API 응답이 이것과 같을 때만 채택한다."""
    mountain: bool
    main: int
    sub: int
    sigungu: Tuple[str, ...] = ()
    province: str = ""        # 시군구 없이 조회한 경우에만 지정: 응답이 이 시·도 안인지 확인한다

    def accepts(self, mountain: bool, main: int, sub: int, address_text: str) -> bool:
        if (mountain, main, sub) != (self.mountain, self.main, self.sub):
            return False
        text = address_text or ""
        if self.province and not (text.startswith(self.province) or text.startswith(PROVINCE_SHORT.get(self.province, self.province))):
            return False
        return all(tok in text for tok in self.sigungu)


def expect_from_address(completed: str) -> Optional[LotExpect]:
    p = parse_address(completed)
    return LotExpect(p.mountain, p.main, p.sub, tuple(p.sg), "" if p.sg else p.prov) if p else None


def _get_json(session: requests.Session, url: str, *, params: dict, headers: Optional[dict] = None,
              timeout: int = 10, tries: int = 3) -> dict:
    """GET + JSON. 429/5xx/네트워크 오류는 잠시 쉬었다 다시 시도하고, 인증 오류 등 4xx는 바로 실패시킨다."""
    last = ""
    for i in range(tries):
        try:
            r = session.get(url, params=params, headers=headers, timeout=timeout)
            if r.status_code == 429 or r.status_code >= 500:
                last = f"HTTP {r.status_code}"
                time.sleep(1.5 * (i + 1))
                continue
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code}")
            return r.json()
        except RuntimeError:
            raise
        except (requests.RequestException, ValueError) as e:
            last = f"{e.__class__.__name__}: {e}"
            time.sleep(1.0 * (i + 1))
    raise RuntimeError(last or "요청 실패")


def get_pnu_from_kakao(address: str, session: Optional[requests.Session] = None,
                       expect: Optional[LotExpect] = None) -> PNUResult:
    """Kakao Local API로 19자리 PNU 추출. expect 를 주면 응답 필지의 지번·시군구가 같은 것만 채택한다."""
    key = _kakao_key()
    if not key:
        return PNUResult(raw_address=address, completed_address=address, pnu=None, source="kakao",
                         status="ERROR", error_message="KAKAO_REST_API_KEY 없음")
    s = session or requests.Session()
    try:
        data = _get_json(s, KAKAO_URL, params={"query": address}, headers={"Authorization": f"KakaoAK {key}"})
    except Exception as e:
        return PNUResult(raw_address=address, completed_address=address, pnu=None,
                         source="kakao", status="ERROR", error_message=str(e))
    first_name = ""
    accepted: Dict[str, PNUResult] = {}
    for doc in data.get("documents") or []:
        info = doc.get("address")
        if not info:
            continue
        b_code = info.get("b_code") or ""
        name = info.get("address_name") or ""
        first_name = first_name or name
        if len(b_code) < 10:
            continue
        if info.get("mountain_yn") in ("Y", "N"):
            mountain = info["mountain_yn"] == "Y"
            main, sub = int(info.get("main_address_no") or 0), int(info.get("sub_address_no") or 0)
        else:
            main_s, sub_s, mt = extract_numbers_and_mountain(name or address)
            mountain, main, sub = mt == "2", int(main_s), int(sub_s)
        if expect and not expect.accepts(mountain, main, sub, name):
            continue
        pnu = f"{b_code[:10]}{'2' if mountain else '1'}{main:04d}{sub:04d}"
        x = float(doc["x"]) if doc.get("x") else None
        y = float(doc["y"]) if doc.get("y") else None
        accepted.setdefault(pnu, PNUResult(raw_address=address, completed_address=address, pnu=pnu, source="kakao",
                                           status="SUCCESS", x=x, y=y, standard_name=name))
    if len(accepted) == 1:
        return next(iter(accepted.values()))
    if len(accepted) > 1:       # 시군구를 못 정해 조회했더니 여러 지역에 같은 주소가 있다 -> 어느 쪽인지 알 수 없다
        names = " / ".join(r.standard_name for r in accepted.values())
        return PNUResult(raw_address=address, completed_address=address, pnu=None, source="kakao",
                         status="NOT_FOUND", error_message=f"같은 주소가 여러 곳에서 검색됨({names})")
    msg = f"응답 필지가 요청과 다름({first_name})" if first_name else "검색 결과 없음"
    return PNUResult(raw_address=address, completed_address=address, pnu=None,
                     source="kakao", status="NOT_FOUND", error_message=msg)


def get_pnu_from_vworld(address: str, session: Optional[requests.Session] = None,
                        expect: Optional[LotExpect] = None) -> PNUResult:
    """VWorld Geocoder API로 19자리 PNU 추출 (Kakao 에 없을 때의 폴백)"""
    key = _vworld_key()
    if not key:
        return PNUResult(raw_address=address, completed_address=address, pnu=None, source="vworld",
                         status="NOT_FOUND", error_message="VWORLD_API_KEY 없음")
    s = session or requests.Session()
    params = {
        "service": "address", "request": "getcoord", "version": "2.0", "crs": "epsg:4326",
        "address": address, "refine": "true", "simple": "false", "format": "json",
        "type": "PARCEL", "key": key,
    }
    try:
        data = _get_json(s, VWORLD_URL, params=params, timeout=15)
    except Exception as e:
        return PNUResult(raw_address=address, completed_address=address, pnu=None,
                         source="vworld", status="ERROR", error_message=str(e))
    resp = data.get("response", {})
    if resp.get("status") == "OK":
        refined = resp.get("refined", {})
        pnu = (refined.get("structure") or {}).get("level4LC", "")
        std_text = refined.get("text", "")
        pt = (resp.get("result") or {}).get("point") or {}
        if pnu and len(pnu) == 19 and pnu.isdigit():
            mountain, main, sub = pnu[10] == "2", int(pnu[11:15]), int(pnu[15:19])
            if not expect or expect.accepts(mountain, main, sub, std_text):
                return PNUResult(raw_address=address, completed_address=address, pnu=pnu, source="vworld",
                                 status="SUCCESS", x=float(pt["x"]) if pt.get("x") else None,
                                 y=float(pt["y"]) if pt.get("y") else None, standard_name=std_text)
            return PNUResult(raw_address=address, completed_address=address, pnu=None, source="vworld",
                             status="NOT_FOUND", error_message=f"응답 필지가 요청과 다름({std_text})")
    return PNUResult(raw_address=address, completed_address=address, pnu=None,
                     source="vworld", status="NOT_FOUND", error_message="VWorld 응답에 PNU 없음")


class PNUResolver:
    """
    주소 완성 + PNU 발급 + 캐싱 + SQLite 저장을 총괄하는 파이프라인 매니저
    """

    def __init__(self, db_path: str = "output/news_articles_pnu.db",
                 kakao_fn: Optional[Callable] = None, vworld_fn: Optional[Callable] = None):
        self.db_path = db_path
        self.session = requests.Session()
        self.kakao_fn = kakao_fn or get_pnu_from_kakao       # 테스트에서 가짜 조회 함수를 넣을 수 있다
        self.vworld_fn = vworld_fn or get_pnu_from_vworld
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            # 1. 기사 정보 테이블
            cur.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    link TEXT UNIQUE,
                    paper TEXT,
                    keyword TEXT,
                    title TEXT,
                    article_date TEXT,
                    area_hint TEXT,
                    raw_address_extracted TEXT,
                    content_hash TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # 컬럼 확인 및 추가 (기존 DB 마이그레이션 호환)
            cur.execute("PRAGMA table_info(articles)")
            cols = [row[1] for row in cur.fetchall()]
            if "content_hash" not in cols:
                cur.execute("ALTER TABLE articles ADD COLUMN content_hash TEXT")
            if "relevance_score" not in cols:
                cur.execute("ALTER TABLE articles ADD COLUMN relevance_score INTEGER")
            if "relevance_keywords" not in cols:
                cur.execute("ALTER TABLE articles ADD COLUMN relevance_keywords TEXT")

            # 2. 기사별 추출 주소 및 PNU 발급 내역 테이블
            cur.execute("""
                CREATE TABLE IF NOT EXISTS article_addresses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_link TEXT,
                    raw_address TEXT,
                    completed_address TEXT,
                    pnu TEXT,
                    source TEXT,
                    status TEXT,
                    standard_name TEXT,
                    x REAL,
                    y REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(article_link) REFERENCES articles(link)
                )
            """)
            cur.execute("PRAGMA table_info(article_addresses)")
            if "basis" not in [row[1] for row in cur.fetchall()]:
                cur.execute("ALTER TABLE article_addresses ADD COLUMN basis TEXT")
            # 3. 주소 -> PNU 고속 캐시 테이블
            cur.execute("""
                CREATE TABLE IF NOT EXISTS address_pnu_cache (
                    completed_address TEXT PRIMARY KEY,
                    pnu TEXT,
                    source TEXT,
                    standard_name TEXT,
                    x REAL,
                    y REAL,
                    status TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("PRAGMA table_info(address_pnu_cache)")
            if "ver" not in [row[1] for row in cur.fetchall()]:
                cur.execute("ALTER TABLE address_pnu_cache ADD COLUMN ver INTEGER")

            # 고속 검색 및 중복 방지용 인덱스
            cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_link ON articles(link)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_title ON articles(title)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_hash ON articles(content_hash)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_art_addr_pnu ON article_addresses(pnu)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_art_addr_link ON article_addresses(article_link)")
            conn.commit()

    def get_cached_pnu(self, completed_address: str) -> Optional[PNUResult]:
        """성공은 항상, 실패는 같은 로직 버전이고 30일 이내일 때만 돌려준다. 그 밖에는 None (다시 조회)."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT pnu, source, standard_name, x, y, status FROM address_pnu_cache "
                "WHERE completed_address = ? AND (status = 'SUCCESS' OR "
                "(status = 'NOT_FOUND' AND ver = ? AND updated_at >= datetime('now', ?)))",
                (completed_address, NEWS_RESOLVER_VERSION, f"-{NOT_FOUND_TTL_DAYS} days"))
            row = cur.fetchone()
            if row:
                pnu, source, std_name, x, y, status = row
                return PNUResult(
                    raw_address="",
                    completed_address=completed_address,
                    pnu=pnu,
                    source=f"cache({source})",
                    status=status,
                    x=x,
                    y=y,
                    standard_name=std_name or "",
                )
        return None

    def cache_pnu(self, res: PNUResult):
        """성공/NOT_FOUND 만 캐시한다. 일시 오류(ERROR)를 캐시하면 영영 재시도되지 않는다."""
        if not res.completed_address or res.status not in ("SUCCESS", "NOT_FOUND"):
            return
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO address_pnu_cache
                (completed_address, pnu, source, standard_name, x, y, status, updated_at, ver)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
            """, (res.completed_address, res.pnu, res.source, res.standard_name, res.x, res.y, res.status,
                  NEWS_RESOLVER_VERSION))
            conn.commit()

    def _lookup(self, completed: str) -> PNUResult:
        """후보 주소 1개를 Kakao -> VWorld 순으로 조회 (응답 필지 검증 포함)."""
        expect = expect_from_address(completed)
        res = self.kakao_fn(completed, session=self.session, expect=expect)
        if res.status == "SUCCESS" and res.pnu:
            return res
        v_res = self.vworld_fn(completed, session=self.session, expect=expect)
        if v_res.status == "SUCCESS" and v_res.pnu:
            return v_res
        if "ERROR" in (res.status, v_res.status):      # 한쪽이라도 일시 오류면 '없음'으로 단정하지 않는다
            return res if res.status == "ERROR" else v_res
        return res

    def resolve(self, raw_addr: str, area_hint: str = "", paper: str = "",
                default_area: str = "", context_text: str = "") -> PNUResult:
        """불완전 주소를 표준 주소 후보로 완성하고, 후보를 차례로 조회해 PNU를 발급 (캐시 -> Kakao -> VWorld)."""
        candidates = complete_korean_address_candidates(
            raw_addr, area_hint=area_hint, paper=paper, default_area=default_area, context_text=context_text)
        if not candidates:
            why = ("시·도와 시군구 단서가 없어 조회하지 않음" if parse_address(raw_addr) is not None
                   else "주소 형식 아님(동/리 + 지번이 없음)")
            return PNUResult(raw_address=raw_addr, completed_address=_normalize_address(raw_addr), pnu=None,
                             source="none", status="NOT_FOUND", basis="none", error_message=why)

        first_fail: Optional[PNUResult] = None
        error_res: Optional[PNUResult] = None
        for completed, basis in candidates:
            res = self.get_cached_pnu(completed)
            if res is None:
                res = self._lookup(completed)
                res.completed_address = completed
                self.cache_pnu(res)
            res.raw_address = raw_addr
            res.completed_address = completed
            res.basis = basis
            if res.status == "SUCCESS" and res.pnu:
                return res
            first_fail = first_fail or res
            if res.status == "ERROR":
                error_res = error_res or res
        # 일시 오류가 섞여 있으면 ERROR 로 돌려줘서 나중에 다시 시도되게 한다
        return error_res or first_fail

    def repair_failed_addresses(self, statuses: Tuple[str, ...] = ("NOT_FOUND", "ERROR"), limit: int = 0,
                                dry_run: bool = False, log: Callable[[str], None] = print) -> Dict[str, int]:
        """DB 에 이미 쌓인 실패 주소를 현재 로직으로 다시 조회해 고친다 (기사 제목·지역힌트·신문사를 단서로 사용).
        dry_run=True 면 DB 는 건드리지 않고 결과만 보여 준다."""
        marks = ",".join("?" for _ in statuses)
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(f"""
                SELECT aa.id, aa.article_link, aa.raw_address, aa.completed_address, aa.status,
                       COALESCE(a.area_hint, ''), COALESCE(a.paper, ''), COALESCE(a.title, '')
                FROM article_addresses aa LEFT JOIN articles a ON a.link = aa.article_link
                WHERE aa.status IN ({marks}) ORDER BY aa.id""", statuses).fetchall()
        if limit:
            rows = rows[:limit]
        stats = {"checked": 0, "fixed": 0, "still_failed": 0, "duplicates_removed": 0}
        for row_id, link, raw, old_completed, old_status, hint, paper, title in rows:
            res = self.resolve(raw, area_hint=hint, paper=paper, context_text=build_context(title))
            stats["checked"] += 1
            if res.status == "SUCCESS":
                stats["fixed"] += 1
                log(f"  ✔ [{paper}] '{raw}' : {old_completed} ({old_status}) → {res.completed_address} → {res.pnu} [{res.basis}]")
            else:
                stats["still_failed"] += 1
                log(f"  ✘ [{paper}] '{raw}' : {res.completed_address} → {res.error_message}")
            if dry_run:
                continue
            with sqlite3.connect(self.db_path) as conn:
                if res.status == "SUCCESS":
                    dup = conn.execute(
                        "SELECT 1 FROM article_addresses WHERE article_link = ? AND pnu = ? AND id != ? LIMIT 1",
                        (link, res.pnu, row_id)).fetchone()
                    if dup:           # 같은 기사에 같은 필지가 이미 있으면 이 행은 중복이다
                        conn.execute("DELETE FROM article_addresses WHERE id = ?", (row_id,))
                        stats["duplicates_removed"] += 1
                        continue
                conn.execute(
                    "UPDATE article_addresses SET completed_address=?, pnu=?, source=?, status=?, "
                    "standard_name=?, x=?, y=?, basis=? WHERE id=?",
                    (res.completed_address, res.pnu, res.source, res.status, res.standard_name,
                     res.x, res.y, res.basis, row_id))
                conn.commit()
        return stats

    def save_article_and_addresses(self, article: dict, address_results: List[PNUResult]) -> Tuple[int, int]:
        """기사 메타데이터와 발급된 PNU 내역을 SQLite에 트랜잭션으로 안전하게 저장.
        - 동일 지번 PNU에 동일한 내용(링크, 제목, 본문해시)의 신문기사는 중복 저장을 방지하여 1건만 유지.
        - 반환값: (저장된 주소 수, 중복 제외된 주소 수)
        """
        link = article.get("link", "").strip()
        if not link:
            return 0, 0

        title = article.get("title", "").strip()
        body = article.get("body", "").strip()

        # 기사 본문(또는 제목)을 정규화하여 중복 판별용 고유 해시 생성
        content_sample = body if len(body) > 30 else f"{title}\n{body}"
        norm_content = re.sub(r"\s+", "", content_sample)
        content_hash = hashlib.md5(norm_content.encode("utf-8")).hexdigest() if norm_content else ""

        saved_count = 0
        skipped_count = 0

        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            # 기사 본문 저장/갱신
            # 같은 기사를 다시 만나도 id 와 created_at(최초 수집 시각)을 지키고 나머지만 갱신한다.
            # (INSERT OR REPLACE 는 행을 지웠다 새로 넣어서 매번 '오늘 수집'으로 보였고, 신규 건수를 셀 수 없었다)
            cur.execute("""
                INSERT INTO articles
                (link, paper, keyword, title, article_date, area_hint, raw_address_extracted, content_hash,
                 relevance_score, relevance_keywords)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(link) DO UPDATE SET
                    paper = excluded.paper, keyword = excluded.keyword, title = excluded.title,
                    article_date = excluded.article_date, area_hint = excluded.area_hint,
                    raw_address_extracted = excluded.raw_address_extracted, content_hash = excluded.content_hash,
                    relevance_score = excluded.relevance_score, relevance_keywords = excluded.relevance_keywords
            """, (
                link,
                article.get("paper", ""),
                article.get("keyword", ""),
                title,
                article.get("date", ""),
                article.get("area", ""),
                article.get("address_extracted", ""),
                content_hash or None,
                article.get("relevance_score"),
                article.get("relevance_keywords", ""),
            ))

            # 동일 기사 호출 내 배치 중복 방지
            seen_in_batch = set()

            # 주소 발급 결과 저장 (동일 PNU + 동일 기사 중복 방지)
            for r in address_results:
                pnu_val = (r.pnu or "").strip()
                completed_val = (r.completed_address or "").strip()
                raw_val = (r.raw_address or "").strip()

                batch_key = (pnu_val if pnu_val else completed_val, raw_val)
                if batch_key in seen_in_batch:
                    skipped_count += 1
                    continue
                seen_in_batch.add(batch_key)

                # A. 유효한 PNU가 발급된 경우:
                #    DB에 동일한 PNU이면서 동일 기사(링크, 제목, 또는 본문 해시)가 이미 있는지 검사
                if pnu_val and r.status == "SUCCESS":
                    cur.execute("""
                        SELECT aa.id, a.paper, a.title
                        FROM article_addresses aa
                        JOIN articles a ON aa.article_link = a.link
                        WHERE aa.pnu = ?
                          AND (
                              a.link = ?
                              OR a.title = ?
                              OR (a.content_hash = ? AND a.content_hash IS NOT NULL AND a.content_hash != '')
                          )
                        LIMIT 1
                    """, (pnu_val, link, title, content_hash))
                    existing = cur.fetchone()
                    if existing:
                        skipped_count += 1
                        print(f"  -> [중복 제외] PNU({pnu_val})에 동일 기사 이미 저장됨: '{title[:30]}' (기존: [{existing[1]}] {existing[2][:25]})")
                        continue

                # B. PNU가 없거나 실패한 주소인 경우:
                #    동일 article_link에 동일 raw_address가 이미 있는지 검사
                else:
                    cur.execute("""
                        SELECT 1 FROM article_addresses
                        WHERE article_link = ? AND raw_address = ?
                        LIMIT 1
                    """, (link, raw_val))
                    if cur.fetchone():
                        skipped_count += 1
                        continue

                # 신규 주소-기사 관계 저장
                cur.execute("""
                    INSERT INTO article_addresses
                    (article_link, raw_address, completed_address, pnu, source, status, standard_name, x, y, basis)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    link,
                    r.raw_address,
                    r.completed_address,
                    r.pnu,
                    r.source,
                    r.status,
                    r.standard_name,
                    r.x,
                    r.y,
                    r.basis,
                ))
                saved_count += 1

            conn.commit()

        return saved_count, skipped_count

    def close(self):
        self.session.close()
