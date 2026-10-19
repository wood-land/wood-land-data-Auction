"""
cities/gyeonggi.py — 경기도 지자체 고시공고 게시판 목록.

새 지자체를 추가할 때는 먼저 해당 사이트의 게시판 구조를 직접 탐색해 확인한 뒤
City(...)를 하나 더 추가한다 (임의 추측 금지, law.md 3-2 참고).
"""

from core.board_crawler import City
from core.jose_extractor import Regions

from cities._shared import DEFAULT_BLACKLIST, DEFAULT_KEYWORDS

PROVINCE_NAME = "경기"

# ============================================================ 양평군
# 대상 게시판: bbsNo=5,key=1119 (보상맵 수집소스 시트, 2026-09-25 실측 확인 — p-table 스킨)
YANGPYEONG = City(
    province="경기도",
    city="양평군",
    base_url="https://www.yp21.go.kr/www/",
    boards=[{"name": "고시공고", "bbsNo": 5, "key": 1119}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="양평군"),
)

# ============================================================ 새올 계열 (saeol_gosi 어댑터)
# "새올" 행정정보시스템 고시 게시판 — 여러 지자체가 같은 벤더 시스템을 쓰는 것을
# 실측으로 확인했다(2026-09-25). cms_adapters/saeol_gosi.py 상단 설명 참고.
ICHEON = City(
    province="경기도",
    city="이천시",
    base_url="https://www.icheon.go.kr/portal/saeol/gosi/list.do?seCode=01&mid=0402010000&token=1719895604683",
    boards=[{"name": "고시"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="이천시"),
    adapter="saeol_gosi",
)

GWACHEON = City(
    province="경기도",
    city="과천시",
    base_url="https://www.gccity.go.kr/portal/saeol/gosi/list.do?mId=0301040000",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="과천시"),
    adapter="saeol_gosi",
)

OSAN = City(
    province="경기도",
    city="오산시",
    base_url="https://www.osan.go.kr/portal/saeol/gosi/list.do?mId=0302010000",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="오산시"),
    adapter="saeol_gosi",
)

PYEONGTAEK = City(
    province="경기도",
    city="평택시",
    base_url="https://www.pyeongtaek.go.kr/pyeongtaek/saeol/gosi/list.do?seCode=01&mid=0401020100&token=1762046625379",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="평택시"),
    adapter="saeol_gosi",
)

ANSEONG = City(
    province="경기도",
    city="안성시",
    base_url="https://www.anseong.go.kr/portal/saeol/gosiList.do?mId=0501040000&token=1717897670367",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="안성시"),
    adapter="saeol_gosi",
)

# ============================================================ 포천시
# eMinwon 고시공고 목록 (eminwon_list 어댑터, 2026-09-25 실측 확인 —
# 첨부파일 다운로드 서버가 자기 도메인이 아니라 eminwon.pcs21.net 공유 파일서버)
POCHEON = City(
    province="경기도",
    city="포천시",
    base_url="https://www.pocheon.go.kr/www/selectEminwonList.do?key=3712&notAncmtSeCode=01",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="포천시"),
    adapter="eminwon_list",
)

# ============================================================ selectGosiList 계열 (eminwon_list 어댑터)
# eMinwon과 같은 프레임워크의 다른 모듈 이름일 뿐, 구조가 같아 같은 어댑터로 처리된다
# (cms_adapters/eminwon_list.py 상단 설명 참고, 2026-09-25 실측 확인)
YEONCHEON = City(
    province="경기도",
    city="연천군",
    base_url="https://www.yeoncheon.go.kr/www/selectGosiList.do?key=3393&not_ancmt_se_code=01",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="연천군"),
    adapter="eminwon_list",
)

HANAM = City(
    province="경기도",
    city="하남시",
    base_url="https://www.hanam.go.kr/www/selectGosiList.do?key=171&not_ancmt_se_code=01,04",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="하남시"),
    adapter="eminwon_list",
)

DONGDUCHEON = City(
    province="경기도",
    city="동두천시",
    base_url="https://www.ddc.go.kr/ddc/selectGosiList.do?key=107&not_ancmt_se_code=01",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="동두천시"),
    adapter="eminwon_list",
)

GURI = City(
    province="경기도",
    city="구리시",
    base_url="https://www.guri.go.kr/www/selectGosiNttList.do?key=387&searchGosiSe=01,04,06",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="구리시"),
    adapter="eminwon_list",
)

GAPYEONG = City(
    province="경기도",
    city="가평군",
    base_url="https://www.gp.go.kr/portal/selectGosiList.do?key=2148&not_ancmt_se_code=01",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="가평군"),
    adapter="eminwon_list",
)

# ============================================================ 의정부시
# 새올 계열 (saeol_gosi 어댑터). www.ui4u.go.kr / eminwon.ui4u.go.kr 둘 다 TLS 체인에
# 중간 인증서가 빠져 있었는데(사용자가 실제 게시판 URL을 알려줘서 재확인함), 정상
# 발급된 인증서라 빠진 인증서만 보강해 해결했다 — saeol_gosi.py 상단 설명 참고.
UIJEONGBU = City(
    province="경기도",
    city="의정부시",
    base_url="https://www.ui4u.go.kr/portal/saeol/gosiList.do?seCode=01&mId=0301040000",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="의정부시"),
    adapter="saeol_gosi",
)

# ============================================================ 경기도청
# ajax/board/getList.do JSON API (gg_board 어댑터, 2026-09-26 실측 확인). 화면의
# <table id="boardList">는 로더 placeholder만 갖고 있고 실제 데이터는 JS가 POST로
# 받아오는 JSON이라(브라우저 네트워크 탭으로 실측 확인) 그 API를 직접 쓴다.
GYEONGGI_DO = City(
    province="경기도",
    city="경기도청",
    base_url="https://www.gg.go.kr/bbs/board.do",
    boards=[{"name": "고시공고", "bs_idx": "469", "menu_id": "1547"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="수원시"),
    adapter="gg_board",
)

# ============================================================ 시흥시 — 새올 계열 (saeol_gosi 어댑터)
# 사용자 제공 URL, 2026-09-26 실측 확인.
SIHEUNG = City(
    province="경기도",
    city="시흥시",
    base_url="https://www.siheung.go.kr/main/saeol/gosi/list.do?mId=0401040000",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="시흥시"),
    adapter="saeol_gosi",
)

# ============================================================ 여주시 — eminwon_list 어댑터
# 사용자 제공 URL, 2026-09-26 실측 확인.
YEOJU = City(
    province="경기도",
    city="여주시",
    base_url="https://www.yeoju.go.kr/www/selectEminwonList.do?key=413",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="여주시"),
    adapter="eminwon_list",
)

# ============================================================ 군포시 — eminwon_list 어댑터
# base_url에 pageUnit을 남겨두면 어댑터가 붙이는 pageUnit과 중복돼 400 에러가 났다
# (2026-09-26 실측 확인) — 페이지네이션 파라미터는 빼고 key만 남긴다.
GUNPO = City(
    province="경기도",
    city="군포시",
    base_url="https://www.gunpo.go.kr/www/selectEminwonList.do?key=3907&Not_ancmt_se_code=01,04",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="군포시"),
    adapter="eminwon_list",
)

# ============================================================ 양주시 — eminwon_list 어댑터
YANGJU = City(
    province="경기도",
    city="양주시",
    base_url="https://www.yangju.go.kr/www/selectEminwonList.do?key=4075",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="양주시"),
    adapter="eminwon_list",
)

# ============================================================ 남양주시 — eminwon_list 어댑터
NAMYANGJU = City(
    province="경기도",
    city="남양주시",
    base_url="https://www.nyj.go.kr/www/selectEminwonWebList.do?key=2492",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="남양주시"),
    adapter="eminwon_list",
)

# ============================================================ 안산시 — ansan_bbs 어댑터
# 사용자 제공 URL, 2026-09-26 실측 확인.
ANSAN = City(
    province="경기도",
    city="안산시",
    base_url="https://www.ansan.go.kr/www/common/bbs/selectPageListBbs.do",
    boards=[{"name": "고시공고", "bbs_code": "WWW13"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="안산시"),
    adapter="ansan_bbs",
)

# ============================================================ 안양시 — emws_board 어댑터
# "EMWS eminwon-web" 계열(emwsWebList.do/View.do). 사이트가 레거시 암호화
# 스위트만 지원해(SSLV3_ALERT_HANDSHAKE_FAILURE) SECLEVEL만 완화했다(사용자
# 제공 URL, 2026-09-26 실측 확인).
ANYANG = City(
    province="경기도",
    city="안양시",
    base_url="https://www.anyang.go.kr/main/emwsWebList.do",
    boards=[{"name": "고시공고", "key": "4101", "search_gosi_se": "01,03,04"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="안양시"),
    adapter="emws_board",
)

# ============================================================ 용인특례시
# 같은 NTIS eMinwon 계열(ntis_ofr 어댑터). 화면(yiNwStable02_01.jsp)은 껍데기고
# 실제 목록은 iframe으로 eminwon.yongin.go.kr을 그대로 끼워 넣은 것이다(실측
# 확인, 2026-09-26). 사이트 자체가 레거시 암호화 스위트만 지원해 ntis_ofr.py의
# _LegacyTLSAdapter가 그대로 적용된다.
YONGIN = City(
    province="경기도",
    city="용인특례시",
    base_url=(
        "https://eminwon.yongin.go.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp?not_ancmt_se_code=01,04"
        "&homepage_pbs_yn=Y&subCheck=Y&ofr_pageSize=10&jndinm=OfrNotAncmtEJB&context=NTIS&list_gubun=&epcCheck=Y"
    ),
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="용인특례시"),
    adapter="ntis_ofr",
)

# ============================================================ 의왕시
# 같은 NTIS eMinwon 계열(ntis_ofr 어댑터). 화면(UWKORINFO0701)은 껍데기고 실제
# 목록은 iframe으로 eminwon.uiwang.go.kr을 그대로 끼워 넣은 것이다(실측 확인,
# 2026-09-26).
UIWANG = City(
    province="경기도",
    city="의왕시",
    base_url=(
        "https://eminwon.uiwang.go.kr/emwp/jsp/ofr/OfrNotAncmtL.jsp?not_ancmt_se_code=01,04,06"
        "&homepage_pbs_yn=Y&subCheck=Y&ofr_pageSize=10&jndinm=OfrNotAncmtEJB&context=NTIS&list_gubun=A"
    ),
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="의왕시"),
    adapter="ntis_ofr",
)

# ============================================================ 파주시 — openworks_board 어댑터
# "OpenWorks" CMS(BD_board.list.do/view.do, jsView() JS 이동) — 어댑터 상단 설명 참고.
# 사용자 제공 URL, 2026-09-27 실측 확인.
PAJU = City(
    province="경기도",
    city="파주시",
    base_url="https://www.paju.go.kr/user/board/BD_board.list.do",
    boards=[{"name": "고시공고", "bbs_cd": 1022, "q_ctg_cd": 4063}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="파주시"),
    adapter="openworks_board",
)

# ============================================================ 고양시 — ntis_ofr 어댑터
# eminwon.goyang.go.kr(표준 NTIS eMinwon 계열)에 직접 접속된다(사용자 화면 www/link/
# BD_notice.do는 파라미터 없이 접속하면 500 에러였지만, eminwon 서브도메인은 그대로
# 정상 동작). 실측 확인, 2026-09-28.
GOYANG = City(
    province="경기도",
    city="고양시",
    base_url="https://eminwon.goyang.go.kr/emwp/jsp/ofr/OfrNotAncmtL.jsp",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="고양시"),
    adapter="ntis_ofr",
)

# ============================================================ 광명시 — gwangmyeong_board 어댑터
# "openworks4" 계열(BD_selectNftcBbsList.do/Detail.do, opDetail() JS 이동). 첨부파일이
# 상세 페이지 인라인 스크립트에 fileList.push({...}) JSON으로 박혀 있는 독특한
# 패턴이라 전용 어댑터를 만들었다. 사용자 제공 URL, 2026-09-28 실측 확인.
GWANGMYEONG = City(
    province="경기도",
    city="광명시",
    base_url="https://www.gm.go.kr/pt/user/nftcBbs/BD_selectNftcBbsList.do",
    boards=[{"name": "고시공고", "nftc_bbs_code": 1001}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="광명시"),
    adapter="gwangmyeong_board",
)

# ============================================================ 광주시 — saeol_gosi 어댑터
# 새올(saeol/gosi/list.do) 계열, 다른 saeol_gosi 지자체와 완전히 동일한 마크업이라
# 코드 수정 없이 그대로 등록된다. 사용자 제공 URL, 2026-09-28 실측 확인.
GYEONGGI_GWANGJU = City(
    province="경기도",
    city="광주시",
    base_url="https://www.gjcity.go.kr/portal/saeol/gosi/list.do?mId=0202010000",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="광주시"),
    adapter="saeol_gosi",
)

# ============================================================ 김포시 — eminwon_list 어댑터
# 목록은 p-table 스킨(eminwon_list.py 기본 fallback), 첨부는 <a class="ntfc_file_down"
# data-user-file-nm=/data-sys-file-nm=/data-file-path=> 속성 패턴이라 어댑터에
# 이 패턴을 추가했다. 사용자 제공 URL, 2026-09-28 실측 확인.
GIMPO = City(
    province="경기도",
    city="김포시",
    base_url="https://www.gimpo.go.kr/portal/ntfcPblancList.do?key=1004&cate_cd=1&searchCnd=40900000000",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="김포시"),
    adapter="eminwon_list",
)

# ============================================================ 부천시 — eminwon_list 어댑터
# 목록 href가 이미 완성된 GET 링크, 첨부는 표준 goDownLoad(...) 패턴이라 코드 수정
# 없이 그대로 등록된다(페이지네이션 파라미터 currentpage만 어댑터에 추가). 사용자
# 제공 URL, 2026-09-28 실측 확인.
BUCHEON = City(
    province="경기도",
    city="부천시",
    base_url="https://www.bucheon.go.kr/site/program/gosi/list?menuid=148002003001",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="부천시"),
    adapter="eminwon_list",
)

# ============================================================ 성남시 — seongnam_board 어댑터
# 목록 제목 칸이 onclick="f_view('<id>')"뿐이라 그 실제 구현(/pm010301/<id> GET)을
# 직접 조립하는 전용 어댑터를 만들었다. 첨부는 eminwon_list.py의 goDownLoad 처리를
# 그대로 재사용(이벤트 인자가 하나 더 있는 변형이라 그 정규식을 확장했다). 목록
# 사이트·첨부 다운로드 서버 둘 다 레거시 TLS 암호화 스위트 대응이 필요했다. 사용자
# 제공 URL, 2026-09-28 실측 확인.
SEONGNAM = City(
    province="경기도",
    city="성남시",
    base_url="https://www.seongnam.go.kr/pm010301",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="성남시"),
    adapter="seongnam_board",
)

# ============================================================ 수원시 — eminwon_list 어댑터
# 새올(saeallOfr/BD_ofrList.do) 계열이지만 목록 마크업 자체가 p-table/p-subject
# 스킨이라 eminwon_list.py의 기본 fallback으로 코드 수정 없이 그대로 등록된다.
# 사용자 제공 URL, 2026-09-28 실측 확인.
SUWON = City(
    province="경기도",
    city="수원시",
    base_url="https://www.suwon.go.kr/web/saeallOfr/BD_ofrList.do",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="수원시"),
    adapter="eminwon_list",
)

# ============================================================ 화성시 — ntis_ofr 어댑터
# eminwon.hscity.go.kr(표준 NTIS eMinwon 계열)에 직접 접속된다(고양시와 같은 패턴).
# 사용자 화면 www/link/BD_notice.do는 파라미터 없이는 빈 응답이었다. 실측 확인,
# 2026-09-28.
HWASEONG = City(
    province="경기도",
    city="화성시",
    base_url="https://eminwon.hscity.go.kr/emwp/jsp/ofr/OfrNotAncmtL.jsp",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="화성시"),
    adapter="ntis_ofr",
)

CITIES = [
    YANGPYEONG, ICHEON, GWACHEON, OSAN, PYEONGTAEK, ANSEONG, POCHEON,
    YEONCHEON, HANAM, DONGDUCHEON, GURI, GAPYEONG, UIJEONGBU, GYEONGGI_DO, SIHEUNG,
    YEOJU, GUNPO, YANGJU, NAMYANGJU, ANSAN, ANYANG, YONGIN, UIWANG, PAJU,
    GOYANG, GWANGMYEONG, GYEONGGI_GWANGJU, GIMPO, BUCHEON, SEONGNAM, SUWON, HWASEONG,
]
