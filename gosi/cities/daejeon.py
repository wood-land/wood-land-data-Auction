"""
cities/daejeon.py — 대전광역시 자치구 고시공고 게시판 목록.

새 지자체를 추가할 때는 먼저 해당 사이트의 게시판 구조를 직접 탐색해 확인한 뒤
City(...)를 하나 더 추가한다 (임의 추측 금지, law.md 3-2 참고).
"""

from core.board_crawler import City
from core.jose_extractor import Regions

from cities._shared import DEFAULT_BLACKLIST, DEFAULT_KEYWORDS

PROVINCE_NAME = "대전"

# ============================================================ 중구
# prog/saeolGosi 계열 (gosi_prog_skin 어댑터, 2026-09-25 실측 확인).
JUNGGU = City(
    province="대전광역시",
    city="중구",
    base_url="https://www.djjunggu.go.kr/prog/saeolGosi/GOSI/sub03_06/list.do",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="대전광역시", sigun_name="중구"),
    adapter="gosi_prog_skin",
)

# ============================================================ 유성구
# 같은 gosi_prog_skin 어댑터. fn_search_view() + 첨부파일 action이 정적 HTML엔
# 비어 있고 JS가 동적으로 채우는 변형이라 어댑터에 fallback을 추가했다.
YUSEONG = City(
    province="대전광역시",
    city="유성구",
    base_url="https://www.yuseong.go.kr/prog/saeolGosi/GOSI/kor/sub04_02_01/list.do",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="대전광역시", sigun_name="유성구"),
    adapter="gosi_prog_skin",
)

# ============================================================ 서구
# 같은 gosi_prog_skin 어댑터. 제목 칸이 <a onclick=...>가 아니라
# <td data-key-no="<id>"><button class="button_view"> 형태라 어댑터에 이 패턴도 추가했다.
SEOGU = City(
    province="대전광역시",
    city="서구",
    base_url="https://www.seogu.go.kr/prog/saeolGosi/GOSI/kor/sub04_02_01/list.do",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="대전광역시", sigun_name="서구"),
    adapter="gosi_prog_skin",
)

# ============================================================ 대전광역시청 — daejeon_gosi 어댑터
# drh/drhGosiList.do (사용자 제공 URL, 2026-09-28 실측 확인). 상세 페이지는 gosigbn(공고=A,
# 고시=N)이 있어야 열리고, 첨부 다운로드는 POST라서 어댑터가 별도로 처리한다.
DAEJEON_CITY = City(
    province="대전광역시",
    city="대전광역시청",
    base_url="https://www.daejeon.go.kr/drh/drhGosiList.do",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="대전광역시", sigun_name="서구"),
    adapter="daejeon_gosi",
)

CITIES = [JUNGGU, YUSEONG, SEOGU, DAEJEON_CITY]
