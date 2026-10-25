"""
tests/test_extractors.py - 실제 공고 문서에서 겪은 추출 실패가 다시 나지 않는지 확인한다(2026-10-16 원인 분석 기준).

실행: python -m unittest discover -s tests -v      (네트워크·API 키 불필요, 표 구조만 담은 tests/fixtures/*.json 사용)
픽스처 만들기: python tests/make_fixtures.py       (개인 정보는 가짜 값으로 바꿔 저장)
"""
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from core import gazette_extractor as G  # noqa: E402
from core import jose_extractor as J  # noqa: E402
from core.pnu import PnuResolver  # noqa: E402


def load_fixture(name):
    with open(os.path.join(HERE, "fixtures", name + ".json"), encoding="utf-8") as f:
        return json.load(f)


def run_fixture(name, sido, sigun):
    """픽스처의 표들을 실제 추출 경로(rows_from_document_grids -> finalize)로 돌린다. -> (행 리스트, debug)."""
    fx = load_fixture(name)
    grids = []
    for t in fx["tables"]:
        g = J.pad_grid(t["grid"])
        g.heading = t["heading"]
        grids.append((t["page"], t["idx"], g))
    rows, debug = J.rows_from_document_grids(grids, fx["file"], "")
    rows = J.finalize_rows(rows, J.Regions(sido_name=sido, sigun_name=sigun))
    return rows, debug


class ExtractionRegressions(unittest.TestCase):
    def test_pocheon_location_in_heading_above_table(self):
        """포천: 소재지가 표 열이 아니라 표 위 제목줄에 있다 -> 소재지가 채워지고 공공 소유(국/공)는 owner_type='국공유' 로 표시돼 함께 나온다."""
        rows, debug = run_fixture("pocheon_pdf_heading", "경기도", "포천시")
        self.assertTrue(rows, "필지가 하나도 안 나옴")
        for r in rows:
            self.assertTrue(r["sojaeji"].startswith("경기도 포천시 가산면 방축리"), r["sojaeji"])
        kinds = {r.get("owner_type") for r in rows}
        self.assertIn("국공유", kinds, "공공 소유 필지가 표시돼 나와야 한다")
        self.assertTrue(kinds - {"국공유"}, "사유(또는 소유 미상) 필지도 함께 나와야 한다")

    def test_gapyeong_title_row_does_not_poison_headers(self):
        """가평 xlsx: 표 제목줄('편 입 용 지 조 서')이 머리글에 섞여 열 판별이 깨지던 문제 + 읍면동/리명 열."""
        rows, _ = run_fixture("gapyeong_xlsx_titlerow", "경기도", "가평군")
        self.assertTrue(rows)
        for r in rows:
            self.assertIn("덕현리", r["sojaeji"])
            self.assertTrue(r["jibun_incl"], r)

    def test_gapyeong_total_row_is_not_a_parcel(self):
        """가평 hwpx: '합 계 / 3필지' 행을 지번 3으로 읽지 않는다."""
        rows, _ = run_fixture("gapyeong_hwpx_total_row", "경기도", "가평군")
        self.assertTrue(rows)
        self.assertNotIn("3", [r["jibun_incl"] for r in rows])
        for r in rows:
            self.assertIn("덕현리", r["sojaeji"])

    def test_gwangju_block_lot_numbers_are_not_parcels(self):
        """광주시: 'A1 1-4'(블록 A1의 획지)를 지번으로 오인하지 않는다."""
        rows, debug = run_fixture("gwangju_hwpx_block_lots", "경기도", "광주시")
        for r in rows:
            self.assertNotRegex(r["sojaeji"], r"\bA\d")
        self.assertTrue(any(d["reason"] == "non-parcel-lot" for d in debug))

    def test_ansan_location_under_address_header(self):
        """안산: 머리글이 '주소>소재지'(2단)라 소재지 열이 소유자 주소로 오인되던 문제."""
        rows, _ = run_fixture("ansan_hwpx_addr_head", "경기도", "안산시")
        self.assertTrue(rows)
        for r in rows:
            self.assertIn("원곡동", r["sojaeji"])

    def test_gimpo_abbreviated_location_is_kept_for_pnu_stage(self):
        """김포: 소재지가 약칭('마곡')이어도 행은 나온다(리 접미사는 PNU 단계의 _abbrev_lookup 이 채운다)."""
        rows, _ = run_fixture("gimpo_hwpx_abbrev", "경기도", "김포시")
        self.assertEqual({r["jibun_incl"] for r in rows}, {"275-7", "275-8"})


class HeadingAndOwner(unittest.TestCase):
    def test_region_heading(self):
        self.assertEqual(J.region_heading("편 입 용 지 조 서\n경기도 포천시 가산면 방축리"), "경기도 포천시 가산면 방축리")
        self.assertEqual(J.region_heading("소재지 : 가산면 방축리"), "가산면 방축리")
        self.assertEqual(J.region_heading("편 입 용 지 조 서"), "")
        self.assertEqual(J.region_heading("1. 도로의 명칭 : 지방도 360호선"), "")

    def test_public_owner(self):
        for name, addr in [("국", None), ("공", None), ("국토교통부", None), ("경기도", None), ("한국도로공사", None),
                           ("포천시", ""), ("산림청", None), ("국토교통부 외 2명", None)]:
            self.assertTrue(J.is_public_owner(name, addr), (name, addr))

    def test_private_owner_kept(self):
        for name, addr in [("홍길동", None), ("김*수", "서울시 강남구 테헤란로 1"), ("이영구", "경기도 부천시 부일로483"),
                           ("주식회사 한무", None), ("재단법인 한무숙재단", None)]:
            self.assertFalse(J.is_public_owner(name, addr), (name, addr))


class PnuHelpers(unittest.TestCase):
    def test_fallback_query_drops_wrong_sigungu_keeps_sido(self):
        """제주 '제주시 남원리'(실제는 서귀포시), 부산 '연제구 금곡동'(실제는 북구): 시군구를 버리고 시도+읍면동·리로 재질의."""
        self.assertEqual(PnuResolver._fallback_query("제주특별자치도 제주시 남원리 12", "12"), "제주특별자치도 남원리 12")
        self.assertEqual(PnuResolver._fallback_query("부산광역시 연제구 금곡동 812", "812"), "부산광역시 금곡동 812")

    def test_full_address_from_kakao_document(self):
        a = {"region_1depth_name": "부산", "region_2depth_name": "북구", "region_3depth_name": "금곡동"}
        self.assertEqual(PnuResolver._full_address(a, False, 812, 0), "부산광역시 북구 금곡동 812")
        a = {"region_1depth_name": "제주특별자치도", "region_2depth_name": "서귀포시", "region_3depth_name": "안덕면 상창리"}
        self.assertEqual(PnuResolver._full_address(a, True, 95, 49), "제주특별자치도 서귀포시 안덕면 상창리 산95-49")

    def test_match_requires_same_jibun(self):
        doc = {"address": {"b_code": "5013031024", "mountain_yn": "N", "main_address_no": "1995", "sub_address_no": "",
                           "region_1depth_name": "제주특별자치도", "region_2depth_name": "서귀포시",
                           "region_3depth_name": "안덕면 상창리"}}
        self.assertEqual(PnuResolver._match(doc, (False, 1995, 0))[0], "5013031024119950000")
        self.assertIsNone(PnuResolver._match(doc, (False, 1996, 0)))


class DocumentGroundedAddresses(unittest.TestCase):
    """2026-10-17 수집 로그(구글시트) 분석에서 나온 소재지 조립 오류. 문서에 적힌 내용만으로 주소를 만든다(추측 금지)."""

    LOC_JIBUN_GRID = [
        ["사업시행자", "소재지 및 지번", "분묘기수"],
        ["평택시장", "평택시 안중읍 학현리 465-8, 465-11, 산70-4, 465-11, 평택시 안중읍 안중리 244-37", "50기"],
    ]

    def test_loc_and_jibun_in_one_cell_carries_region_to_following_lots(self):
        """경북도청 게시판의 평택시 분묘개장 공고: 지번만 이어지면 앞 소재지를 붙이고, 새 소재지가 나오면 바꾼다."""
        g = J.pad_grid(self.LOC_JIBUN_GRID)
        rows, _ = J.rows_from_document_grids([(1, 0, g)], "평택.hwpx", "분묘개장 공고")
        rows = J.finalize_rows(rows, J.Regions(sido_name="경상북도", sigun_name="안동시"))
        got = [r["sojaeji"] for r in J.dedupe_parcels(rows)]
        self.assertEqual(got, ["평택시 안중읍 학현리 465-8", "평택시 안중읍 학현리 465-11",
                               "평택시 안중읍 학현리 산70-4", "평택시 안중읍 안중리 244-37"])

    def test_other_city_in_document_is_not_prefixed_with_board_city(self):
        """게시판 지자체(안동시)와 다른 시·군이 문서에 있으면 '경상북도 안동시 택시안중읍'처럼 조립하지 않는다."""
        res = J.Regions(sido_name="경상북도", sigun_name="안동시").resolve("평택시 안중읍 학현리")
        self.assertEqual(res["region"], "평택시 안중읍 학현리")
        self.assertEqual(res["status"], "CHECK")
        same = J.Regions(sido_name="경상북도", sigun_name="안동시").resolve("임하면 금소리")  # 같은 지자체는 기존 규칙 그대로
        self.assertTrue(same["region"].startswith("경상북도 안동시"), same)

    def test_region_in_merged_row_inside_xlsx_table(self):
        """경주시 용지조서 xlsx: 소재지가 표 안쪽 병합 줄('경상북도 경주시 강동면 유금리')에 있다."""
        loc = "경상북도 경주시 강동면 유금리"
        g = J.pad_grid([
            ["용 지 조 서"] * 8,
            [""] * 3 + [loc] * 5,
            [""] * 8,
            ["일련", "지번", "지목", "편입면적", "소유자", "", "비고", ""],
            ["번호", "지번", "", "( ㎡ )", "성 명", "주 소", "", ""],
            ["1", "327-9", "답", "59", "홍길동", "경주시 현곡면 111", "", ""],
        ])
        rows, _ = J.rows_from_document_grids([(1, 0, g)], "용지조서.xlsx", "")
        self.assertEqual([r["sojaeji"] for r in rows], [loc])

    def test_unlabeled_location_column_and_city_abbreviation_kept_as_written(self):
        """머리글 없는 소재지 열의 '평창 병내리': 게시판 지자체를 붙이거나 '평창병내리'로 합치지 않고 문서 표기 그대로."""
        g = J.pad_grid([
            ["일련", "", "지번", "지목", "편입면적"],
            ["번호", "", "지번", "", "( ㎡ )"],
            ["1", "평창 병내리", "253-4", "전", "25"],
            ["2", "평창 병내리", "253-2", "전", "30"],
            ["3", "강릉 삼산리", "10-1", "답", "12"],
        ])
        rows, _ = J.rows_from_document_grids([(1, 0, g)], "x.xlsx", "")
        rows = J.finalize_rows(rows, J.Regions(sido_name="경상북도", sigun_name="경주시"))
        self.assertEqual([r["sojaeji"] for r in rows], ["평창 병내리 253-4", "평창 병내리 253-2", "강릉 삼산리 10-1"])

    TBL = ("1 대강 당동 193-23 구거 607 412 국(농림축 산식품부) "
           "10 대강 당동 61-1 전 131 131 인천시 남구 관교동 13-11 박*균 경기도 화성시 근저당권 "
           "11 대강 당동 61-0 전 986 108 인천광역시 남구 관교동 13-11 박*균 근저당권 "
           "12 대강 당동 60-4 답 138 111 단*군 ")

    def test_gazette_table_with_myeon_ri_columns_uses_suffix_from_document(self):
        """단양군보 공고 제2026-1284호: '면 | 리' 열 값('대강 당동')에 문서가 보여 주는 접미사를 붙인다. 국(…) 소유는 제외."""
        head = "나. 위 치 : 단양군 대강면 장림리, 당동리, 두음리 일원 "
        rows = G.generic_rows(head + self.TBL, "충청북도", "단양군")
        self.assertEqual([(r["sojaeji"], r["jibun_incl"]) for r in rows],
                         [("충청북도 단양군 대강면 당동리", "61-1"), ("충청북도 단양군 대강면 당동리", "61-0"),
                          ("충청북도 단양군 대강면 당동리", "60-4")])

    def test_gazette_table_without_evidence_is_not_guessed(self):
        """면·리 접미사를 문서에서 확인할 수 없으면 '당동'만 떼어 '충청북도 단양군 당동'을 만들지 않는다."""
        self.assertEqual(G.generic_rows(self.TBL, "충청북도", "단양군"), [])

    def test_gazette_table_with_suffixed_columns_still_read(self):
        rows = G.generic_rows("적성면 소야리 산62 임 홍길동 1,200 800", "경기도", "연천군")
        self.assertEqual([(r["sojaeji"], r["jibun_incl"]) for r in rows], [("경기도 연천군 적성면 소야리", "산62")])

    def _xlsx_bytes(self, rows):
        import io
        from openpyxl import Workbook
        wb = Workbook(); ws = wb.active
        for r in rows:
            ws.append(r)
        buf = io.BytesIO(); wb.save(buf)
        return buf.getvalue()

    def test_notice_without_parcel_list_is_not_flagged_as_warning(self):
        """필지 목록이 없는 공고(사용자: 필요 없음)는 '표 해석했으나 필지 0행'(주의)이 아니라 NO_PARCELS(정상)로 기록한다."""
        data = self._xlsx_bytes([["사업명", "도시재생 집수리 정비사업"], ["시행기간", "2026. 10. 17. ~ 2027. 3."], ["문의", "도시재생과"]])
        rep = {}
        rows = J.extract_from_attachment(data, "xlsx", "시행공고.xlsx", "도시재생 집수리 정비사업 시행공고",
                                         J.Regions(sido_name="충청북도", sigun_name="제천시"), report=rep)
        self.assertEqual(rows, [])
        self.assertEqual(rep["code"], "NO_PARCELS", rep)

    def test_unreadable_parcel_list_still_warns(self):
        """지번 목록처럼 보이는데 못 읽은 문서는 계속 ZERO_ROWS(주의)로 남겨 사람이 보게 한다."""
        data = self._xlsx_bytes([["소재지 편입 보상 대상 토지 목록"], ["가산면 방축리 산12-1 임야 100 80"], ["가산면 방축리 34-5 전 200 150"],
                                 ["가산면 방축리 77 답 300 120"], ["가산면 방축리 88-2 대 50 50"]])
        rep = {}
        J.extract_from_attachment(data, "xlsx", "목록.xlsx", "보상 공고", J.Regions(sido_name="경기도", sigun_name="포천시"), report=rep)
        self.assertIn(rep["code"], ("ZERO_ROWS", "OK", "ADDR_CHECK", "NO_REGION"), rep)  # 읽었든 못 읽었든 'NO_PARCELS'로 숨기지 않는다
        self.assertNotEqual(rep["code"], "NO_PARCELS", rep)


class BlockedSites(unittest.TestCase):
    def test_modes_split_hosted_and_domestic_runner_work(self):
        """막힌 게시판은 호스티드 러너(skip)에서 빠지고 국내 IP 러너(only)에서만 돌며, 기본(all)은 기존 동작 그대로."""
        from core.blocked_sites import BLOCKED_ON_HOSTED, should_run
        for module, cities in BLOCKED_ON_HOSTED.items():
            for city in cities:
                self.assertFalse(should_run("skip", module, city))
                self.assertTrue(should_run("only", module, city))
                self.assertTrue(should_run("all", module, city))
        self.assertTrue(should_run("skip", "경북", "경산시"))
        self.assertFalse(should_run("only", "경북", "경산시"))
        self.assertTrue(should_run("all", "경북", "경산시"))
        self.assertFalse(should_run("only", "강원", "원주시"))  # 막힌 곳이 없는 지역은 'only' 에서 할 일이 없다


class MetroDistrictExcluded(unittest.TestCase):
    def test_metro_districts_are_never_candidates(self):
        from core.blocked_sites import is_metro_district
        self.assertTrue(is_metro_district("부산", "수영구"))
        self.assertTrue(is_metro_district("인천", "계양구"))
        self.assertTrue(is_metro_district("부산", "기장군"))
        self.assertFalse(is_metro_district("대구", "대구광역시청"))
        self.assertFalse(is_metro_district("경기", "여주시"))
        self.assertFalse(is_metro_district("경남", "합천군"))  # 도 소속 군은 대상


class ExcludedDistricts(unittest.TestCase):
    def test_seoul_busan_incheon_districts_are_never_candidates(self):
        from core.blocked_sites import is_excluded_district
        self.assertTrue(is_excluded_district("부산", "수영구"))
        self.assertTrue(is_excluded_district("인천", "계양구"))
        self.assertTrue(is_excluded_district("부산", "기장군"))
        self.assertFalse(is_excluded_district("부산", "부산광역시청"))
        self.assertFalse(is_excluded_district("대구", "달성군"))  # 대구·대전·광주·울산·세종은 일반 후보
        self.assertFalse(is_excluded_district("경기", "여주시"))


class DetectBlocked(unittest.TestCase):
    """수집 로그(구글시트)로 Actions 가 반복해서 막히는 지자체를 찾는 규칙(detect_blocked.py)과 자동 등록 목록."""
    TODAY = __import__("datetime").date(2026, 10, 20)

    @staticmethod
    def board(day, city, status, err="", kind="고시공고", region="경북"):
        return {"시각": f"2026-10-{day:02d} 08:45:00", "지역": region, "지자체": city, "종류": kind, "상태": status, "오류": err, "상세": ""}

    def find(self, tabs, **kw):
        import detect_blocked as D
        return D.find_candidates(tabs, today=self.TODAY, **kw)

    def test_repeated_connection_errors_on_different_days_are_candidates(self):
        err = "ConnectTimeout: HTTPSConnectionPool(host='eminwon.cs.go.kr', port=443): Max retries exceeded"
        tabs = {"경북_게시판상태": [self.board(17, "청송군", "오류(목록)", err), self.board(19, "청송군", "오류(목록)", err)]}
        got = self.find(tabs)
        self.assertEqual(list(got), [("경북", "청송군")])
        self.assertEqual(got[("경북", "청송군")]["hosts"], {"eminwon.cs.go.kr"})

    def test_pc_tabs_are_ignored_and_success_rows_clear_a_city(self):
        err = "ConnectTimeout: x"
        pc = {"PC경북_게시판상태": [self.board(17, "청송군", "오류(목록)", err, region="PC경북"),
                               self.board(19, "청송군", "오류(목록)", err, region="PC경북")]}
        self.assertEqual(self.find(pc), {})  # 이 PC 의 로그는 Actions 차단 판단에 쓰지 않는다
        tabs = {"경북_게시판상태": [self.board(17, "청송군", "오류(목록)", err), self.board(19, "청송군", "오류(목록)", err),
                              self.board(18, "청송군", "정상", "")]}  # 고시공고 게시판 '정상' 요약 행 = 읽힌 적 있음
        self.assertEqual(self.find(tabs), {})
        tabs["경북_게시판상태"].append(self.board(19, "청송군", "건너뜀(막힌 게시판: PC 수집)", ""))
        self.assertEqual(self.find({"경북_게시판상태": tabs["경북_게시판상태"][:2] + tabs["경북_게시판상태"][3:]}).keys(),
                         {("경북", "청송군")})  # '건너뜀' 행은 정상 증거가 아니다

    def test_single_day_failure_is_not_enough(self):
        err = "ConnectTimeout: x"
        tabs = {"전북_게시판상태": [self.board(17, "군산시", "오류(목록)", err, region="전북"),
                              self.board(17, "군산시", "오류(목록)", err, region="전북")]}  # 같은 날 두 번 = 1일
        self.assertEqual(self.find(tabs), {})

    def test_any_successful_read_in_window_means_not_blocked(self):
        err = "HTTPError: 404 Client Error"
        tabs = {"경북_게시판상태": [self.board(17, "영천시", "오류(목록)", err), self.board(18, "영천시", "정상", kind="시보"),
                               self.board(19, "영천시", "오류(목록)", err)]}
        self.assertEqual(self.find(tabs), {})

    def test_download_timeouts_in_document_log_count_and_parse_errors_do_not(self):
        dl = {"시각": "2026-10-17 08:45:00", "지역": "경북", "지자체": "구미시", "원인코드": "DL_FAIL",
              "상세": "ConnectTimeout: HTTPSConnectionPool(host='eminwon.gumi.go.kr', port=443): Max retries"}
        dl2 = dict(dl, 시각="2026-10-19 08:45:00")
        parse = {"시각": "2026-10-17 08:45:00", "지역": "경북", "지자체": "안동시", "원인코드": "PARSE_ERROR", "상세": "ValueError: x"}
        tabs = {"경북_문서처리": [dl, dl2, parse, dict(parse, 시각="2026-10-19 08:45:00")]}
        got = self.find(tabs)
        self.assertEqual(list(got), [("경북", "구미시")])
        self.assertIn("첨부", got[("경북", "구미시")]["kinds"])

    def test_old_rows_outside_window_are_ignored(self):
        err = "ConnectTimeout: x"
        tabs = {"경북_게시판상태": [self.board(1, "청송군", "오류(목록)", err), self.board(2, "청송군", "오류(목록)", err)]}
        self.assertEqual(self.find(tabs, window=7), {})  # 10-20 기준 7일 = 10-13 이후만 본다

    def test_auto_registered_list_is_merged_with_manual_list(self):
        import tempfile
        from pathlib import Path
        from core import blocked_sites as B
        old = B.AUTO_FILE
        with tempfile.TemporaryDirectory() as d:
            B.AUTO_FILE = Path(d) / "auto.json"
            try:
                self.assertFalse(B.is_blocked("전북", "남원시"))
                B.register_auto("전북", "남원시", "시험")
                B.register_auto("전북", "남원시", "중복 등록은 한 번만")
                self.assertEqual(B.all_blocked()["전북"], ["남원시"])
                self.assertFalse(B.should_run("skip", "전북", "남원시"))
                self.assertTrue(B.should_run("only", "전북", "남원시"))
                self.assertIn("충청북도청", B.all_blocked()["충북"])  # 수동 목록은 그대로
            finally:
                B.AUTO_FILE = old

    def test_registration_needs_confirmation_and_rejection_is_remembered(self):
        import tempfile
        from pathlib import Path
        import detect_blocked as D
        from core import blocked_sites as B
        err = "ConnectTimeout: HTTPSConnectionPool(host='www.namwon.go.kr', port=443): Max retries"
        recent = __import__("datetime").date.today()
        rows = [dict(self.board(1, "남원시", "오류(목록)", err, region="전북"), 시각=f"{(recent - __import__('datetime').timedelta(days=d)).isoformat()} 08:45:00") for d in (1, 2)]
        old_auto, old_rej, old_load, old_pc = B.AUTO_FILE, B.REJECTED_FILE, D.load_tabs, D.pc_can_read
        with tempfile.TemporaryDirectory() as d:
            B.AUTO_FILE, B.REJECTED_FILE = Path(d) / "a.json", Path(d) / "r.json"
            D.load_tabs = lambda sheet_id=None: ({"전북_게시판상태": rows}, "")
            D.pc_can_read = lambda *a, **k: (True, True)
            try:
                self.assertEqual(D.run(apply=True, confirm=None, log=lambda m: None), [])      # 승인 수단이 없으면 등록 안 함
                self.assertEqual(D.run(apply=True, confirm=lambda q: False, log=lambda m: None), [])  # 거절
                self.assertFalse(B.is_blocked("전북", "남원시"))
                self.assertTrue(B.recently_rejected("전북", "남원시"))
                asked = []
                D.run(apply=True, confirm=lambda q: asked.append(q) or True, log=lambda m: None)
                self.assertEqual(asked, [])  # 거절한 직후 7일은 다시 묻지 않는다
                B.REJECTED_FILE.write_text("{}", encoding="utf-8")  # 거절 기록을 지우면 다시 묻고, 승인하면 등록
                self.assertEqual(D.run(apply=True, confirm=lambda q: True, log=lambda m: None), [("전북", "남원시")])
                self.assertTrue(B.is_blocked("전북", "남원시"))
            finally:
                B.AUTO_FILE, B.REJECTED_FILE, D.load_tabs, D.pc_can_read = old_auto, old_rej, old_load, old_pc


class BidDocumentsAndAiGuards(unittest.TestCase):
    def test_bid_location_rows_read_only_exact_jibun_with_place_names(self):
        """입찰·견적·제안서류: '공사현장: …' 과 '(고아읍 관심리 557-3)' 처럼 지번까지 적힌 위치만 읽는다."""
        text = ("1. 견적제출에 부치는 사항 가. 공사명 사벌매호취수장 사면정비공사 나. 공사현장: 상주시 사벌국면 매호리 255-9번지 일원 "
                "다. 공사개요 H=2.0m 추정금액 금45,000,000원 공사기간 60일간 "
                "대상지 1 고아읍 박록주로 일원 (고아읍 관심리 557-3) · 조형물 2 양포동 구포동 가락골 옹벽 일원 (구포동 976-8) · 정비 "
                "건물 (제3동 12) 와 위치: 가락골 일원")
        got = [(r["sojaeji"], r["jibun_incl"]) for r in J.bid_location_rows(text)]
        self.assertEqual(got, [("상주시 사벌국면 매호리", "255-9"), ("고아읍 관심리", "557-3"), ("구포동", "976-8")])

    def test_bid_notice_does_not_turn_amounts_into_parcels(self):
        """견적 공고의 금액·기간 숫자가 지번으로 읽혀 쓰레기 행(소재지 '착공일로부터')이 생기지 않는다."""
        import io
        from openpyxl import Workbook
        wb = Workbook(); ws = wb.active
        ws.append(["공사현장: 상주시 사벌국면 매호리 255-9번지 일원"]); ws.append(["공사기간", "착공일로부터 60일간"]); ws.append(["추정금액", "45,000,000"])
        buf = io.BytesIO(); wb.save(buf)
        rep = {}
        rows = J.extract_from_attachment(buf.getvalue(), "xlsx", "공고문.xlsx", "소액수의 견적제출 안내공고[사벌매호취수장 사면정비공사]",
                                         J.Regions(sido_name="경상북도", sigun_name="상주시"), report=rep)
        self.assertEqual([r["sojaeji"] for r in rows], ["경상북도 상주시 사벌국면 매호리 255-9"])
        self.assertEqual(rep["code"], "OK")

    def _fixer(self, answer):
        import collections
        import sqlite3
        from core.ai_fix import AiFixer
        con = sqlite3.connect(":memory:")
        con.execute("ATTACH DATABASE ':memory:' AS cache")

        class R:
            pass
        r = R(); r.con = con; r.stats = collections.Counter(); r._transient = False; r.calls_to_kakao = 0
        r._call = lambda q: (r.__dict__.__setitem__("calls_to_kakao", r.calls_to_kakao + 1) or ({"documents": []}, "ok"))
        fx = AiFixer(r); fx.enabled = True; fx.key = "x"; fx._ask = lambda payload: answer
        return fx, r

    def test_ai_fix_rejects_place_names_not_in_the_source(self):
        """DeepSeek 이 쓰레기 행('착공일로부터', 지번 60)에 지어낸 지명(사벌국면 덕가리)을 붙여도 카카오에 묻지 않고 거부한다."""
        fx, r = self._fixer({"sido": "경상북도", "sigungu": "상주시", "eupmyeondong": "사벌국면", "ri": "덕가리", "jibun": "60"})
        self.assertIsNone(fx.fix("착공일로부터", "60", "상주시", title="소액수의 견적제출 안내공고[사벌매호취수장 사면정비공사]"))
        self.assertEqual(r.calls_to_kakao, 0)

    def test_ai_fix_allows_place_names_that_appear_in_the_input(self):
        fx, r = self._fixer({"sido": "경상남도", "sigungu": "거제시", "eupmyeondong": "설천면", "ri": "두산리", "jibun": "12"})
        fx.fix("두산 12", "12", "거제시", title="설천면 두산리 일원 정비사업")
        self.assertEqual(r.calls_to_kakao, 1)  # 근거가 있으니 카카오 검증 단계로 간다

    def test_ai_doc_extract_place_must_appear_in_text(self):
        from core.ai_extract import AiDocExtractor
        body = re.sub(r"\s+", "", "공사현장 고아읍 관심리 557-3 일원")
        self.assertTrue(AiDocExtractor._place_in_text("경상북도 구미시 고아읍 관심리", body))
        self.assertFalse(AiDocExtractor._place_in_text("경상북도 상주시 사벌국면 덕가리", body))
        self.assertFalse(AiDocExtractor._place_in_text("경상북도 상주시", body))  # 읍면동·리 이름이 없으면 거부


if __name__ == "__main__":
    unittest.main()

class OcrOriginMarking(unittest.TestCase):
    """OCR 로 읽은 행은 parcels.ocr=1 로 표시하고, 같은 필지를 글자 층에서 다시 읽으면 표시를 푼다. 예전 DB 도 열이 덧붙는다."""

    def test_flag_set_cleared_and_old_db_migrated(self):
        import shutil
        import tempfile
        from core import sqlite_store as S
        d = tempfile.mkdtemp()
        old = os.path.join(os.path.dirname(HERE), "data", "충북.sqlite")
        db = os.path.join(d, "t.sqlite")
        if os.path.exists(old):
            shutil.copy(old, db)
        con = S.connect(db)
        self.addCleanup(con.close)
        self.addCleanup(shutil.rmtree, d, True)
        self.assertIn("ocr", [r[1] for r in con.execute("PRAGMA table_info(parcels)")])
        self.assertIn("ocr", [r[1] for r in con.execute("PRAGMA table_info(v_parcels)")])
        a = {"sojaeji": "충북 단양군 단양읍 별곡리", "jibun": "1-1", "jimok": "답", "area_incl": "10", "post_title": "t", "post_url": "u-ocr"}
        S._insert_parcel(con, "4380000000999990001", {**a, "ocr": 1}, "단양군", "공보")
        get = lambda: con.execute("SELECT ocr FROM parcels WHERE pnu='4380000000999990001'").fetchone()[0]
        self.assertEqual(get(), 1)
        S._insert_parcel(con, "4380000000999990001", {**a, "ocr": 0}, "단양군", "공보")
        self.assertEqual(get(), 0)  # 글자 층에서 다시 읽으면 표시를 푼다
        con.execute("DELETE FROM parcels WHERE pnu='4380000000999990001'")
        con.commit()


class SeenPosts(unittest.TestCase):
    """처리를 끝낸 글 기록(seen_posts): ok 는 바로, empty 는 2번 읽은 뒤, 추출 버전이 바뀌면 다시 읽는다."""

    def test_skip_rules(self):
        import shutil
        import tempfile
        from core import sqlite_store as S
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        con = S.connect(os.path.join(d, "t.sqlite"))
        self.addCleanup(con.close)
        k_ok, k_empty = S.post_key("http://x/1", "토지조서 공고"), S.post_key("http://x/2", "주민설명회")
        self.assertEqual(S.load_seen(con, "고시공고", "A시"), set())
        S.record_seen(con, "고시공고", "A시", [{"key": k_ok, "status": "ok", "rows": 3}, {"key": k_empty, "status": "empty"}])
        self.assertEqual(S.load_seen(con, "고시공고", "A시"), {k_ok})  # 필지 없는 글은 한 번 더 읽는다
        S.record_seen(con, "고시공고", "A시", [{"key": k_empty, "status": "empty"}])
        self.assertEqual(S.load_seen(con, "고시공고", "A시"), {k_ok, k_empty})
        self.assertEqual(S.load_seen(con, "고시공고", "B시"), set())  # 지자체별로 따로
        old = S.EXTRACT_VERSION
        try:
            S.EXTRACT_VERSION = old + 1  # 추출 코드를 고쳐 버전을 올리면 전부 다시 읽는다
            self.assertEqual(S.load_seen(con, "고시공고", "A시"), set())
        finally:
            S.EXTRACT_VERSION = old
        con.execute("UPDATE seen_posts SET last_at='2020-01-01T00:00:00'")
        S.prune_seen(con)
        self.assertEqual(S.load_seen(con, "고시공고", "A시"), set())  # 오래된 기록은 정리된다


class PruneOld(unittest.TestCase):
    """오래된 점검용 행만 정리하고 필지·공고는 지우지 않는다."""

    def test_prune_keeps_parcels(self):
        import shutil
        import tempfile
        from datetime import datetime, timedelta, timezone
        from core import sqlite_store as S
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        con = S.connect(os.path.join(d, "t.sqlite"))
        self.addCleanup(con.close)
        S._insert_parcel(con, "4380000000999990002", {"sojaeji": "x", "jibun": "1", "post_title": "t", "post_url": "u", "post_date": "2020-01-01"}, "단양군", "공보")
        old, new = "2020-01-01", datetime.now(timezone.utc).date().isoformat()
        for pd in (old, new, None, "2020.01.01"):
            con.execute("INSERT INTO parcels_unresolved (sojaeji, jibun, title, url, post_date, reason) VALUES ('a', '1', ?, 'u', ?, 'no_match')", (str(pd), pd))
        con.execute("INSERT INTO runs (started_at, job) VALUES ('2020-01-01T00:00:00+00:00', 'old')")
        con.execute("INSERT INTO runs (started_at, job) VALUES (?, 'new')", (datetime.now(timezone.utc).isoformat(timespec="seconds"),))
        con.commit()
        S.prune_old(con)
        left = sorted(r[0] for r in con.execute("SELECT title FROM parcels_unresolved"))
        self.assertEqual(left, sorted([new, "None", "2020.01.01"]))  # 오래된 ISO 날짜 행만 사라진다
        self.assertEqual([r[0] for r in con.execute("SELECT job FROM runs")], ["new"])
        self.assertEqual(con.execute("SELECT count(*) FROM parcels").fetchone()[0], 1)
        self.assertEqual(con.execute("SELECT count(*) FROM notices").fetchone()[0], 1)


class UnresolvedRootCauses(unittest.TestCase):
    """PNU 로 못 바꾼 행(parcels_unresolved)을 분석해 찾은 원인별 규칙. 카카오는 가짜 응답으로 대신한다."""

    @staticmethod
    def doc(region2, region3, no, mountain="N", bcode="4480035030"):
        main, _, sub = no.partition("-")
        return {"address": {"b_code": bcode, "mountain_yn": mountain, "main_address_no": main, "sub_address_no": sub,
                            "region_1depth_name": "충남", "region_2depth_name": region2, "region_3depth_name": region3}}

    def resolver(self, known):
        """known: {질의 문자열: [카카오 문서...]}. 목록에 없는 질의는 결과 0건."""
        import shutil
        import tempfile
        from core import sqlite_store as S
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        con = S.connect(os.path.join(d, "t.sqlite"))
        self.addCleanup(con.close)
        r = PnuResolver(con)
        r.key = "test"
        r.ai.enabled = False
        self.calls = []

        def fake(query):
            self.calls.append(query)
            return {"documents": known.get(query, [])}, "ok"
        r._call = fake
        return r

    def test_forest_lot_without_san_gets_san_from_jimok(self):
        """문서 지목이 임야인데 지번에 '산'이 없으면 '산'을 붙여 찾는다(공주시 명곡리 16 임 -> 산16)."""
        r = self.resolver({"공주시 유구읍 명곡리 산16": [self.doc("공주시", "유구읍 명곡리", "16", "Y")]})
        self.assertIsNone(self.resolver({}).resolve("공주시 유구읍 명곡리", "16", city="공주시"))  # 지목을 모르면 산을 붙이지 않는다
        pnu = r.resolve("공주시 유구읍 명곡리", "16", city="공주시", jimok="임")
        self.assertTrue(pnu and pnu[10] == "2" and pnu.endswith("00160000"))
        self.assertIsNone(self.resolver({}).resolve("공주시 유구읍 명곡리", "16", city="공주시", jimok="답"))  # 임야가 아니면 붙이지 않는다

    def test_eupmyeon_rename_is_tried_with_exact_jibun_only(self):
        r = self.resolver({"전라남도 무안군 일로읍 망월리 764": [self.doc("무안군", "일로읍 망월리", "764")]})
        self.assertTrue(r.resolve("전라남도 무안군 일로면 망월리", "764", city="무안군"))
        r2 = self.resolver({"전라남도 무안군 일로읍 망월리 765": [self.doc("무안군", "일로읍 망월리", "765")]})
        self.assertIsNone(r2.resolve("전라남도 무안군 일로면 망월리", "764", city="무안군"))  # 지번이 다르면 인정하지 않는다

    def test_split_jibun_columns_do_not_break_abbreviation(self):
        """'하빈 무등 1238 1238-2'(분할 전·후 지번이 소재지에 붙음) -> 하빈면 무등리 1238-2."""
        r = self.resolver({"달성군 하빈면 무등리 1238-2": [self.doc("달성군", "하빈면 무등리", "1238-2")]})
        self.assertTrue(r.resolve("하빈 무등 1238 1238-2", "1238-2", city="달성군"))

    def test_non_parcel_rows_and_aliases(self):
        from core import pnu as P
        for junk in ("합 계 3", "합계(107필지) 합계( 107", "전북특별자치도 익산시 낭산면 구평리 (2필지) 3", "허가일로부터 10"):
            self.assertTrue(P.looks_like_non_parcel(junk), junk)
        for ok in ("충청남도 공주시 유구읍 명곡리", "하빈 무등", "A1 1-4"):
            self.assertFalse(P.looks_like_non_parcel(ok), ok)
        self.assertEqual(self.resolver({}).resolve_full("합 계 3", "3", city="가평군")[1], "not_parcel")
        old = P.load_aliases
        try:
            P.load_aliases = lambda: {"홍성군": {"화붕리": "화봉리"}}
            self.assertEqual(P.apply_aliases("충청남도 홍성군 화붕리", "홍성군"), "충청남도 홍성군 화봉리")
            self.assertEqual(P.apply_aliases("충청남도 홍성군 화붕리", "공주시"), "충청남도 홍성군 화붕리")  # 다른 지자체에는 적용하지 않는다
        finally:
            P.load_aliases = old


class BareMyeonRiGuard(unittest.TestCase):
    def test_already_suffixed_or_jimok_tokens_are_not_bare_names(self):
        """머리글 근거가 있어도 '유구읍 명곡리'(접미사 있음)·'임 구'(지목)에 면·리를 또 붙이지 않는다(가짜 소재지 '유구읍면 명곡리리' 방지)."""
        self.assertIsNone(J.bare_myeon_ri("유구읍", "명곡리", "", True))
        self.assertIsNone(J.bare_myeon_ri("임", "구", "", True))
        self.assertIsNone(J.bare_myeon_ri("전", "답", "", True))
        self.assertEqual(J.bare_myeon_ri("대강", "당동", "", True), ("대강면", "당동리"))  # 접미사 없는 이름은 머리글 근거로 붙인다

    def test_reset_recent_unresolved_once_per_version(self):
        import shutil
        import tempfile
        from datetime import datetime, timedelta, timezone
        from core import sqlite_store as S
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        con = S.connect(os.path.join(d, "t.sqlite"))
        self.addCleanup(con.close)
        today = datetime.now(timezone.utc).date()
        for pd in (today, today - timedelta(days=10)):
            con.execute("INSERT INTO parcels_unresolved (sojaeji, jibun, title, url, post_date, reason) VALUES ('a', '1', ?, 'u', ?, 'no_match')",
                        (pd.isoformat(), pd.isoformat()))
        con.commit()
        self.assertEqual(S.reset_recent_unresolved(con), 1)  # 최근 글(곧 다시 읽힘)만 비운다
        self.assertEqual(con.execute("SELECT count(*) FROM parcels_unresolved").fetchone()[0], 1)
        con.execute("INSERT INTO parcels_unresolved (sojaeji, jibun, title, url, post_date, reason) VALUES ('b', '2', 'x', 'u', ?, 'no_match')", (today.isoformat(),))
        con.commit()
        self.assertEqual(S.reset_recent_unresolved(con), 0)  # 같은 버전에서는 다시 하지 않는다


class DeclaredLocationAndSanOrder(unittest.TestCase):
    def test_declared_location_fills_bare_ri_rows(self):
        """'위치: 충청남도 아산시 음봉면 동암리, 덕지리 일원' 아래 표에 '동암리 701-6' 만 있으면 문서가 적은 시군·읍면으로 채운다."""
        text = ("○ 위치 : 충청남도 아산시 음봉면 동암리, 덕지리, 월랑리 일원\n소관청별 토지조서\n1 동암리 701-6 도 958.0\n"
                "24 덕지리 536-1 구 199.0 199.0")
        rows = [{"sojaeji": "충청남도 홍성군 동암리 701-6", "jibun_incl": "701-6"}, {"sojaeji": "충청남도 홍성군 덕지리 536-1", "jibun_incl": "536-1"}]
        J.apply_declared_locations(text, rows)
        self.assertEqual([r["sojaeji"] for r in rows], ["충청남도 아산시 음봉면 동암리 701-6", "충청남도 아산시 음봉면 덕지리 536-1"])
        # 행 자신이 다른 시군을 리와 함께 적었으면 그대로 둔다
        rows = [{"sojaeji": "충청남도 홍성군 동암리 3", "jibun_incl": "3"}]
        J.apply_declared_locations(text + " 홍성군 동암리 3 전", rows)
        self.assertEqual(rows[0]["sojaeji"], "충청남도 홍성군 동암리 3")
        # 같은 리가 다른 곳으로 선언되면(모호) 아무것도 바꾸지 않는다
        rows = [{"sojaeji": "충청남도 홍성군 동암리 3", "jibun_incl": "3"}]
        J.apply_declared_locations("위치 : 아산시 음봉면 동암리 일원, 천안시 서북구 동암리 일원", rows)
        self.assertEqual(rows[0]["sojaeji"], "충청남도 홍성군 동암리 3")

    def test_plain_jibun_is_tried_before_san(self):
        """임야 지목이어도 '산' 없는 지번이 실제 있으면 그것을 쓴다(산은 못 찾았을 때만 붙인다)."""
        helper = UnresolvedRootCauses()
        known = {"공주시 유구읍 명곡리 16": [helper.doc("공주시", "유구읍 명곡리", "16")],
                 "공주시 유구읍 명곡리 산16": [helper.doc("공주시", "유구읍 명곡리", "16", "Y")]}
        helper.addCleanup = self.addCleanup
        r = helper.resolver(known)
        pnu = r.resolve("공주시 유구읍 명곡리", "16", city="공주시", jimok="임")
        self.assertEqual(pnu[10], "1")  # 대지(산 아님)
        self.assertEqual(helper.calls, ["공주시 유구읍 명곡리 16"])  # 산 질의는 하지 않았다


class PublicLandInGazetteTables(unittest.TestCase):
    """공보(글로 펴진 표)에서 소유자가 국가·공공기관이면 owner_type='국공유' 로 표시해 함께 수집한다(2026-10-26 사용자 지시, 이전에는 제외).
    소유자가 안 적힌 표는 owner_type 이 빈 값(DB 에서는 미상)이다."""

    R = J.Regions("충청남도", "아산시")

    def lots(self, text):
        return [(r["jibun_incl"], r["owner_type"]) for r in self.R.rows_from_text(text)]

    def test_public_owner_headings_and_owner_cells(self):
        text = ("- 소관청별 토지조서 국유지 - 농림축산식품부 (변경없음) 구분 소재지 지번 지목 대장면적 편입면적 귀속면적 소유관청 비고 "
                "1 동암리 701-6 도 958.0 958.0 958.0 농림축산식품부 2 동암리 701-7 도 360.0 360.0 360.0 농림축산식품부 "
                "- 소관청별 토지조서 공유지 - 아산시 (변경없음) 1 동암리 727-1 도 3,333.1 3,333.1 3,333.1 아산시 "
                "- 관할기관 무상귀속분 (변경없음)")
        self.assertEqual(self.lots(text), [("701-6", "국공유"), ("701-7", "국공유"), ("727-1", "국공유")])  # 국유지·공유지 소제목 아래 표는 공공으로 표시

    def test_private_and_unstated_owner_tables_are_kept(self):
        text = ("- 토지조서 사유지 구분 소재지 지번 지목 면적 1 동암리 801-1 전 100.0 100.0 2 동암리 802 답 200.0 200.0 ")
        self.assertEqual(self.lots(text), [("801-1", ""), ("802", "")])  # 소유자 표기가 없으면 소유 미상으로 읽는다
        mixed = ("- 토지조서 국유지 1 동암리 701-6 도 958.0 958.0 농림축산식품부 "
                 "- 토지조서 사유지 1 동암리 801-1 전 100.0 100.0 2 동암리 802 답 200.0 200.0 ")
        self.assertEqual(self.lots(mixed), [("701-6", "국공유"), ("801-1", ""), ("802", "")])  # 사유지 소제목이 더 가까우면 다시 사유 쪽으로 읽는다

    def test_owner_agency_after_row_without_heading(self):
        text = "1 동암리 701-6 도 958.0 958.0 농림축산식품부 2 동암리 801-1 전 100.0 100.0 홍길동 "
        self.assertEqual(self.lots(text), [("701-6", "국공유"), ("801-1", "")])
