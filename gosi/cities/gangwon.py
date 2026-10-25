"""
cities/gangwon.py — 강원도 지자체 고시공고 게시판 목록.

새 지자체를 추가할 때는 먼저 해당 사이트의 게시판 구조(목록/상세/첨부 URL 패턴)를
직접 탐색해 확인한 뒤 City(...)를 하나 더 추가한다 (임의 추측 금지, law.md 3-2 참고).
같은 selectBbsNttList.do 구조(std_ezweb 어댑터)를 쓰는지도 실측으로 확인해야 한다.
"""

from core.board_crawler import City
from core.jose_extractor import Regions

from cities._shared import DEFAULT_BLACKLIST, DEFAULT_KEYWORDS

PROVINCE_NAME = "강원"

# ============================================================ 원주시
# 대상 게시판: bbsNo=140,key=216(공고) / bbsNo=141,key=217(고시)
# 화이트리스트에 걸려도 토지보상과 무관해 제외할 제목 키워드: 기본 목록 + 원주시에서 따로 확인된 오탐.
# (예전에는 원주시만 2개짜리 자체 목록을 써서 기본 목록의 '기술제안' 등이 적용되지 않았다 - 2026-10-26 기술제안서 공고가 수집된 원인)
_WONJU_BLACKLIST = list(DEFAULT_BLACKLIST)

# 원주시 법정동/법정리 (토지조서 소재지 검증용). 출처: 원주시청 읍면동안내 '법정리' 표 +
# 위키백과 '원주시의 행정 구역'. 빠졌거나 새로 생긴 지명은 wonju_regions.txt 에 한 줄씩
# 추가하면 된다 (core.jose_extractor.Regions.load 참고).
_WONJU_EUPMYEON_RI = {
    "문막읍": "문막리 포진리 궁촌리 비두리 후용리 반계리 취병리 건등리 동화리 대둔리",
    "소초면": "장양리 흥양리 수암리 평장리 의관리 둔둔리 교항리 학곡리",
    "호저면": "주산리 만종리 무장리 옥산리 대덕리 고산리 광격리 산현리 매호리 용곡리",
    "지정면": "간현리 판대리 안창리 보통리 가곡리 신평리 월송리",
    "부론면": "법천리 흥호리 손곡리 노림리 정산리 단강리",
    "귀래면": "운남리 운계리 귀래리 주포리 용암리",
    "흥업면": "흥업리 사제리 대안리 매지리",
    "판부면": "금대리 서곡리 신촌리",
    "신림면": "신림리 금창리 구학리 용암리 성남리 황둔리 송계리",
}
_WONJU_LEGAL_DONGS = (
    "중앙동 평원동 원동 인동 개운동 명륜동 단구동 일산동 학성동 단계동 우산동 가현동 "
    "태장동 봉산동 행구동 무실동 반곡동 관설동"
)
_WONJU_ADMIN_DONGS = "원인동 명륜1동 명륜2동 태장1동 태장2동 반곡관설동"  # 행정동 표기(법정동 아님, 주소 검증 필요)
# 리/동으로 끝나지만 지명이 아닌 흔한 낱말 (한 글자 리/동 규칙에서 걸러냄)
_WONJU_NOT_REGION_WORDS = """관리 처리 수리 정리 지리 원리 논리 심리 물리 도리 무리 조리 분리 소리 거리 마리 우리 자리 고리 머리 다리
    이동 활동 자동 운동 행동 작동 진동 충동 감동 노동 수동 전동 개동 기동 변동 주동 발동 가동 실동 연동 상동 하동"""

WONJU = City(
    province="강원도",
    city="원주시",
    base_url="https://www.wonju.go.kr/www/",
    boards=[
        {"name": "공고", "bbsNo": 140, "key": 216},
        {"name": "고시", "bbsNo": 141, "key": 217},
    ],
    keywords=DEFAULT_KEYWORDS,
    blacklist=_WONJU_BLACKLIST,
    regions=Regions(
        sido_name="강원도",
        sigun_name="원주시",
        eupmyeon_ri=_WONJU_EUPMYEON_RI,
        legal_dongs=_WONJU_LEGAL_DONGS,
        admin_dongs=_WONJU_ADMIN_DONGS,
        not_region_words=_WONJU_NOT_REGION_WORDS,
    ),
)

# ============================================================ 횡성군
# 대상 게시판: bbsNo=65,key=821 (보상맵 수집소스 시트, 2026-09-25 실측 확인 — p-table 스킨)
# 법정동/법정리 목록 미확보: 지금은 시/군 이름만으로 검증하고(소재지 대부분 CHECK로
# 표시됨), 데이터가 쌓이면 원주시처럼 eupmyeon_ri/legal_dongs를 채운다(살아있는 목록).
HOENGSEONG = City(
    province="강원도",
    city="횡성군",
    base_url="https://www.hsg.go.kr/www/",
    boards=[{"name": "고시공고", "bbsNo": 65, "key": 821}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="강원도", sigun_name="횡성군"),
)

# ============================================================ 영월군
# 대상 게시판: bbsNo=17,key=273 (보상맵 수집소스 시트, 2026-09-25 실측 확인 — bbs_default 스킨)
YEONGWOL = City(
    province="강원도",
    city="영월군",
    base_url="https://www.yw.go.kr/www/",
    boards=[{"name": "고시공고", "bbsNo": 17, "key": 273}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="강원도", sigun_name="영월군"),
)

# ============================================================ 태백시
# 대상 게시판: bbsNo=25,key=352 (보상맵 수집소스 시트, 2026-09-25 실측 확인 — bbs_default 스킨)
TAEBAEK = City(
    province="강원도",
    city="태백시",
    base_url="https://www.taebaek.go.kr/www/",
    boards=[{"name": "고시공고", "bbsNo": 25, "key": 352}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="강원도", sigun_name="태백시"),
)

# ============================================================ 홍천군
# eMinwon 고시공고 목록 (eminwon_list 어댑터, 2026-09-25 실측 확인)
HONGCHEON = City(
    province="강원도",
    city="홍천군",
    base_url="https://www.hongcheon.go.kr/www/selectEminwonList.do?key=278",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="강원도", sigun_name="홍천군"),
    adapter="eminwon_list",
)

# ============================================================ 강원도청
# portal/bulletin/notification 게시판 (gwd_bulletin 어댑터, 2026-09-26 실측 확인).
# 화면은 <form name="mForm"> JS 제출이지만 method가 GET이라 쿼리스트링 그대로 연다.
GANGWON_DO = City(
    province="강원도",
    city="강원도청",
    base_url="https://state.gwd.go.kr/portal/bulletin/notification",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="강원도", sigun_name="춘천시"),
    adapter="gwd_bulletin",
)

# ============================================================ 인제군
# 강원도청과 같은 "skinTb-data-resList" 플랫폼(gwd_bulletin 어댑터). 서버가 중간
# 인증서를 안 보내(unable to get local issuer certificate) 어댑터에 그 인증서를
# 추가해 해결했다(2026-09-26 실측 확인 — 검증을 끈 게 아니라 완성한 것).
INJE = City(
    province="강원도",
    city="인제군",
    base_url="https://www.inje.go.kr/portal/adm/bulletin",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="강원도", sigun_name="인제군"),
    adapter="gwd_bulletin",
)

# ============================================================ 양구군 — yanggu_board 어댑터
# 사용자 제공 URL, 2026-09-26 실측 확인.
YANGGU = City(
    province="강원도",
    city="양구군",
    base_url="https://www.yanggu.go.kr/user_sub",
    boards=[{"name": "고시공고", "mu_idx": "226"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="강원도", sigun_name="양구군"),
    adapter="yanggu_board",
)

# ============================================================ 평창군
# 강원도청과 같은 "skinTb-data-resList" 플랫폼(gwd_bulletin 어댑터). 제목 링크가
# onclick="goPage(this.href)" 형태로 href 자체가 이미 완성된 링크라 어댑터에
# 그 경우도 처리하도록 추가했다(2026-09-26 실측 확인).
PYEONGCHANG = City(
    province="강원도",
    city="평창군",
    base_url="https://www.pc.go.kr/portal/government/government-notification",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="강원도", sigun_name="평창군"),
    adapter="gwd_bulletin",
)

# ============================================================ 춘천시 — chuncheon_board 어댑터
# 화면은 Vue SPA라 서버 HTML에 목록이 없다 — 브라우저 네트워크 탭에서 실제
# JSON API(_chuncheon/noticeList.do/noticeView.do)를 찾았다(2026-09-26 실측 확인).
CHUNCHEON = City(
    province="강원도",
    city="춘천시",
    base_url="https://www.chuncheon.go.kr",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="강원도", sigun_name="춘천시"),
    adapter="chuncheon_board",
)

# ============================================================ 동해시 — std_ezweb 어댑터
# 사이트가 레거시 암호화 스위트만 지원해(SSLV3_ALERT_HANDSHAKE_FAILURE)
# std_ezweb.py의 _LegacyTLSAdapter가 적용된다(사용자 제공 URL, 2026-09-26 실측 확인).
DONGHAE = City(
    province="강원도",
    city="동해시",
    base_url="https://dh.go.kr/www/",
    boards=[{"name": "고시공고", "bbsNo": 87, "key": 478}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="강원도", sigun_name="동해시"),
)

# ============================================================ 철원군 — std_ezweb 어댑터
# 중간 인증서(RapidSSL TLS RSA CA G1)가 빠져 있었다 — 발급기관 공개 배포처에서
# 받아 std_ezweb.py에 내장해 해결했다(사용자 제공 URL, 2026-09-26 실측 확인).
# 제목에 "핫이슈" 배지가 섞여 나와 std_ezweb.py의 제목 추출을 일반화했다.
CHEORWON = City(
    province="강원도",
    city="철원군",
    base_url="https://www.cwg.go.kr/www/",
    boards=[{"name": "고시공고", "bbsNo": 25, "key": 1226}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="강원도", sigun_name="철원군"),
)

# ============================================================ 정선군
# 같은 NTIS eMinwon 계열(ntis_ofr 어댑터). iframe 트릭(실측 확인, 2026-09-26).
JEONGSEON = City(
    province="강원도",
    city="정선군",
    base_url="https://eminwon.jeongseon.go.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp?not_ancmt_se_code=01,04,05,06",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="강원도", sigun_name="정선군"),
    adapter="ntis_ofr",
)

# ============================================================ 강릉시 — eminwon_list 어댑터
# selectGosiNttList.do/selectGosiNttView.do(eminwon_list.py가 지원하는 모듈 이름
# 중 하나). www.gn.go.kr은 동해시와 같은 레거시 암호화 스위트 문제가 있어
# eminwon_list.py에 SECLEVEL 완화를 추가했다. 첨부 서버(eminwon.gangneung.go.kr)는
# 정상 TLS + 완성된 FileDownNew.jsp GET 링크라 별도 조치 불필요(사용자 제공 URL,
# 2026-09-27 실측 확인).
GANGNEUNG = City(
    province="강원도",
    city="강릉시",
    base_url="https://www.gn.go.kr/www/selectGosiNttList.do?key=263&searchGosiSe=01,04,06",
    boards=[{"name": "고시/공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="강원도", sigun_name="강릉시"),
    adapter="eminwon_list",
)

# ============================================================ 속초시 — gwd_bulletin 어댑터
# 강원도청/인제군과 같은 "skinTb-data-resList" 플랫폼이지만 목록 항목이 onclick=
# goPage(...)가 아니라 href="#nolink" + data-key="<id>"이고, JS가 hidden 필드
# notAncmtMgtNo로 옮겨 폼 제출한다 — 그 필드명 그대로 쿼리스트링을 붙여도 동일하게
# 열린다. 첨부도 강원도청과 달리 eminwon.sokcho.go.kr의 FileDown.jsp 완성된 GET
# 링크다. 서버가 인제군과 같은 중간 인증서(Sectigo ... CA DV R36)를 안 보내 같은
# 우회를 적용했다(실측 확인, 2026-09-28).
SOKCHO = City(
    province="강원도",
    city="속초시",
    base_url="https://www.sokcho.go.kr/sc/portal/sokchonews/notification",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="강원도", sigun_name="속초시"),
    adapter="gwd_bulletin",
)

# ============================================================ 삼척시 — haman_web_board 어댑터
# 함안군과 같은 ul.lst1>li.li1 마크업이지만 id 파라미터는 mgtNo=다(haman_web_board.py의
# "amode=view" 일반화로 흡수됨). 첨부는 /DownloadEx.do?url=<urlencode(eminwon
# FileDown.jsp)>(창원시와 같은 자체 프록시)라 href에 "FileDown" 문자열이 그대로
# 남아 eminwon_list.py의 기존 매칭에 걸리고, 파일명은 링크 텍스트로 대체된다(실측
# 확인, 2026-09-28).
SAMCHEOK = City(
    province="강원도",
    city="삼척시",
    base_url="https://www.samcheok.go.kr/media/00084/00095.web",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="강원도", sigun_name="삼척시"),
    adapter="haman_web_board",
)

# ============================================================ 화천군 — ntis_ofr 어댑터
# 도메인이 "ihc.go.kr"이라 다른 지자체와 이름이 안 맞지만(화천군 공식 도메인,
# 검색으로 확인) 대표누리집의 고시/공고 페이지가 감싼 iframe이 가리키는
# eminwon.ihc.go.kr NTIS 백엔드를 그대로 쓴다(실측 확인, 2026-09-28).
HWACHEON = City(
    province="강원도",
    city="화천군",
    base_url="https://eminwon.ihc.go.kr/emwp/jsp/ofr/OfrNotAncmtL.jsp?not_ancmt_se_code=01,04",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="강원도", sigun_name="화천군"),
    adapter="ntis_ofr",
)

# ============================================================ 고성군(강원) — gosi_prog_skin 어댑터
# 충남 홍성군 등과 같은 "prog/saeolGosi/.../list.do" 계열, 목록 마크업은 대전
# 서구와 같은 <td data-key-no="<id>"> 변형이다. 서버가 최신 암호화 스위트를
# 지원하지 않아(SSLV3_ALERT_HANDSHAKE_FAILURE) SECLEVEL=1 완화를 추가했다(실측
# 확인, 2026-09-28). 경남 고성군과 이름이 같아 사이트/City.city 모두 "(강원)"을
# 붙이지 않고 도(province)로 구분한다.
GOSEONG_GW = City(
    province="강원도",
    city="고성군",
    base_url="https://www.gwgs.go.kr/prog/saeolGosi/GOSI/kor/sub04_030401/list.do",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="강원도", sigun_name="고성군"),
    adapter="gosi_prog_skin",
)

# ============================================================ 양양군 — ntis_ofr 어댑터
# 대표누리집 고시/공고 화면 안의 iframe(레이블은 "이전 자료"지만 실제로는 se_code
# 01,04,05,06을 모두 포함한 전체 목록)이 가리키는 eminwon.yangyang.go.kr NTIS
# 백엔드를 그대로 쓴다(실측 확인, 2026-09-28).
YANGYANG = City(
    province="강원도",
    city="양양군",
    base_url="https://eminwon.yangyang.go.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp?not_ancmt_se_code=01,04,05,06",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="강원도", sigun_name="양양군"),
    adapter="ntis_ofr",
)

CITIES = [
    WONJU, HOENGSEONG, YEONGWOL, TAEBAEK, HONGCHEON, GANGWON_DO, INJE, YANGGU, PYEONGCHANG,
    CHUNCHEON, DONGHAE, CHEORWON, JEONGSEON, GANGNEUNG,
    SOKCHO, SAMCHEOK, HWACHEON, GOSEONG_GW, YANGYANG,
]
