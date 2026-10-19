"""
cities/gyeongnam.py — 경상남도 지자체 고시공고 게시판 목록.

새 지자체를 추가할 때는 먼저 해당 사이트의 게시판 구조를 직접 탐색해 확인한 뒤
City(...)를 하나 더 추가한다 (임의 추측 금지, law.md 3-2 참고).
"""

from core.board_crawler import City
from core.jose_extractor import Regions

from cities._shared import DEFAULT_BLACKLIST, DEFAULT_KEYWORDS

PROVINCE_NAME = "경남"

# ============================================================ 밀양시
# eMinwon 고시공고 목록 (eminwon_list 어댑터, 2026-09-25 실측 확인 —
# 첨부파일이 href="javascript:goDownLoad(...)"뿐이라 eminwon.<도메인> 조립 경로 사용)
MIRYANG = City(
    province="경상남도",
    city="밀양시",
    base_url="https://www.miryang.go.kr/web/eMinwonList.do?mnNo=20903000000&owd=&searchCateId=01,02,03,04,05,06,07&searchCnd=&searchWrd=",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상남도", sigun_name="밀양시"),
    adapter="eminwon_list",
)

# ============================================================ 양산시 — 새올 계열 (saeol_gosi 어댑터)
# 사용자 제공 URL, 2026-09-26 실측 확인.
YANGSAN = City(
    province="경상남도",
    city="양산시",
    base_url="https://www.yangsan.go.kr/portal/saeol/gosi/list.do?mid=0102010000",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상남도", sigun_name="양산시"),
    adapter="saeol_gosi",
)

# ============================================================ 고성군 — jeonbuk_style_board 어댑터
# 사용자 제공 URL, 2026-09-26 실측 확인.
GOSEONG = City(
    province="경상남도",
    city="고성군",
    base_url="https://www.goseong.go.kr",
    boards=[{"name": "고시공고", "board_id": "BBS_0000015", "menu_cd": "DOM_000000103001014000", "path": "goseong"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상남도", sigun_name="고성군"),
    adapter="jeonbuk_style_board",
)

# ============================================================ 함안군 — haman_web_board 어댑터
# 목록은 <table>이 아니라 <ul class="lst1"><li> 레이아웃(이 사이트 전용)이지만
# 첨부 다운로드는 밀양시와 같은 GET 방식이라 eminwon_list.py의 fetch_attachments를
# 재사용했다(사용자 제공 URL, 2026-09-26 실측 확인).
HAMAN = City(
    province="경상남도",
    city="함안군",
    base_url="https://www.haman.go.kr/00960/00962.web",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상남도", sigun_name="함안군"),
    adapter="haman_web_board",
)

# ============================================================ 하동군 — haman_web_board 어댑터
# 함안군과 같은 벤더(같은 list1f1t3i1 스킨, 실측 확인).
HADONG = City(
    province="경상남도",
    city="하동군",
    base_url="https://www.hadong.go.kr/media/00012.web",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상남도", sigun_name="하동군"),
    adapter="haman_web_board",
)

# ============================================================ 진주시 — haman_web_board 어댑터
JINJU = City(
    province="경상남도",
    city="진주시",
    base_url="https://www.jinju.go.kr/05586.web",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상남도", sigun_name="진주시"),
    adapter="haman_web_board",
)

# ============================================================ 김해시 — haman_web_board 어댑터
GIMHAE = City(
    province="경상남도",
    city="김해시",
    base_url="https://www.gimhae.go.kr/03360/00023/00029.web",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상남도", sigun_name="김해시"),
    adapter="haman_web_board",
)

# ============================================================ 창녕군 — haman_web_board 어댑터
CHANGNYEONG = City(
    province="경상남도",
    city="창녕군",
    base_url="https://www.cng.go.kr/03517/01553.web",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상남도", sigun_name="창녕군"),
    adapter="haman_web_board",
)

# ============================================================ 합천군 — haman_web_board 어댑터
# 서버 응답이 느려 타임아웃이 잦다(실측 확인) — 다른 곳엔 없는 지연이라 이 지자체만의
# 특성으로 보고 별도 조치 없이 board_crawler의 재시도 로직에 맡긴다.
HAPCHEON = City(
    province="경상남도",
    city="합천군",
    base_url="https://www.hc.go.kr/04948.web",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상남도", sigun_name="합천군"),
    adapter="haman_web_board",
)

# ============================================================ 거제시 — geoje_board 어댑터
# 밀양시와 같은 GET 방식 첨부 다운로드지만 실제 다운로드 경로가
# "/emwp/jsp/ofr/FileDown.jsp"가 아니라 "/emwp/jsp/lga/homepage/FileDown.jsp"로
# 달라(실측 확인, 2026-09-26) eminwon_list.py를 그대로 쓰지 못하고 별도 어댑터로 뒀다.
GEOJE = City(
    province="경상남도",
    city="거제시",
    base_url="https://www.geoje.go.kr/index.geoje",
    boards=[{"name": "고시공고", "menu_cd": "DOM_000008902001002000"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상남도", sigun_name="거제시"),
    adapter="geoje_board",
)

# ============================================================ 창원시 — changwon_board 어댑터
# 같은 ".web" 확장자를 쓰는 함안군 등(haman_web_board, <ul class="lst1">)과는
# 완전히 다른 마크업(<table class="t3">)이라 새 어댑터가 필요했다(사용자 제공
# URL, 2026-09-26 실측 확인). 첨부는 자체 프록시(DownloadEx.do)를 그대로 쓴다.
CHANGWON = City(
    province="경상남도",
    city="창원시",
    base_url="https://www.changwon.go.kr/cwportal/10310/10438/10439.web",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상남도", sigun_name="창원시"),
    adapter="changwon_board",
)

# ============================================================ 산청군 — std_ezweb 어댑터(bbs_default_list 스킨)
# 원주시와 같은 selectBbsNttList.do/selectBbsNttView.do/downloadBbsFile.do 백엔드지만
# 목록 테이블 class가 "bbs_default_list"(신규 스킨)이고 날짜 칸 끝에 마침표가 붙어
# (예: "2026.09.23.") 어댑터에 두 가지 모두 대응을 추가했다. 사용자 제공 URL,
# 2026-09-27 실측 확인.
SANCHEONG = City(
    province="경상남도",
    city="산청군",
    base_url="https://www.sancheong.go.kr/www/",
    boards=[{"name": "고시/공고", "bbsNo": 118, "key": 158}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상남도", sigun_name="산청군"),
    adapter="std_ezweb",
)

# ============================================================ 남해군 — haman_web_board 어댑터
# 함안군과 같은 list1f1t3i1 스킨(ul.lst1 > li.li1, cpage 페이지네이션)이라 코드
# 수정 없이 그대로 등록된다. 사용자 제공 URL, 2026-09-27 실측 확인.
NAMHAE = City(
    province="경상남도",
    city="남해군",
    base_url="https://www.namhae.go.kr/modules/saeol/gosi.do?pageCd=WW0512030402&siteGubun=portal",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상남도", sigun_name="남해군"),
    adapter="haman_web_board",
)

# ============================================================ 통영시 — haman_web_board 어댑터
# 함안군과 같은 벤더(.web URL, ul.lst1>li.li1, id 파라미터는 not_ancmt_mgt_no=)다.
# 실측 확인, 2026-09-28.
TONGYEONG = City(
    province="경상남도",
    city="통영시",
    base_url="https://www.tongyeong.go.kr/00852/00853/00858.web",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상남도", sigun_name="통영시"),
    adapter="haman_web_board",
)

# ============================================================ 사천시 — haman_web_board 어댑터
# 같은 ul.lst1>li.li1 마크업이지만 id 파라미터가 not_ancmt_mgt_no=가 아니라 idx=라
# haman_web_board.py의 항목 판별 조건을 "amode=view"로 일반화했다. 첨부는
# /board/download.do?gcode=...&name=...(남원시와 같은 패턴, 링크 텍스트가 진짜
# 파일명인 것과 "다운로드" 라벨뿐인 중복 링크가 하나씩 있음)라 eminwon_list.py의
# 기존 로직이 그대로 처리한다(실측 확인, 2026-09-28).
SACHEON = City(
    province="경상남도",
    city="사천시",
    base_url="https://www.sacheon.go.kr/news/00009/00014.web",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상남도", sigun_name="사천시"),
    adapter="haman_web_board",
)

# ============================================================ 의령군 — uiryeong_board 어댑터(신규)
# board/list.uiryeong?boardId=...&menuCd=... URL이 고창군(bbs_list_skin)과 비슷해
# 보이지만 실제 마크업은 <table class="list01">이라 새 어댑터를 만들었다(law.md 3-2,
# 실측 확인 2026-09-28). 첨부는 eminwon.uiryeong.go.kr의 FileDown.jsp 완성된 GET
# 링크라 eminwon_list.py를 재사용한다.
UIRYEONG = City(
    province="경상남도",
    city="의령군",
    base_url="https://www.uiryeong.go.kr/board/list.uiryeong",
    boards=[{"name": "고시공고", "board_id": "BBS_0000070", "menu_cd": "DOM_000000203003001001"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상남도", sigun_name="의령군"),
    adapter="uiryeong_board",
)

# ============================================================ 함양군 — ntis_ofr 어댑터
# 대표누리집 안내 페이지의 iframe이 가리키는 eminwon.hygn.go.kr NTIS 백엔드를
# 그대로 쓴다(완주군 등과 같은 iframe 트릭, 실측 확인 2026-09-28).
HAMYANG = City(
    province="경상남도",
    city="함양군",
    base_url="https://eminwon.hygn.go.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp?not_ancmt_se_code=01,02,03,04,07",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상남도", sigun_name="함양군"),
    adapter="ntis_ofr",
)

# ============================================================ 거창군 — haman_web_board 어댑터
# 함안군과 완전히 같은 마크업(ul.lst1>li.li1, id 파라미터도 not_ancmt_mgt_no=)이다
# (실측 확인, 2026-09-28).
GEOCHANG = City(
    province="경상남도",
    city="거창군",
    base_url="https://www.geochang.go.kr/00445/00451.web",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상남도", sigun_name="거창군"),
    adapter="haman_web_board",
)

# ============================================================ 경상남도청 — gyeongnam_do_board 어댑터
# index.gyeong?menuCd=DOM_000000135003009001 (도청 고시공고 전용 모듈, 2026-09-28 실측 확인).
# 다른 도청 블록처럼 Regions는 도청 소재지(창원시)로 둔다.
GYEONGNAM_DO = City(
    province="경상남도",
    city="경상남도청",
    base_url="https://www.gyeongnam.go.kr/index.gyeong",
    boards=[{"name": "고시공고", "menu_cd": "DOM_000000135003009001"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상남도", sigun_name="창원시"),
    adapter="gyeongnam_do_board",
)

CITIES = [
    MIRYANG, YANGSAN, GOSEONG, HAMAN, HADONG, JINJU, GIMHAE, CHANGNYEONG, HAPCHEON, GEOJE, CHANGWON,
    SANCHEONG, NAMHAE, TONGYEONG, SACHEON, UIRYEONG, HAMYANG, GEOCHANG, GYEONGNAM_DO,
]
