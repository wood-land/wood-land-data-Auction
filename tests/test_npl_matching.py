"""npl/matching.py 단위 테스트 (브라우저/시트 없이 동작). 실행: python -m unittest discover -s tests -v"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "npl"))
import matching  # noqa: E402

HEAD = ["구분", "사건번호", "주소", "입찰일", "감평가", "최저가", "상세페이지"]


def _tab(rows):
    return [HEAD] + rows


class MatchingTest(unittest.TestCase):
    def setUp(self):
        self.index, self.seen = {}, set()
        matching.add_tab_to_index(self.index, self.seen, _tab([
            ["경매", "서울중앙 2024타경639(2)", "경기 이천시 부발읍 신하리 1", "2026-11-20 10:00:00", "100,000,000", "64,000,000",
             "https://x/ca/caView.php?tid=111&chkNo=1&TotNo=5"],
            ["경매", "수원 2024타경639", "경기 화성시 봉담읍 2", "2026-11-21 10:00:00", "300,000,000", "1",
             "https://x/ca/caView.php?tid=222&chkNo=2&TotNo=5"],
            ["공매", "2024-1", "서울", "2026-11-21", "1", "1", "https://x/pa/paView.php?tid=9"],
        ]), "tab1")

    def test_keys(self):
        self.assertEqual(matching.normalize_case_key("24-639 (2)"), ("24", "639"))
        self.assertEqual(matching.normalize_case_key("서울중앙 2024타경639(2)"), ("24", "639"))
        self.assertEqual(matching.case_item_no("24-639 (2)"), "2")

    def test_pa_rows_excluded(self):
        self.assertEqual(self.seen, {"111", "222"})

    def test_same_number_other_court_is_separated_by_price_and_address(self):
        r = {"사건번호": "24-639", "물번": "", "감정가": 300000000, "매각기일": "2026-11-21", "소재지": "경기 화성시 봉담읍 2"}
        cand, score = matching.match_one(r, self.index)
        self.assertEqual(cand["tid"], "222")

    def test_item_number_mismatch_rejected(self):
        r = {"사건번호": "24-639", "물번": "3", "감정가": 100000000, "매각기일": "2026-11-20", "소재지": "경기 이천시 부발읍 신하리 1"}
        cand, _ = matching.match_one(r, self.index)
        self.assertIsNone(cand)

    def test_low_score_is_unmatched(self):
        r = {"사건번호": "24-639", "물번": "", "감정가": 5, "매각기일": "2030-01-01", "소재지": "제주"}
        cand, _ = matching.match_one(r, self.index)
        self.assertIsNone(cand)


if __name__ == "__main__":
    unittest.main()
