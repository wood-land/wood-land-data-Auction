"""이름이 겹치는 시·군(고성군: 강원·경남, 광주시: 경기·광주광역시)을 기본 지역으로 쓰는 신문사는 시·도를 함께 적어야 한다(2026-11-17).
경남 고성군 '고성신문' 의 '동해면 내곡리 1536-1' 이 강원 고성군으로 완성되어 주소 변환이 실패했다."""
import importlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from common.admin_names import AMBIGUOUS_SIGUNGU  # noqa: E402
from common.pnu_resolver import complete_korean_address_candidates  # noqa: E402


def _all_sites():
    pkg = importlib.import_module("regions")
    out = []
    for name in sorted(os.listdir(os.path.dirname(pkg.__file__))):
        if name.startswith("12_") and name.endswith(".py"):
            mod = importlib.import_module("regions." + name[:-3])
            out += list(getattr(mod, "SITES", []))
    return out


def test_ambiguous_default_area_has_province():
    bad = [(s.name, s.default_area) for s in _all_sites() if s.default_area.strip() in AMBIGUOUS_SIGUNGU]
    assert not bad, f"시·도 없이 이름이 겹치는 시·군을 기본 지역으로 씀: {bad}"


def test_gosung_newspaper_resolves_to_gyeongnam():
    got = complete_korean_address_candidates("동해면 내곡리 1536-1", "경상남도 고성군", "고성신문", "경상남도 고성군", "")
    assert got[0][0] == "경상남도 고성군 동해면 내곡리 1536-1"
