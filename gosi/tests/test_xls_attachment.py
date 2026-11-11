"""구버전 .xls 첨부(한국부동산원 토지조서 열람용) 지원 테스트 (2026-11-10).
이전에는 .xls 가 UNSUPPORTED 로 처리돼 부동산원 글이 0필지로 적재됐다.
실행: gosi 폴더에서 `python -m unittest discover -s tests -v`"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from core.board_crawler import JOSE_SUPPORTED_EXT  # noqa: E402
from core.jose_extractor import Regions, extract_from_attachment, local_grids  # noqa: E402

FIXTURE = os.path.join(HERE, "fixtures", "reb_jiso_small.xls")


class XlsAttachmentTest(unittest.TestCase):
    def setUp(self):
        with open(FIXTURE, "rb") as f:
            self.data = f.read()

    def test_crawler_does_not_skip_xls(self):
        # 2026-11-10: 추출기는 .xls 를 읽는데 크롤러의 지원 확장자에서 빠져 첨부가 조용히 건너뛰어졌다(Actions 실행으로 발견).
        self.assertIn("xls", JOSE_SUPPORTED_EXT)

    def test_xls_is_read_as_grid(self):
        grids = local_grids("xls", self.data)
        self.assertTrue(grids)

    def test_xls_with_wrong_signature_is_unsupported(self):
        self.assertIsNone(local_grids("xls", b"PK\x03\x04not-ole"))

    def test_extract_parcels_from_xls(self):
        rep = {}
        rows = extract_from_attachment(
            self.data, "xls", "붙임2. 토지조서(열람용).xls", "시험 지방도 확포장공사",
            Regions(sido_name="대구광역시", sigun_name="동구"), report=rep,
        )
        self.assertEqual(rep["code"], "OK")
        self.assertEqual([r["jibun"] for r in rows], ["186-1", "185-3"])
        self.assertTrue(all("원화리" in r["sojaeji"] for r in rows))


if __name__ == "__main__":
    unittest.main()
