"""구글시트 목차(시트1)의 E열 '최근추출날짜' 수식 시험(가짜 세션, 네트워크 없음)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import run_log as RL


class _Resp:
    def __init__(self, data=None):
        self._d = data or {}

    def raise_for_status(self):
        pass

    def json(self):
        return self._d


class FakeSession:
    def __init__(self, titles):
        self.titles = titles
        self.put_values = None
        self.cleared = None

    def get(self, url, **kw):
        sheets = [{"properties": {"sheetId": i, "title": t, "index": i}} for i, t in enumerate(self.titles)]
        return _Resp({"sheets": sheets})

    def post(self, url, **kw):
        if url.endswith(":clear"):
            self.cleared = url
        return _Resp()

    def put(self, url, **kw):
        self.put_values = kw["json"]["values"]
        return _Resp()


class LastRecordTest(unittest.TestCase):
    def test_formula_reads_last_row_of_column_a(self):
        f = RL.last_record_formula("PCwj경기_문서처리")
        self.assertIn("INDEX('PCwj경기_문서처리'!A:A,COUNTA('PCwj경기_문서처리'!A:A))", f)
        self.assertIn("COUNTA('PCwj경기_문서처리'!A:A)>1", f)  # 머리글만 있으면 빈 칸

    def test_quote_in_title_is_escaped(self):
        self.assertIn("'a''b'!A:A", RL.last_record_formula("a'b"))

    def test_index_has_five_columns_with_header(self):
        s = FakeSession(["시트1", "PCwj경기_문서처리", "경남_게시판상태", "news_실행기록"])
        RL.RunLog._update_index(s, "https://x/v4/spreadsheets/ID")
        v = s.put_values
        self.assertEqual(v[0], ["지역", "시트", "바로가기(클릭)", "행수", "최근추출날짜"])
        self.assertEqual(len(v), 4)
        for row in v[1:]:
            self.assertEqual(len(row), 5)
            self.assertTrue(row[4].startswith("=IF(COUNTA("))
        self.assertTrue(s.cleared.endswith("!A:E:clear"))
        # 탭 이름이 수식의 해당 행에 맞게 들어가 있다
        by_tab = {r[2].split('"')[-2]: r[4] for r in v[1:]}
        self.assertIn("'news_실행기록'!A:A", by_tab["news_실행기록"])
        self.assertIn("'경남_게시판상태'!A:A", by_tab["경남_게시판상태"])


if __name__ == "__main__":
    unittest.main()
