"""
cities/gyeongbuk.py — 경상북도 지자체 고시공고 게시판 목록.

새 지자체를 추가할 때는 먼저 해당 사이트의 게시판 구조를 직접 탐색해 확인한 뒤
City(...)를 하나 더 추가한다 (임의 추측 금지, law.md 3-2 참고).
"""

from core.board_crawler import City
from core.jose_extractor import Regions

from cities._shared import DEFAULT_BLACKLIST, DEFAULT_KEYWORDS

PROVINCE_NAME = "경북"

# ============================================================ 새올 계열 (saeol_gosi 어댑터)
# cms_adapters/saeol_gosi.py 상단 설명 참고 — 6곳 모두 같은 벤더 시스템으로 실측 확인(2026-09-25)
YEONGCHEON = City(
    province="경상북도",
    city="영천시",
    base_url="https://www.yc.go.kr/portal/saeol/gosi/list.do?mId=0301040000",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상북도", sigun_name="영천시"),
    adapter="saeol_gosi",
)

CHEONGDO = City(
    province="경상북도",
    city="청도군",
    base_url="https://www.cheongdo.go.kr/portal/saeol/gosi/list.do?mid=0301020000&token=1719885817202",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상북도", sigun_name="청도군"),
    adapter="saeol_gosi",
)

GUMI = City(
    province="경상북도",
    city="구미시",
    base_url="https://www.gumi.go.kr/portal/saeol/gosi/list.do?seCode=01&mid=0401040000&token=1719885899127",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상북도", sigun_name="구미시"),
    adapter="saeol_gosi",
)

GIMCHEON = City(
    province="경상북도",
    city="김천시",
    base_url="https://www.gc.go.kr/portal/saeol/gosi/list.do?seCode=01&mId=1202180100",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상북도", sigun_name="김천시"),
    adapter="saeol_gosi",
)

CHILGOK = City(
    province="경상북도",
    city="칠곡군",
    base_url="https://www.chilgok.go.kr/portal/saeol/gosi/list.do?mId=0201030000",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상북도", sigun_name="칠곡군"),
    adapter="saeol_gosi",
)

ANDONG = City(
    province="경상북도",
    city="안동시",
    base_url="https://www.andong.go.kr/portal/saeol/gosi/list.do?mId=0401020100",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상북도", sigun_name="안동시"),
    adapter="saeol_gosi",
)

# ============================================================ 경상북도청
# gb_do_board 어댑터 (2026-09-26 실측 확인). 상세 조회에 CSRF 토큰이 필요해
# 매번 목록 페이지를 다시 열어 토큰을 읽는다.
GYEONGBUK_DO = City(
    province="경상북도",
    city="경상북도청",
    base_url="https://www.gb.go.kr/page/10109/67.do",
    boards=[{"name": "고시공고", "board_mng_no": "71"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상북도", sigun_name="안동시"),
    adapter="gb_do_board",
)

# ============================================================ 봉화군 — 새올 계열 (saeol_gosi 어댑터)
# 사용자 제공 URL, 2026-09-26 실측 확인.
BONGHWA = City(
    province="경상북도",
    city="봉화군",
    base_url="https://www.bonghwa.go.kr/portal/saeol/gosi/list.do?seCode=01&mid=0201030000",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상북도", sigun_name="봉화군"),
    adapter="saeol_gosi",
)

# ============================================================ 울릉군 — mnu_uid_board 어댑터
# 사용자 제공 URL, 2026-09-26 실측 확인.
ULLEUNG = City(
    province="경상북도",
    city="울릉군",
    base_url="https://www.ulleung.go.kr/ko/page.do",
    boards=[{"name": "고시공고", "mnu_uid": "571"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상북도", sigun_name="울릉군"),
    adapter="mnu_uid_board",
)

# ============================================================ 영주시 — mnu_uid_board 어댑터
# 울릉군과 같은 백엔드지만 테이블 class가 달라(tbl_list) 어댑터에 selector를 추가했다.
YEONGJU = City(
    province="경상북도",
    city="영주시",
    base_url="https://www.yeongju.go.kr/open_content/main/page.do",
    boards=[{"name": "고시공고", "mnu_uid": "10619"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상북도", sigun_name="영주시"),
    adapter="mnu_uid_board",
)

# ============================================================ 문경시 — 새올 계열 (saeol_gosi 어댑터)
# 서버가 중간 인증서를 안 보내(의정부시와 똑같은 Sectigo 체인 누락) 그 인증서를
# 재사용해 해결했고, 제목 링크도 다른 지자체(boardView)와 달리 onclick="gosiView(...)"
# 라 어댑터에 그 패턴 해석도 추가했다(2026-09-26 실측 확인).
MUNGYEONG = City(
    province="경상북도",
    city="문경시",
    base_url="https://www.gbmg.go.kr/portal/saeol/gosi/list.do?mId=0301060000",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상북도", sigun_name="문경시"),
    adapter="saeol_gosi",
)

# ============================================================ 상주시 — sangju_board 어댑터
# 목록은 이 사이트 전용 마크업이지만 첨부 다운로드는 장성군과 같은 POST 방식이라
# eminwon_list.py의 download_attachment를 재사용했다(사용자 제공 URL, 2026-09-26 실측 확인).
SANGJU = City(
    province="경상북도",
    city="상주시",
    base_url="https://www.sangju.go.kr/page/10297/10606.tc",
    boards=[{"name": "고시공고", "mn": "10297", "not_ancmt_se_code": "01,02,03,04,05,07"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상북도", sigun_name="상주시"),
    adapter="sangju_board",
)

# ============================================================ 경산시 — edotxpress_board 어댑터
# "EDotXPress" CMS 계열, page.do?mnu_uid= 형태지만 울릉군·영주시(mnu_uid_board)와는
# 완전히 다른 마크업이다(사용자 제공 URL, 2026-09-26 실측 확인).
GYEONGSAN = City(
    province="경상북도",
    city="경산시",
    base_url="https://www.gbgs.go.kr/open_content/ko/page.do",
    boards=[{"name": "고시공고", "mnu_uid": "2160"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상북도", sigun_name="경산시"),
    adapter="edotxpress_board",
)

# ============================================================ 포항시 — saeol_gosi 어댑터
# 같은 "새올" 계열(다른 saeol_gosi 지자체와 동일한 data-action="view.do?..."
# 패턴). 사용자 제공 URL, 2026-09-26 실측 확인.
POHANG = City(
    province="경상북도",
    city="포항시",
    base_url="https://www.pohang.go.kr/portal/saeol/gosi/list.do?mid=0202010000",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상북도", sigun_name="포항시"),
    adapter="saeol_gosi",
)

# ============================================================ 고령군 — goryeong_board 어댑터
# 사용자 제공 URL, 2026-09-27 실측 확인.
GORYEONG = City(
    province="경상북도",
    city="고령군",
    base_url="https://www.goryeong.go.kr/kor/boardList.do",
    boards=[{"name": "고시공고", "idx": 154, "brd_id": 1023}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상북도", sigun_name="고령군"),
    adapter="goryeong_board",
)

# ============================================================ 군위군 — eminwon_list 어댑터
# CSV의 URL(mnu_uid=170)은 404였다 — 실제 고시공고 게시판은 홈페이지에서 직접
# 찾은 mnu_uid=666(실측 확인, 2026-09-27). 목록은 td.subject(class에 "title"이
# 없어 <a> 있는 칸으로 fallback), 첨부는 남원시와 같은 완성된 GET 링크
# (/programs/board/saeol/notice/download.do?file_seq=&not_ancmt_mgt_no=)라
# eminwon_list.py가 그대로 지원한다. 페이지네이션 파라미터 pageNo도 추가했다.
GUNWI = City(
    province="경상북도",
    city="군위군",
    base_url="https://www.gunwi.go.kr/ko/page.do?mnu_uid=666",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상북도", sigun_name="군위군"),
    adapter="eminwon_list",
)

# ============================================================ 경주시 — eminwon_list 어댑터
# 목록 마크업이 td.aL.title(class에 "title" 포함, <a> 있음)이라 eminwon_list.py의
# 1순위 selector가 바로 잡는다. 첨부는 표준 goDownLoad(...) 패턴. 사용자 제공 URL,
# 2026-09-28 실측 확인.
GYEONGJU = City(
    province="경상북도",
    city="경주시",
    base_url="https://www.gyeongju.go.kr/open_content/ko/page.do?mnu_uid=423",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상북도", sigun_name="경주시"),
    adapter="eminwon_list",
)

# ============================================================ 예천군 — eminwon_list 어댑터
# 목록은 순수 GET + <a href="?id=&dn=">, 첨부는 표준 goDownLoad(...) 패턴이라 코드
# 수정 없이 그대로 등록된다. 사용자 제공 URL, 2026-09-28 실측 확인.
YECHEON = City(
    province="경상북도",
    city="예천군",
    base_url="https://www.ycg.kr/open.content/ko/administrative/news/announcement/",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상북도", sigun_name="예천군"),
    adapter="eminwon_list",
)

# ============================================================ 울진군 — uljin_board 어댑터
# <table>이 아니라 <ul class="bbs_list"> 레이아웃이고 페이지네이션이 onclick=
# "goPage('<N>')"(실제로는 히든필드 startPage로 GET)이라 전용 어댑터를 만들었다.
# 첨부는 상세 페이지의 완성된 GET 링크라 eminwon_list.py를 재사용한다. 사용자
# 제공 URL, 2026-09-28 실측 확인.
ULJIN = City(
    province="경상북도",
    city="울진군",
    base_url="https://www.uljin.go.kr/index.uljin",
    boards=[{"name": "고시공고", "menu_cd": "DOM_000000103002007001"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상북도", sigun_name="울진군"),
    adapter="uljin_board",
)

# ============================================================ 성주군 — seongju_board 어댑터
# 목록 마크업은 saeol_gosi.py와 같지만(td.list_tit/list_date) 페이지네이션에
# srchEnable=1 등 부가 파라미터가 전부 필요하고, "공지글" 고정행이 cutoff 판정을
# 망가뜨려(어댑터 상단 설명 참고) 전용 어댑터를 만들었다. 사용자 제공 URL,
# 2026-09-28 실측 확인.
SEONGJU = City(
    province="경상북도",
    city="성주군",
    base_url="https://www.sj.go.kr/page.do",
    boards=[{"name": "고시공고", "mnu_uid": "1044"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상북도", sigun_name="성주군"),
    adapter="seongju_board",
)

# ============================================================ 영덕군 — eminwon_list 재사용(워드프레스 kboard)
# 워드프레스 "kboard" 플러그인(td.kboard-list-title/kboard-list-date, "title"
# 부분문자열이 걸려 eminwon_list의 제목 칸 판별을 그대로 재사용 가능) — 페이지네이션
# 파라미터는 pageid(밑줄 없음, base_url의 고정 게시판 ID page_id=763과는 다른
# 파라미터), 첨부는 ?action=kboard_file_download&uid=&file=fileN 형태의 완성된
# GET 링크지만 Referer 헤더(상세 페이지 URL) 없이는 에러 페이지만 돌아온다 —
# eminwon_list.py에 전용 분기 추가. 사용자 제공 URL, 2026-09-28 실측 확인.
YEONGDEOK = City(
    province="경상북도",
    city="영덕군",
    base_url="https://www.yd.go.kr/?page_id=763",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상북도", sigun_name="영덕군"),
    adapter="eminwon_list",
)

# ============================================================ 영양군 — eminwon_list 재사용
# 도메인이 yeongyang.go.kr이 아니라 www.yyg.go.kr(구 도메인 frameset 리다이렉트,
# 실측 확인). 목록은 표준 <table class="table_list">(제목 칸 class="align_left",
# 날짜 칸 class="mob_dp_inflex"), 페이지네이션은 "page" 파라미터(이미 eminwon_list
# 공통 세트에 있음). 첨부는 <form name="nnn"> POST + goDownLoad(...)인데, 보령시와
# 달리 첫 인자(user_file_nm) 자체가 암호화 토큰이 아니라 확장자 포함 평문 실제
# 파일명이다 — eminwon_list.py에 확장자 존재 여부로 판별하는 분기를 추가했다(또한
# 여기선 <a>가 아니라 <button onclick=...>라 버튼도 같이 훑도록 확장). 사용자 제공
# URL, 2026-09-28 실측 확인.
YEONGYANG = City(
    province="경상북도",
    city="영양군",
    base_url="https://www.yyg.go.kr/www/organization/yyg_news/notification",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상북도", sigun_name="영양군"),
    adapter="eminwon_list",
)

# ============================================================ 의성군 — eminwon_list 재사용(새올 계열)
# 실제 도메인은 usc.go.kr이 아니라 www.usc.go.kr/ko/(usc.go.kr 루트는 meta refresh로
# /ko/main.do로 리다이렉트) — 목록은 page.do?mnu_uid=157(새올 계열이지만 saeol_gosi.py
# 와 클래스명이 다름: td.subject/td.date, class에 "title"이 없어 eminwon_list의
# "마지막 <a> 칸" 폴백으로 잡힌다), pageNo만으로 페이지네이션 정상 동작(성주군과 달리
# 부가 파라미터 불필요, 공지글 고정행도 없음). 첨부는 download.do 완성 링크가
# eminwon.uiseong.go.kr의 FileDown.jsp로 리다이렉트되는데, 이 다운로드 서버가 강릉시와
# 같은 레거시 암호화 스위트 문제가 있어 eminwon_list.py의 SECLEVEL 완화 대상에
# 추가했다(목록 사이트 호스트와 달라 무조건 마운트하도록 로직도 같이 고쳤다).
# 사용자 제공 URL, 2026-09-28 실측 확인.
UISEONG = City(
    province="경상북도",
    city="의성군",
    base_url="http://www.usc.go.kr/ko/page.do?mnu_uid=157",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상북도", sigun_name="의성군"),
    adapter="eminwon_list",
)

# ============================================================ 청송군 — ntis_ofr 어댑터
# 사이트 자체 CMS(www.cs.go.kr/countyOffice/...)의 "고시공고" 게시판은 iframe으로
# eminwon.cs.go.kr의 NTIS eMinwon 표준 게시판(OfrNotAncmtLSub.jsp)을 그대로 보여주는
# 것이었다(실측 확인 — 사이트 CMS 쪽 페이지 소스에 주석 처리된 iframe 태그로 남아있고,
# 두 URL이 완전히 같은 목록/순서를 반환한다) — 그래서 사이트 자체 CMS를 새로 만들지
# 않고 기존 ntis_ofr.py를 그대로 재사용한다. <form name="form1">에 not_ancmt_se_code/
# cha_dep_code_nm 필드가 이미 박혀 있어 파라미터 하드코딩 불필요. 사용자 제공 URL,
# 2026-09-28 실측 확인.
CHEONGSONG = City(
    province="경상북도",
    city="청송군",
    base_url="https://eminwon.cs.go.kr/emwp/jsp/ofr/OfrNotAncmtLSub.jsp?not_ancmt_se_code=01,04,05&cha_dep_code_nm=51600010000",
    boards=[{"name": "고시공고"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상북도", sigun_name="청송군"),
    adapter="ntis_ofr",
)

CITIES = [
    YEONGCHEON, CHEONGDO, GUMI, GIMCHEON, CHILGOK, ANDONG, GYEONGBUK_DO, BONGHWA,
    ULLEUNG, YEONGJU, MUNGYEONG, SANGJU, GYEONGSAN, POHANG, GORYEONG, GUNWI,
    GYEONGJU, YECHEON, ULJIN, SEONGJU, YEONGDEOK, YEONGYANG, UISEONG, CHEONGSONG,
]
