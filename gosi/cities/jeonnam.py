"""
cities/jeonnam.py — 전라남도 지자체 고시공고 게시판 목록.

새 지자체를 추가할 때는 먼저 해당 사이트의 게시판 구조를 직접 탐색해 확인한 뒤
City(...)를 하나 더 추가한다 (임의 추측 금지, law.md 3-2 참고).
"""

from core.board_crawler import City
from core.jose_extractor import Regions

from cities._shared import DEFAULT_BLACKLIST, DEFAULT_KEYWORDS

PROVINCE_NAME = "전남"

# ============================================================ 담양군
# 담양군 전용 JSON API 어댑터 (cms_adapters/damyang_eminwon_api.py 상단 설명 참고,
# 2026-09-25 실측 확인 — 페이지가 JS 렌더링이라 목록/상세 모두 JSON API로 직접 조회)
DAMYANG = City(
    province="전라남도",
    city="담양군",
    base_url=(
        "https://www.damyang.go.kr/eminwon/searchList?domainId=DOM_0000001"
        "&contentsSid=2&menuCd=DOM_000000190001002001&boardType=special&listType=01"
    ),
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라남도", sigun_name="담양군"),
    adapter="damyang_eminwon_api",
)

# ============================================================ 장성군
# jangseong_board 어댑터 (2026-09-26 실측 확인). 목록은 이 사이트 전용 마크업이지만
# 첨부 다운로드는 보령시(eminwon_list.py)와 같은 POST 방식이라 그 로직을 재사용했다.
JANGSEONG = City(
    province="전라남도",
    city="장성군",
    base_url="https://www.jangseong.go.kr/home/www/news/jangseong/announcement",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라남도", sigun_name="장성군"),
    adapter="jangseong_board",
)

# ============================================================ 나주시
# naju_board 어댑터 (2026-09-26 실측 확인). JS 없이 평범한 GET. 첨부는 밀양시와
# 같은 GET 방식(eminwon.naju.go.kr FileDown.jsp에 파일명이 그대로 쿼리파라미터로
# 실려 있음).
NAJU = City(
    province="전라남도",
    city="나주시",
    base_url="https://www.naju.go.kr/www/administration/notice/gosi_new",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라남도", sigun_name="나주시"),
    adapter="naju_board",
)

# ============================================================ 화순군 — NTIS eMinwon 계열 (ntis_ofr 어댑터)
# L.jsp 변형(LSub.jsp는 0건) — 사용자 제공 URL, 2026-09-26 실측 확인.
HWASUN = City(
    province="전라남도",
    city="화순군",
    base_url="http://eminwon.hwasun.go.kr/emwp/jsp/ofr/OfrNotAncmtL.jsp",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라남도", sigun_name="화순군"),
    adapter="ntis_ofr",
)

# ============================================================ 해남군 — jeonju_board 어댑터
# 전주시와 같은 .9is 플랫폼이지만 스킨이 달라(table.board_list) 어댑터에 selector를
# 추가했다(사용자 제공 URL, 2026-09-26 실측 확인).
HAENAM = City(
    province="전라남도",
    city="해남군",
    base_url="https://www.haenam.go.kr/planweb/board/list.9is?boardUid=18e3368f5fb80fdc015fdc42b7e003e0&contentUid=18e3368f5d745106015de95f1ccd205c",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라남도", sigun_name="해남군"),
    adapter="jeonju_board",
)

# ============================================================ 곡성군 — eminwon_list 어댑터
# 제물포구와 똑같이 서버가 중간 인증서를 안 보내(Thawte TLS RSA CA G1 누락) 같은
# 인증서를 재사용해 해결했다(사용자 제공 URL, 2026-09-26 실측 확인).
GOKSEONG = City(
    province="전라남도",
    city="곡성군",
    base_url="https://www.gokseong.go.kr/board/GosiList.do?menuNo=102001003000",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라남도", sigun_name="곡성군"),
    adapter="eminwon_list",
)

# ============================================================ 함평군 — hampyeong_board 어댑터
# 목록은 이 사이트 전용 마크업(div 기반)이지만 첨부 다운로드는 장성군과 같은 POST
# 방식이라 eminwon_list.py의 download_attachment를 재사용했다(사용자 제공 URL,
# 2026-09-26 실측 확인).
HAMPYEONG = City(
    province="전라남도",
    city="함평군",
    base_url="https://www.hampyeong.go.kr/pg/GosiList.do",
    boards=[{"name": "고시공고", "page_id": "www273", "not_ancmt_se_code": "01,02,03,04"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라남도", sigun_name="함평군"),
    adapter="hampyeong_board",
)

# ============================================================ 광양시 — gwangyang_board 어댑터
# gwangyang_board.py 상단 설명 참고 — 사용자 제공 URL, 2026-09-26 실측 확인.
GWANGYANG = City(
    province="전라남도",
    city="광양시",
    base_url="https://gwangyang.go.kr/saeol/gosi.es",
    boards=[{"name": "고시공고", "mid": "a11005020000"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라남도", sigun_name="광양시"),
    adapter="gwangyang_board",
)

# ============================================================ 목포시 — eminwon_list 어댑터
# 목록은 <table class="board_basic">(eminwon_list.py의 일반 fallback 경로가
# 처리)이고, 상세 페이지 제목 <a>는 일부 잘려 있지만(예: "...결산 승인결..") 실제
# <h3> 제목/첨부는 상세 페이지에만 있다 — 목록 단계 키워드 매칭은 잘린 텍스트
# 기준이라 아주 드물게 키워드가 잘린 꼬리부분에만 있으면 놓칠 수 있다(알려진 제약).
# 첨부는 <form name="nnn"> POST(eminwon.mokpo.go.kr/emwp/jsp/ofr/FileDownNew.jsp,
# 보령시와 같은 패턴) — eminwon_list.py가 이미 지원한다. 사용자 제공 URL,
# 2026-09-27 실측 확인.
MOKPO = City(
    province="전라남도",
    city="목포시",
    base_url="https://www.mokpo.go.kr/www/mokpo_news/notification/public_notice",
    boards=[{"name": "고시/공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라남도", sigun_name="목포시"),
    adapter="eminwon_list",
)

# ============================================================ 완도군 — eminwon_list 어댑터
# 목록은 <table class="board_t1">(eminwon_list.py의 일반 fallback 경로가 제목/날짜/
# 공고번호를 모두 처리)이고, 첨부는 <form name="nnn"> POST(eminwon.wando.go.kr/emwp/
# jsp/ofr/FileDownNew.jsp, 보령시와 같은 패턴)라 그대로 지원된다. 사용자 제공 URL,
# 2026-09-27 실측 확인.
WANDO = City(
    province="전라남도",
    city="완도군",
    base_url="https://www.wando.go.kr/wando/sub.cs?m=318",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라남도", sigun_name="완도군"),
    adapter="eminwon_list",
)

# ============================================================ 진도군 — eminwon_list 어댑터
# 목록은 새올(notAncmtMgtNo) 계열 마크업(td.title이라 eminwon_list.py의 1순위
# selector가 바로 잡는다)이지만, 첨부 다운로드는 goDownload(...)가 주석 처리돼
# 죽어 있고 실제로는 완성된 GET 링크(/doc/dataDown.jsp?fileNo=&fileMgtNo=&stype=)를
# 쓴다 — eminwon_list.py에 이 패턴을 추가했다(사용자 제공 URL, 2026-09-27 실측 확인).
JINDO = City(
    province="전라남도",
    city="진도군",
    base_url="https://jindo.go.kr/home/gosi/general.cs?m=24",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라남도", sigun_name="진도군"),
    adapter="eminwon_list",
)

# ============================================================ 장흥군 — eminwon_list 어댑터
# 목포시와 같은 "www/.../notification?idx=&mode=view" + "?page=" 벤더(목록 제목도
# 마찬가지로 일부 잘려 나온다 — 알려진 제약). 사용자 제공 URL, 2026-09-27 실측 확인.
JANGHEUNG = City(
    province="전라남도",
    city="장흥군",
    base_url="https://www.jangheung.go.kr/www/organization/news/notification",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라남도", sigun_name="장흥군"),
    adapter="eminwon_list",
)

# ============================================================ 영광군 — yeonggwang_board 어댑터
# 그누보드 계열(offset 페이지네이션), 첨부 다운로드 서버가 eminwon.yeonggwang.
# jeonnam.kr(일반적인 eminwon.<같은도메인> 규칙이 아님)이라 전용 어댑터가
# 필요했다(사용자 제공 URL, 2026-09-27 실측 확인).
YEONGGWANG = City(
    province="전라남도",
    city="영광군",
    base_url="https://www.yeonggwang.go.kr/bbs/",
    boards=[{"name": "고시공고", "b_id": "gosigonggo", "site": "headquarter_new", "mn": 9059}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라남도", sigun_name="영광군"),
    adapter="yeonggwang_board",
)

# ============================================================ 전남광주통합특별시(구 전라남도청) — sap_gosi 어댑터
# CSV의 "전라남도청"(jeonnam.go.kr/J0203)은 2026-07-01 행정통합으로 폐지된
# 구 게시판이다 — 그 페이지 자체에 "2026.7.1. 이후 고시/공고는 통합특별시
# 임시 누리집 내 고시공고 메뉴를 이용해 주시기 바랍니다"라는 안내가 있다(실측
# 확인, 2026-09-27). 실제 신규 사이트(jeonnam-gwangju.go.kr)의 고시공고 페이지도
# JS 렌더링 뒤에 <iframe src="https://sido.jeonnam.go.kr/citynet/jsp/sap/
# SAPGosiBizProcess.do?...">로 실제 목록을 띄우는데, 이게 인천광역시청과 같은
# SAPGosiBizProcess.do 벤더라(sap_gosi.py 상단 주석이 "광주가 같은 벤더를 쓸
# 가능성"을 이미 언급했었다) 코드 수정 없이 그대로 등록된다.
# ※ 이 게시판은 광주광역시청 고시공고도 함께 담고 있다(2026-09-28 실측: "수소차 보급사업
#   (광주)", "하정웅미술관" 등 광주 글이 같은 목록에 섞여 있음 — 사용자가 알려준 광주광역시청
#   URL jeonnam-gwangju.go.kr/contentsView.do?pageId=jngj24 의 iframe이 바로 이 SAP 주소).
#   그래서 광주광역시청을 별도 City로 또 등록하지 않는다(중복 수집 방지). 옛 광주 게시판
#   (gwangju.go.kr pageId=www791)은 2026-06-30까지의 보관용이다.
JEONNAM_GWANGJU = City(
    province="전남광주통합특별시",
    city="전남광주통합특별시(구 전라남도청)",
    base_url="https://sido.jeonnam.go.kr/citynet/jsp/sap/SAPGosiBizProcess.do",
    boards=[{"name": "고시공고", "sido": ""}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전남광주통합특별시", sigun_name=""),
    adapter="sap_gosi",
)

# ============================================================ 영암군 — eminwon_list 어댑터
# 목록은 표준 <table class="list_table">(eminwon_list.py의 일반 fallback으로 처리),
# 페이지네이션은 "page" 파라미터(이미 공통 세트에 있음). 서버가 중간 인증서(Sectigo
# Public Server Authentication CA DV R36)를 안 보내 체인이 안 만들어져(제물포구·
# 곡성군과 같은 유형이지만 CA 벤더가 다름) 발급기관 공개 배포처에서 받은 중간
# 인증서로 체인을 완성했다(검증을 끄는 게 아니라 채우는 것) — eminwon_list.py의
# _MISSING_CA_HOSTS를 host별 인증서 매핑으로 일반화했다. 첨부는 <form name="nnn">
# POST(eminwon.yeongam.go.kr)인데 링크 텍스트에 "파일명.ext 다운로드"처럼 라벨이
# 그대로 붙어 있어(보령시와 달리) 확장자 뒤 라벨만 떼도록 eminwon_list.py에 분기
# 추가. 사용자 제공 URL, 2026-09-28 실측 확인.
YEONGAM = City(
    province="전라남도",
    city="영암군",
    base_url="https://www.yeongam.go.kr/home/www/open_information/yeongam_news/announcement",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라남도", sigun_name="영암군"),
    adapter="eminwon_list",
)

# ============================================================ 구례군 — eminwon_list 어댑터
# 곡성군과 같은 벤더(board/GosiList.do, eGovFramework 계열)지만 제목 <a href="javaScript:
# searchDetail('<id>')">(href 자체가 javascript: URI, 곡성군은 href="#"+onclick 조합이라
# 다르다). 상세 URL은 searchDetail() 함수 본문의 location.href 대입에서 고정 쿼리
# 문자열을 그대로 읽어 not_ancmt_mgt_no만 붙여 재구성한다 — eminwon_list.py에 이
# location.href 패턴과, 곡성군의 document.<폼>.action 대입 패턴 둘 다 지원하도록
# 일반화했다(페이지 전체가 아니라 searchDetail() 함수 본문 안에서만 찾아 페이지의
# 다른 무관한 .action/location.href 대입과 안 섞이게 했다 — 처음엔 이걸로 실패했었다).
# 첨부는 <form name="nnn"> POST(보령시와 같은 패턴). 사용자 제공 URL, 2026-09-28
# 실측 확인.
GURYE = City(
    province="전라남도",
    city="구례군",
    base_url="https://www.gurye.go.kr/board/GosiList.do?not_ancmt_se_code=01,04,06,07&menuNo=115004002001",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라남도", sigun_name="구례군"),
    adapter="eminwon_list",
)

# ============================================================ 강진군 — eminwon_list 어댑터
# 목포시·장흥군과 같은 "www/.../notice/gosi?idx=&mode=view" 벤더(eminwon_list.py의
# 일반 fallback으로 목록/날짜 처리, td.align_left 칸이 제목). 첨부는 완성된 GET
# href(a[href*='FileDown'])라 별도 조치 불필요. 사용자 제공 URL, 2026-09-28 실측 확인.
GANGJIN = City(
    province="전라남도",
    city="강진군",
    base_url="https://www.gangjin.go.kr/www/government/notice/gosi",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라남도", sigun_name="강진군"),
    adapter="eminwon_list",
)

# ============================================================ 고흥군 — goheung_eminwon_api 어댑터
# 페이지가 순수 JS 렌더링(POST /getEminwon.do로 JSON을 받아 그리는 방식)이라
# goheung_eminwon_api.py 상단 설명 참고. 담양군과 비슷한 유형이지만 엔드포인트/
# 필드명이 전혀 달라 전용 어댑터를 새로 만들었다. 첨부는 fileHref가 이미 완성된
# GET 링크지만 JSON 값 자체에 "&"가 "&amp;"로 인코딩돼 있어 html.unescape가
# 필요했다(실측 확인, 2026-09-28).
GOHEUNG = City(
    province="전라남도",
    city="고흥군",
    base_url="https://www.goheung.go.kr/contentsView.do?pageId=www99",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라남도", sigun_name="고흥군"),
    adapter="goheung_eminwon_api",
)

# ============================================================ 무안군 — eminwon_list 어댑터
# 완도군과 같은 <table class="board_t1"> 벤더, 제목 칸이 class="title"이라
# eminwon_list.py 1순위 selector로 바로 잡힌다. "www/.../announcement?idx=&mode=view"
# + "?page=" 페이지네이션(강진군과 같은 계열). 첨부는 완성된 GET href. 사용자 제공
# URL, 2026-09-28 실측 확인.
MUAN = City(
    province="전라남도",
    city="무안군",
    base_url="https://www.muan.go.kr/www/openmuan/new/announcement",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라남도", sigun_name="무안군"),
    adapter="eminwon_list",
)

# ============================================================ 보성군 — eminwon_list 어댑터
# 완도군·무안군과 같은 <table class="board_t1"> 벤더. 실제 메인페이지는 "?main=true"
# 리다이렉트 인트로 페이지가 앞에 있어(코로나 안내 잔재로 추정) 진짜 홈은
# "/?main=true"를 통해 찾았다. "www/.../notification?idx=&mode=view" + "?page="
# 계열. 첨부는 완성된 GET href. 사용자 제공 URL, 2026-09-28 실측 확인.
BOSEONG = City(
    province="전라남도",
    city="보성군",
    base_url="https://www.boseong.go.kr/www/open_administration/city_news/notification",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라남도", sigun_name="보성군"),
    adapter="eminwon_list",
)

# ============================================================ 순천시 — eminwon_list 어댑터
# 목록은 <table class="bbsList">(td.title_minwon 칸에 "title" 부분문자열이 있어
# eminwon_list.py 1순위 selector로 잡힌다). 첨부는 <form name="form1"> POST(보령시와
# 같은 암호화 토큰 방식이지만 폼 이름이 "nnn"이 아니라 "form1")라 eminwon_list.py의
# POST 폼 판별을 이름이 아니라 hidden 필드(user_file_nm/sys_file_nm/file_path) 존재
# 여부로 일반화했다. 사용자 제공 URL, 2026-09-28 실측 확인.
SUNCHEON = City(
    province="전라남도",
    city="순천시",
    base_url="https://www.suncheon.go.kr/kr/news/0004/0005/0001/",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라남도", sigun_name="순천시"),
    adapter="eminwon_list",
)

# ============================================================ 신안군 — eminwon_list 어댑터
# 영양군과 같은 <table class="list_table"> 벤더(제목 칸에 class 없이 style="text-align:
# left"만 있음 — eminwon_list.py의 "마지막 <a> 칸" 폴백으로 잡힌다). 첨부는 완성된
# GET href(a[href*='FileDown'])라 별도 조치 불필요. 사용자 제공 URL, 2026-09-28
# 실측 확인.
SHINAN = City(
    province="전라남도",
    city="신안군",
    base_url="https://www.shinan.go.kr/home/www/openinfo/participation_07/participation_07_04",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라남도", sigun_name="신안군"),
    adapter="eminwon_list",
)

# ============================================================ 여수시 — eminwon_list 어댑터
# 목포시와 같은 <table class="board_basic"> 벤더, "www/.../new_notify?idx=&mode=view"
# + "?page=" 계열. 첨부는 완성된 GET href. 사용자 제공 URL, 2026-09-28 실측 확인.
YEOSU = City(
    province="전라남도",
    city="여수시",
    base_url="https://www.yeosu.go.kr/www/govt/news/notify",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전라남도", sigun_name="여수시"),
    adapter="eminwon_list",
)

CITIES = [
    DAMYANG, JANGSEONG, NAJU, HWASUN, HAENAM, GOKSEONG, HAMPYEONG, GWANGYANG, MOKPO, WANDO,
    JINDO, JANGHEUNG, YEONGGWANG, JEONNAM_GWANGJU, YEONGAM, GURYE, GANGJIN, GOHEUNG, MUAN,
    BOSEONG, SUNCHEON, SHINAN, YEOSU,
]
