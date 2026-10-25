"""고시공고 제목 제외 목록(DEFAULT_BLACKLIST) 테스트. 네트워크 없이 돈다.
실행: gosi 폴더에서 `python -m unittest discover -s tests -v`"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import run_gosigongo as R  # noqa: E402
from cities._shared import DEFAULT_BLACKLIST  # noqa: E402
from core.board_crawler import matches_blacklist  # noqa: E402


class Blacklist(unittest.TestCase):
    EXCLUDED = [
        "「문막처리구역 하수관로 정비사업」신기술·특허공법 선정을 위한 기술제안서 공고(지향성압입공법)",
        "영월군 고시 제2026-191호 보전산지 지정해제 고시",
        "급경사지 붕괴위험지역 지정 해제 고시",  # 띄어쓰기가 달라도 걸린다
        "산지전용협의 기간만료지 복구명령 공시송달 공고",
        "영월 군관리계획 결정(경미한 변경) 및 지형도면 승인",
        "농업생산기반시설 사용허가(변경) 관련 의견 청취 공고",
        "개발행위허가 제한기간 연장 및 지형도면 고시",
    ]
    KEPT = [
        "도시계획시설(도로)사업 실시계획인가 고시",
        "공익사업 토지보상계획 열람 공고",
    ]

    def test_excluded_titles(self):
        for t in self.EXCLUDED:
            self.assertTrue(matches_blacklist(t, DEFAULT_BLACKLIST), t)

    def test_other_titles_kept(self):
        for t in self.KEPT:
            self.assertFalse(matches_blacklist(t, DEFAULT_BLACKLIST), t)

    def test_every_city_uses_the_default_list(self):
        """원주시만 2개짜리 자체 목록을 써서 기본 목록이 적용되지 않던 일이 다시 없도록: 다른 목록을 쓰는 지자체가 없어야 한다(있으면 이유를 적고 여기서 허용)."""
        different = [(name, c.city) for name, mod in R.discover_provinces().items() for c in mod.CITIES
                     if list(c.blacklist) != list(DEFAULT_BLACKLIST)]
        self.assertEqual(different, [])


if __name__ == "__main__":
    unittest.main()
