"""원주시 시보(e-카탈로그): 목록은 iframe 의 JS 배열 arItem, 본문은 쪽별 XML(search.xml). 2026-10-31 실제 사이트에서 확인한 구조. 네트워크 없이 돈다.
실행: gosi 폴더에서 `python -m unittest discover -s tests -v`"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from cms_adapters import gazette_generic as GG  # noqa: E402
from core import gazette_extractor as GX  # noqa: E402

LIST_HTML = """<script>
var arItem = new Array();
arItem[0] = new Array('0205T40000','AFC00','제1871호(2026.10.30.)','2109','','001.jpg','','8','');
arItem[1] = new Array('0205T30000','AFC00','제1870호(2026.10.23.)','2108','','001.jpg','','24','');
</script>"""

XML = """<?xml version="1.0" encoding="utf-8"?>
<document>
	<page><no>1</no><search><![CDATA[원 주 시 시보 제1871호 ○ 공고 제2026-2865호 원주 도시계획시설 체육공원201호 사업 실시계획 인가 고시 토지조서 소재지 태장동 2790 전 100 ○ 공고 제2026-2900호 다른 공고]]></search></page>
	<page><no>2</no><search><![CDATA[]]></search></page>
</document>"""


class WonjuEbookTest(unittest.TestCase):
    def test_list_items_with_parentheses_in_title(self):
        rows = GG.wonju_rows(LIST_HTML, {"name": "시보"})
        self.assertEqual([r["notice_no"] for r in rows], ["제1871호", "제1870호"])
        self.assertEqual(rows[0]["date_str"], "2026-10-30")
        self.assertEqual(rows[0]["detail_url"], "https://www.wonju.go.kr/e-book/catImage/2109/search.xml")

    def test_attachment_is_the_search_xml(self):
        atts = GG.fetch_attachments(None, "https://www.wonju.go.kr/e-book/catImage/2109/search.xml")
        self.assertEqual(len(atts), 1)
        self.assertEqual(atts[0]["ext"], "xml")

    def test_ebook_xml_is_sniffed_and_split_by_notice(self):
        data = XML.encode("utf-8")
        self.assertEqual(GX.sniff_kind(data), "ebook_xml")
        text = GX.document_text(data)
        self.assertIn("태장동 2790", text)
        notices = [n for n in GX.split_notices(text)]
        self.assertGreaterEqual(len(notices), 2)  # 공고마다 줄이 나뉜다

    def test_plain_xml_is_not_ebook(self):
        self.assertEqual(GX.sniff_kind(b"<?xml version='1.0'?><root/>"), "unknown")


if __name__ == "__main__":
    unittest.main()
