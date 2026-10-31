"""확장자는 .hwpx 인데 내용이 구버전 이진 한글(OLE)인 첨부, 문서가 아닌 응답(HTML·공백)을 가려내는 규칙 테스트.
강원도청·강릉시·경상북도청·달성군(구버전 한글), 통영시·해운대구(오류·이동 안내 페이지) 실데이터에서 확인한 유형이다(2026-10-27~29).
실행: gosi 폴더에서 `python -m unittest discover -s tests -v`"""
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from core import jose_extractor as J  # noqa: E402

OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64


class LegacyHwpTest(unittest.TestCase):
    def test_ole_with_hwpx_extension_is_detected(self):
        self.assertTrue(J._is_legacy_hwp("hwpx", OLE))
        self.assertTrue(J._is_legacy_hwp("HWP", OLE))
        self.assertFalse(J._is_legacy_hwp("hwpx", b"PK\x03\x04rest"))
        self.assertFalse(J._is_legacy_hwp("pdf", OLE))

    def test_not_a_document(self):
        self.assertTrue(J.not_a_document(b"\r\n\r\n\r\n"))
        self.assertTrue(J.not_a_document(b"\r\r\r\r\t<script>alert('x')</script>"))
        self.assertTrue(J.not_a_document(b""))
        self.assertFalse(J.not_a_document(OLE))
        self.assertFalse(J.not_a_document(b"PK\x03\x04" + b"\x00" * 100))
        self.assertFalse(J.not_a_document(b"%PDF-1.4 " + b"x" * 6000))

    def test_legacy_hwp_text_is_read_instead_of_unsupported(self):
        text = "공고\n강원도 춘천시 신북읍 삼옥리 81 전 100\n"
        with mock.patch("core.hwp_text.hwp_to_text", return_value=text):
            self.assertEqual(J._legacy_hwp_text(OLE), text)
            self.assertEqual(J.full_text("hwpx", OLE), text)
            rep = {}
            J.extract_from_attachment(OLE, "hwpx", "고시문.hwpx", "제목", mock.Mock(rows_from_text=lambda t: []),
                                      report=rep)
            self.assertNotEqual(rep["code"], "UNSUPPORTED")

    def test_unreadable_legacy_hwp_gives_empty_text(self):
        from core import hwp_text
        with mock.patch("core.hwp_text.hwp_to_text", side_effect=hwp_text.HwpUnsupported("암호")):
            self.assertEqual(J._legacy_hwp_text(OLE), "")


if __name__ == "__main__":
    unittest.main()
