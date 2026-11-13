"""
cities/incheon.py — 인천광역시 자치구/군 고시공고 게시판 목록.

새 지자체를 추가할 때는 먼저 해당 사이트의 게시판 구조를 직접 탐색해 확인한 뒤
City(...)를 하나 더 추가한다 (임의 추측 금지, law.md 3-2 참고).
"""

from core.board_crawler import City
from core.jose_extractor import Regions

from cities._shared import DEFAULT_BLACKLIST, DEFAULT_KEYWORDS

PROVINCE_NAME = "인천"

# ============================================================ 강화군
# open_content/main/eminwon 계열 (eminwon_list 어댑터, 2026-09-25 실측 확인).
# 제목/공고번호 두 칸 모두 <a>가 걸려 있어(중복 링크), eminwon_list.py의 제목 칸
# 판별을 "마지막 <a> 칸"으로 일반화했다.
GANGHWA = City(
    province="인천광역시",
    city="강화군",
    base_url="https://www.ganghwa.go.kr/open_content/main/ganghwa/news/announce.jsp",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="인천광역시", sigun_name="강화군"),
    adapter="eminwon_list",
)

ONGJIN = City(
    province="인천광역시",
    city="옹진군",
    base_url="https://www.ongjin.go.kr/open_content/main/community/board/announce.jsp",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="인천광역시", sigun_name="옹진군"),
    adapter="eminwon_list",
)

# ============================================================ 제물포구
# 같은 계열이지만 사이트 자체 인증서 체인이 깨져 있었다(www.icdonggu.go.kr) —
# 빠진 중간 인증서를 발급기관 공개 배포처에서 받아 eminwon_list.py의
# prepare_session()에 내장해 해결했다(검증을 끈 게 아니라 완성한 것).
JEMULPO = City(
    province="인천광역시",
    city="제물포구",
    base_url="https://www.icdonggu.go.kr/main/information/news/announce.jsp",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="인천광역시", sigun_name="제물포구"),
    adapter="eminwon_list",
)

# ============================================================ 인천광역시청
# SAPGosiBizProcess.do 계열 (sap_gosi 어댑터, 2026-09-26 실측 확인). 화면은
# <form name="myform"> JS 제출(viewData())이지만 action 문자열 자체가 이미 완성된
# GET 쿼리스트링이라 그대로 GET한다.
INCHEON_CITY = City(
    province="인천광역시",
    city="인천광역시청",
    base_url="https://announce.incheon.go.kr/citynet/jsp/sap/SAPGosiBizProcess.do",
    boards=[{"name": "고시공고", "sido": "ic"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="인천광역시", sigun_name="남동구"),
    adapter="sap_gosi",
)

# ============================================================ 계양구
# eminwon_list 어댑터. 같은 open_content/main/.../*.jsp 계열(강화군·옹진군과 유사).
GYEYANG = City(
    province="인천광역시",
    city="계양구",
    base_url="https://www.gyeyang.go.kr/open_content/main/open_info/admin/gosi.jsp",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="인천광역시", sigun_name="계양구"),
    adapter="eminwon_list",
)

# ============================================================ 남동구
# main/eminwon/eminwonAnnounceList.do 계열 (namdong_board 어댑터,
# 2026-09-26 실측 확인). <table>이 아니라 <ul class="etcList">이고, 첨부의
# user_file_nm 쿼리파라미터가 암호화된 값이라 링크 텍스트를 파일명으로 쓴다.
NAMDONG = City(
    province="인천광역시",
    city="남동구",
    base_url="https://www.namdong.go.kr/main/eminwon/eminwonAnnounceList.do",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="인천광역시", sigun_name="남동구"),
    adapter="namdong_board",
)

# ============================================================ 연수구 — NTIS eMinwon 계열 (ntis_ofr 어댑터)
# main/community/notify/gosi.asp는 안내 페이지고, 그 안의
# <iframe src="https://eminwon.yeonsu.go.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp?...">가
# 실제 목록이다. 다른 지자체(정읍시 등)의 onclick="searchDetail(...)"와 달리
# 목록 행의 <a href>가 이미 완성된 OfrAction.do GET 링크라(실측 확인, 2026-09-27)
# ntis_ofr.py에 이 패턴(not_ancmt_mgt_no= 쿼리파라미터로 id 추출)을 추가했다.
# <form name="form1">이 아니라 <form name="form">인 변형(기장군과 같은 유형)이라
# fetch_attachments의 폼 이름 탐색도 list와 같은 순서로 일반화했다.
YEONSU = City(
    province="인천광역시",
    city="연수구",
    base_url="https://eminwon.yeonsu.go.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp?not_ancmt_se_code=01,02,03,04,06,07&list_gubun=",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="인천광역시", sigun_name="연수구"),
    adapter="ntis_ofr",
)

# ============================================================ 부평구 — NTIS eMinwon 계열 (ntis_ofr 어댑터)
# main/participation/news/announce.jsp는 JS(jQuery AJAX)로 목록을 그리는 페이지라
# 정적 HTML에 iframe/폼이 없었다 — 실제 데이터는 eminwon.icbp.go.kr의 표준 NTIS
# 백엔드(다른 iframe 트릭 지자체와 같은 시스템)에서 나온다는 것을 직접 접속해
# 확인했다. 실측 확인, 2026-09-27.
BUPYEONG = City(
    province="인천광역시",
    city="부평구",
    base_url="https://eminwon.icbp.go.kr/emwp/jsp/ofr/OfrNotAncmtL.jsp",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="인천광역시", sigun_name="부평구"),
    adapter="ntis_ofr",
)

CITIES = [GANGHWA, ONGJIN, JEMULPO, INCHEON_CITY, GYEYANG, NAMDONG, YEONSU, BUPYEONG]
