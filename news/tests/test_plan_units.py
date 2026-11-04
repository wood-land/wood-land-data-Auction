import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import plan_units as pu
from plan_units import UNITS, next_unit, pick


class NextUnitTest(unittest.TestCase):
    def test_success_moves_to_next_and_wraps_around(self):
        self.assertEqual(next_unit([("강원", "success")]), "충청:충남")
        self.assertEqual(next_unit([(UNITS[-1], "success")]), UNITS[0])
        self.assertEqual(next_unit([("경북:2/2", "success")]), "경기:선정")

    def test_skipped_day_does_not_skip_a_unit(self):
        # 2026-11-01 사고: 날짜 방식은 강원을 건너뛰었다. 기록 기준이면 경북 뒤에 바로 강원이 아니라 '지난번 다음'이다.
        hist = [("경기:선정", "success")]
        self.assertEqual(next_unit(hist), "강원")

    def test_failure_retries_same_unit_once_then_moves_on(self):
        self.assertEqual(next_unit([("경남:1/2", "failure")]), "경남:1/2")
        self.assertEqual(next_unit([("경남:1/2", "cancelled")]), "경남:1/2")
        self.assertEqual(next_unit([("경남:1/2", "failure"), ("경남:1/2", "failure")]), "경남:2/2")

    def test_earlier_failure_followed_by_success_does_not_count(self):
        self.assertEqual(next_unit([("강원", "failure"), ("강원", "success")]), "충청:충남")

    def test_only_trailing_failures_of_same_unit_count(self):
        hist = [("강원", "failure"), ("충청:충남", "failure")]
        self.assertEqual(next_unit(hist), "충청:충남")

    def test_unknown_or_empty_history_gives_none(self):
        self.assertIsNone(next_unit([]))
        self.assertIsNone(next_unit([("없는단위", "success")]))
        self.assertIsNone(next_unit([("강원", "skipped")]))


class PickTest(unittest.TestCase):
    D = datetime.date(2026, 11, 4)

    def test_schedule_uses_history_and_falls_back_to_date(self):
        self.assertEqual(pick("schedule", "", [("전라:전북", "success")], self.D), ["전라:광주전남"])
        self.assertEqual(pick("schedule", "", None, self.D), [UNITS[self.D.toordinal() % len(UNITS)]])
        self.assertEqual(pick("schedule", "", [], self.D), [UNITS[self.D.toordinal() % len(UNITS)]])

    def test_manual_runs(self):
        self.assertEqual(pick("workflow_dispatch", "충청:충남, 강원", None, self.D), ["충청:충남", "강원"])
        self.assertEqual(pick("workflow_dispatch", "", None, self.D), UNITS)


class UnitsMatchCrawlerTest(unittest.TestCase):
    def test_every_unit_resolves_and_covers_each_scheduled_paper_once(self):
        import run_crawl as rc
        regions = rc.discover_regions()
        seen = {}
        for u in UNITS:
            name, _, part = u.partition(":")
            full = next(r for r in regions if r.startswith(name))
            active = [s.name for s in regions[full].SITES if s.enabled]
            if part and "/" in part:
                n, m = (int(x) for x in part.split("/"))
                names = active[n - 1::m]
            elif part:
                names = [x for x in rc.PART_GROUPS[full][part] if x in active]
            else:
                names = active
            self.assertTrue(names, u)
            for x in names:
                self.assertNotIn(x, seen, f"{x} 가 {seen.get(x)} 와 {u} 에 중복")
                seen[x] = u
        self.assertEqual(len(seen), 107)            # 99곳 + 경기 8곳
        self.assertEqual({k for k, v in seen.items() if v == "경기:선정"},
                         {"경기신문", "용인시민신문", "평택시민신문", "이천설봉신문", "구리남양주뉴스", "여주신문", "양평시민의소리", "가평타임즈"})
        self.assertNotIn("기호일보", seen)            # 경기·인천의 나머지 17곳은 정기 수집에 없다


if __name__ == "__main__":
    unittest.main()
