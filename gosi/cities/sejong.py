"""
cities/sejong.py — 세종특별자치시 고시공고 게시판 목록.

새 지자체를 추가할 때는 먼저 해당 사이트의 게시판 구조를 직접 탐색해 확인한 뒤
City(...)를 하나 더 추가한다 (임의 추측 금지, law.md 3-2 참고).
"""

from core.board_crawler import City
from core.jose_extractor import Regions

from cities._shared import DEFAULT_BLACKLIST, DEFAULT_KEYWORDS

PROVINCE_NAME = "세종"

# ============================================================ 세종특별자치시청
# publicnotice_prog 어댑터 (사용자 제공 URL, 2026-09-26 실측 확인).
SEJONG_CITY = City(
    province="세종특별자치시",
    city="세종특별자치시청",
    base_url="https://www.sejong.go.kr/prog/publicNotice/kor/sub02_030301/C1_1/list.do",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="세종특별자치시", sigun_name="세종시"),
    adapter="publicnotice_prog",
)

CITIES = [SEJONG_CITY]
