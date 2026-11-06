# -*- coding: utf-8 -*-
"""중앙기관 게시판 설정과 게시일 파싱 회귀 테스트(2026-11-06 실측으로 찾은 문제들)."""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cities import central_agencies as C  # noqa: E402
from cms_adapters import gazette_generic as G  # noqa: E402


class ParseDate(unittest.TestCase):
    def test_future_typo_year_in_title_is_skipped(self):
        """서천군보: 제목에 '(2028.8.28.)' 오타, 게시일 칸은 2026-08-28 -> 게시일은 뒤의 정상 날짜."""
        text = "762 서천군보 제1178호(2028.8.28.) 자치행정과 70 2026-08-28 ZIP 파일다운로드"
        self.assertEqual(G._parse_date(text), dt.date(2026, 8, 28))

    def test_normal_first_date_still_wins(self):
        self.assertEqual(G._parse_date("제1871호(2026.10.30.) 2026-10-31"), dt.date(2026, 10, 30))

    def test_only_future_or_invalid_dates_give_none(self):
        self.assertIsNone(G._parse_date("제1호(2099.1.1.)"))
        self.assertIsNone(G._parse_date("2026-02-31"))
        self.assertIsNone(G._parse_date("날짜 없음"))


class CentralAgencyConfig(unittest.TestCase):
    def test_basin_offices_use_mcee_domain(self):
        """옛 www.me.go.kr 은 일부 환경에서 127.0.0.1 로 풀려 접속이 거부된다 -> mcee.go.kr 직접 사용."""
        basin = [c for c in C.CITIES if c.city.endswith("유역환경청")]
        self.assertEqual(len(basin), 4)
        for c in basin:
            self.assertIn("mcee.go.kr", c.base_url, c.city)
            self.assertNotIn("//www.me.go.kr", c.base_url, c.city)

    def test_defense_boards_do_not_miss_compensation_and_plan_notices(self):
        def hit(city, title):
            return any(k in title for k in city.keywords)
        self.assertTrue(hit(C.DIA_FACILITY, "[전라제주]국방·군사시설사업 보상계획 열람공고"))
        self.assertTrue(hit(C.DIA_FACILITY, "00부대 부지 매입 공고"))
        self.assertTrue(hit(C.MND_GOSI, "국방부고시 제2026-36호(국방ㆍ군사시설사업계획 승인/철원지역 군 사용 사유재산 정리사업)"))
        self.assertFalse(hit(C.MND_GOSI, "[국방부고시 제2026-484] 2026년 국방분야 혁신제품 심의예정 공고"))


if __name__ == "__main__":
    unittest.main()
