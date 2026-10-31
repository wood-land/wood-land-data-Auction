"""공보 목록 파서 보강(2026-10-31 실제 사이트 점검) 단위 테스트. 네트워크 없이 돈다.
  - 보령시 시보: '시보 1150호'(제 없는 호수), 첨부 주소·글자에 확장자 없이 title="PDF 로 받아 보실 수 있습니다"
  - 통영시 공보: <tr><th>통영시 공보 제693호</th><td>다운로드</td></tr> 표. 목록 행이 표 전체로 넓어져 모든 호가 한 글로 묶이던 문제
실행: gosi 폴더에서 `python -m unittest discover -s tests -v`"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from cms_adapters import gazette_generic as GG  # noqa: E402
from test_gazette_boards import FakeSession  # noqa: E402

BORYEONG = """<html><body><ul>
<li><div><p>시보 1150호</p><a href="/cmm/fms/FileDown.do?atchFileId=FILE_1&amp;fileSn=1" title="해당 소식지를 PDF 로 받아 보실 수 있습니다.">다운로드</a>
<a href="#" onclick="preview('eBook_D','FILE_1', '1'); return false;">미리보기</a></div></li>
<li><div><p>시보 1149호</p><a href="/cmm/fms/FileDown.do?atchFileId=FILE_2&amp;fileSn=1" title="해당 소식지를 PDF 로 받아 보실 수 있습니다.">다운로드</a>
<a href="#" onclick="preview('eBook_D','FILE_2', '1'); return false;">미리보기</a></div></li>
</ul></body></html>"""

TONGYEONG = """<html><body><table><tbody>
<tr><td>356</td><th scope="row">통영시 공보 제693호</th><td><a class="download" href="/board/download.do?gcode=9105&amp;name=a693.pdf" title="통영시 공보 제693호.pdf 다운로드">다운로드</a></td></tr>
<tr><td>355</td><th scope="row">통영시 공보 제692호</th><td><a class="download" href="/board/download.do?gcode=9105&amp;name=a692.pdf" title="통영시 공보 제692호.pdf 다운로드">다운로드</a></td></tr>
</tbody></table></body></html>"""


class GazetteBoards2Test(unittest.TestCase):
    def test_issue_number_without_je(self):
        self.assertTrue(GG.ISSUE_RE.search("시보 1150호"))
        self.assertTrue(GG.ISSUE_RE.search("군보 987 호"))
        self.assertTrue(GG.ISSUE_RE.search("제693호"))
        self.assertFalse(GG.ISSUE_RE.search("101호 사무실"))  # 간행물 이름이 앞에 없으면 호실 번호로 보고 읽지 않는다

    def test_boryeong_rows_and_pdf_ext(self):
        url = "https://www.brcn.go.kr/list.do"
        rows = GG.fetch_list_page(FakeSession({url: BORYEONG}), url, {"name": "시보"}, 1)
        self.assertEqual([r["title"] for r in rows], ["시보 1150호", "시보 1149호"])
        atts = GG.fetch_attachments(FakeSession({}), rows[0]["detail_url"])
        self.assertEqual(len(atts), 1)
        self.assertEqual(atts[0]["ext"], "pdf")

    def test_tongyeong_each_issue_is_its_own_post(self):
        url = "https://www.tongyeong.go.kr/00852/00872/00882.web"
        rows = GG.fetch_list_page(FakeSession({url: TONGYEONG}), url, {"name": "공보"}, 1)
        self.assertEqual([r["title"] for r in rows], ["통영시 공보 제693호", "통영시 공보 제692호"])
        self.assertNotEqual(rows[0]["detail_url"], rows[1]["detail_url"])
        atts = GG.fetch_attachments(FakeSession({}), rows[0]["detail_url"])
        self.assertEqual(len(atts), 1)  # 한 호에 첨부 하나(다른 호 파일이 섞이지 않는다)
        self.assertIn("a693", atts[0]["url"])


if __name__ == "__main__":
    unittest.main()
