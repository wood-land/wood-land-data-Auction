"""Verified crawler settings for Jeolla and Gwangju local newspapers.

Includes provincial daily newspapers and grassroots municipal newspapers across
Jeonbuk, Jeonnam, and Gwangju Metropolitan City.
"""
from crawler_core import Site

REGION_NAME = "전라·광주"

_PENDING = "홈페이지는 확인했으나 검색 결과와 기사 날짜·본문 추출을 검증하지 못함"
_ARIRANG_LIST = "#section-list li"
_LIST_TITLE = "a[href*='articleView.html']"
_ARTICLE_DATE = "meta[property='article:published_time']"
_ARTICLE_BODY = "#article-view-content-div"


def _verified(name: str, area: str, homepage: str, method: str = "POST",
              list_selector: str = _ARIRANG_LIST, note: str = "") -> Site:
    search_url = homepage.rstrip("/") + "/news/articleList.html"
    common = dict(
        name=name,
        search_url=search_url,
        list_item_sel=list_selector,
        list_title_sel=_LIST_TITLE,
        list_date_sel="",
        article_date_sel=_ARTICLE_DATE,
        article_body_sel=_ARTICLE_BODY,
        homepage_url=homepage,
        default_area=area,
        fetch="requests",
        search_method=method,
        enabled=True,
        note=note,
    )
    if method == "POST":
        common["search_form_data"] = (
            ("sc_area", "A"), ("view_type", "sm"),
            ("sc_word", "{kw}"), ("page", "{page}"),
        )
    else:
        common["search_url"] += "?sc_area=A&view_type=sm&sc_word={kw}&page={page}"
    return Site(**common)


def _pending(name: str, area: str, homepage: str, note: str = "") -> Site:
    return Site(
        name=name,
        search_url="",
        list_item_sel="",
        list_title_sel="",
        list_date_sel="",
        article_date_sel="",
        article_body_sel="",
        homepage_url=homepage,
        default_area=area,
        fetch="requests",
        enabled=False,
        disabled_reason=_PENDING,
        note=note or "홈페이지 접속 상태 또는 검색 구조 추가 검증 필요",
    )


SITES: list[Site] = [
    # ── 1. 광역 대표 일간지 (전북, 전남, 광주) ──
    Site(
        name="전북일보",
        search_url="https://www.jjan.kr/search?searchText={kw}&page={page}",
        list_item_sel="div.news_list_unit",
        list_title_sel="a[href*='/article/']",
        list_date_sel="",
        article_date_sel="meta[property='article:published_time']",
        article_body_sel=".article_txt_container",
        homepage_url="https://www.jjan.kr/",
        default_area="전북특별자치도",
        fetch="requests",
        search_method="GET",
        enabled=True,
        note="전북 대표 일간지. GET search 결과(10건) 및 meta published_time, .article_txt_container 본문 추출 확인",
    ),
    _verified("전북도민일보", "전북특별자치도", "https://www.domin.co.kr", "POST",
              list_selector="div.list-block",
              note="전북 대표 일간지. POST sc_word 검색 20건(div.list-block) 및 기사 날짜/본문 확인"),
    _verified("전주일보", "전북특별자치도", "https://www.jjilbo.co.kr", "POST",
              list_selector="#section-list li",
              note="전북 권역 일간지. POST sc_word 검색 21건 및 기사 날짜/본문 확인"),
    _verified("전남일보", "전라남도", "https://www.jnilbo.com", "POST",
              list_selector="#section-list li",
              note="전남·광주 대표 일간지. POST sc_word 검색 21건 및 기사 날짜/본문 확인"),
    _verified("남도일보", "광주광역시", "https://www.namdonews.com", "POST",
              list_selector="#section-list li",
              note="광주·전남 일간지. POST sc_word 검색 21건 및 기사 날짜/본문 확인"),
    Site(
        name="무등일보",
        search_url="https://www.mdilbo.com/search?keyword={kw}",
        list_item_sel="ul.headline_lst > li",
        list_title_sel="a",
        list_date_sel="div.date span",
        article_date_sel="span.info_view",
        article_body_sel=".article_body",
        homepage_url="https://www.mdilbo.com/",
        default_area="광주광역시",
        fetch="selenium",
        search_method="GET",
        enabled=True,
        note="광주·전남 일간지. 동적 검색 결과 렌더링으로 fetch='selenium' 적용. ul.headline_lst 및 span.info_view, .article_body 확인",
    ),
    Site(
        name="전남도민일보",
        search_url="http://jndmnews.com/searchs.php?searchword={kw}&page={page}",
        list_item_sel="tr",
        list_title_sel="a.sublist",
        list_date_sel="span.date",
        article_date_sel="#byline li",
        article_body_sel="#content",
        homepage_url="http://jndmnews.com/",
        default_area="전라남도",
        fetch="requests",
        search_method="GET",
        encoding="euc-kr",
        enabled=True,
        note="전남 일간지. GET searchs.php euc-kr 검색 16건 실측. a.sublist 및 #byline li 날짜, #content 본문 추출 확인",
    ),

    # ── 2. 전북 시·군 지자체 풀뿌리 지역신문 ──
    Site(
        name="익산신문",
        search_url="http://www.iksannews.com/default/search_list.php?search_order={kw}",
        list_item_sel="table",
        list_title_sel="a[href*='index_view_page.php']",
        list_date_sel="",
        article_date_sel="span.view_title_info",
        article_body_sel="#fontSzArea",
        homepage_url="http://www.iksannews.com/",
        default_area="익산시",
        fetch="requests",
        search_method="GET",
        encoding="euc-kr",
        enabled=True,
        note="전북 익산시 대표 주간지. search_list.php euc-kr 검색 85건 실측, span.view_title_info 및 #fontSzArea 본문 추출 확인",
    ),
    _verified("정읍신문", "정읍시", "http://www.jnewsk.com", "POST",
              list_selector="#section-list li",
              note="전북 정읍시 대표 주간지. POST sc_word 검색 20건 실측 및 기사 추출 확인"),
    _verified("무주신문", "무주군", "http://www.mujunews.com", "POST",
              list_selector="#section-list li",
              note="전북 무주군 대표 주간지(바지연). POST sc_word 검색 13건 실측 및 기사 추출 확인"),
    _verified("부안독립신문", "부안군", "http://www.ibuan.com", "POST",
              list_selector="#section-list li",
              note="전북 부안군 대표 주간지(바지연). POST sc_word 검색 20건 실측 및 기사 추출 확인"),
    _pending("남원신문", "남원시", "http://www.namwonnews.com", "검색 결과 필터 미작동(대조어 동일 건수)으로 보류"),
    _pending("열린순창", "순창군", "http://www.openchang.com", "기사 본문 컨테이너 추가 확인 필요"),
    _pending("군산미래신문", "군산시", "https://kmrnews.com", "공개 검색 엔드포인트 추가 확인 필요"),
    _pending("김제시민의신문", "김제시", "http://www.gimjenews.co.kr", "도메인 DNS 응답 대기"),
    _pending("진안신문", "진안군", "http://www.jinannews.kr", "도메인 접속 대기"),
    _pending("고창신문", "고창군", "http://www.gochangnews.com", "도메인 접속 대기"),

    # ── 3. 전남 시·군 지자체 풀뿌리 지역신문 ──
    _verified("목포시민신문", "목포시", "http://www.mokposm.co.kr", "POST",
              list_selector="div.list-block",
              note="전남 목포시 대표 주간지(바지연). POST sc_word 검색 20건 실측 및 기사 추출 확인"),
    _verified("광양신문", "광양시", "http://www.gynet.co.kr", "POST",
              list_selector="div.list-block",
              note="전남 광양시 대표 주간지(바지연). POST sc_word 검색 20건(div.list-block) 실측 및 기사 추출 확인"),
    _verified("장성군민신문", "장성군", "http://www.jsnews.co.kr", "POST",
              list_selector="#section-list li",
              note="전남 장성군 대표 주간지. POST sc_word 검색 20건 실측 및 기사 추출 확인"),
    _verified("완도신문", "완도군", "http://www.wandonews.com", "POST",
              list_selector="#section-list li",
              note="전남 완도군 대표 주간지. POST sc_word 검색 20건 실측 및 기사 추출 확인"),
    _verified("해남신문", "해남군", "http://www.hnews.co.kr", "POST",
              list_selector="#section-list li",
              note="전남 해남군 대표 주간지(바지연). POST sc_word 검색 20건 실측 및 기사 추출 확인"),
    _pending("여수신문", "여수시", "http://www.yeosunews.net", "서버 응답 지연(Timeout)으로 보류"),
    _pending("담양뉴스", "담양군", "http://www.dnnews.co.kr", "검색어 필터링 미작동으로 보류"),
    _pending("담양곡성타임스", "담양·곡성", "http://www.dnktime.com", "도메인 접속 대기"),
    _pending("순천광장신문", "순천시", "http://www.agora.or.kr", "도메인 DNS 응답 대기"),
    _pending("나주시민의신문", "나주시", "http://www.naju.or.kr", "공개 검색 엔드포인트 추가 확인 필요"),
    _pending("보성시민신문", "보성군", "http://www.bsnews.or.kr", "도메인 접속 대기"),
    _pending("영광신문", "영광군", "http://www.ygunews.com", "도메인 접속 대기"),
]
