"""임시 배치 탭 중간 저장의 행 번호 처리 단위 테스트(2026-11-07).
배경: 로컬 엑셀에는 이번 주 탭의 기존 행(약 9천 행)이 먼저 들어 있고 임시 배치 탭에는 새 물건만 쌓이는데, 서식 적용·직전 저장분 확인을
로컬 행 번호로 해서 'Range (...!B8893) exceeds grid limits. Max rows: 101' 오류가 자동저장마다 났다. 실제로 쓴 행 범위를 응답에서 읽는다.
실행: auction 폴더에서 `python -m unittest discover -s tests -v` (네트워크 없이 돈다)"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openpyxl import Workbook  # noqa: E402

import crawler as C  # noqa: E402


class UpdatedRowSpan(unittest.TestCase):
    def test_parses_range(self):
        self.assertEqual(C._updated_row_span({"updates": {"updatedRange": "'_batch_20261031_W44_data_x'!A2:AC79"}}), (2, 79))
        self.assertEqual(C._updated_row_span({"updates": {"updatedRange": "Sheet1!A5:AC5"}}), (5, 5))
        self.assertEqual(C._updated_row_span({"updates": {"updatedRange": "Sheet1!A7"}}), (7, 7))

    def test_unreadable_gives_none(self):
        for bad in (None, {}, {"updates": {}}, {"updates": {"updatedRange": ""}}, "x"):
            self.assertIsNone(C._updated_row_span(bad))


class FakeWs:
    """배치 탭: 헤더 + 100행 격자로 시작. append 응답은 실제 API처럼 이 탭의 행 번호를 돌려준다."""
    title = "_batch_test"

    def __init__(self):
        self.row_count, self.col_count = 101, 40
        self.used = 1  # 헤더만
        self.formats = []
        self.resized = []

    def resize(self, rows=None, cols=None):
        self.resized.append((rows, cols))
        self.row_count = rows or self.row_count
        self.col_count = cols or self.col_count

    def append_rows(self, values, value_input_option=None, table_range=None):
        start = self.used + 1
        self.used += len(values)
        return {"updates": {"updatedRange": f"'{self.title}'!A{start}:AC{self.used}"}}

    def format(self, rng, fmt):
        self.formats.append(rng)


class AppendUsesTabRowNumbers(unittest.TestCase):
    def make_local(self, existing, new):
        wb = Workbook()
        sh = wb.active
        sh.append(["h"] * 3)
        for i in range(existing + new):
            sh.append([f"r{i}", 1, 2])
        return sh

    def test_formats_only_rows_written_in_batch_tab_not_local_row_numbers(self):
        ws = FakeWs()
        sh = self.make_local(existing=8892, new=78)          # 로컬 8,971행, 이 중 기존 8,892행은 배치 탭에 없다
        state = {"synced_rows": 1 + 8892}
        self.assertTrue(C.append_new_rows_to_gsheet(sh, ws, state))
        self.assertEqual(state["synced_rows"], sh.max_row)    # 로컬 기준 진행 위치는 그대로
        self.assertEqual(state["remote_last_row"], 79)        # 탭 기준 마지막 행 = 헤더 + 78
        self.assertTrue(all(int("".join(c for c in r.split(":")[0] if c.isdigit())) <= 79 for r in ws.formats), ws.formats)
        self.assertTrue(all(r[0] is None or r[0] < 500 for r in ws.resized), ws.resized)  # 로컬 행 수(9천)만큼 부풀리지 않는다

    def test_second_autosave_continues_after_previous_last_row(self):
        ws = FakeWs()
        sh = self.make_local(existing=8892, new=78)
        state = {"synced_rows": 1 + 8892}
        C.append_new_rows_to_gsheet(sh, ws, state)
        for i in range(80):
            sh.append([f"n{i}", 1, 2])
        C.append_new_rows_to_gsheet(sh, ws, state)
        self.assertEqual(state["remote_last_row"], 159)

    def test_no_span_in_response_does_not_break(self):
        ws = FakeWs()
        ws.append_rows = lambda *a, **k: None
        sh = self.make_local(existing=5, new=3)
        state = {"synced_rows": 6}
        self.assertTrue(C.append_new_rows_to_gsheet(sh, ws, state))
        self.assertNotIn("remote_last_row", state)
        self.assertEqual(ws.formats, [])


if __name__ == "__main__":
    unittest.main()
