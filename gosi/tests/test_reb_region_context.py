"""한국부동산원처럼 토지조서 표에 리만 적히고 시군이 다른 곳(표 중간 제목 행, 같은 글의 공고문 '사업시행지역')에만 있는 글의 소재지 보완 (2026-11-10).
이전에는 게시판 기본 소재지(대구 동구)가 붙어 카카오가 찾지 못했다. 실행: gosi 폴더에서 `python -m unittest discover -s tests -v`"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from core.jose_extractor import apply_declared_locations, declared_locations, section_heading  # noqa: E402


class SectionHeadingTest(unittest.TestCase):
    def test_merged_region_row_is_heading(self):
        self.assertEqual(section_heading(["경기도 가평군 조종면", "", "", ""]), "경기도 가평군 조종면")
        self.assertEqual(section_heading(["경기도 의정부시"] * 6), "경기도 의정부시")

    def test_data_or_title_row_is_not_heading(self):
        self.assertEqual(section_heading(["1", "신상리", "738-2", "전"]), "")
        self.assertEqual(section_heading(["마일천 개선(재해)복구사업"] * 4), "")


class LabelLocationTest(unittest.TestCase):
    def test_single_location_after_label(self):
        d = declared_locations("사업시행지역 : 국가하천 홍천강-강원특별자치도 홍천군 서면 반곡리 일원 ￭ 사업시행자 : 환경청")
        self.assertEqual(d["반곡리"], ("강원특별자치도", "홍천군", "서면"))

    def test_beonji_before_iwon(self):
        d = declared_locations("사업시행지역 : 경기도 가평군 상면 율길리181번지 일원(솔안천) 마. 사업규모")
        self.assertEqual(d["율길리"], ("경기도", "가평군", "상면"))

    def test_range_inherits_parent_and_keeps_other_sigun(self):
        d = declared_locations("사업시행지역 : 가평군 가평읍 상색리 ~ 춘천시 남산면 서천리 ￭ 사업시행자")
        self.assertEqual(d["상색리"], ("", "가평군", "가평읍"))
        self.assertEqual(d["서천리"], ("", "춘천시", "남산면"))
        d = declared_locations("사업시행지역 : 경기도 가평군 조종면 신상리930 ~ 현리241-22번지 일원(세곡천)")
        self.assertEqual(d["현리"], ("경기도", "가평군", "조종면"))


class ApplyContextTest(unittest.TestCase):
    def test_default_board_region_is_replaced_without_stale_sido(self):
        rows = [{"sojaeji": "대구광역시 동구 가평읍 상색리 204-7", "jibun_incl": "204-7"}]
        apply_declared_locations("사업시행지역 : 가평군 가평읍 상색리 ~ 춘천시 남산면 서천리 일원", rows)
        self.assertEqual(rows[0]["sojaeji"], "가평군 가평읍 상색리 204-7")

    def test_sido_kept_when_declared(self):
        rows = [{"sojaeji": "대구광역시 동구 서면 반곡리 59-3", "jibun_incl": "59-3"}]
        apply_declared_locations("사업시행지역 : 강원특별자치도 홍천군 서면 반곡리 일원", rows)
        self.assertEqual(rows[0]["sojaeji"], "강원특별자치도 홍천군 서면 반곡리 59-3")


if __name__ == "__main__":
    unittest.main()


class SplitColumnTableTest(unittest.TestCase):
    """소재지가 '군 | 읍·면 | 리' 열로 나뉘고 값에 접미사가 없는 표(한국부동산원 마일천·십이탄천, 2026-11-11). 이전에는 0행이라 DeepSeek 이 읽었다."""

    @staticmethod
    def _xlsx(sigun, eup, ri):
        import io
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["마일천 개선(재해)복구사업"] + [None] * 8)
        ws.append(["일련번호", "소재지", None, None, None, None, "지목", "지적(㎡)", "편입면적(㎡)"])
        ws.append([None, "군", "읍•면", "리", "분할전", "분할후", None, None, None])
        ws.append([1, sigun, eup, ri, "393", "393-6", "대", 2450, 73])
        ws.append([2, sigun, eup, ri, "393-5", "393-8", "양", 315, 5])
        ws.merge_cells("A1:I1")
        ws.merge_cells("B2:F2")
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def _rows(self, sigun, eup, ri, context):
        from core.jose_extractor import Regions, extract_from_attachment
        rep = {}
        rows = extract_from_attachment(self._xlsx(sigun, eup, ri), "xlsx", "토지조서.xlsx", "마일천 개선(재해)복구사업",
                                       Regions(sido_name="대구광역시", sigun_name="동구"), report=rep, context_text=context)
        return rows, rep

    def test_bare_values_get_suffix_from_header_and_notice(self):
        rows, rep = self._rows("가평", "조종", "신하리", "사업시행지역 : 경기도 가평군 조종면 마일리 산270번지 일원")
        self.assertEqual(rep["code"], "OK")
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r["sojaeji"].startswith("가평군 조종면 신하리") or r["sojaeji"].startswith("경기도 가평군 조종면 신하리") for r in rows))
        self.assertEqual([r["jibun"] for r in rows], ["393-6", "393-8"])  # 분할후 지번

    def test_suffixed_values_are_kept(self):
        rows, _ = self._rows("가평군", "상면", "율길리", "")
        self.assertEqual(len(rows), 2)
        self.assertIn("가평군 상면 율길리", rows[0]["sojaeji"])

    def test_eupmyeon_without_evidence_is_omitted_not_guessed(self):
        rows, _ = self._rows("가평", "조종", "신하리", "")  # 본문에 '조종면'/'조종읍' 근거 없음
        self.assertEqual(len(rows), 2)
        self.assertNotIn("조종읍", rows[0]["sojaeji"])
        self.assertNotIn("조종면", rows[0]["sojaeji"])
        self.assertIn("가평군", rows[0]["sojaeji"])
