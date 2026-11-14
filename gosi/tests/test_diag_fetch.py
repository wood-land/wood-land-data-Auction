"""diag_fetch.py(게시판 구조 진단) 테스트 - 네트워크 없이 요약 함수와 도메인 제한, 로컬 서버로 전체 흐름을 확인한다.
실행: gosi 폴더에서 `python -m unittest discover -s tests -v`"""
import http.server
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import diag_fetch as D  # noqa: E402

LIST_HTML = """<html><head><title>부산광역시보</title><meta http-equiv="refresh" content="0;url=/x"></head><body>
<iframe src="/frame.html"></iframe>
<form action="/list.do" method="post"><input name="pageIndex"><input name="bbsId"></form>
<table><tr><td>1</td><td><a href="javascript:fn_view('11')" onclick="fn_view('11')">제1150호 시보</a></td><td>2026-11-10</td></tr>
<tr><td>2</td><td><a href="/a.pdf">제1149호 시보</a></td><td>2026.11.03</td></tr></table>
<script src="/js/ebook.js"></script></body></html>"""


class SummarizeTest(unittest.TestCase):
    def test_structure_is_summarized(self):
        info = D.summarize(LIST_HTML, "https://www.busan.go.kr/news/index")
        self.assertEqual(info["title"], "부산광역시보")
        self.assertEqual(info["tables"], 1)
        self.assertEqual(info["table_rows"], 2)
        self.assertEqual(info["frames"], ["https://www.busan.go.kr/frame.html"])
        self.assertEqual(info["forms"][0]["fields"], ["pageIndex", "bbsId"])
        self.assertEqual(info["lines_with_date_or_issue"], 4)
        self.assertIn("fn_view", info["ebook_or_js_hints"])
        self.assertEqual(info["meta_refresh"], ["0;url=/x"])
        text = D.render("페이지", info)
        self.assertIn("iframe/frame", text)
        self.assertIn("제1150호", text)


class HostGuardTest(unittest.TestCase):
    def test_only_go_kr_is_allowed(self):
        env = {}
        self.assertTrue(D.host_allowed("https://www.busan.go.kr/news/index", env))
        self.assertTrue(D.host_allowed("https://announce.incheon.go.kr/", env))
        self.assertFalse(D.host_allowed("https://evil.example.com/", env))
        self.assertFalse(D.host_allowed("https://www.busan.go.kr.evil.com/", env))
        self.assertFalse(D.host_allowed("file:///etc/passwd", env))
        self.assertFalse(D.host_allowed("http://127.0.0.1:8000/", env))

    def test_override_for_tests_only(self):
        self.assertTrue(D.host_allowed("http://127.0.0.1:8000/", {"DIAG_ALLOW_ANY_HOST": "1"}))

    def test_decode_falls_back_to_cp949(self):
        raw = "제목 시보".encode("cp949")
        text, enc = D.decode_body(raw, None)
        self.assertEqual(text, "제목 시보")
        self.assertEqual(enc, "cp949")


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = LIST_HTML if self.path != "/frame.html" else "<html><title>프레임</title><body>제1호 2026-11-01</body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *a):
        pass


class EndToEndTest(unittest.TestCase):
    def test_main_writes_summary_and_follows_iframe(self):
        srv = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as d:
                os.environ["DIAG_ALLOW_ANY_HOST"] = "1"
                rc = D.main([f"http://127.0.0.1:{srv.server_address[1]}/list", "--out", d])
                self.assertEqual(rc, 0)
                text = Path(d, "summary.txt").read_text(encoding="utf-8")
                self.assertIn("===== 페이지", text)
                self.assertIn("===== iframe 1", text)
                self.assertIn("현재 공보 파서 재현", text)
                self.assertTrue(Path(d, "page.html").exists() and Path(d, "frame1.html").exists())
        finally:
            os.environ.pop("DIAG_ALLOW_ANY_HOST", None)
            srv.shutdown()

    def test_non_go_kr_is_refused(self):
        os.environ.pop("DIAG_ALLOW_ANY_HOST", None)
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(D.main(["https://evil.example.com/", "--out", d]), 2)


class _FakeResp:
    status_code = 200
    url = "https://www.busan.go.kr/x"
    headers = {"content-type": "text/html; charset=utf-8"}
    encoding = "utf-8"
    history = []
    content = "<html><title>ok</title></html>".encode("utf-8")


class _FlakySession:
    def __init__(self, fails):
        self.fails, self.calls = fails, 0

    def get(self, url, **kw):
        self.calls += 1
        if self.calls <= self.fails:
            import requests
            raise requests.exceptions.ConnectionError("Connection reset by peer")
        return _FakeResp()


class RetryTest(unittest.TestCase):
    def test_retries_until_success(self):
        with tempfile.TemporaryDirectory() as d:
            s = _FlakySession(fails=2)
            html, info, attempts = D.fetch_with_retry(s, "https://www.busan.go.kr/x", Path(d), "page", retries=4, wait=0, sleep=lambda w: None)
            self.assertEqual(s.calls, 3)
            self.assertIn("ok", html)
            self.assertEqual(len(attempts), 3)
            self.assertIn("성공", attempts[-1])

    def test_all_failures_raise_with_attempt_log(self):
        with tempfile.TemporaryDirectory() as d:
            s = _FlakySession(fails=9)
            with self.assertRaises(Exception) as cm:
                D.fetch_with_retry(s, "https://www.busan.go.kr/x", Path(d), "page", retries=3, wait=0, sleep=lambda w: None)
            self.assertEqual(s.calls, 3)
            self.assertEqual(len(cm.exception.attempts), 3)



class NoticeDiagHelpersTest(unittest.TestCase):
    """diag_notice.py: 본문 일치 주변 추출과 입력 검증(네트워크 없이)."""

    def test_context_snippets(self):
        import diag_notice as N
        text = "앞 글자 " * 30 + "기정 주안동 599-40 임야" + " 뒤 글자" * 30 + " 변경 주안동 606-7 대"
        got = N.context_snippets(text, r"주안동", width=10)
        self.assertEqual(len(got), 2)
        self.assertIn("기정 주안동 599-40", got[0])
        self.assertIn("변경 주안동 606-7", got[1])

    def test_snippets_skip_overlapping_matches_and_respect_limit(self):
        import diag_notice as N
        text = "주안동 " * 50
        self.assertLessEqual(len(N.context_snippets(text, r"주안동", width=5, limit=3)), 3)

    def test_non_go_kr_and_bad_post_id_are_refused(self):
        import diag_notice as N
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(N.main(["--board-url", "https://evil.example.com/", "--post-id", "1", "--out", d]), 2)
            self.assertEqual(N.main(["--board-url", "https://www.incheon.go.kr/IC010303", "--post-id", "1; rm -rf /", "--out", d]), 2)

if __name__ == "__main__":
    unittest.main()
