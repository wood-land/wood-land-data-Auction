"""건수 검증(judge_count_shortfall) 단위 테스트. 실행: auction 폴더에서 `python -m unittest discover -s tests -v`
(브라우저·네트워크 없이 돈다. 실제로 겪은 사례를 그대로 넣어 둔다.)"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import crawler as C  # noqa: E402


class CountShortfall(unittest.TestCase):
    def test_tolerance_is_at_least_3_or_0_1_percent(self):
        self.assertEqual(C.count_shortfall_tolerance(100), 3)
        self.assertEqual(C.count_shortfall_tolerance(2514), 3)
        self.assertEqual(C.count_shortfall_tolerance(6570), 6)

    def test_one_missing_with_no_unresolved_is_warning_not_failure(self):
        """2026-10-24 토요일: 공매 사이트 2,514건 / 스캔 2,513건 / 추출 실패 0건 -> 경고만."""
        fails, warns = C.judge_count_shortfall("공매", 2514, 2513, 0, 2856)
        self.assertEqual(fails, [])
        self.assertEqual(len(warns), 1)

    def test_two_missing_in_auction_is_warning(self):
        """2026-10-23 금요일: 경매 6,570건 / 스캔 6,568건 / 추출 실패 0건 -> 경고만."""
        fails, warns = C.judge_count_shortfall("경매", 6570, 6568, 0, 9495)
        self.assertEqual(fails, [])
        self.assertEqual(len(warns), 1)

    def test_unresolved_failure_is_never_tolerated(self):
        fails, _ = C.judge_count_shortfall("공매", 2514, 2513, 1, 2856)
        self.assertEqual(len(fails), 1)

    def test_large_shortfall_fails(self):
        fails, _ = C.judge_count_shortfall("공매", 2514, 2400, 0, 2856)
        self.assertEqual(len(fails), 1)

    def test_rows_fewer_than_expected_fails(self):
        fails, _ = C.judge_count_shortfall("공매", 2514, 2514, 0, 2000)
        self.assertEqual(len(fails), 1)

    def test_exact_match_is_clean(self):
        self.assertEqual(C.judge_count_shortfall("경매", 100, 100, 0, 150), ([], []))


if __name__ == "__main__":
    unittest.main()
