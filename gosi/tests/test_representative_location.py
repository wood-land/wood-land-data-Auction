"""사업 대표 위치(시군구) 기준 필지 읽기 회귀 테스트 (2026-11-17, 부산광역시 고시 제2026-434호 '부경대학교 용당캠퍼스' 지형도면 고시로 재현).
 1) '면적(㎡)>변경후' 열을 지번 열로 읽지 않는다. 면적 '15,540' 이 지번 15·540 이 되어 필지가 전국의 용당동으로 번졌다.
 2) 지번 열이 없고 위치 칸에 '용당동 251 일원', '감만동 182-81 일원' 처럼 적힌 시설 조서도 동·리 + 지번으로 읽는다('산68' 의 산 포함).
 3) 시군구 없이 동·리만 적힌 행에는 대표 위치(문서에서 가장 먼저 시군구까지 적힌 소재지, 또는 본문 '남구 고시 제…')의 시군구를 붙인다.
 4) PNU 변환: 소재지에 시도가 적혀 있으면 카카오 결과의 시도도 같아야 한다(부산 용당동 540 에 경남 양산시 용당동 540 이 붙던 문제).
실행: gosi 폴더에서 `python -m unittest discover -s tests -v`"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from core import jose_extractor as J  # noqa: E402
from core.pnu import sido_agrees  # noqa: E402

TITLE = "도시관리계획(시설:○○대학교 용당캠퍼스) 지형도면 고시"

# 시설 결정 조서(대표 위치 한 줄): 위치 칸에 시군구까지 적힘, 지번 열 없음
GRID_MAIN = [
    ["구분", "도면표시번호", "시설명", "시설의 세분", "위 치", "면 적 (㎡)", "면 적 (㎡)", "면 적 (㎡)", "최초 결정일", "비 고"],
    ["구분", "도면표시번호", "시설명", "시설의 세분", "위 치", "기 정", "변 경", "변경후", "최초 결정일", "비 고"],
    ["기정", "148", "학교", "대학", "남구 용당동 251번지 일원", "320,310", "-", "320,310", "부고 제1981-117호", ""],
]
# 토지 구역별 조서: 위치 칸에 동·리 + 지번(시군구 없음), 면적에 '15,540' 처럼 쉼표 숫자
GRID_LAND = [
    ["구분", "도면표시번호", "세 부 시설명", "위 치", "면 적(㎡)", "면 적(㎡)", "면 적(㎡)", "최 초 결정일", "비고"],
    ["구분", "도면표시번호", "세 부 시설명", "위 치", "기 정", "변 경", "변경후", "최 초 결정일", "비고"],
    ["기정", "1-1", "건축 부지", "용당동 산68 일원", "1,917", "-", "1,917", "81.5.21", ""],
    ["", "1-2", "", "용당동 251", "15,540", "-", "15,540", "", ""],
    ["", "1-3", "", "감만동 182-81 일원", "6,255", "-", "6,255", "", ""],
    ["", "1-4", "", "용당동 251-1 일원", "7,047", "-", "7,047", "", ""],
]


def rows_of(*grids, text=""):
    J._NOTICE_LOCAL.text = text
    try:
        rows, _ = J.rows_from_document_grids([(1, i, g) for i, g in enumerate(grids)], "a.hwpx", TITLE)
    finally:
        J._NOTICE_LOCAL.text = ""
    return rows


class AreaColumnIsNotJibunTest(unittest.TestCase):
    def test_area_after_change_is_not_a_jibun_column(self):
        rows = rows_of(GRID_LAND)
        self.assertEqual([(r["sojaeji"], r["jibun_incl"]) for r in rows],
                         [("용당동", "산68"), ("용당동", "251"), ("감만동", "182-81"), ("용당동", "251-1")])
        self.assertEqual(rows[1]["area_incl"], "15540")

    def test_facility_table_one_row_location_is_read(self):
        rows = rows_of(GRID_MAIN)
        self.assertEqual([(r["sojaeji"], r["jibun_incl"]) for r in rows], [("남구 용당동", "251")])


class RepresentativeLocationTest(unittest.TestCase):
    def test_bare_dong_rows_get_sigungu_of_first_explicit_location(self):
        rows = rows_of(GRID_MAIN, GRID_LAND)
        R = J.wide_variant(J.Regions(sido_name="부산광역시", sigun_name="연제구"))
        rows = J.apply_representative_location(rows, "", R)
        self.assertEqual([r["sojaeji"] for r in rows],
                         ["부산광역시 남구 용당동", "부산광역시 남구 용당동", "부산광역시 남구 용당동", "부산광역시 남구 감만동", "부산광역시 남구 용당동"])

    def test_notice_issuer_is_used_when_no_row_has_sigungu(self):
        rows = rows_of(GRID_LAND)
        R = J.wide_variant(J.Regions(sido_name="부산광역시", sigun_name="연제구"))
        rows = J.apply_representative_location(rows, "부산광역시 남구 고시 제2026-139호(2026.11.11.)로 …", R)
        self.assertTrue(all(r["sojaeji"].startswith("부산광역시 남구 ") for r in rows))

    def test_row_with_its_own_sigungu_is_kept(self):
        rows = [{"sojaeji": "남구 용당동", "jibun_incl": "1"}, {"sojaeji": "해운대구 우동", "jibun_incl": "2"}, {"sojaeji": "감만동", "jibun_incl": "3"}]
        R = J.wide_variant(J.Regions(sido_name="부산광역시", sigun_name="연제구"))
        out = J.apply_representative_location(rows, "", R)
        self.assertEqual([r["sojaeji"] for r in out], ["부산광역시 남구 용당동", "부산광역시 해운대구 우동", "부산광역시 남구 감만동"])

    def test_no_anchor_changes_nothing(self):
        rows = [{"sojaeji": "감만동", "jibun_incl": "3"}]
        self.assertEqual(J.apply_representative_location(rows, "", None)[0]["sojaeji"], "감만동")

    def test_head_office_sido_is_not_trusted_for_non_wide_sources(self):
        # 본사 소재지(대구 동구)가 시도인 출처(한국부동산원)의 '가평군 조종면 신하리' 에 대구광역시를 붙이면 안 된다
        rows = [{"sojaeji": "가평군 조종면 신하리", "jibun_incl": "1"}]
        out = J.apply_representative_location(rows, "", J.Regions(sido_name="대구광역시", sigun_name="동구"))
        self.assertEqual(out[0]["sojaeji"], "가평군 조종면 신하리")

    def test_full_extraction_resolves_all_rows_under_nam_gu(self):
        # 표 해석 → 대표 위치 → 소재지 완성까지 이어서: 필지는 전부 부산 남구, 면적 숫자가 지번이 되지 않는다
        rows = rows_of(GRID_MAIN, GRID_LAND)
        R = J.wide_variant(J.Regions(sido_name="부산광역시", sigun_name="연제구"))
        rows = J.finalize_rows(J.apply_representative_location(rows, "", R), R)
        self.assertEqual({r["sojaeji"].rsplit(" ", 1)[0] for r in rows}, {"부산광역시 남구 용당동", "부산광역시 남구 감만동"})
        self.assertNotIn("15", {r["jibun_incl"] for r in rows})


GRID_JIBUN_ONLY = [
    ["번호", "지번", "지목", "면적(㎡)"],
    ["1", "산12-3", "임야", "1,200"],
    ["2", "45", "답", "300"],
    ["3", "46-1", "전", "250"],
    ["4", "47", "대", "80"],
]


class BareJibunListTest(unittest.TestCase):
    """대표 위치가 '○○동 일원' 이고 하단에는 지번만 나열된 문서: '00시 ○○동 00번지' 로 쓴다(사용자 지시 2026-11-17)."""

    def _rows(self, text):
        rows = rows_of(GRID_JIBUN_ONLY)
        return J.fill_bare_rows_from_representative(rows, text)

    def test_full_location_with_sigungu(self):
        rows = self._rows("위치 : 경기도 가평군 조종면 신하리 일원")
        self.assertEqual({r["sojaeji"] for r in rows}, {"경기도 가평군 조종면 신하리"})
        self.assertEqual([r["jibun_incl"] for r in rows], ["산12-3", "45", "46-1", "47"])

    def test_resolved_to_complete_address_with_jibun(self):
        rows = self._rows("사업위치 : 부산광역시 남구 용당동 일원 사업기간 2026")
        R = J.wide_variant(J.Regions(sido_name="부산광역시", sigun_name="연제구"))
        rows = J.finalize_rows(rows, R)
        self.assertEqual(rows[1]["sojaeji"], "부산광역시 남구 용당동 45")

    def test_dong_only_gets_sigungu_from_issuer(self):
        rows = self._rows("사업의 위치 : 용당동 일원")
        R = J.wide_variant(J.Regions(sido_name="부산광역시", sigun_name="연제구"))
        rows = J.apply_representative_location(rows, "부산광역시 남구 고시 제2026-139호", R)
        self.assertEqual(rows[0]["sojaeji"], "부산광역시 남구 용당동")

    def test_two_declared_dongs_are_ambiguous_and_left_alone(self):
        rows = self._rows("위치 : 가평군 상면 율길리, 신하리 일원")
        self.assertEqual({r["sojaeji"] for r in rows}, {""})

    def test_rows_that_already_have_a_location_are_untouched(self):
        rows = [{"sojaeji": "남구 감만동", "jibun_incl": "1"}]
        self.assertEqual(J.fill_bare_rows_from_representative(rows, "위치 : 부산광역시 남구 용당동 일원")[0]["sojaeji"], "남구 감만동")


class SidoAgreesTest(unittest.TestCase):
    def test_other_sido_is_rejected(self):
        self.assertFalse(sido_agrees("부산광역시 남구 용당동 540", "경남"))
        self.assertTrue(sido_agrees("부산광역시 남구 용당동 540", "부산"))

    def test_no_sido_or_unknown_passes(self):
        self.assertTrue(sido_agrees("남구 용당동 540", "경남"))
        self.assertTrue(sido_agrees("부산광역시 남구 용당동 540", ""))

    def test_old_and_new_names_of_the_same_region_agree(self):
        self.assertTrue(sido_agrees("전라남도 순천시 용당동 1", "전남광주통합특별시"))
        self.assertTrue(sido_agrees("충청북도 영동군 법곡리 1", "충북"))
        self.assertFalse(sido_agrees("경기도 광주시 송정동 1", "광주"))


if __name__ == "__main__":
    unittest.main()
