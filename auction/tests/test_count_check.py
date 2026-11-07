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


class RunShouldFail(unittest.TestCase):
    """2026-11-07: 목요일 예약 실행의 '마감 때문에 미완료'만 경고로, 나머지는 그대로 실패."""
    SAFE = {"OK", "건너뜀(원격이 이미 더 많음, 안전)", ""}
    NOTES = ["마감 320분 도달", "경매 수집 미완료(처리 6,387 / 시작 6,727)"]

    def test_deadline_partial_is_warning_only_when_partial_ok(self):
        self.assertFalse(C.run_should_fail("OK", True, self.NOTES, True, True, self.SAFE))
        self.assertTrue(C.run_should_fail("OK", True, self.NOTES, True, False, self.SAFE))  # 토요일·수동 실행은 그대로 실패

    def test_incomplete_without_deadline_still_fails(self):
        self.assertTrue(C.run_should_fail("OK", True, ["경매 수집 미완료(처리 100 / 시작 6,727)"], False, True, self.SAFE))

    def test_unsafe_merge_or_count_failure_still_fails_even_if_partial_ok(self):
        self.assertTrue(C.run_should_fail("병합 실패", True, self.NOTES, True, True, self.SAFE))
        self.assertTrue(C.run_should_fail("OK", False, self.NOTES, True, True, self.SAFE))

    def test_clean_run_does_not_fail(self):
        self.assertFalse(C.run_should_fail("OK", True, [], False, False, self.SAFE))
        self.assertFalse(C.run_should_fail("", True, [], False, True, self.SAFE))


if __name__ == "__main__":
    unittest.main()
