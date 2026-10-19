"""
cities/jeju.py — 제주특별자치도 고시공고 게시판 목록.

새 지자체를 추가할 때는 먼저 해당 사이트의 게시판 구조를 직접 탐색해 확인한 뒤
City(...)를 하나 더 추가한다 (임의 추측 금지, law.md 3-2 참고).
"""

from core.board_crawler import City
from core.jose_extractor import Regions

from cities._shared import DEFAULT_BLACKLIST, DEFAULT_KEYWORDS

PROVINCE_NAME = "제주"

# ============================================================ 제주도청
# tool/sido/api.jsp JSON API (jeju_sido_api 어댑터, 2026-09-26 실측 확인). 화면
# (jeju2.htm)은 Vue SPA라 서버 HTML에 목록이 없어 브라우저 네트워크 탭으로 실제
# API를 찾았다. 첨부 다운로드는 인천광역시청 등과 같은 SAP 계열
# citynet/jsp/cmm/attach/download.jsp.
JEJU_DO = City(
    province="제주특별자치도",
    city="제주도청",
    base_url="https://www.jeju.go.kr/tool/sido/api.jsp",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="제주특별자치도", sigun_name="제주시"),
    adapter="jeju_sido_api",
)

# ============================================================ 제주시 — jejusi_board 어댑터
# jejusi_board.py 상단 설명 참고 — 사용자 제공 URL, 2026-09-26 실측 확인.
JEJUSI = City(
    province="제주특별자치도",
    city="제주시",
    base_url="https://www.jejusi.go.kr/information/intro/notice.do",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="제주특별자치도", sigun_name="제주시"),
    adapter="jejusi_board",
)

# ============================================================ 서귀포시 — NTIS eMinwon 계열 (ntis_ofr 어댑터)
# info/news/law/law.htm은 안내 페이지고, 그 안의
# <iframe src="https://eminwon.seogwipo.go.kr/emwp/jsp/ofr/OfrNotAncmtL.jsp?...">가
# 실제 목록이다(다른 iframe 트릭 지자체와 동일한 패턴). 실측 확인, 2026-09-27.
SEOGWIPO = City(
    province="제주특별자치도",
    city="서귀포시",
    base_url="https://eminwon.seogwipo.go.kr/emwp/jsp/ofr/OfrNotAncmtL.jsp?not_ancmt_se_code=01,04,07",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="제주특별자치도", sigun_name="서귀포시"),
    adapter="ntis_ofr",
)

CITIES = [JEJU_DO, JEJUSI, SEOGWIPO]
