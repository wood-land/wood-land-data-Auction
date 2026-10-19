"""
cities/chungnam.py — 충청남도 지자체 고시공고 게시판 목록.

새 지자체를 추가할 때는 먼저 해당 사이트의 게시판 구조를 직접 탐색해 확인한 뒤
City(...)를 하나 더 추가한다 (임의 추측 금지, law.md 3-2 참고).
"""

from core.board_crawler import City
from core.jose_extractor import Regions

from cities._shared import DEFAULT_BLACKLIST, DEFAULT_KEYWORDS

PROVINCE_NAME = "충남"

# ============================================================ 보령시
# eMinwon 고시공고 목록 (eminwon_list 어댑터, 2026-09-25 실측 확인 —
# 첨부파일이 <form name="nnn"> POST 방식, 토큰이 암호화돼 있어 링크 텍스트를 파일명으로 씀)
BORYEONG = City(
    province="충청남도",
    city="보령시",
    base_url="https://www.brcn.go.kr/prog/eminwon/kor/BB/sub04_03_01/list.do",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청남도", sigun_name="보령시"),
    adapter="eminwon_list",
)

# ============================================================ 홍성군
# prog/saeolGosi 계열 (gosi_prog_skin 어댑터, 2026-09-25 실측 확인).
HONGSEONG = City(
    province="충청남도",
    city="홍성군",
    base_url="https://www.hongseong.go.kr/prog/saeolGosi/kor/sub03_0204/GOSI_ALL/list.do",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청남도", sigun_name="홍성군"),
    adapter="gosi_prog_skin",
)

# ============================================================ 서천군
# 같은 gosi_prog_skin 어댑터. 제목 칸이 <a data-not-ancmt-mgt-no="<id>"> 형태라
# 어댑터에 이 패턴도 추가했다.
SEOCHEON = City(
    province="충청남도",
    city="서천군",
    base_url="https://www.seocheon.go.kr/prog/saeolGosi/01/kor/sub04_06_01/list.do",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청남도", sigun_name="서천군"),
    adapter="gosi_prog_skin",
)

# ============================================================ 예산군
# 같은 gosi_prog_skin 어댑터. 제목 칸이 <button data-list-no="<id>"> 형태라
# 어댑터에 이 패턴도 추가했다.
YESAN = City(
    province="충청남도",
    city="예산군",
    base_url="https://www.yesan.go.kr/prog/saeolGosi/GOSI/kor/sub04_03_01/list.do",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청남도", sigun_name="예산군"),
    adapter="gosi_prog_skin",
)

# ============================================================ 충청남도청
# cnportal/province/province 게시판 (chungnam_do_board 어댑터, 2026-09-26 실측 확인).
# 뒷단은 인천광역시청과 같은 SAPGosiBizProcess.do(minwon.chungnam.go.kr)지만 화면
# 마크업이 달라 별도 어댑터를 썼다. 검색 폼이 날짜범위를 요구해 항상 "1년 전~오늘"을
# 실어 보낸다.
CHUNGNAM_DO = City(
    province="충청남도",
    city="충청남도청",
    base_url="https://www.chungnam.go.kr/cnportal/province/province/view.do",
    boards=[{"name": "고시공고", "menu_no": "500487"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청남도", sigun_name="홍성군"),
    adapter="chungnam_do_board",
)

# ============================================================ 태안군 — NTIS eMinwon 계열 (ntis_ofr 어댑터)
# 사용자 제공 URL, 2026-09-26 실측 확인.
TAEAN = City(
    province="충청남도",
    city="태안군",
    base_url="https://eminwon.taean.go.kr/emwp/jsp/ofr/OfrNotAncmtL.jsp",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청남도", sigun_name="태안군"),
    adapter="ntis_ofr",
)

# ============================================================ 청양군 — NTIS eMinwon 계열 (ntis_ofr 어댑터)
CHEONGYANG = City(
    province="충청남도",
    city="청양군",
    base_url="https://eminwon.cheongyang.go.kr/emwp/jsp/ofr/OfrNotAncmtL.jsp",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청남도", sigun_name="청양군"),
    adapter="ntis_ofr",
)

# ============================================================ 공주시 — gosi_prog_skin 어댑터
# 사용자 제공 URL, 2026-09-26 실측 확인.
GONGJU = City(
    province="충청남도",
    city="공주시",
    base_url="https://www.gongju.go.kr/prog/saeolGosi/GOSI_03/sub04_03_03/list.do",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청남도", sigun_name="공주시"),
    adapter="gosi_prog_skin",
)

# ============================================================ 당진시 — publicnotice_prog 어댑터
# 사용자 제공 URL, 2026-09-26 실측 확인.
DANGJIN = City(
    province="충청남도",
    city="당진시",
    base_url="https://www.dangjin.go.kr/prog/publicNotice/kor/sub03_02_01_01/list.do",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청남도", sigun_name="당진시"),
    adapter="publicnotice_prog",
)

# ============================================================ 계룡시 — gosi_gotopage_board 어댑터
# 사용자 제공 URL, 2026-09-27 실측 확인.
GYERYONG = City(
    province="충청남도",
    city="계룡시",
    base_url="https://www.gyeryong.go.kr/kr/html/sub03/030102.html",
    boards=[{"name": "고시/공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청남도", sigun_name="계룡시"),
    adapter="gosi_gotopage_board",
)

# ============================================================ 부여군 — gosi_gotopage_board 어댑터
# 계룡시와 같은 벤더(?mode=V&mng_no=, ?GotoPage=)지만 첨부파일 다운로드 방식은
# fn_saeol_downFile(...) POST라 어댑터가 두 방식 모두 지원한다. 사용자 제공 URL,
# 2026-09-27 실측 확인.
BUYEO = City(
    province="충청남도",
    city="부여군",
    base_url="https://www.buyeo.go.kr/html/kr/news/news_040202.html",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청남도", sigun_name="부여군"),
    adapter="gosi_gotopage_board",
)

# ============================================================ 논산시 — NTIS eMinwon 계열 (ntis_ofr 어댑터)
# www.nonsan.go.kr/kor/html/sub03/03010201.html은 안내 페이지고, 그 안의
# <iframe src="//eminwon.nonsan21.net/emwp/jsp/ofr/OfrNotAncmtLSub.jsp?...">가
# 실제 목록이다(완주군·진천군·괴산군과 같은 iframe 트릭, 도메인이 nonsan21.net으로
# 다른 점만 특이). 실측 확인, 2026-09-27.
NONSAN = City(
    province="충청남도",
    city="논산시",
    base_url="https://eminwon.nonsan21.net/emwp/jsp/ofr/OfrNotAncmtLSub.jsp?not_ancmt_se_code=01,05,04,06",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청남도", sigun_name="논산시"),
    adapter="ntis_ofr",
)

# ============================================================ 서산시 — ntis_ofr_local_view 어댑터
# www.seosan.go.kr/www/contents.do?key=1258는 안내 페이지고, 그 안의
# <iframe src="/common/program/eminwonView.jsp?...method=selectListOfrNotAncmt...">가
# 실제 목록이다. 다른 지자체(완주군 등)처럼 eminwon.*.go.kr로 직접 iframe이
# 뜨는 게 아니라 자기 사이트가 로컬 JSP로 NTIS 백엔드를 대신 GET 프록시해 주는
# 변형이라 새 어댑터가 필요했다(ntis_ofr.py의 목록 파싱/폼 필드 읽기는 재사용).
# 실측 확인, 2026-09-27.
SEOSAN = City(
    province="충청남도",
    city="서산시",
    base_url=(
        "https://www.seosan.go.kr/common/program/eminwonView.jsp"
        "?jndinm=OfrNotAncmtEJB&context=NTIS&method=selectListOfrNotAncmt"
        "&methodnm=selectListOfrNotAncmtHomepage&homepage_pbs_yn=Y&subCheck=Y"
        "&ofr_pageSize=10&not_ancmt_se_code=01,04,06"
    ),
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청남도", sigun_name="서산시"),
    adapter="ntis_ofr_local_view",
)

# ============================================================ 아산시 — eminwon_list 어댑터
# 목록 테이블에 td.title 칸이 두 개다(공고번호 칸도 "title", 진짜 제목 칸은
# "title alignLeft") — eminwon_list.py의 제목 칸 판별을 클래스 개수 기준으로
# 일반화해 고쳤다. 페이지네이션도 화면엔 없지만 실제로는 대문자 "PageNo"
# (소문자 pageNo는 서버가 무시하고 항상 1페이지 반환)라 이것도 추가했다.
# 첨부는 <form name="nnn"> POST(eminwon.asan.go.kr, 보령시와 같은 패턴). 사용자
# 제공 URL, 2026-09-27 실측 확인.
ASAN = City(
    province="충청남도",
    city="아산시",
    base_url="https://asan.go.kr/main/cms/?no=257",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청남도", sigun_name="아산시"),
    adapter="eminwon_list",
)

# ============================================================ 천안시 — gosi_prog_skin 어댑터
# 같은 "prog/saeolGosi/.../list.do" 계열이지만 목록 항목이 onclick/data 속성 없이
# <td class="subject"><a href=".../view.do?notAncmtMgtNo=<id>">인 새 변형이라
# 어댑터에 5번째 판별 방식을 추가했다(페이지 안의 fn_search_view() 정의는 실제로는
# 어디서도 호출되지 않는 죽은 코드였다 — 실측 확인, 2026-09-28). 첨부는 fileForm의
# action이 이미 채워져 있어(대전 중구·홍성군과 같은 방식) 기존 로직 그대로 처리된다.
CHEONAN = City(
    province="충청남도",
    city="천안시",
    base_url="https://www.cheonan.go.kr/prog/saeolGosi/GOSI/kor/sub02_02_01/list.do",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청남도", sigun_name="천안시"),
    adapter="gosi_prog_skin",
)

# ============================================================ 금산군 — gosi_gotopage_board 어댑터
# 계룡시·부여군과 같은 벤더(?mode=V&mng_no=, ?GotoPage=)지만 목록에 등록일 칸이
# 따로 없이 "게재기간"(YYYY-MM-DD~YYYY-MM-DD) 범위만 있어 시작일을 등록일 대신
# 쓰도록 어댑터에 추가했다. 첨부도 새 방식(<div class="ui bbs--view--file">
# 안의 완성된 GET 링크, 링크 텍스트가 순수 파일명)이라 함께 추가했다(실측 확인,
# 2026-09-28).
GEUMSAN = City(
    province="충청남도",
    city="금산군",
    base_url="https://www.geumsan.go.kr/kr/html/sub03/030302.html",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청남도", sigun_name="금산군"),
    adapter="gosi_gotopage_board",
)

CITIES = [
    BORYEONG, HONGSEONG, SEOCHEON, YESAN, CHUNGNAM_DO, TAEAN, CHEONGYANG, GONGJU, DANGJIN,
    GYERYONG, BUYEO, NONSAN, SEOSAN, ASAN, CHEONAN, GEUMSAN,
]
