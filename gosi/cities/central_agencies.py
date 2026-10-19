"""
cities/central_agencies.py — 중앙/광역 공공기관 고시공고 게시판 목록.

지방국토관리청·지방항공청·유역환경청·개발공사 등은 특정 시/군에 속하지 않는
중앙·광역 단위 기관이라, 시/도별 cities/*.py 대신 이 파일에 모아 둔다(보상맵
수집소스 카탈로그의 "중앙/관보·공공기관", "지방국토관리청", "개발·도시공사",
"유역환경청" 분류와 같은 결). City.regions는 기관 소재지 기준으로 최소한만
채운다 — 이 기관들의 관할 구역은 시/군 하나가 아니라서 주소 검증 정확도가
낮을 수 있다("살아있는 목록"으로 나중에 보완).

새 기관을 추가할 때는 먼저 해당 사이트의 게시판 구조를 직접 탐색해 확인한 뒤
City(...)를 하나 더 추가한다 (임의 추측 금지, law.md 3-2 참고).
"""

from core.board_crawler import City
from core.jose_extractor import Regions

from cities._shared import DEFAULT_BLACKLIST, DEFAULT_KEYWORDS

PROVINCE_NAME = "중앙기관"

# ============================================================ 국토교통부 산하 — molit_bord0201 어댑터
# cms_adapters/molit_bord0201.py 상단 설명 참고 (2026-09-25 실측 확인).
# City.base_url은 원래 spreadsheet의 BRD.jsp(진입 페이지)가 아니라, 그 안에서 찾은
# 실제 목록 엔드포인트 LST.jsp?id=<게시판id> 이다.
WONJU_ROCM = City(
    province="국토교통부",
    city="원주지방국토관리청",
    base_url="https://www.molit.go.kr/wrocm/USR/BORD0201/m_15959/LST.jsp?id=wcmo0402",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="강원도", sigun_name="원주시"),
    adapter="molit_bord0201",
)

DAEJEON_ROCM = City(
    province="국토교통부",
    city="대전지방국토관리청",
    base_url="https://www.molit.go.kr/drocm/USR/BORD0201/m_16064/LST.jsp?id=dcmo0402",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="대전광역시", sigun_name="대전"),
    adapter="molit_bord0201",
)

IKSAN_ROCM = City(
    province="국토교통부",
    city="익산지방국토관리청",
    base_url="https://www.molit.go.kr/irocm/USR/BORD0201/m_15643/LST.jsp?id=icmo0402",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라북도", sigun_name="익산시"),
    adapter="molit_bord0201",
)

BUSAN_ROCM = City(
    province="국토교통부",
    city="부산지방국토관리청",
    base_url="https://www.molit.go.kr/brocm/USR/BORD0201/m_15087/LST.jsp?id=pcmo0401",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="부산광역시", sigun_name="부산"),
    adapter="molit_bord0201",
)

SEOUL_ROA = City(
    province="국토교통부",
    city="서울지방항공청",
    base_url="https://www.molit.go.kr/sroa/USR/BORD0201/m_35702/LST.jsp?id=sraac_0401",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="서울특별시", sigun_name="서울"),
    adapter="molit_bord0201",
)

BUSAN_ROA = City(
    province="국토교통부",
    city="부산지방항공청",
    base_url="https://www.molit.go.kr/broa/USR/BORD0201/m_11508/LST.jsp?id=phc0401",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="부산광역시", sigun_name="부산"),
    adapter="molit_bord0201",
)

# ============================================================ 환경부 유역환경청 — mcee_board 어댑터
# cms_adapters/mcee_board.py 상단 설명 참고 (2026-09-25 실측 확인).
# www.me.go.kr URL이 mcee.go.kr로 리다이렉트되지만 requests가 자동으로 따라간다.
GEUMGANG_REGION = City(
    province="환경부",
    city="금강유역환경청",
    base_url="https://www.me.go.kr/gg/web/index.do?menuId=2283",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청남도", sigun_name="대전"),
    adapter="mcee_board",
)

HANGANG_REGION = City(
    province="환경부",
    city="한강유역환경청",
    base_url="https://www.me.go.kr/hg/web/index.do?menuId=1255",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="서울"),
    adapter="mcee_board",
)

NAKDONGGANG_REGION = City(
    province="환경부",
    city="낙동강유역환경청",
    base_url="https://www.me.go.kr/ndg/web/index.do?menuId=3284",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상남도", sigun_name="창원"),
    adapter="mcee_board",
)

YEONGSANGANG_REGION = City(
    province="환경부",
    city="영산강유역환경청",
    base_url="https://www.me.go.kr/ysg/web/index.do?menuId=4284",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="광주광역시", sigun_name="광주"),
    adapter="mcee_board",
)

# ============================================================ 한국부동산원 — reb_board 어댑터
# 보상정보 > 보상계획 공고 / 협의 공고 전용 게시판(사용자 제공 URL, 2026-09-28 실측 확인).
# 제목이 사업명뿐이라(예: "솔안천 개선(재해)복구사업") 키워드 필터를 쓰지 않고 전체를 수집한다.
# Regions는 본사(대구 동구) 기준 최소값 — 사업지는 전국이라 소재지가 CHECK로 뜰 수 있다.
KOREA_REB = City(
    province="국토교통부",
    city="한국부동산원",
    base_url="https://www.reb.or.kr/reb/na/ntt/selectNttList.do",
    boards=[
        {"name": "보상계획공고", "mi": 9583, "bbs_id": 1143},
        # 협의 공고 게시판(사용자 지정 URL mi=9584&bbsId=1144, 2026-09-28 실측 확인) — 같은
        # 어댑터/구조.
        {"name": "협의공고", "mi": 9584, "bbs_id": 1144},
    ],
    # 두 게시판(보상정보 > 보상계획 공고 / 협의 공고)의 모든 글이 보상 대상이라는 사용자 확인
    # (2026-09-28)에 따라 키워드 없이 전체 수집한다(match_all). 제목이 사업명뿐이라 키워드로는
    # 누락이 생긴다(기본 키워드는 100건 중 36건만 걸렸다).
    keywords=[],
    match_all=True,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="대구광역시", sigun_name="동구"),
    adapter="reb_board",
)

# ============================================================ LH(한국토지주택공사) 보상정보 — lh_board 어댑터
# 보상정보 게시판 bid=0060 (사용자 제공 URL, 2026-09-28 실측 확인). Regions는 본사(진주시)
# 기준 최소값 — 사업지는 전국이다.
LH_BOSANG = City(
    province="한국토지주택공사",
    city="LH보상정보",
    base_url="https://lh.or.kr/board.es",
    boards=[{"name": "보상정보", "mid": "a10403170500", "bid": "0060"}],
    # 보상정보 게시판의 모든 글(보상계획/보상협의/대토보상/현물보상)이 대상이라는 사용자
    # 확인(2026-09-28)에 따라 키워드 없이 전체 수집한다(match_all). 기본 키워드만으론 30일간
    # 11건 중 4건만 걸렸다(실측).
    keywords=[],
    match_all=True,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상남도", sigun_name="진주시"),
    adapter="lh_board",
)

# ============================================================ 국방시설본부 — mil_bbs_board 어댑터
# 공지사항 게시판(4459)에서 제목 검색어 "매입"으로 거른다(사용자가 알려준 검색어, 2026-09-28
# 실측 확인 — 일반 공지 게시판이라 기본 키워드를 쓰면 무관한 글만 늘어난다).
# 소재지는 서울 용산구(홈페이지 하단 주소로 확인).
DIA_FACILITY = City(
    province="국방부",
    city="국방시설본부",
    base_url="https://www.dia.mil.kr/bbs/dia/72741/artclList.do",
    boards=[{"name": "공지사항"}],
    keywords=["매입"],
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="서울특별시", sigun_name="용산구"),
    adapter="mil_bbs_board",
)

# ============================================================ 국방부 고시공고 — mil_bbs_board 어댑터
# 고시·공고 게시판(157 -> /bbs/mnd/26390, 2026-09-28 실측 확인). 국방시설본부와 같은
# 플랫폼이고, 사용자가 알려준 검색어 "매입"으로 제목을 거른다.
MND_GOSI = City(
    province="국방부",
    city="국방부고시공고",
    base_url="https://www.mnd.go.kr/bbs/mnd/26390/artclList.do",
    boards=[{"name": "고시공고"}],
    keywords=["매입"],
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="서울특별시", sigun_name="용산구"),
    adapter="mil_bbs_board",
)

CITIES = [
    WONJU_ROCM, DAEJEON_ROCM, IKSAN_ROCM, BUSAN_ROCM, SEOUL_ROA, BUSAN_ROA,
    GEUMGANG_REGION, HANGANG_REGION, NAKDONGGANG_REGION, YEONGSANGANG_REGION,
    KOREA_REB, LH_BOSANG, DIA_FACILITY, MND_GOSI,
]
