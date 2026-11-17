"""고시공고 검색 키워드('손실보상' 추가, 2026-10-31)와 공보 게시판 제외 목록(경기도청·서산시·제주시·서귀포시) 테스트.
실행: gosi 폴더에서 `python -m unittest discover -s tests -v`"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import run_gazette as G  # noqa: E402
from cities._shared import DEFAULT_BLACKLIST, DEFAULT_KEYWORDS  # noqa: E402

EXCEL = os.path.join(os.path.dirname(HERE), "output", "시군구_공보게시판_목록_new.xlsx")


class KeywordsTest(unittest.TestCase):
    def test_sonsil_bosang_is_a_keyword(self):
        self.assertIn("손실보상", DEFAULT_KEYWORDS)

    def test_keyword_not_blocked_by_blacklist(self):
        title = "OO도로 개설공사 손실보상 협의 공고"
        self.assertTrue(any(k in title for k in DEFAULT_KEYWORDS))
        self.assertFalse(any(b in title for b in DEFAULT_BLACKLIST))


class RiverZoneExclusionTest(unittest.TestCase):
    """하천구역 결정·지정·변경 고시는 공익사업 시행이 아니라 구역 지정 공고라 제외한다(사용자 지시 2026-11-17)."""

    def _blocked(self, title):
        from core.board_crawler import matches_blacklist
        return matches_blacklist(title, DEFAULT_BLACKLIST)

    def test_river_zone_designation_is_blocked(self):
        for t in ("해남 남천 등 6개 하천 하천구역 결정(변경) 및 지형도면 고시를 위한 주민 열람 공고",
                  "하천구역 결정(변경) 및 지형도면 고시 - 죽동천",
                  "하천공사 준공, 하천구역의 결정(변경) 및 지형도면 고시(양동지구 하천재해예방사업)",
                  "소하천구역의 결정(변경,폐지) 및 지형도면 고시",
                  "홍성군 고시 제2026-212호 소하천 구역의 결정[변경] 및 지형도면[변경]에 관한 고시",
                  "BA OF 하천구역 결정(변경, 홍수관리구역 지정 및 지형도면 고시를 위한 주민 열람 공고"):
            self.assertTrue(self._blocked(t), t)

    def test_river_projects_are_not_blocked(self):
        for t in ("남강 산청지구 하천환경정비사업 보상계획 열람 공고", "가산천 가산1지구 지방하천정비사업 보상계획 등 공고",
                  "하천공사 시행계획(변경) 고시 하천 보상"):
            self.assertFalse(self._blocked(t), t)


class CadastralResurveyExclusionTest(unittest.TestCase):
    """지적재조사지구 지정·변경·완료지구 고시는 제외한다(사용자 지시 2026-11-17)."""

    def test_resurvey_district_notices_are_blocked(self):
        from core.board_crawler import matches_blacklist
        for t in ("강원특별자치도 고시 제2026-468호 강원특별자치도 지적재조사지구 지정(변경) 고시",
                  "◉경상남도 고시 제2026-481호 지적재조사지구 변경 고시",
                  "대전광역시 고시 제2026-262호 중구 산성1지구 지적재조사지구 지정 고시",
                  "오산시 고시 제2026-249호 지적재조사사업 완료지구 지형도면 고시"):
            self.assertTrue(matches_blacklist(t, DEFAULT_BLACKLIST), t)


class ReclamationExclusionTest(unittest.TestCase):
    """제목에 '개간'이 들어간 공고(예: 정비사업(개간))는 추출하지 않는다(사용자 지시 2026-11-17)."""

    def test_title_with_gaegan_is_blocked(self):
        from core.board_crawler import matches_blacklist
        for t in ("OO지구 농어촌정비사업(개간) 사업시행계획 공고", "○○ 개간 허가 공고"):
            self.assertTrue(matches_blacklist(t, DEFAULT_BLACKLIST), t)
        self.assertFalse(matches_blacklist("OO도로 개설공사 보상계획 공고", DEFAULT_BLACKLIST))


class AdministrativeDispositionExclusionTest(unittest.TestCase):
    """토지 보상과 무관한 영업·사업장 행정처분 통지는 '의견 청취' 키워드에 걸려도 제외한다(사용자 지시 2026-11-17)."""

    def test_minbak_disposition_is_blocked_but_land_hearing_is_not(self):
        from core.board_crawler import matches_blacklist
        t = "농어촌민박사업자 직권말소 및 사업장 폐쇄 처분에 대한 의견청취 통지"
        self.assertTrue(any(k.replace(" ", "") in t.replace(" ", "") for k in DEFAULT_KEYWORDS))  # 키워드에는 걸린다
        self.assertTrue(matches_blacklist(t, DEFAULT_BLACKLIST))
        self.assertFalse(matches_blacklist("OO도로 개설공사 사업인정에 관한 의견청취 공고", DEFAULT_BLACKLIST))


class ExcludedBoardsTest(unittest.TestCase):
    def test_excluded_boards_are_not_loaded(self):
        cities = {b["city"] for b in G.load_boards(EXCEL)}
        for c in ("경기도청", "서산시", "제주시", "서귀포시"):
            self.assertNotIn(c, cities)
        self.assertIn("제주도청", cities)  # 제주 도보는 그대로 수집한다


if __name__ == "__main__":
    unittest.main()
