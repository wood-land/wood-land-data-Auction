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


class ExcludedBoardsTest(unittest.TestCase):
    def test_excluded_boards_are_not_loaded(self):
        cities = {b["city"] for b in G.load_boards(EXCEL)}
        for c in ("경기도청", "서산시", "제주시", "서귀포시"):
            self.assertNotIn(c, cities)
        self.assertIn("제주도청", cities)  # 제주 도보는 그대로 수집한다


if __name__ == "__main__":
    unittest.main()


class HeadOfficeOnlyTest(unittest.TestCase):
    """부산·인천은 광역시청(본청)만 수집한다(사용자 결정 2026-11-13). 자치구·군은 고시공고·공보 모두 수집하지 않는다."""

    def test_gazette_only_head_office_for_busan_and_incheon(self):
        boards = G.load_boards(EXCEL)
        for module, head in (("부산", "부산광역시청"), ("인천", "인천광역시청")):
            cities = {b["city"] for b in boards if b["module"] == module}
            self.assertLessEqual(cities, {head}, f"{module} 에 본청 외 게시판이 남아 있음: {cities}")

    def test_gosigongo_city_lists_are_head_office_only(self):
        from cities import busan, incheon
        self.assertEqual([c.city for c in busan.CITIES], ["부산광역시청"])
        self.assertEqual([c.city for c in incheon.CITIES], ["인천광역시청"])
        self.assertTrue(busan.BUSAN_DISTRICTS and incheon.INCHEON_DISTRICTS)  # 정의는 남겨 둠(다시 켤 수 있다)
