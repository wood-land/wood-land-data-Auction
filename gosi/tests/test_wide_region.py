"""광역시청·도청 본청 공보의 소재지 읽기(2026-11-14, 인천광역시청 시보 제2489호 실제 본문으로 재현).
 1) 머리글 단서(면/리 열 이름)는 그 행이 속한 표의 머리글에서만 인정한다(앞쪽 다른 표의 '읍·면·리' 머리글이 뒤 표에 퍼져 '기정면 주안동리' 를 만들었다).
 2) '시·군 | 읍·면·리' 표의 '연수구 동춘동' 은 시군구·동이 완전한 이름이라 접미사를 붙이지 않는다.
 3) 본청 Regions 는 시도만 붙이고 본청 소재지(남동구)를 시군구 기본값으로 붙이지 않는다(wide_area).
 4) '위치 ... 미추홀구 주안동 606-8번지 일원' 선언으로 구를 채운다.
실행: gosi 폴더에서 `python -m unittest discover -s tests -v`"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from core import gazette_extractor as GX  # noqa: E402
from core import jose_extractor as J  # noqa: E402
from cities import incheon  # noqa: E402

# 앞쪽 공고: 머리글에 '시·군 | 읍·면·리' 열 이름이 있는 표(정당한 면·리 단서). 뒤쪽 공고: 소재지 칸에 기정/변경 구분이 붙은 다른 표.
TEXT = (
    "(붙임) 수용하거나 사용될 토지의 세목 연번 소재지 지번 지목 공부 면적 (㎡) 편입 면적 (㎡) 토지소유자 관계인 비 시·군 읍·면·리 성명 주소 공유 고 지분 "
    "1 연수구 동춘동 223-4 답 100.0 50.0 김*수 인천광역시 연수구 *** 2 연수구 옥련동 301 대 200.0 80.0 이*희 인천광역시 연수구 *** "
    "제90조 의거 주민 의견을 청취하고자 공고·열람합니다. 1. 사업시행지의 위치(변경 없음) ❍ 인천광역시 미추홀구 주안동 606-8번지 일원 "
    "2. 수용하거나 사용될 토지의 세목 ▢ 토지조서 번호 소재지 지번 지목 지적 면적 편입 면적 소 유 자 관 계 인 비고 지분 성명 주소 성명 주소 권리관계 "
    "1 기정 주안동 606-35 대 92.8 92.8 1/1 조*성 서울특별시 강남구 대치동 ***-** 변경 주안동 606-35 대 92.8 92.8 1/1 공유지 미추홀구(인천광역시) 말소 "
    "2 기정 주안동 606-19 대 65.9 65.9 1/1 전*순 인천광역시 남동구 만수동 ***-** 변경 주안동 606-19 대 65.9 65.9 1/1 공유지 미추홀구(인천광역시) "
)


class WideRegionTest(unittest.TestCase):
    def setUp(self):
        self.regions = J.wide_variant(incheon.INCHEON_CITY.regions)
        self.rows = GX.extract_rows(TEXT, self.regions, site_name="인천광역시청", title="t", default_sido="인천광역시", default_sigun="")
        self.soj = [r["sojaeji"] for r in self.rows]

    def test_no_invented_myeon_ri_or_head_office_gu(self):
        for s in self.soj:
            self.assertNotRegex(s, r"[가-힣]면 [가-힣]+리|동리")
            self.assertNotIn("남동구", s)

    def test_division_words_do_not_become_places_and_gu_comes_from_declaration(self):
        self.assertIn("인천광역시 미추홀구 주안동 606-35", self.soj)
        self.assertIn("인천광역시 미추홀구 주안동 606-19", self.soj)
        self.assertEqual(len([s for s in self.soj if "주안동 606-35" in s]), 1)  # 기정/변경 같은 필지는 한 행

    def test_gu_dong_pair_keeps_gu(self):
        self.assertIn("인천광역시 연수구 동춘동 223-4", self.soj)
        self.assertIn("인천광역시 연수구 옥련동 301", self.soj)


class CueAndGuardTest(unittest.TestCase):
    def test_cue_is_local_to_the_table(self):
        has_cue = J.bare_cue_checker(TEXT)
        first_row = TEXT.index("1 연수구")
        later_row = TEXT.index("1 기정 주안동")
        self.assertTrue(has_cue(first_row))      # 읍·면·리 머리글 바로 아래 표
        self.assertFalse(has_cue(later_row))     # 뒤의 다른 표(머리글에 면/리 열 이름 없음)

    def test_sigungu_name_is_not_a_bare_myeon_name(self):
        self.assertIsNone(J.bare_myeon_ri("연수구", "동춘동", "", True))
        self.assertEqual(J.bare_myeon_ri("대강", "당동", "", True), ("대강면", "당동리"))  # 기존 동작
        self.assertEqual(J.bare_myeon_ri("유구", "명곡", "", True), ("유구면", "명곡리"))  # 2글자 '유구' 는 면 이름

    def test_head_office_default_sigun_not_attached(self):
        wide = J.wide_variant(incheon.INCHEON_CITY.regions)
        plain = incheon.INCHEON_CITY.regions
        self.assertEqual(wide.resolve("주안동")["region"], "인천광역시 주안동")
        self.assertIn("남동구", plain.resolve("주안동")["region"])  # 원본은 그대로(복사본만 바뀐다)
        self.assertFalse(plain.wide_area)

    def test_metro_head_office_only(self):
        for name in ("인천광역시청", "부산광역시청", "세종특별자치시청"):
            self.assertTrue(J.is_metro_head_office(name), name)
        for name in ("충청북도청", "부평구", "원주시", "한국부동산원", "전남광주통합특별시(구 전라남도청)"):
            self.assertFalse(J.is_metro_head_office(name), name)  # 도청은 wide 대상이 아니다(리 이름 중복으로 오결합 위험)

    def test_is_wide_city(self):
        for name in ("인천광역시청", "충청북도청", "세종특별자치시청", "전남광주통합특별시(구 전라남도청)"):
            self.assertTrue(J.is_wide_city(name), name)
        for name in ("부평구", "원주시", "한국부동산원"):
            self.assertFalse(J.is_wide_city(name), name)


if __name__ == "__main__":
    unittest.main()
