"""공보 목록·첨부 파서 보강(2026-10-25 실제 사이트 점검에서 찾은 3가지)의 단위 테스트. 네트워크 없이 돈다.
  - 영양군 전자군보: 날짜 없는 이미지 카드형 목록(다운로드 버튼이 onclick=window.open)
  - 울릉군 군보: 상세 주소가 <script>location.href='…'</script> 껍데기 페이지
  - 구미시 시보: '바로 보기'(뷰어) 링크가 제목/상세로 잡혀 500 오류, 첨부 링크는 따로 있음
실행: gosi 폴더에서 `python -m unittest discover -s tests -v`"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import requests  # noqa: E402

from cms_adapters import gazette_generic as GG  # noqa: E402


class FakeSession:
    """url(쿼리 포함 문자열) -> HTML 매핑. 모르는 주소는 500 을 낸다."""

    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get(self, url, **kw):
        self.calls.append(url)
        resp = requests.Response()
        resp.url = url
        resp.encoding = "utf-8"
        resp.headers["content-type"] = "text/html; charset=utf-8"
        if url in self.pages:
            resp.status_code = 200
            resp._content = self.pages[url].encode("utf-8")
        else:
            resp.status_code = 500
            resp._content = b"error"
        return resp


YEONGYANG = """<html><body><div class="ebook_list">
<div class="ebook br6"><div class="ebook_foot"><span class="tit"><span>군보(1545)</span><i class="ico_new itid"><span class="sr_only">새글</span></i></span>
<div class="btn_flex"><!--button type="button" onclick="window.open('/ybscript.io/common/file_download/1/2/a.pdf?pkey=x&mode=preview', '_blank');">미리보기</button-->
<button class="btn_base" onclick="window.open('/ybscript.io/common/file_download/168534/153940/%EC%98%81%EC%96%91%EA%B5%B0%EB%B3%B4%281%2C545%ED%98%B8%29.pdf?pkey=55gXrT3qv', '_blank');" type="button"><span>다운로드</span></button></div></div></div>
<div class="ebook br6"><div class="ebook_foot"><span class="tit"><span>군보(1544호)</span></span>
<div class="btn_flex"><button class="btn_base" onclick="window.open('/ybscript.io/common/file_download/168533/153939/b.pdf?pkey=y', '_blank');" type="button"><span>다운로드</span></button></div></div></div>
</div></body></html>"""

ULLEUNG_STUB = """<!DOCTYPE HTML><html><head><title></title></head><body>
<script type="text/javascript">//<![CDATA[
 location.href='?cmd=258&bod_uid=49960&mnu_uid=576&';
//]]></script></body></html>"""
ULLEUNG_VIEW = """<html><body><div class="view"><h3>(2026.10.20.)울릉군보 제622호</h3><div class="files">
<a href="/board_download.do?file_uid=58977&amp;mnu_uid=576&amp;bod_uid=49960" title="울릉군보(제622호).pdf 파일 다운로드">울릉군보(제622호).pdf</a>
<a href="#self">울릉군보(제622호).pdf 미리보기 새창</a></div>
<p>""" + "공고 내용 " * 40 + """</p></div></body></html>"""

GUMI_ROW = """<div class="bod_view"><div class="view_info"><ul><li class="view_write"><span>작성자</span> 홍보담당관 </li>
<li class="view_date"><span>등록일</span>{date}</li></ul></div>
<div class="view_cont">구미전자시보 제{no}호<br/>공고<br/>○ 구미시 공고 제2026-2844호 공시송달 공고</div>
<dl class="view_file"><dt>첨부 파일</dt><dd><div><ul class="file_list"><li class="file-item">
<a class="download" href="#" onclick="yhLib.file.download('{fid}','SN1'); return false;" title="첨부파일(구미전자시보 제{no}호.pdf) 다운로드"><span>구미전자시보 제{no}호.pdf</span> <span class="file_size">[0.73MB]</span></a>
<a class="btn_preview" href="#" onclick="yhLib.file.synapView('{fid}','SN1','x','/webdata/','구미전자시보 제{no}호.pdf','false'); return false;" target="_blank"><span class="blank">바로 보기</span></a>
</li></ul></div></dd></dl></div>"""
GUMI_JS = "<script>var yhLib={file:{download:function(a,b){window.open(verifiedURL('/common/file/download.do?atchFileId='+a+'&fileSn='+b));return false;},synapView:function(a,b){}}};</script>"


class EbookCards(unittest.TestCase):
    def test_undated_cards_become_rows_with_direct_file_urls(self):
        """영양군: 날짜 없는 카드 -> 제목/첨부 직접 링크 행. 미리보기(preview) 버튼은 쓰지 않는다."""
        GG._PAGE_MAP.clear()
        rows = GG.fetch_list_page(FakeSession({"https://www.yyg.go.kr/e": YEONGYANG}), "https://www.yyg.go.kr/e", {"name": "군보"}, 1)
        self.assertEqual([r["title"] for r in rows], ["군보(1545)", "군보(1544호)"])  # '새글' 표시는 제목에서 뺀다
        self.assertTrue(all(r["date"] is None for r in rows))
        atts = GG.fetch_attachments(FakeSession({}), rows[0]["detail_url"])  # 상세 조회 없이 목록의 첨부를 돌려준다
        self.assertEqual(len(atts), 1)
        self.assertEqual(atts[0]["ext"], "pdf")
        self.assertIn("/ybscript.io/common/file_download/168534/153940/", atts[0]["url"])
        self.assertNotIn("preview", atts[0]["url"])


class JsRedirectStub(unittest.TestCase):
    def test_follows_location_href_stub_to_find_attachment(self):
        """울릉군: ?cmd=2 는 껍데기, 첨부는 ?cmd=258 에 있다."""
        stub = "https://www.ulleung.go.kr/ko/page.do?mnu_uid=576&bod_uid=49960&cmd=2"
        real = "https://www.ulleung.go.kr/ko/page.do?cmd=258&bod_uid=49960&mnu_uid=576&"
        s = FakeSession({stub: ULLEUNG_STUB, real: ULLEUNG_VIEW})
        atts = GG.fetch_attachments(s, stub)
        self.assertEqual(s.calls, [stub, real])
        self.assertEqual(len(atts), 1)
        self.assertIn("board_download.do?file_uid=58977", atts[0]["url"])

    def test_follows_redirect_even_when_page_has_menus(self):
        """실제 울릉군 응답: 메뉴 링크가 수백 개 있는 전체 페이지 위쪽에 한 줄 리다이렉트 스크립트가 있다."""
        full = ULLEUNG_STUB.replace("</body>", "<ul>" + "<li><a href='/m'>메뉴</a></li>" * 50 + "</ul></body>")
        stub = "https://www.ulleung.go.kr/ko/page.do?mnu_uid=576&bod_uid=49960&cmd=2"
        real = "https://www.ulleung.go.kr/ko/page.do?cmd=258&bod_uid=49960&mnu_uid=576&"
        s = FakeSession({stub: full, real: ULLEUNG_VIEW})
        atts = GG.fetch_attachments(s, stub)
        self.assertEqual(s.calls, [stub, real])
        self.assertEqual(len(atts), 1)

    def test_normal_pages_are_not_followed(self):
        """보이는 글자가 많은 일반 페이지에 location.href 가 있어도 따라가지 않는다."""
        page = "<html><body><p>" + "본문 " * 60 + "</p><script>function f(){location.href='/x';}</script></body></html>"
        s = FakeSession({"https://a.go.kr/p": page})
        GG._get(s, "https://a.go.kr/p")
        self.assertEqual(s.calls, ["https://a.go.kr/p"])


class ViewerLinkNotTitle(unittest.TestCase):
    def test_gumi_uses_download_file_not_viewer(self):
        """구미시: 제목/상세가 '바로 보기' 뷰어(500)가 아니라 첨부 파일이 되고, 상세를 열지 않고도 첨부가 나온다."""
        GG._PAGE_MAP.clear()
        html = ("<html><body><div>" + GUMI_ROW.format(date="2026-10-21(수)", no=2317, fid="AAA")
                + GUMI_ROW.format(date="2026-10-14(수)", no=2316, fid="BBB") + "</div>" + GUMI_JS + "</body></html>")
        url = "https://www.gumi.go.kr/portal/contents.do?mid=0401090000"
        s = FakeSession({url: html})
        rows = GG.fetch_list_page(s, url, {"name": "시보"}, 1)
        # 한 글에서 후보 요소가 여러 개 잡혀 같은 글이 중복 행으로 나오는 것은 예전부터의 동작(run_gazette 가 (제목, 날짜)로 걸러낸다)
        self.assertEqual({r["detail_url"] for r in rows}, {
            "https://www.gumi.go.kr/common/file/download.do?atchFileId=AAA&fileSn=SN1",
            "https://www.gumi.go.kr/common/file/download.do?atchFileId=BBB&fileSn=SN1"})
        self.assertEqual(rows[0]["title"], "구미전자시보 제2317호.pdf")
        self.assertIn("/common/file/download.do?atchFileId=AAA", rows[0]["detail_url"])
        self.assertNotIn("viewer", rows[0]["detail_url"])
        atts = GG.fetch_attachments(FakeSession({}), rows[0]["detail_url"])  # 네트워크 없이 첨부가 나온다
        self.assertEqual(atts[0]["ext"], "pdf")

    def test_detail_failure_falls_back_to_list_attachments(self):
        """상세가 500 이어도 목록에서 이미 본 첨부가 있으면 그것을 쓴다."""
        GG._LIST_FILES["https://x.go.kr/detail"] = [{"name": "a.pdf", "url": "https://x.go.kr/file/a.pdf", "ext": "pdf", "sized": False}]
        atts = GG.fetch_attachments(FakeSession({}), "https://x.go.kr/detail")  # 이 주소는 FakeSession 에서 500
        self.assertEqual([a["url"] for a in atts], ["https://x.go.kr/file/a.pdf"])


if __name__ == "__main__":
    unittest.main()
