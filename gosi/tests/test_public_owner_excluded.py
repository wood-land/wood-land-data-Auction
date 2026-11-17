"""소유자가 국·공·시유지(국가·지자체·공공기관)인 필지는 추출하지 않는다(2026-11-17, 제천시 청풍면 사오리 토지조서로 재현).
표의 소유자 칸이 '공'·'국' 한 글자, 주소 칸이 '충청북도'·'제천시'·'산림청'·'건설교통부' 이고 사유지는 사람 이름·개인 주소다.
실행: gosi 폴더에서 `python -m unittest discover -s tests -v`"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from core import jose_extractor as J  # noqa: E402

HEAD1 = ["일련번호", "토지소재지", "토지소재지", "지번", "지목", "지적(㎡)", "편입면적(㎡)", "소유자", "소유자", "비고"]
HEAD2 = ["일련번호", "구", "동", "지번", "지목", "지적(㎡)", "편입면적(㎡)", "성명", "주소", "비고"]
GRID = [HEAD1, HEAD2,
        ["1", "청풍", "사오", "65-8", "도", "1,636", "86.0", "공", "충청북도", ""],
        ["2", "청풍", "사오", "65-7", "도", "12,287", "378", "공", "제천시", ""],
        ["3", "청풍", "사오", "산19-2", "임", "79,464", "424", "국", "산림청", ""],
        ["4", "청풍", "사오", "57-12", "도", "232", "32", "국", "건설교통부", ""],
        ["5", "청풍", "사오", "산18-1", "임", "185,501", "291", "오근조", "서울 강남 개포동 189", ""],
        ["6", "청풍", "사오", "82-8", "전", "1,136", "30", "홍길동", "제천시 청풍면 사오리 12", ""]]


class PublicOwnerExcludedTest(unittest.TestCase):
    def _rows(self, grid=GRID):
        J._NOTICE_LOCAL.text = "소재지: 제천시 청풍면 사오리 일원"
        try:
            rows, _ = J.rows_from_document_grids([(1, 0, grid)], "a.pdf", "토지조서")
        finally:
            J._NOTICE_LOCAL.text = ""
        return rows

    def test_public_rows_are_classified(self):
        self.assertEqual([r["owner_type"] for r in self._rows()], ["국공유", "국공유", "국공유", "국공유", "사유", "사유"])

    def test_public_rows_are_dropped(self):
        rows, dropped = J.drop_public_owner_rows(self._rows())
        self.assertEqual(dropped, 4)
        self.assertEqual([r["jibun_incl"] for r in rows], ["산18-1", "82-8"])

    def test_all_public_gives_empty_result(self):
        rows, dropped = J.drop_public_owner_rows(self._rows(GRID[:6]))
        self.assertEqual((rows, dropped), ([], 4))


if __name__ == "__main__":
    unittest.main()
