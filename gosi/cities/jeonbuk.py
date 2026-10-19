"""
cities/jeonbuk.py — 전라북도 지자체 고시공고 게시판 목록.

새 지자체를 추가할 때는 먼저 해당 사이트의 게시판 구조를 직접 탐색해 확인한 뒤
City(...)를 하나 더 추가한다 (임의 추측 금지, law.md 3-2 참고).
"""

from core.board_crawler import City
from core.jose_extractor import Regions

from cities._shared import DEFAULT_BLACKLIST, DEFAULT_KEYWORDS

PROVINCE_NAME = "전북"

# ============================================================ NTIS eMinwon 계열 (ntis_ofr 어댑터)
# cms_adapters/ntis_ofr.py 상단 설명 참고 — 2026-09-25 실측 확인
JEONGEUP = City(
    province="전라북도",
    city="정읍시",
    base_url="http://eminwon.jeongeup.go.kr/emwp/jsp/ofr/OfrNotAncmtL.jsp?not_ancmt_se_code=01,02,03,04,05,06,07",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라북도", sigun_name="정읍시"),
    adapter="ntis_ofr",
)

IKSAN = City(
    province="전라북도",
    city="익산시",
    base_url="https://eminwon.iksan.go.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp?not_ancmt_se_code=01,02,03,04,05&cpath=",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라북도", sigun_name="익산시"),
    adapter="ntis_ofr",
)

# ============================================================ 고창군
# board/list.gochang (bbs_list_skin 어댑터, 2026-09-25 실측 확인). 같은 "index.XXX?
# menuCd=" 형태 URL을 쓰는 다른 지자체(부산 동구·임실군 등)는 실측 결과 다른
# 시스템이었다 — URL 모양만으로 같은 벤더라고 가정하지 않는다(law.md 3-2).
GOCHANG = City(
    province="전라북도",
    city="고창군",
    base_url="https://www.gochang.go.kr/board/list.gochang?boardId=BBS_0000180&menuCd=DOM_000000102003007000",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라북도", sigun_name="고창군"),
    adapter="bbs_list_skin",
)

# ============================================================ 전주시
# jeonju_board 어댑터 (2026-09-26 실측 확인). base_url 자체가 spreadsheet가
# 가리킨 keyword=보상 서버측 사전 필터라 페이지 수가 훨씬 적다.
JEONJU = City(
    province="전라북도",
    city="전주시",
    base_url=(
        "https://www.jeonju.go.kr/planweb/board/list.9is?boardUid=9be517a7914528ce01930aa3ddc26cf0"
        "&contentUid=ff8080818990c349018b041a879f395a&rowCount=10&searchType=dataContent&keyword=%EB%B3%B4%EC%83%81"
    ),
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라북도", sigun_name="전주시"),
    adapter="jeonju_board",
)

# ============================================================ 임실군
# 같은 NTIS eMinwon 계열(ntis_ofr 어댑터). 화면(index.imsil?menuCd=...)은 껍데기고
# 실제 목록은 iframe으로 eminwon.imsil.go.kr을 그대로 끼워 넣은 것이라(브라우저
# 개발자도구로 iframe src 확인, 2026-09-26), 그 iframe URL을 base_url로 쓴다.
IMSIL = City(
    province="전라북도",
    city="임실군",
    base_url="https://eminwon.imsil.go.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp?not_ancmt_se_code=01,02,03,04,05&subcheck=Y",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라북도", sigun_name="임실군"),
    adapter="ntis_ofr",
)

# ============================================================ 군산시 — NTIS eMinwon 계열 (ntis_ofr 어댑터)
# 사용자 제공 URL, 2026-09-26 실측 확인.
GUNSAN = City(
    province="전라북도",
    city="군산시",
    base_url="https://eminwon.gunsan.go.kr/emwp/jsp/ofr/OfrNotAncmtL.jsp",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라북도", sigun_name="군산시"),
    adapter="ntis_ofr",
)

# ============================================================ 장수군 — NTIS eMinwon 계열 (ntis_ofr 어댑터)
JANGSU = City(
    province="전라북도",
    city="장수군",
    base_url="https://eminwon.jangsu.go.kr/emwp/jsp/ofr/OfrNotAncmtL.jsp",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라북도", sigun_name="장수군"),
    adapter="ntis_ofr",
)

# ============================================================ 무주군 — NTIS eMinwon 계열 (ntis_ofr 어댑터)
MUJU = City(
    province="전라북도",
    city="무주군",
    base_url="https://eminwon.muju.go.kr/emwp/jsp/ofr/OfrNotAncmtL.jsp",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라북도", sigun_name="무주군"),
    adapter="ntis_ofr",
)

# ============================================================ 전북특별자치도청 — jeonbuk_style_board 어댑터
# 사용자 제공 URL, 2026-09-26 실측 확인.
JEONBUK_DO = City(
    province="전북특별자치도",
    city="전북특별자치도청",
    base_url="https://www.jeonbuk.go.kr",
    boards=[{"name": "고시공고", "board_id": "BBS_0000129", "menu_cd": "DOM_000000102002005000", "path": "jeonbuk"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전북특별자치도", sigun_name="전주시"),
    adapter="jeonbuk_style_board",
)

# ============================================================ 완주군
# 같은 NTIS eMinwon 계열(ntis_ofr 어댑터). 화면(index.9is?contentUid=...)은 껍데기고
# 실제 목록은 iframe으로 eminwon.wanju.go.kr을 그대로 끼워 넣은 것이다(브라우저
# 개발자도구로 iframe src 확인, 2026-09-26).
WANJU = City(
    province="전라북도",
    city="완주군",
    base_url="https://eminwon.wanju.go.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp?not_ancmt_se_code=01,04&epcCheck=Y&recent_mm=90",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라북도", sigun_name="완주군"),
    adapter="ntis_ofr",
)

# ============================================================ 진안군
# 같은 NTIS eMinwon 계열(ntis_ofr 어댑터). 이전 조사에서 "WAF 차단"으로 오판했으나,
# 실제로는 이 서버가 특정 요청에 간헐적으로 400을 내는 것(정읍시/부산진구 등과 같은
# 이미 문서화된 현상)이었다 — 재시도(board_crawler.py의 backoff)로 정상 재현 확인
# (2026-09-26 실측 확인).
JINAN = City(
    province="전라북도",
    city="진안군",
    base_url="https://eminwon.jinan.go.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp?not_ancmt_se_code=01,04",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라북도", sigun_name="진안군"),
    adapter="ntis_ofr",
)

# ============================================================ 남원시 — eminwon_list 어댑터
# 목록은 <table class="bbs_table">(td.title이라 eminwon_list.py의 1순위 selector가
# 바로 잡는다), 첨부는 <a href="download.do?boardUid=&postUid=&atchFileUid=">완성된
# GET 링크(링크 텍스트가 파일명)라 어댑터에 이 패턴을 추가했다. 사용자 제공 URL,
# 2026-09-27 실측 확인.
NAMWON = City(
    province="전라북도",
    city="남원시",
    base_url="https://www.namwon.go.kr/board/post/list.do?boardUid=ff8080818ea1fec5018ea24137680031&menuUid=ff8080818e3beff0018e4077131b007a",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라북도", sigun_name="남원시"),
    adapter="eminwon_list",
)

# ============================================================ 김제시 — bbs_list_table_board 어댑터
# 부안군과 같은 table.bbs_list_t 마크업(실측 확인, 2026-09-28). 등록일이
# "YYYY-MM-DD"(4자리 연도) 형식인 점만 부안군과 다르다.
GIMJE = City(
    province="전라북도",
    city="김제시",
    base_url="https://www.gimje.go.kr/board/list.gimje",
    boards=[{"name": "고시공고", "board_id": "BBS_0000044", "menu_cd": "DOM_000000104003000000"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라북도", sigun_name="김제시"),
    adapter="bbs_list_table_board",
)

# ============================================================ 순창군 — NTIS eMinwon 계열 (ntis_ofr 어댑터)
# 대표누리집에 새창(target="_blank")으로 바로 걸린 eminwon.sunchang.go.kr 링크를
# 그대로 쓴다(실측 확인, 2026-09-28).
SUNCHANG = City(
    province="전라북도",
    city="순창군",
    base_url="https://eminwon.sunchang.go.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp?not_ancmt_se_code=01,02,03,04,05",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라북도", sigun_name="순창군"),
    adapter="ntis_ofr",
)

# ============================================================ 부안군 — bbs_list_table_board 어댑터(신규)
# board/list.buan?boardId=...&menuCd=... URL이 고창군(bbs_list_skin)·의령군
# (uiryeong_board)과 비슷해 보이지만 실제 마크업은 <table class="bbs_list_t">라
# 새 어댑터를 만들었다(law.md 3-2, 실측 확인 2026-09-28). 등록일이 "YY.MM.DD"
# (2자리 연도) 형식이라 김제시와 함께 이 어댑터가 두 형식 모두 지원한다.
BUAN = City(
    province="전라북도",
    city="부안군",
    base_url="https://www.buan.go.kr/board/list.buan",
    boards=[{"name": "고시공고", "board_id": "BBS_0000054", "menu_cd": "DOM_000000103001003000"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라북도", sigun_name="부안군"),
    adapter="bbs_list_table_board",
)

CITIES = [
    JEONGEUP, IKSAN, GOCHANG, JEONJU, IMSIL, GUNSAN, JANGSU, MUJU, JEONBUK_DO, WANJU, JINAN,
    NAMWON, GIMJE, SUNCHANG, BUAN,
]
