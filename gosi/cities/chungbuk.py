"""
cities/chungbuk.py — 충청북도 지자체 고시공고 게시판 목록.

새 지자체를 추가할 때는 먼저 해당 사이트의 게시판 구조를 직접 탐색해 확인한 뒤
City(...)를 하나 더 추가한다 (임의 추측 금지, law.md 3-2 참고).
"""

from core.board_crawler import City
from core.jose_extractor import Regions

from cities._shared import DEFAULT_BLACKLIST, DEFAULT_KEYWORDS

PROVINCE_NAME = "충북"

# ============================================================ 보은군
# 대상 게시판: bbsNo=66,key=194 (보상맵 수집소스 시트, 2026-09-25 실측 확인 — p-table 스킨)
BOEUN = City(
    province="충청북도",
    city="보은군",
    base_url="https://www.boeun.go.kr/www/",
    boards=[{"name": "고시공고", "bbsNo": 66, "key": 194}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청북도", sigun_name="보은군"),
)

# ============================================================ 제천시
# 대상 게시판: bbsNo=18,key=5233 (보상맵 수집소스 시트, 2026-09-25 실측 확인 — p-table 스킨)
JECHEON = City(
    province="충청북도",
    city="제천시",
    base_url="https://www.jecheon.go.kr/www/",
    boards=[{"name": "고시공고", "bbsNo": 18, "key": 5233}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청북도", sigun_name="제천시"),
)

# ============================================================ 음성군
# eMinwon 고시공고 목록 (eminwon_list 어댑터, 2026-09-25 실측 확인)
EUMSEONG = City(
    province="충청북도",
    city="음성군",
    base_url="https://www.eumseong.go.kr/www/selectEminwonList.do?key=352",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청북도", sigun_name="음성군"),
    adapter="eminwon_list",
)

# ============================================================ 옥천군
# std_ezweb 어댑터. bbsNo=40,key=236 (사용자 제공 URL, 2026-09-26 실측 확인).
OKCHEON = City(
    province="충청북도",
    city="옥천군",
    base_url="https://www.oc.go.kr/www/",
    boards=[{"name": "고시공고", "bbsNo": 40, "key": 236}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청북도", sigun_name="옥천군"),
)

# ============================================================ 충주시 — eminwon_list 어댑터
# base_url에 pageIndex를 남겨두면 어댑터가 붙이는 pageIndex와 중복돼 목록이 비게
# 나왔다(2026-09-26 실측 확인) — 페이지네이션 파라미터는 빼고 key/ancmt_se_code만 남긴다.
CHUNGJU = City(
    province="충청북도",
    city="충주시",
    base_url="https://chungju.go.kr/www/selectEminwonList.do?key=510&ofr_pageSize=10&ancmt_se_code=01,02,04,05",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청북도", sigun_name="충주시"),
    adapter="eminwon_list",
)

# ============================================================ 청주시 — eminwon_list 어댑터
# 메소드명이 selectEminwonNoticeList.do로 다른 지자체(selectEminwonList.do)와
# 다르지만 같은 백엔드/마크업이라 그대로 GET된다(2026-09-26 실측 확인).
CHEONGJU = City(
    province="충청북도",
    city="청주시",
    base_url="https://www.cheongju.go.kr/www/selectEminwonNoticeList.do?key=281",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청북도", sigun_name="청주시"),
    adapter="eminwon_list",
)

# ============================================================ 증평군 — NTIS eMinwon 계열 (ntis_ofr 어댑터)
# LSub.jsp 변형(L.jsp는 400 에러) — 사용자 제공 URL, 2026-09-26 실측 확인.
JEUNGPYEONG = City(
    province="충청북도",
    city="증평군",
    base_url="https://eminwon.jp.go.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청북도", sigun_name="증평군"),
    adapter="ntis_ofr",
)

# ============================================================ 진천군 — NTIS eMinwon 계열 (ntis_ofr 어댑터)
# 사용자 제공 URL, 2026-09-26 실측 확인.
JINCHEON = City(
    province="충청북도",
    city="진천군",
    base_url="https://eminwon.jincheon.go.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp?not_ancmt_se_code=01,04",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청북도", sigun_name="진천군"),
    adapter="ntis_ofr",
)

# ============================================================ 괴산군 — NTIS eMinwon 계열 (ntis_ofr 어댑터)
# www.goesan.go.kr/www/contents.do?key=1439는 안내 페이지고, 그 안의
# <iframe src="https://eminwon.goesan.go.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp?...">가
# 실제 목록이다(실측 확인, 2026-09-27) — 완주군·진천군과 같은 iframe 트릭.
GOESAN = City(
    province="충청북도",
    city="괴산군",
    base_url="https://eminwon.goesan.go.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp?not_ancmt_se_code=01",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청북도", sigun_name="괴산군"),
    adapter="ntis_ofr",
)

# ============================================================ 영동군 — gosi_gotopage_board 어댑터
# 계룡시·부여군과 같은 벤더(?mode=V&...&GotoPage=)지만 id 파라미터 이름이 mng_no가
# 아니라 no다(어댑터가 둘 다 인식하도록 일반화). www.yd21.go.kr은 동해시·강릉시와
# 같은 레거시 TLS 암호화 스위트 문제가 있어 어댑터에 SECLEVEL 완화를 추가했다.
# 사용자 제공 URL, 2026-09-27 실측 확인.
YEONGDONG = City(
    province="충청북도",
    city="영동군",
    base_url="https://www.yd21.go.kr/kr/html/sub02/020103.html",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청북도", sigun_name="영동군"),
    adapter="gosi_gotopage_board",
)

# ============================================================ 단양군 — NTIS eMinwon 계열 (ntis_ofr 어댑터)
# 대표누리집 안내 페이지에 감싼 iframe이 가리키는 eminwon.danyang.go.kr NTIS
# 백엔드를 그대로 쓴다(실측 확인, 2026-09-28).
DANYANG = City(
    province="충청북도",
    city="단양군",
    base_url="https://eminwon.danyang.go.kr/emwp/jsp/ofr/OfrNotAncmtL.jsp?not_ancmt_se_code=01,02,03,04,05&list_gubun=A",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청북도", sigun_name="단양군"),
    adapter="ntis_ofr",
)

# ============================================================ 충청북도청 — chungbuk_do_board 어댑터
# selectGosiPblancList.do?key=422 (도청 고시/공고 전용 화면, 2026-09-28 실측 확인).
# 다른 도청 블록(충남·경기·경북)처럼 Regions는 도청 소재지(청주시)로 둔다 — 도 전역
# 공고라 소재지가 다른 시·군이면 토지조서 소재지가 CHECK로 표시된다.
CHUNGBUK_DO = City(
    province="충청북도",
    city="충청북도청",
    base_url="https://www.chungbuk.go.kr/www/selectGosiPblancList.do",
    boards=[{"name": "고시공고", "key": 422}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청북도", sigun_name="청주시"),
    adapter="chungbuk_do_board",
)

CITIES = [
    BOEUN, JECHEON, EUMSEONG, OKCHEON, CHUNGJU, CHEONGJU, JEUNGPYEONG, JINCHEON,
    GOESAN, YEONGDONG, DANYANG, CHUNGBUK_DO,
]
