"""
cities/busan.py — 부산광역시 및 자치구 고시공고 게시판 목록.

새 지자체를 추가할 때는 먼저 해당 사이트의 게시판 구조를 직접 탐색해 확인한 뒤
City(...)를 하나 더 추가한다 (임의 추측 금지, law.md 3-2 참고).
"""

from core.board_crawler import City
from core.jose_extractor import Regions

from cities._shared import DEFAULT_BLACKLIST, DEFAULT_KEYWORDS

PROVINCE_NAME = "부산"

# ============================================================ 부산광역시청
# nbgosi 게시판 (nbgosi_board 어댑터, 2026-09-26 실측 확인). JS 없이 평범한 GET.
BUSAN_CITY = City(
    province="부산광역시",
    city="부산광역시청",
    base_url="https://www.busan.go.kr/nbgosi",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="부산광역시", sigun_name="연제구"),
    adapter="nbgosi_board",
)

# ============================================================ 부산 동구
# 같은 NTIS eMinwon 계열(ntis_ofr 어댑터). 화면(index.donggu?menuCd=...)은 껍데기고
# 실제 목록은 iframe으로 eminwon.bsdonggu.go.kr을 그대로 끼워 넣은 것이다(브라우저
# 개발자도구로 iframe src 확인, 2026-09-26) — "index.CITY?menuCd=" 모양만 보고
# 다른 부산 구들도 같은 iframe 트릭을 쓴다고 가정하지 않고 하나씩 실측했다.
BUSAN_DONGGU = City(
    province="부산광역시",
    city="동구",
    base_url="https://eminwon.bsdonggu.go.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp?not_ancmt_se_code=01,04,05&list_gubun=",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="부산광역시", sigun_name="동구"),
    adapter="ntis_ofr",
)

# ============================================================ 부산 동래구
BUSAN_DONGNAE = City(
    province="부산광역시",
    city="동래구",
    base_url="https://eminwon.dongnae.go.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp?not_ancmt_se_code=01,04,05&list_gubun=&nodate_recent_mm=12",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="부산광역시", sigun_name="동래구"),
    adapter="ntis_ofr",
)

# ============================================================ 부산 진구
# 목록 테이블에 summary 속성이 없고(익산시·정읍시와 다른 마크업 변형), "번호" 칸도
# title 칸과 같은 onclick을 가진 <a>라 ntis_ofr.py의 테이블 선택/제목 추출 로직을
# 내용 기반으로 일반화해야 했다(2026-09-26 실측 확인, _raw_items_from_table 참고).
BUSAN_JIN = City(
    province="부산광역시",
    city="진구",
    base_url="https://eminwon.busanjin.go.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp?not_ancmt_se_code=01,04&list_gubun=A",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="부산광역시", sigun_name="진구"),
    adapter="ntis_ofr",
)

# ============================================================ 부산 사상구
BUSAN_SASANG = City(
    province="부산광역시",
    city="사상구",
    base_url="https://eminwon.sasang.go.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp?not_ancmt_se_code=01,02,04,05&list_gubun=A&recent_mm=12&epcCheck=Y",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="부산광역시", sigun_name="사상구"),
    adapter="ntis_ofr",
)

# ============================================================ 부산 사하구
BUSAN_SAHA = City(
    province="부산광역시",
    city="사하구",
    base_url="https://eminwon.saha.go.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp?not_ancmt_se_code=01,04,05&list_gubun=&cha_dep_code_nm=null",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="부산광역시", sigun_name="사하구"),
    adapter="ntis_ofr",
)

# ============================================================ 부산 북구
BUSAN_BUKGU = City(
    province="부산광역시",
    city="북구",
    base_url="https://eminwon.bsbukgu.go.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp?not_ancmt_se_code=01,02,04&gbn=1&menuCD=DOM_000000105001005000",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="부산광역시", sigun_name="북구"),
    adapter="ntis_ofr",
)

# ============================================================ 부산 수영구
BUSAN_SUYEONG = City(
    province="부산광역시",
    city="수영구",
    base_url="https://eminwon.suyeong.go.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp?not_ancmt_se_code=01,04&recent_mm=12&homepagetype=new",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="부산광역시", sigun_name="수영구"),
    adapter="ntis_ofr",
)

# ============================================================ 부산 연제구 — 새올 계열 (saeol_gosi 어댑터)
# 사용자 제공 URL, 2026-09-26 실측 확인.
BUSAN_YEONJE = City(
    province="부산광역시",
    city="연제구",
    base_url="https://www.yeonje.go.kr/portal/saeol/gosi/list.do?mId=0206030000",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="부산광역시", sigun_name="연제구"),
    adapter="saeol_gosi",
)

# ============================================================ 부산 금정구 — jeonbuk_style_board 어댑터
# 전북특별자치도청과 같은 이지사이트 계열이지만 제목 칸 class가 "subject"로 달라
# (실측 확인, 2026-09-26) 어댑터에 selector를 추가했다.
BUSAN_GEUMJEONG = City(
    province="부산광역시",
    city="금정구",
    base_url="https://www.geumjeong.go.kr",
    boards=[{"name": "고시공고", "board_id": "BBS_0000006", "menu_cd": "DOM_000000124002003000", "path": "geumj"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="부산광역시", sigun_name="금정구"),
    adapter="jeonbuk_style_board",
)

# ============================================================ 부산 해운대구
# 같은 NTIS eMinwon 계열(ntis_ofr 어댑터). iframe 트릭(브라우저 개발자도구로 확인, 2026-09-26).
BUSAN_HAEUNDAE = City(
    province="부산광역시",
    city="해운대구",
    base_url="https://eminwon.haeundae.go.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp?not_ancmt_se_code=01,04,05&nodate_recent_mm=12",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="부산광역시", sigun_name="해운대구"),
    adapter="ntis_ofr",
)

# ============================================================ 부산 영도구 — haman_web_board 어댑터
# 함안군과 같은 벤더(같은 list1f1t3i1 스킨, 실측 확인).
BUSAN_YEONGDO = City(
    province="부산광역시",
    city="영도구",
    base_url="https://www.yeongdo.go.kr/00000/00007/00013.web",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="부산광역시", sigun_name="영도구"),
    adapter="haman_web_board",
)

# ============================================================ 부산 기장군
# 같은 NTIS eMinwon 계열(ntis_ofr 어댑터). 화면(index.gijang?menuCd=...)은
# 껍데기고 실제 목록은 iframe으로 eminwon.gijang.go.kr을 그대로 끼워 넣은
# 것이다(실측 확인, 2026-09-26). 이 지자체는 <form name="form1">이 아니라
# <form name="form">을 쓰는 변형이라 ntis_ofr.py의 폼 이름 탐색을 일반화했다.
BUSAN_GIJANG = City(
    province="부산광역시",
    city="기장군",
    base_url="https://eminwon.gijang.go.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp?not_ancmt_se_code=01,02,04&list_gubun=",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="부산광역시", sigun_name="기장군"),
    adapter="ntis_ofr",
)

CITIES = [
    BUSAN_CITY, BUSAN_DONGGU, BUSAN_DONGNAE, BUSAN_JIN, BUSAN_SASANG,
    BUSAN_SAHA, BUSAN_BUKGU, BUSAN_SUYEONG, BUSAN_YEONJE, BUSAN_GEUMJEONG, BUSAN_HAEUNDAE,
    BUSAN_YEONGDO, BUSAN_GIJANG,
]
