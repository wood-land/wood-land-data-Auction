"""
cities/ulsan.py — 울산광역시 지자체 고시공고 게시판 목록.

새 지자체를 추가할 때는 먼저 해당 사이트의 게시판 구조를 직접 탐색해 확인한 뒤
City(...)를 하나 더 추가한다 (임의 추측 금지, law.md 3-2 참고).
"""

from core.board_crawler import City
from core.jose_extractor import Regions

from cities._shared import DEFAULT_BLACKLIST, DEFAULT_KEYWORDS

PROVINCE_NAME = "울산"

# ============================================================ 울주군
# 새올 계열 (saeol_gosi 어댑터) — cms_adapters/saeol_gosi.py 상단 설명 참고
ULJU = City(
    province="울산광역시",
    city="울주군",
    base_url="https://www.ulju.ulsan.kr/ulju/saeol/gosi/list.do?seCode=01&mId=0403010000&token=1708183796471",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="울산광역시", sigun_name="울주군"),
    adapter="saeol_gosi",
)

# ============================================================ 울산광역시청
# u/rep/transfer/notice 게시판 (ulsan_city_gosi 어댑터, 2026-09-26 실측 확인).
# JS 없이 평범한 GET. 첨부 다운로드가 인천광역시청·충청남도청과 같은 SAP 계열
# minwon.ulsan.go.kr/.../attach/download.jsp 라 그 파싱 로직만 재사용했다.
ULSAN_CITY = City(
    province="울산광역시",
    city="울산광역시청",
    base_url="https://www.ulsan.go.kr/u/rep/transfer/notice/list.ulsan",
    boards=[{"name": "고시공고", "m_id": "001004002000000000"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="울산광역시", sigun_name="남구"),
    adapter="ulsan_city_gosi",
)

CITIES = [ULJU, ULSAN_CITY]
