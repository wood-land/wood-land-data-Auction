"""
cities/gwangju.py — 광주 지자체 고시공고 게시판 목록.

새 지자체를 추가할 때는 먼저 해당 사이트의 게시판 구조를 직접 탐색해 확인한 뒤
City(...)를 하나 더 추가한다 (임의 추측 금지, law.md 3-2 참고).
"""

from core.board_crawler import City
from core.jose_extractor import Regions

from cities._shared import DEFAULT_BLACKLIST, DEFAULT_KEYWORDS

PROVINCE_NAME = "광주"

# ============================================================ 남구
# 보상맵 시트의 URL(api/eminwon/gosiList.es)은 깨져 있었으나, 사용자가 실제 게시판
# URL(menu.es?mid=a10604020100)을 알려줘서 확인 — 그 페이지는 iframe으로 정읍시·
# 익산시와 같은 NTIS eMinwon 백엔드를 불러온다(ntis_ofr 어댑터, 2026-09-25 실측).
# 목록 마크업이 <div>/<ul>/<li> 레이아웃이라 ntis_ofr.py에 그 경로를 추가했다.
# 응답이 느린 사이트라(실측 중 수십 초씩 걸림) 재시도가 자주 걸릴 수 있다.
NAMGU = City(
    province="광주광역시",
    city="남구",
    base_url=(
        "https://eminwon.namgu.gwangju.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp"
        "?not_ancmt_se_code=01,04&jndinm=OfrNotAncmtEJB&context=NTIS"
        "&method=selectListOfrNotAncmt&methodnm=selectListOfrNotAncmtHomepage"
        "&ofr_pageSize=10&homepage_pbs_yn=Y&subCheck=Y"
    ),
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="광주광역시", sigun_name="남구"),
    adapter="ntis_ofr",
)

# ============================================================ 북구 — NTIS eMinwon 계열 (ntis_ofr 어댑터)
# LSub.jsp 변형(L.jsp는 400 에러) — 사용자 제공 URL, 2026-09-26 실측 확인.
GWANGJU_BUKGU = City(
    province="광주광역시",
    city="북구",
    base_url="https://eminwon.bukgu.gwangju.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="광주광역시", sigun_name="북구"),
    adapter="ntis_ofr",
)

CITIES = [NAMGU, GWANGJU_BUKGU]
