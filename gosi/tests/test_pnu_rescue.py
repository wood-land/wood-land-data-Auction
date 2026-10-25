"""PNU 변환 보완(2026-10-26) 테스트: 과거 PNU 실패 사례에서 찾은 4가지 유형을 카카오 대역으로 확인한다. 네트워크 없이 돈다.
  - 면이 빠진 리 이름('충청북도 단양군 당동' = 대강면 당동리)
  - 읍·면이 틀리게 적힌 경우('안성시 공도읍 개정리' = 미양면 개정리)
  - 시군 첫 글자가 빠져 읍에 붙은 경우('택시안중읍' = 평택시 안중읍, 제목에 '평택')
  - 행정동 번호('남산3동')
실행: gosi 폴더에서 `python -m unittest discover -s tests -v`"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from core import pnu as P  # noqa: E402
from core import sqlite_store as S  # noqa: E402


def doc(sido, sigun, dong, code, main, sub=0, mountain="N", ri_level=False):
    return {"address": {"address_name": f"{sido} {sigun} {dong}", "b_code": code, "region_1depth_name": sido,
                        "region_2depth_name": sigun, "region_3depth_name": dong,
                        "main_address_no": "" if ri_level else str(main), "sub_address_no": "" if ri_level else str(sub),
                        "mountain_yn": mountain}}


class FakeKakao:
    """질의 문자열 -> 문서 목록. 모르는 질의는 결과 없음."""

    def __init__(self, table):
        self.table = table
        self.queries = []

    def __call__(self, query):
        self.queries.append(query)
        return {"documents": self.table.get(query, [])}, "ok"


class PnuRescue(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = S.connect(os.path.join(self.tmp.name, "t.sqlite"))
        self.r = P.PnuResolver(self.con)
        self.r.key = "k"
        self.r.ai.enabled = False

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def use(self, table):
        self.r._call = FakeKakao(table)
        return self.r._call

    def test_bare_ri_after_sido_sigun(self):
        self.use({"단양군 당동리 171": [doc("충북", "단양군", "대강면 당동리", "4380031023", 171)]})
        pnu, why = self.r.resolve_full("충청북도 단양군 당동", "171-0", "", "단양군", "", "", "")
        self.assertEqual((pnu, why), ("4380031023101710000", "ok"))
        self.assertIn("대강면 당동리", self.r.last_full)

    def test_bare_ri_missing_parcel_falls_back_to_ri_code(self):
        """리는 있는데 그 지번이 지도에 없으면(분할·폐지) 리 코드로 조립한다(verified=0 로 저장되는 ok_ri)."""
        self.use({"단양군 당동리": [doc("충북", "단양군", "대강면 당동리", "4380031023", 0, ri_level=True)]})
        pnu, why = self.r.resolve_full("충청북도 단양군 당동", "48-7", "", "단양군", "", "", "")
        self.assertEqual((pnu, why), ("4380031023100480007", "ok_ri"))

    def test_wrong_eup_found_by_ri_only(self):
        self.use({"안성시 개정리 350-14": [doc("경기", "안성시", "미양면 개정리", "4155034023", 350, 14)]})
        pnu, why = self.r.resolve_full("경기도 안성시 공도읍 개정리", "350-14", "", "경기도청", "", "", "")
        self.assertEqual((pnu, why), ("4155034023103500014", "ok"))

    def test_ri_only_gives_up_when_ambiguous(self):
        self.use({"안성시 개정리 5": [doc("경기", "안성시", "미양면 개정리", "4155034023", 5),
                                       doc("경기", "안성시", "공도읍 개정리", "4155025021", 5)]})
        self.assertIsNone(self.r._ri_only_lookup("경기도 안성시 공도읍 개정리", "5", "경기도청", (False, 5, 0)))

    def test_concatenated_sigun_repaired_from_title(self):
        self.assertEqual(P.repair_concat_sigun("경상북도 안동시 택시안중읍 학현리", "「평택 도시계획시설 1호 근린공원」 조성사업"),
                         "평택시 안중읍 학현리")
        self.assertEqual(P.repair_concat_sigun("경상북도 안동시 택시안중읍 학현리", "제목에 지역 없음"), "경상북도 안동시 택시안중읍 학현리")
        self.use({"평택시 안중읍 학현리 465-8": [doc("경기", "평택시", "안중읍 학현리", "4122025322", 465, 8)]})
        pnu, why = self.r.resolve_full("경상북도 안동시 택시안중읍 학현리", "465-8", "「평택 도시계획시설 근린공원」", "경상북도청",
                                       "「평택 도시계획시설 근린공원」", "", "")
        self.assertEqual((pnu, why), ("4122025322104650008", "ok"))

    def test_admin_dong_number_removed(self):
        k = self.use({"대구광역시 중구 남산동 2210": [doc("대구", "중구", "남산동", "2711010100", 2210)]})
        pnu, why = self.r.resolve_full("대구광역시 중구 남산3동", "2210", "", "대구광역시청", "", "", "")
        self.assertEqual(why, "ok")
        self.assertEqual(k.queries[0], "대구광역시 중구 남산동 2210")

    def test_garbage_rows_are_not_parcels(self):
        for soj in ("사 용 기 간 사용승인 허가일 ~ 2035", "사. 입찰가격 평점산식의 A값: 금 1"):
            self.assertEqual(self.r.resolve_full(soj, "1", "", "진천군", "", "", "")[1], "not_parcel")


if __name__ == "__main__":
    unittest.main()
