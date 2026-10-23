"""
tests/test_preflight.py - 러너 IP 차단 사전 점검(core/preflight.py) 판정이 맞는지 확인한다(네트워크 불필요).

실행: python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from core import preflight as PF  # noqa: E402


class PreflightTest(unittest.TestCase):
    def test_host_port(self):
        self.assertEqual(PF.host_port("https://a.go.kr/x?y=1"), ("a.go.kr", 443))
        self.assertEqual(PF.host_port("http://a.go.kr:8080/"), ("a.go.kr", 8080))
        self.assertIsNone(PF.host_port(""))
        self.assertIsNone(PF.host_port("http://www.facebook.com/sharer.php?u=x"))   # 잘못 잡힌 공유 링크는 점검하지 않는다

    def test_probe_dedups_hosts(self):
        urls = ["https://a.go.kr/1", "https://a.go.kr/2", "http://b.go.kr/"]
        ok, total, bad = PF.probe(urls, check=lambda hp: hp[0] == "a.go.kr")
        self.assertEqual((ok, total, bad), (1, 2, ["b.go.kr:80"]))

    def test_looks_blocked(self):
        self.assertTrue(PF.looks_blocked(0, 25))      # 2026-10-23 막힌 러너: 전남 0/25
        self.assertFalse(PF.looks_blocked(22, 25))    # 정상 러너: 22/25
        self.assertFalse(PF.looks_blocked(6, 8))      # 대구 최악 사례 6/8
        self.assertFalse(PF.looks_blocked(0, 3))      # 표본이 작으면 판정하지 않음

    def test_reachable_retries_once(self):
        calls = []

        class Sock:
            def close(self):
                pass

        def flaky(hp, timeout):
            calls.append(hp)
            if len(calls) == 1:
                raise OSError("timeout")
            return Sock()

        self.assertTrue(PF.reachable(("a", 443), connect=flaky))
        self.assertEqual(len(calls), 2)

    def test_blocked_list_keeps_only_confirmed_sites(self):
        from core import blocked_sites as B
        self.assertEqual(set(B.BLOCKED_ON_HOSTED["전남"]), {"순천시", "강진군", "구례군"})
        self.assertNotIn("대구", B.BLOCKED_ON_HOSTED)


class NetworkDiagTest(unittest.TestCase):
    """수집 로그에 접속 실패 원인(단계)이 남고, 지역 단위로 '러너 IP 차단 / 사이트 문제'가 판정되는지 확인한다."""

    def setUp(self):
        from core.run_log import RunLog
        self.log = RunLog()
        self.log.region = "시험"
        self._orig = PF.diagnose_host
        self.codes = {}
        PF.diagnose_host = lambda host, port=443, timeout=6: (self.codes.get(host, "TCP_TIMEOUT"), "시험")

    def tearDown(self):
        PF.diagnose_host = self._orig

    def board(self, city, host, status="오류(목록)"):
        err = f"ConnectTimeout: HTTPSConnectionPool(host='{host}', port=443): Max retries exceeded"
        self.log.board({"city": city, "kind": "공보", "status": status, "detail": err, "url": f"https://{host}/x"})

    def test_hint_gets_stage_and_is_added_once(self):
        self.board("A", "a.go.kr")
        self.log.enrich_network()
        self.log.enrich_network()
        hint = self.log._rows["게시판상태"][0][12]
        self.assertEqual(hint.count("진단["), 1)
        self.assertIn("진단[TCP_TIMEOUT] a.go.kr", hint)

    def test_whole_region_unreachable_is_runner_block(self):
        for i in range(6):
            self.board(f"c{i}", f"h{i}.go.kr")
        self.assertIn("러너 IP 차단 의심", self.log.network_summary())

    def test_reachable_now_means_rate_limit(self):
        for i in range(6):
            self.codes[f"h{i}.go.kr"] = "OK"
            self.board(f"c{i}", f"h{i}.go.kr")
        self.assertIn("요청 빈도 제한", self.log.network_summary())

    def test_few_failures_are_site_specific(self):
        self.board("ok1", "x.go.kr", status="정상")
        for i in range(8):
            self.board(f"ok{i + 2}", f"y{i}.go.kr", status="정상")
        self.board("bad", "z.go.kr")
        s = self.log.network_summary()
        self.assertIn("일부 사이트만", s)
        self.assertIn("1/10곳", s)

    def test_no_errors_no_summary(self):
        self.board("ok", "x.go.kr", status="정상")
        self.assertEqual(self.log.network_summary(), "")

    def test_stage_counts(self):
        self.codes = {"a.go.kr": "DNS"}
        self.assertEqual(PF.stage_counts(["a.go.kr:443", "b.go.kr:443", "c.go.kr:443"]), {"TCP_TIMEOUT": 2, "DNS": 1})


if __name__ == "__main__":
    unittest.main()
