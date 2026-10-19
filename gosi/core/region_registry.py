"""
region_registry.py — 이미 cities/*.py에 등록된 지자체들의 Regions를 시군구 이름으로
찾아볼 수 있게 모아 둔 레지스트리. 전자관보처럼 게시글마다 소재지가 전국 각지로
달라지는 출처(cms_adapters/gwanbo_board.py)에서, 이미 검증된 읍면리 데이터를 가진
Regions를 재사용하기 위한 용도다.

새 Regions 매칭 로직을 여기에 추가하지 않는다 — 각 지자체의 실제 읍면리 데이터는
cities/<도>.py에만 있고, 이 파일은 그걸 "시군구 이름 -> Regions"로 인덱싱만 한다.
"""
from __future__ import annotations

import importlib
import re
from pathlib import Path
from typing import Optional

# central_agencies/dev_corps는 실제 지자체가 아니라 산하기관/공사 게시판이고, 그 Regions는
# 보통 본거지 도시를 가리키는 "얇은"(읍면리 데이터 없는) 인스턴스라 더 정확한 원본 등록
# (cities/<도>.py의 진짜 그 지자체 City)을 밀어내지 않도록 레지스트리 구축에서 제외한다.
_SKIP_MODULES = {"central_agencies", "dev_corps", "gwanbo", "_shared", "__init__"}

# 여러 광역시가 같은 이름을 공유하는 자치구(부산/대구/인천/광주/대전/울산의 중구·남구·
# 북구·동구·서구) — 시군구 이름 하나만 보고 매칭하면 엉뚱한 광역시의 Regions를 잘못
# 골라올 수 있어, 이 이름들은 시/도 이름이 본문에 함께 있을 때만 매칭을 허용한다.
_AMBIGUOUS_SIGUN = {"중구", "남구", "북구", "동구", "서구"}

# sido_name -> 본문에서 찾을 축약형(예: "부산광역시" -> "부산"). 광역시/특별시 계열만
# 필요하다(도 단위는 애초에 자치구 이름이 겹치지 않는다).
_SIDO_SHORT = {
    "서울특별시": "서울",
    "부산광역시": "부산",
    "대구광역시": "대구",
    "인천광역시": "인천",
    "광주광역시": "광주",
    "대전광역시": "대전",
    "울산광역시": "울산",
}

_registry_cache: Optional[dict] = None


def _richness(regions) -> int:
    """이 Regions가 얼마나 자세한 읍면리 데이터를 갖고 있는지(중복 이름이 여럿일 때
    더 자세한 쪽을 고르는 기준)."""
    return len(regions.dongs) + len(regions.eups) + len(regions.ri_parent)


def _build_registry() -> dict:
    registry: dict[str, tuple[str, object]] = {}  # sigun_name -> (sido_name, Regions)
    cities_dir = Path(__file__).resolve().parent.parent / "cities"
    for path in sorted(cities_dir.glob("*.py")):
        stem = path.stem
        if stem.startswith("_") or stem in _SKIP_MODULES:
            continue
        mod = importlib.import_module(f"cities.{stem}")
        for city in getattr(mod, "CITIES", []):
            regions = city.regions
            if regions is None or callable(regions):
                continue
            key = regions.sigun_name
            if not key:
                continue
            existing = registry.get(key)
            if existing is None or _richness(regions) > _richness(existing[1]):
                registry[key] = (regions.sido_name, regions)
    return registry


def _registry() -> dict:
    global _registry_cache
    if _registry_cache is None:
        _registry_cache = _build_registry()
    return _registry_cache


def resolve_regions_for_title(title: str):
    """제목(전자관보 관례상 발행기관명이 접두어로, 지역명은 본문 어디든 섞여 나온다)에서
    이미 등록된 시군구 이름을 찾아 그 Regions를 돌려준다. 못 찾으면 None(호출쪽에서 그
    게시글의 토지조서 추출을 건너뛴다) — 전국 어디든 나올 수 있는 출처라 모르는 지역까지
    억지로 맞추지 않는 게 안전하다(law.md 3-2, 임의 추측 금지).

    시군구 이름과 함께 "시/군/구" 접미사가 실제 제목에서는 종종 빠진다(예: "김포-파주
    건설공사"에는 "파주시"가 아니라 "파주"만 나온다) — 그래서 접미사를 뗀 어간을
    단어 경계(\\b)로 찾는다. 다만 중구/남구/북구/동구/서구처럼 여러 광역시가 공유하는
    이름은 어간이 1글자뿐이라 오탐 위험이 커서, 그 경우엔 접미사까지 포함한 전체 이름과
    해당 광역시 이름이 둘 다 나올 때만 인정한다.
    """
    if not title:
        return None
    registry = _registry()
    # 어간이 긴(더 구체적인) 이름부터 검사해야, 예를 들어 "완주군"과 "주"처럼 짧은
    # 이름이 우연히 먼저 걸리는 일을 피한다.
    candidates = sorted(registry.items(), key=lambda kv: len(kv[0]), reverse=True)
    for sigun_name, (sido_name, regions) in candidates:
        if sigun_name in _AMBIGUOUS_SIGUN:
            if sigun_name not in title:
                continue
            short = _SIDO_SHORT.get(sido_name)
            if not short or short not in title:
                continue
            return regions
        # 접미사(시/군/구 등)가 붙은 채로 다른 말과 곧장 이어지는 경우가 많다
        # ("파주교육지원청", "완주군수" 등 — 한글은 띄어쓰기 없이도 합성어가 되므로
        # \b 단어경계로는 못 잡는다) — 그래서 단순 부분일치로 찾는다. 2글자 미만
        # 어간은 오탐 위험이 커서 제외한다(실제로 등록된 이름 중엔 없지만 방어적으로).
        stem = re.sub(r"(특별자치시|특별자치도|광역시|특별시|시|군|구)$", "", sigun_name)
        if len(stem) < 2:
            continue
        if stem in title:
            return regions
    return None
