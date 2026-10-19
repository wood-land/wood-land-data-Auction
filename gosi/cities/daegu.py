"""
cities/daegu.py — 대구광역시 및 자치구 고시공고 게시판 목록.

새 지자체를 추가할 때는 먼저 해당 사이트의 게시판 구조를 직접 탐색해 확인한 뒤
City(...)를 하나 더 추가한다 (임의 추측 금지, law.md 3-2 참고).
"""

from core.board_crawler import City
from core.jose_extractor import Regions

from cities._shared import DEFAULT_BLACKLIST, DEFAULT_KEYWORDS

PROVINCE_NAME = "대구"

# ============================================================ 북구 — NTIS eMinwon 계열 (ntis_ofr 어댑터)
# 사용자 제공 URL, 2026-09-26 실측 확인.
BUKGU = City(
    province="대구광역시",
    city="북구",
    base_url="https://eminwon.buk.daegu.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp?not_ancmt_se_code=01,04",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="대구광역시", sigun_name="북구"),
    adapter="ntis_ofr",
)

# ============================================================ 수성구 — NTIS eMinwon 계열 (ntis_ofr 어댑터)
SUSEONG = City(
    province="대구광역시",
    city="수성구",
    base_url="https://eminwon.suseong.kr/emwp/jsp/ofr/OfrNotAncmtL.jsp",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="대구광역시", sigun_name="수성구"),
    adapter="ntis_ofr",
)

# ============================================================ 대구광역시청 — daegu_sido_gosi 어댑터
# 화면은 <form id="sidoGosiAPIVO"> JS 제출이지만 실제 엔드포인트(daeguSidoGosiList.do/
# View.do)에 POST하면 래핑 페이지 없이 바로 재현된다(2026-09-26 실측 확인).
DAEGU_CITY = City(
    province="대구광역시",
    city="대구광역시청",
    base_url="https://www.daegu.go.kr/index.do",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="대구광역시", sigun_name="중구"),
    adapter="daegu_sido_gosi",
)

# ============================================================ 달성군
# 같은 NTIS eMinwon 계열(ntis_ofr 어댑터). iframe 트릭(브라우저 개발자도구로 확인, 2026-09-26).
DALSEONG = City(
    province="대구광역시",
    city="달성군",
    base_url="https://eminwon.dalseong.daegu.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp?not_ancmt_se_code=01,04",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="대구광역시", sigun_name="달성군"),
    adapter="ntis_ofr",
)

CITIES = [BUKGU, SUSEONG, DAEGU_CITY, DALSEONG]
