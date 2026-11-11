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


class MixedLandObjectSheetTest(unittest.TestCase):
    """토지·물건이 한 시트에 섞이고 제목/사업명 줄이 길어 자료가 7번째 줄에서 시작하는 조서(한국부동산원 천안 직산, 2026-11-11).
    이전에는 자료 행 탐색 범위(앞 6줄) 밖이라 0행이었다. 공고문의 필지 수(16)는 '편입' 지번 개수다."""

    @staticmethod
    def _xlsx():
        import io
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["토 지 조 서"] + [None] * 9)
        ws.append(["토 지 조 서"] + [None] * 9)
        ws.append(["사 업 명: 직산 도시첨단산업단지 진입도로 개설공사"] + [None] * 9)
        ws.append(["사업시행자: 천안시"] + [None] * 9)
        ws.append(["대분류", "소재지", "지번", "지번", "지목", "현황", "용도지역.지구", "면적및수량", "면적및수량", "단위"])
        ws.append(["대분류", "소재지", "당초", "편입", "지목", "현황", "용도지역.지구", "전체", "편입", "단위"])
        loc = "충청남도 천안시 서북구 직산읍 모시리"
        ws.append(["토지", loc, "115-7", "115-18", "임야", "임야", "자연녹지지역", "67", "48", "㎡"])
        ws.append(["토지", loc, "115-7", "115-18", "임야", "임야", "자연녹지지역", "67", "48", "㎡"])  # 같은 필지의 다른 소유자 행
        ws.append(["토지", loc, "49-1", "49-4", "대", "임야", "자연녹지지역", "1,041", "11", "㎡"])
        ws.append(["물건", loc, "115-7", "115-18", "", "주택", "", "1", "1", "동"])  # 물건 행은 필지가 아니다
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def test_land_rows_read_with_incl_jibun_and_objects_skipped(self):
        from core.jose_extractor import Regions, extract_from_attachment
        rep = {}
        rows = extract_from_attachment(self._xlsx(), "xlsx", "2. 토지,물건 조서.xlsx", "직산 도시첨단산업단지 진입도로 개설공사",
                                       Regions(sido_name="대구광역시", sigun_name="동구"), report=rep)
        self.assertEqual(rep["code"], "OK")
        self.assertEqual(sorted(r["jibun"] for r in rows), ["115-18", "49-4"])  # 편입 지번, 소유자 중복·물건 행 제외
        self.assertTrue(all(r["sojaeji"].startswith("충청남도 천안시 서북구 직산읍 모시리") for r in rows))



class ApplyDoesNotShortenTest(unittest.TestCase):
    def test_full_region_row_is_not_overwritten_by_partial_declaration(self):
        rows = [{"sojaeji": "충청남도 천안시 서북구 직산읍 모시리 115-18", "jibun_incl": "115-18"}]
        apply_declared_locations("위치 및 면적 충남 천안시 서북구 직산읍 모시리 일원 (16필지, 498㎡)", rows)
        self.assertEqual(rows[0]["sojaeji"], "충청남도 천안시 서북구 직산읍 모시리 115-18")


class NationwideExtractAllTest(unittest.TestCase):
    """사업지가 전국인 기관(2026-11-11 사용자 지시): 토지조서에서 읽을 수 있는 행은 모두 추출한다. 문서에 시군이 없으면 본사 기본 소재지
    (대구 동구 등)를 붙이지 않고 문서에 적힌 읍면·리·지번 그대로 둔다. 사업시행지역이 양 끝 리 범위여도 포기하지 않는다."""

    @staticmethod
    def _xlsx(rows):
        import io
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["토 지 조 서"] + [None] * 4)
        ws.append(["연번", "소재지", "지번", "지목", "면적(㎡)"])
        for i, (loc, jb) in enumerate(rows, 1):
            ws.append([i, loc, jb, "전", 100])
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def _run(self, rows, context, nationwide=True):
        from core.jose_extractor import Regions, extract_from_attachment
        rep = {}
        got = extract_from_attachment(self._xlsx(rows), "xlsx", "토지조서.xlsx", "도로건설공사", Regions("대구광역시", "동구", nationwide=nationwide),
                                      report=rep, context_text=context)
        return got, rep

    def test_range_declared_keeps_all_rows(self):
        rows, rep = self._run([("상색리", "204-7"), ("달전리", "405-105")],
                              "사업시행지역 : 가평군 가평읍 상색리 ~ 춘천시 남산면 서천리 ￭ 사업시행자")
        self.assertEqual([r["jibun"] for r in rows], ["204-7", "405-105"])
        self.assertTrue(rows[0]["sojaeji"].startswith("가평군 가평읍 상색리"))
        self.assertEqual(rows[1]["sojaeji"], "달전리 405-105")  # 시군 근거가 없어도 추출, 본사 기본값은 붙이지 않음
        self.assertNotIn("skipped_region", rep)

    def test_address_without_sigun_is_extracted_as_written(self):
        rows, _ = self._run([("서면 반곡리", "59-3"), ("남산면 산수리", "318")],
                            "사업시행지역 : 국가하천 홍천강-강원특별자치도 홍천군 서면 반곡리 일원")
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[0]["sojaeji"].startswith("강원특별자치도 홍천군 서면 반곡리"))
        self.assertEqual(rows[1]["sojaeji"], "남산면 산수리 318")

    def test_regular_city_keeps_board_default(self):
        rows, _ = self._run([("상색리", "204-7"), ("달전리", "405-105")],
                            "사업시행지역 : 가평군 가평읍 상색리 ~ 춘천시 남산면 서천리", nationwide=False)
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[1]["sojaeji"].startswith("대구광역시 동구"))


if __name__ == "__main__":
    unittest.main()
