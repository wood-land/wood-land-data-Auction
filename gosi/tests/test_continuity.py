"""한 고시문 안의 엉뚱한 지역 필지 거르기(2026-11-17, 사용자 지시: 한국부동산원 같은 전국 출처도 지번은 인근 필지로 이어서 적는다).
 - core.continuity.region_outliers: 문서 순서 PNU 에서 앞뒤 이웃과 동떨어진 시군구, 합쳐서 소수인 다른 시도를 외딴 필지로 본다.
 - 진짜로 두 시군·두 시도에 걸친 사업(걸친 쪽이 한 덩어리)은 걸리지 않는다.
 - save_parcels 가 외딴 필지를 parcels 에 넣지 않고 parcels_unresolved(outlier_region)에 남기며, 재시도가 되살리지 않는다.
실행: gosi 폴더에서 `python -m unittest discover -s tests -v`"""
import os
import sqlite3
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from core.continuity import region_outliers  # noqa: E402


def pnu(code5, n):
    return f"{code5}10800{1:1d}{n:04d}0000"[:19]


class RegionOutliersTest(unittest.TestCase):
    def test_single_stray_parcel_in_the_middle(self):
        seq = [pnu("26290", i) for i in range(1, 8)]
        seq[3] = pnu("48330", 540)  # 부산 남구 한가운데 끼어든 경남 양산시 용당동 540
        self.assertEqual(region_outliers(seq), {3})

    def test_minor_other_sido_cluster_is_outlier(self):
        seq = [pnu("26290", i) for i in range(1, 15)] + [pnu("30170", 394), pnu("30170", 408)]  # 부산 14 + 대전 2
        self.assertEqual(region_outliers(seq), {14, 15})

    def test_real_two_region_project_is_kept(self):
        # 서울 성동구 → 경기 하남시로 이어지는 사업: 한쪽 덩어리가 앞, 다른 쪽이 뒤
        seq = [pnu("11200", i) for i in range(1, 9)] + [pnu("41450", i) for i in range(1, 7)]
        self.assertEqual(region_outliers(seq), set())

    def test_scattered_list_of_different_regions_is_kept(self):
        # 각기 다른 시군 필지를 하나씩 나열한 공고는 외딴 필지로 보지 않는다
        seq = [pnu(c, 1) for c in ("11200", "26290", "30170", "41450", "48330", "27140", "28110")]
        self.assertEqual(region_outliers(seq), set())

    def test_small_notice_is_not_judged(self):
        self.assertEqual(region_outliers([pnu("26290", 1), pnu("48330", 2), pnu("26290", 3)]), set())

    def test_unresolved_entries_are_skipped_in_order(self):
        seq = [pnu("26290", 1), None, pnu("26290", 2), pnu("48330", 9), pnu("26290", 3), None, pnu("26290", 4), pnu("26290", 5)]
        self.assertEqual(region_outliers(seq), {3})


class SaveParcelsTest(unittest.TestCase):
    class FakeResolver:
        class ai:  # noqa: N801
            enabled = False
        last_full = ""

        def __init__(self, table):
            self.table = table

        def resolve_full(self, sojaeji, jibun, context="", city="", title="", project="", jimok=""):
            self.last_full = ""
            p = self.table.get((sojaeji, jibun))
            return (p, "ok") if p else (None, "no_match")

    def test_outlier_goes_to_unresolved_and_is_not_retried(self):
        import tempfile
        from core import sqlite_store as S
        old_cache = os.environ.get("GOSI_CACHE_DIR")
        self.addCleanup(lambda: os.environ.__setitem__("GOSI_CACHE_DIR", old_cache) if old_cache is not None else os.environ.pop("GOSI_CACHE_DIR", None))
        with tempfile.TemporaryDirectory() as d:
            os.environ["GOSI_CACHE_DIR"] = os.path.join(d, "cache")
            con = S.connect(os.path.join(d, "t.sqlite"))
            table, rows = {}, []
            for i in range(1, 8):
                table[("부산광역시 남구 용당동", str(i))] = pnu("26290", i)
                rows.append({"sojaeji": "부산광역시 남구 용당동", "jibun": str(i), "post_url": "http://x/1", "post_title": "t", "post_date": "2026-11-17"})
            table[("부산광역시 남구 용당동", "540")] = pnu("48330", 540)  # 같은 글 한가운데 경남 양산시로 변환된 행
            rows.insert(3, {"sojaeji": "부산광역시 남구 용당동", "jibun": "540", "post_url": "http://x/1", "post_title": "t", "post_date": "2026-11-17"})
            res = self.FakeResolver(table)
            new, failed = S.save_parcels(con, res, "부산광역시청", "고시공고", rows)
            self.assertEqual((new, failed), (7, 1))
            self.assertEqual(con.execute("SELECT COUNT(*) FROM parcels WHERE pnu LIKE '48330%'").fetchone()[0], 0)
            self.assertEqual(con.execute("SELECT reason FROM parcels_unresolved").fetchall(), [("outlier_region",)])
            # 재시도가 이 행을 되살리지 않는다(마지막 시도가 아주 오래돼도)
            con.execute("UPDATE parcels_unresolved SET last_tried_at='2000-01-01', resolver_version=0")
            S.retry_unresolved(con, res)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM parcels WHERE pnu LIKE '48330%'").fetchone()[0], 0)
            con.close()


if __name__ == "__main__":
    unittest.main()
