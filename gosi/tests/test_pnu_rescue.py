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
        self.assertIn("대구광역시 중구 남산동 2210", k.queries)  # 원래 질의가 실패한 뒤 번호를 지워 다시 묻는다

    def test_numbered_legal_dong_is_kept(self):
        """'대저2동' 은 행정동이 아니라 법정동 이름이다 - 번호를 지우면 대저1동 으로 가 버린다."""
        self.use({"부산광역시 강서구 대저2동 464-1": [doc("부산", "강서구", "대저2동", "2644010200", 464, 1)],
                  "부산광역시 강서구 대저동 464-1": [doc("부산", "강서구", "대저1동", "2644010100", 464, 1)]})
        pnu, why = self.r.resolve_full("부산광역시 강서구 대저2동", "464-1", "", "낙동강유역환경청", "", "", "")
        self.assertEqual(pnu, "2644010200104640001")

    def test_region_agreement(self):
        self.assertTrue(P.region_agrees("경기도 광주시 송정동", "광주시"))
        self.assertFalse(P.region_agrees("경기도 광주시 송정동", "이천시"))  # 같은 이름의 동이 다른 시에 있어도 받지 않는다
        self.assertTrue(P.region_agrees("경기도 용인특례시 인구이동읍", "용인시 처인구"))
        self.assertTrue(P.region_agrees("대구광역시 중구 남산동", "중구"))
        self.assertTrue(P.region_agrees("충청북도 단양군 당동", ""))
        self.assertTrue(P.region_agrees("강원도 당동", "단양군"))  # 시군구 이름이 없으면 확인할 게 없다

    def test_wrong_city_lookalike_is_not_accepted(self):
        """경기도 광주시 송정동 187 이 광주시에 없을 때 카카오가 돌려주는 이천시 송정동 187 을 받으면 엉뚱한 PNU 가 된다."""
        self.use({"경기도 광주시 송정동 187": [doc("경기", "이천시", "송정동", "4150011000", 187)],
                  "경기도 송정동 187": [doc("경기", "이천시", "송정동", "4150011000", 187)]})
        pnu, why = self.r.resolve_full("경기도 광주시 송정동", "187", "", "광주시", "", "", "")
        self.assertNotEqual(pnu, "4150011000101870000")

    def test_garbage_rows_are_not_parcels(self):
        for soj in ("사 용 기 간 사용승인 허가일 ~ 2035", "사. 입찰가격 평점산식의 A값: 금 1",
                    "면 적 249", "토지등소유자 수 537", "○ 대지면적 : 6"):
            self.assertEqual(self.r.resolve_full(soj, "1", "", "진천군", "", "", "")[1], "not_parcel")

    def test_real_addresses_are_not_mistaken_for_garbage(self):
        for soj in ("충청북도 단양군 대강면 당동리", "경기도 안성시 공도읍 개정리", "충청남도 홍성군 서부면 면적리"):
            self.assertFalse(P.looks_like_non_parcel(soj), soj)


if __name__ == "__main__":
    unittest.main()
