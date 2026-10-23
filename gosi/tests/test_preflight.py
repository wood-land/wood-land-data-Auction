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


if __name__ == "__main__":
    unittest.main()
