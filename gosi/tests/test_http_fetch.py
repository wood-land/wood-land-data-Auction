"""core/http_fetch.py(재시도 + 서버 인증서 체인 보완)와 남해군 어댑터 수정(amode=_view)의 단위 테스트. 네트워크 없이 돈다.
실행: gosi 폴더에서 `python -m unittest discover -s tests -v`"""
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import requests  # noqa: E402
from requests.adapters import HTTPAdapter  # noqa: E402

from cms_adapters import haman_web_board  # noqa: E402
from core import http_fetch  # noqa: E402


def http_error(status):
    resp = requests.Response()
    resp.status_code = status
    return requests.exceptions.HTTPError(f"{status} error", response=resp)


class RetryCall(unittest.TestCase):
    def run_flaky(self, errors, tries=3):
        calls = []

        def f():
            calls.append(1)
            if len(calls) <= len(errors):
                raise errors[len(calls) - 1]
            return "ok"

        slept = []
        try:
            return http_fetch.retry_call(f, tries=tries, sleep=slept.append), len(calls), slept
        except Exception as e:  # noqa: BLE001
            return e, len(calls), slept

    def test_400_twice_then_success(self):
        """영천시·안동시: 같은 첨부가 처음엔 400, 다시 받으면 성공."""
        result, calls, slept = self.run_flaky([http_error(400), http_error(400)])
        self.assertEqual((result, calls), ("ok", 3))
        self.assertEqual(slept, [1.5, 3.0])

    def test_timeout_is_retried(self):
        """합천군: ReadTimeout 도 다시 받는다."""
        result, calls, _ = self.run_flaky([requests.exceptions.ReadTimeout("slow")])
        self.assertEqual((result, calls), ("ok", 2))

    def test_403_and_404_are_not_retried(self):
        for status in (401, 403, 404):
            result, calls, _ = self.run_flaky([http_error(status)])
            self.assertIsInstance(result, requests.exceptions.HTTPError)
            self.assertEqual(calls, 1, status)

    def test_ssl_error_is_not_retried(self):
        result, calls, _ = self.run_flaky([requests.exceptions.SSLError("bad cert")])
        self.assertIsInstance(result, requests.exceptions.SSLError)
        self.assertEqual(calls, 1)

    def test_gives_up_after_tries(self):
        result, calls, _ = self.run_flaky([http_error(503)] * 5, tries=3)
        self.assertIsInstance(result, requests.exceptions.HTTPError)
        self.assertEqual(calls, 3)


class ExtraCaAdapter(unittest.TestCase):
    def sent_verify(self, url, verify=True):
        adapter = http_fetch.ExtraCaAdapter()
        req = requests.Request("GET", url).prepare()
        with mock.patch.object(HTTPAdapter, "send", return_value="resp") as send:
            adapter.send(req, verify=verify)
        return send.call_args.kwargs["verify"]

    def test_gokseong_gets_extended_bundle(self):
        v = self.sent_verify("https://eminwon.gokseong.go.kr/emwp/jsp/ofr/FileDown.jsp")
        self.assertTrue(isinstance(v, str) and v.endswith(".pem") and os.path.exists(v))
        text = open(v, encoding="utf-8").read()
        extra = (http_fetch.EXTRA_CA_DIR / "gokseong_intermediate.pem").read_text(encoding="utf-8").strip()
        self.assertIn(extra, text)  # 곡성이 빠뜨린 중간 인증서가 들어 있다
        self.assertGreater(len(text), len(extra) + 10000)  # certifi 기본 번들도 같이 들어 있다

    def test_other_hosts_keep_default_verification(self):
        self.assertIs(self.sent_verify("https://www.namhae.go.kr/"), True)

    def test_verify_false_is_left_alone(self):
        self.assertIs(self.sent_verify("https://eminwon.gokseong.go.kr/", verify=False), False)

    def test_install_mounts_adapter(self):
        s = http_fetch.install(requests.Session())
        self.assertIsInstance(s.get_adapter("https://eminwon.gokseong.go.kr/"), http_fetch.ExtraCaAdapter)


class FakeSession:
    def __init__(self, html):
        self.html = html

    def get(self, url, **kw):
        resp = requests.Response()
        resp.status_code = 200
        resp._content = self.html.encode("utf-8")
        resp.encoding = "utf-8"
        resp.url = "https://www.namhae.go.kr/modules/saeol/gosi.do?pageCd=X&siteGubun=portal"
        return resp


def list_html(href):
    return (f'<div class="list1f1t3i1"><ul class="lst1"><li class="li1"><div><a class="a1" href="{href}">'
            '<span class="wrap1texts"><strong class="t1">2027년 지적재조사사업 실시계획 공람공고</strong>'
            '<i class="wrap1t3"><span class="t3">고시번호 : 남해군 공고 제2026-1510호</span>'
            '<span class="t3">등록일 : 2026-10-23</span></i></span></a></div></li></ul></div>')


class NamhaeAdapter(unittest.TestCase):
    def rows(self, href):
        return haman_web_board.fetch_list_page(FakeSession(list_html(href)), "https://www.namhae.go.kr/x.do", {"name": "고시공고"}, 1)

    def test_new_underscore_view_link(self):
        """남해군(2026-10): ?amode=_view 로 바뀐 링크도 읽는다."""
        rows = self.rows("?amode=_view&amp;not_ancmt_mgt_no=37096&amp;pageCd=X&amp;siteGubun=portal")  # 실제 HTML 처럼 &amp; 로 쓴다
        self.assertEqual(len(rows), 1)
        self.assertEqual(str(rows[0]["date"]), "2026-10-23")
        self.assertIn("not_ancmt_mgt_no=37096", rows[0]["detail_url"])

    def test_old_view_link_still_works(self):
        """함안군 등 기존 ?amode=view 링크도 그대로 읽는다."""
        self.assertEqual(len(self.rows("?amode=view&amp;not_ancmt_mgt_no=1")), 1)


if __name__ == "__main__":
    unittest.main()
