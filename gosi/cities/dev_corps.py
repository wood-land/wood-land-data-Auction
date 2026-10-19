"""
cities/dev_corps.py — 지방개발공사/도시공사 고시공고 게시판 목록.

개발공사·도시공사는 특정 시/군에 속하지 않는 광역 단위 공기업이라, 시/도별
cities/*.py 대신 이 파일에 모아 둔다(보상맵 수집소스 카탈로그의 "개발·도시공사"
분류와 같은 결). City.regions는 소재지 기준으로 최소한만 채운다 — 이 기관들의
사업 범위는 도 전역이라 주소 검증 정확도가 낮을 수 있다.

새 기관을 추가할 때는 먼저 해당 사이트의 게시판 구조를 직접 탐색해 확인한 뒤
City(...)를 하나 더 추가한다 (임의 추측 금지, law.md 3-2 참고). 13곳의 개발공사·
도시공사를 확인한 결과 대부분 서로 다른 벤더였고(같은 "지방 개발공사"라는 것만으로
같은 시스템이라고 가정할 수 없었다), 경북·경남개발공사만 같은 JSON API 벤더였다.
"""

from core.board_crawler import City
from core.jose_extractor import Regions

from cities._shared import DEFAULT_BLACKLIST, DEFAULT_KEYWORDS

PROVINCE_NAME = "공기업"

# ============================================================ 경상북도개발공사 — devcorp_bbs_api 어댑터
# cms_adapters/devcorp_bbs_api.py 상단 설명 참고 (2026-09-25 실측 확인). 게시판 하나에
# 분양/임대/보상/기타 공고가 섞여 있어 키워드 필터로 보상 관련만 걸러진다.
GBDC = City(
    province="경상북도",
    city="경상북도개발공사",
    base_url="https://www.gbdc.co.kr",
    boards=[{"name": "공고", "bbs_id": "4c9b3e75-2935-4bcd-96be-62fb07903949"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상북도", sigun_name="예천군"),
    adapter="devcorp_bbs_api",
)

# ============================================================ 경상남도개발공사 — devcorp_bbs_api 어댑터
# "보상공고" 게시판이 따로 있어(ATTR01로 카테고리 필터) 전부 보상 관련 공고다.
GNDC = City(
    province="경상남도",
    city="경상남도개발공사",
    base_url="https://www.gndc.co.kr",
    boards=[
        {
            "name": "보상공고",
            "bbs_id": "B491A490314446318099F9D828047900",
            "attr01": "COLM1_CD&notice_07|COLM3_CD",
        }
    ],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경상남도", sigun_name="진주시"),
    adapter="devcorp_bbs_api",
)

# ============================================================ 전북개발공사 — notice_bbsgubun 어댑터
# cms_adapters/notice_bbsgubun.py 상단 설명 참고 (2026-09-26 실측 확인). 서버 TLS
# cipher가 낡아 핸드셰이크가 실패해(SSLV3_ALERT_HANDSHAKE_FAILURE) 어댑터에서 cipher
# suite만 완화한다(인증서 검증은 그대로 켠 채로).
JBDC = City(
    province="전북특별자치도",
    city="전북개발공사",
    base_url="https://www.jbdc.co.kr/notice/notice.do",
    boards=[{"name": "보상공고", "bbsgubun": "10"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="전북특별자치도", sigun_name="전주시"),
    adapter="notice_bbsgubun",
)

# ============================================================ 강원개발공사 — wnoti_board 어댑터
# cms_adapters/wnoti_board.py 상단 설명 참고 (2026-09-26 실측 확인). JS/세션 이슈
# 없이 평범한 GET 게시판이라 어댑터가 가장 단순하다.
GDCO = City(
    province="강원특별자치도",
    city="강원개발공사",
    base_url="https://www.gdco.co.kr/customer/wnoti_list.php",
    boards=[{"name": "보상공고", "board_id": "REWARDNOTI"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="강원특별자치도", sigun_name="춘천시"),
    adapter="wnoti_board",
)

# ============================================================ 충남개발공사 — bbs_govstd_form 어댑터
# cms_adapters/bbs_govstd_form.py 상단 설명 참고 (2026-09-26 실측 확인). 화면은
# <form name="frm"> JS 제출이지만 list.do/view.do 모두 평범한 쿼리스트링 GET으로
# 재현된다. 첨부 링크 텍스트 끝에 "(62 KB)" 같은 파일크기 표기가 붙어 있어 제거한다.
CNDC = City(
    province="충청남도",
    city="충남개발공사",
    base_url="https://www.cndc.kr/bbs/list.do",
    boards=[{"name": "보상공고", "key": "2404080036"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청남도", sigun_name="홍성군"),
    adapter="bbs_govstd_form",
)

# ============================================================ 충북개발공사 — zboard_govstd 어댑터
# cms_adapters/zboard_govstd.py 상단 설명 참고 (2026-09-26 실측 확인). JS 없이
# 평범한 GET 게시판. 첨부 링크 텍스트가 "1 : 파일명.ext [12345 byte]" 형태라
# 접두/접미사를 제거해야 실제 파일명이 나온다.
CBDC = City(
    province="충청북도",
    city="충북개발공사",
    base_url="https://www.cbdc.co.kr/zboard/list.do",
    boards=[{"name": "보상공고", "lm_code": "BBSMSTR_000000000016"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="충청북도", sigun_name="청주시"),
    adapter="zboard_govstd",
)

# ============================================================ 부천도시공사 — fmcs_board 어댑터
# cms_adapters/fmcs_board.py 상단 설명 참고 (2026-09-26 실측 확인). 보상 전용
# 게시판이 아니라 일반 공지사항판이라 다른 지자체와 같이 키워드 필터로 걸러진다.
BEST = City(
    province="경기도",
    city="부천도시공사",
    base_url="https://www.best.or.kr/fmcs/156",
    boards=[{"name": "공지사항"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="경기도", sigun_name="부천시"),
    adapter="fmcs_board",
)

# ============================================================ sh서울주택도시공사 — ish_board 어댑터
# cms_adapters/ish_board.py 상단 설명 참고 (2026-09-26 실측 확인). 화면은 "이노릭스"
# 자체 다운로드 클라이언트를 쓰는 것처럼 보이지만 실제로는 JS의 initParam.downList를
# 읽어 /com/file/innoFD.do 로 평범한 GET 스트리밍 다운로드를 한다(플러그인 불필요).
ISH = City(
    province="서울특별시",
    city="서울주택도시공사(SH)",
    base_url="https://www.i-sh.co.kr/main/lay2/program/S1T294C301/www/brd/m_257/view.do",
    boards=[{"name": "공고", "multi_itm_seq": "32"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="서울특별시", sigun_name="강남구"),
    adapter="ish_board",
)

# ============================================================ 부산도시공사 — krds_board 어댑터
# cms_adapters/krds_board.py 상단 설명 참고 (2026-09-26 실측 확인). "보상계획" 전용
# 게시판이 따로 있다(boardId=BBS_0000005). 날짜 형식이 "YYYY.MM.DD"(점 구분)라
# 다른 지자체의 "-" 구분과 다르다.
BMC = City(
    province="부산광역시",
    city="부산도시공사",
    base_url="https://www.bmc.busan.kr/board/view.do",
    boards=[{"name": "보상계획", "board_id": "BBS_0000005", "menu_cd": "DOM_000000101001004000"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="부산광역시", sigun_name="해운대구"),
    adapter="krds_board",
)

# ============================================================ 인천도시공사 — ih_bbs 어댑터
# cms_adapters/ih_bbs.py 상단 설명 참고 (2026-09-26 실측 확인). 사람이 보는
# notice.jsp?page=N 은 페이징이 안 먹고 항상 1페이지만 보여줘서 실제 목록 엔드포인트
# (bbs/bbsMsgList.do?bcd=notice&pgno=N)로 직접 접근한다. 상세 페이지엔 모든 공지에
# 고정으로 붙는 사이드바 다운로드 링크가 있어 div.add_file로 범위를 좁혀야 한다.
IH = City(
    province="인천광역시",
    city="인천도시공사",
    base_url="https://www.ih.co.kr/main/customer/notification/notice.jsp",
    boards=[{"name": "공지사항", "bcd": "notice"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="인천광역시", sigun_name="남동구"),
    adapter="ih_bbs",
)

# ============================================================ 대전도시공사 — dcco_board 어댑터
# cms_adapters/dcco_board.py 상단 설명 참고 (2026-09-26 실측 확인). JS 없이
# 평범한 GET 게시판(전용 보상 게시판 아님, 키워드로 걸러짐).
DCCO = City(
    province="대전광역시",
    city="대전도시공사",
    base_url="https://www.dcco.kr/web/board/view.do",
    boards=[{"name": "공지사항", "m_id": "113"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="대전광역시", sigun_name="서구"),
    adapter="dcco_board",
)

# ============================================================ 울산도시공사 — umca_board 어댑터
# cms_adapters/umca_board.py 상단 설명 참고 (2026-09-26 실측 확인). "보상공고"
# 전용 게시판(bbsId=BBS_0000000000000005). storyCms/HHBbs 계열 CMS로, 페이지네이션
# 실제 파라미터명이 "pageIndex"가 아니라 "page"다.
UMCA = City(
    province="울산광역시",
    city="울산도시공사",
    base_url="https://www.umca.co.kr/umca/bbs/view.do",
    boards=[{"name": "보상공고", "bbs_id": "BBS_0000000000000005", "m_id": "001001005000000000"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="울산광역시", sigun_name="남구"),
    adapter="umca_board",
)

# ============================================================ 광주광역시도시공사 — board_es 어댑터
# cms_adapters/board_es.py 상단 설명 참고 (2026-09-26 실측 확인). 서버가 중간
# 인증서를 안 보내(unable to get local issuer certificate) 발급기관 공개 배포처에서
# 받은 중간 인증서를 신뢰 저장소에 추가해 해결했다(검증을 끈 게 아니라 완성한 것).
GMCC = City(
    province="광주광역시",
    city="광주광역시도시공사",
    base_url="https://www.gmcc.co.kr/board.es",
    boards=[{"name": "공고", "mid": "a10402000000", "bid": "0018"}],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=Regions(sido_name="광주광역시", sigun_name="남구"),
    adapter="board_es",
)

CITIES = [GBDC, GNDC, JBDC, GDCO, CNDC, CBDC, BEST, ISH, BMC, IH, DCCO, UMCA, GMCC]
