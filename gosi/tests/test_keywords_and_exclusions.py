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


class ExcludedBoardsTest(unittest.TestCase):
    def test_excluded_boards_are_not_loaded(self):
        cities = {b["city"] for b in G.load_boards(EXCEL)}
        for c in ("경기도청", "서산시", "제주시", "서귀포시"):
            self.assertNotIn(c, cities)
        self.assertIn("제주도청", cities)  # 제주 도보는 그대로 수집한다


if __name__ == "__main__":
    unittest.main()
