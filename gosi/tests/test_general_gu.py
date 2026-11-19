"""일반구가 있는 시(안산 상록구·수원 영통구·천안 서북구 등)의 '구' 가 동 이름에 붙던 오류(2026-11-19).
공백을 지운 소재지에 동 정규식이 5글자까지 가져가 '상록구 팔곡일동' 이 '록구팔곡일동' 이 됐다(안산 296행, 수원·성남·천안·창원 등 같은 구조)."""
import importlib
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))


def _regions(mod, city):
    return [c for c in importlib.import_module("cities." + mod).CITIES if c.city == city][0].regions


class GeneralGuTest(unittest.TestCase):
    def test_gu_stays_a_separate_word(self):
        cases = [("gyeonggi", "안산시", "안산시 상록구 팔곡일동", "경기도 안산시 상록구 팔곡일동"),
                 ("gyeonggi", "수원시", "수원시 영통구 매탄동", "경기도 수원시 영통구 매탄동"),
                 ("gyeonggi", "수원시", "영통구 매탄동", "경기도 수원시 영통구 매탄동"),
                 ("gyeonggi", "성남시", "성남시 분당구 정자동", "경기도 성남시 분당구 정자동"),
                 ("chungnam", "천안시", "천안시 서북구 성환읍 매주리", "충청남도 천안시 서북구 성환읍 매주리"),
                 ("gyeongnam", "창원시", "창원시 의창구 팔용동", "경상남도 창원시 의창구 팔용동")]
        for mod, city, raw, want in cases:
            r = _regions(mod, city).resolve(raw)
            self.assertEqual(r["region"], want, raw)

    def test_city_without_gu_is_unchanged(self):
        r = _regions("gyeonggi", "안산시").resolve("안산시 선감동")
        self.assertEqual(r["region"], "경기도 안산시 선감동")


if __name__ == "__main__":
    unittest.main()
