"""
regions/12_4_chungcheong_daejeon_sejong.py - 충청도(충북/충남/대전/세종) 신문사 설정

충청권 광역 일간지 및 대전 5개 구, 세종시, 충남 15개 시·군, 충북 11개 시·군
풀뿌리 지역신문사 설정.

실행:
  python run_crawl.py 충청 --check
  python run_crawl.py 충청 --pnu
"""

from crawler_core import TEMPLATE_ARTICLEVIEW, Site, site_from

REGION_NAME = "충청·대전·세종"


def _ndsoft_verified(name: str, area: str, base_url: str,
                     list_item_sel: str = "#section-list li",
                     list_title_sel: str = "h4.titles a, h2.titles a, div.list-titles a, h2.altlist-subject a",
                     article_date_sel: str = "ul.infomation, ul.info, div.info-text, span.date",
                     article_body_sel: str = "#article-view-content-div, div.article-body",
                     note: str = "") -> Site:
    """NDSoft 솔루션 기반 실측 검증 통과 신문사 생성"""
    return Site(
        name=name,
        search_url=f"{base_url}/news/articleList.html?sc_area=A&view_type=sm",
        list_item_sel=list_item_sel,
        list_title_sel=list_title_sel,
        list_date_sel="span.byline em:last-child",
        article_date_sel=article_date_sel,
        article_body_sel=article_body_sel,
        link_contains="articleView",
        homepage_url=base_url,
        default_area=area,
        fetch="requests",
        search_method="POST",
        search_form_data=(
            ("sc_area", "A"),
            ("view_type", "sm"),
            ("sc_word", "{kw}"),
            ("page", "{page}"),
        ),
        enabled=True,
        note=note or f"{area} 대표 지역매체. POST sc_word 검색 및 기사 추출 실측 완료",
    )


def _sn_search_verified(name: str, area: str, base_url: str, note: str = "") -> Site:
    """search.html 엔진 기반 실측 검증 통과 신문사 생성 (아산투데이, 충주신문)"""
    return Site(
        name=name,
        search_url=(
            f"{base_url}/search.html"
            f"?submit=submit&search={{kw}}&search_and=1&search_exec=all&search_section=all&news_order=1&page={{page}}"
        ),
        list_item_sel="div.search_result_list_box dl, div.search_result_list_box, dl",
        list_title_sel="dt a",
        list_date_sel="",
        article_date_sel="p.front_area, .read_date, span.date, div.sub_read_top",
        article_body_sel="#textinput, div#textinput",
        homepage_url=base_url,
        default_area=area,
        fetch="requests",
        enabled=True,
        note=note or f"{area} 대표 지역매체. search.html 엔진 실측 통과",
    )


def _pending(name: str, area: str, homepage_url: str, reason: str) -> Site:
    """도메인 접속 대기 또는 파서 추가 작업이 필요한 보류 신문사"""
    return Site(
        name=name,
        search_url=f"{homepage_url}/search?kw={{kw}}&page={{page}}",
        list_item_sel="div.list-item",
        list_title_sel="a.title",
        list_date_sel="span.date",
        article_date_sel="span.date",
        article_body_sel="div.article-body",
        homepage_url=homepage_url,
        default_area=area,
        fetch="requests",
        enabled=False,
        disabled_reason=f"홈페이지 확인 및 검색·기사 선택자 실측 필요: {reason}",
    )


SITES = [
    # ══════════════════════════════════════════════════════════════════
    # ── 1. 충청권 광역 일간지 및 대표지 (8곳) ──
    # ══════════════════════════════════════════════════════════════════
    site_from(
        TEMPLATE_ARTICLEVIEW,
        name="충청일보",
        search_url=(
            "https://prt.ccdailynews.com/engine_yonhap/search.php"
            "?picktab=article&searchcont=article&searchword={kw}&page={page}&sort="
        ),
        list_item_sel="#search_result div.list",
        list_title_sel="div.txtbox div.title a",
        list_date_sel="ul.info",
        homepage_url="https://www.ccdailynews.com",
        default_area="충청",
        fetch="requests",
        enabled=True,
        note="충청권 대표 일간지. engine_yonhap 솔루션 GET 검색 10건 실측",
    ),
    site_from(
        TEMPLATE_ARTICLEVIEW,
        name="금강일보",
        search_url=(
            "https://prt.ggilbo.com/engine_yonhap/search.php"
            "?picktab=article&searchcont=article&searchword={kw}&page={page}&sort="
        ),
        list_item_sel="#search_result div.list",
        list_title_sel="div.txtbox div.title a",
        list_date_sel="ul.info",
        homepage_url="http://www.ggilbo.com",
        default_area="대전·충청",
        fetch="requests",
        enabled=True,
        note="대전·충청 대표 일간지. engine_yonhap 솔루션 GET 검색 10건 실측",
    ),
    Site(
        name="대전일보",
        search_url="http://www.daejonilbo.com/news/articleList.html?sc_area=A&sc_word={kw}&view_type=sm&page={page}",
        list_item_sel="#section-list li",
        list_title_sel="h4.titles a",
        list_date_sel="span.byline em:last-child",
        article_date_sel="ul.infomation",
        article_body_sel="#article-view-content-div",
        link_contains="articleView",
        homepage_url="http://www.daejonilbo.com",
        default_area="대전광역시",
        fetch="requests",
        search_method="GET",
        enabled=True,
        note="대전·충청 최고(最古) 일간지. NDSoft GET 검색 103건 실측",
    ),
    Site(
        name="중도일보",
        search_url="https://www.joongdo.co.kr/search/searchWeb_2020.php?sword={kw}&page={page}",
        list_item_sel="div.newsList01 dl, div.newsList01, dl",
        list_title_sel="dt a",
        list_date_sel="span.date, .time",
        article_date_sel="ul.view-term, ul.view-term li, div.view-bott, ul.info, span.date, .time",
        article_body_sel="#article_body, div.article_body, #view_content, div.content",
        link_contains="view.php?key=",
        homepage_url="https://www.joongdo.co.kr",
        default_area="대전·충남",
        fetch="selenium",
        enabled=True,
        note="대전·충남 대표 일간지. 연합뉴스 OpenAPI 비동기 렌더링 Selenium 실측 통과",
    ),
    Site(
        name="충북일보",
        search_url="https://www.inews365.com/news/search_result.html?search={kw}&page={page}",
        list_item_sel="ul.result_list li, div.search_result li, table tr, li",
        list_title_sel="a[href*='article.html?no=']",
        list_date_sel="span.date, .date",
        article_date_sel=".date, .time, li, div.info",
        article_body_sel="#news_body_area, #articleBody",
        link_contains="article.html?no=",
        homepage_url="https://www.inews365.com",
        default_area="충청북도",
        fetch="requests",
        enabled=True,
        note="충북 대표 일간지. search_result.html GET 검색 54건 실측 통과",
    ),
    _ndsoft_verified("중부매일", "충청", "https://www.jbnews.com",
                     list_item_sel="#section-list li",
                     note="충청권 대표 일간지. NDSoft POST sc_word 검색 20건 실측"),
    _ndsoft_verified("충청투데이", "충청", "https://www.cctoday.co.kr",
                     list_item_sel="#section-list li",
                     note="충청권 대표 일간지. NDSoft POST sc_word 검색 20건 실측"),
    _ndsoft_verified("동양일보", "충청", "http://www.dynews.co.kr",
                     list_item_sel="#section-list li",
                     note="충청권 종합일간지. NDSoft POST sc_word 검색 61건 실측"),
    _ndsoft_verified("세종의소리", "세종특별자치시", "http://www.sjsori.com",
                     list_item_sel="li.altlist-webzine-item",
                     list_title_sel="h2.altlist-subject a",
                     article_date_sel="div.info-group ul.breadcrumbs",
                     note="세종시 대표 인터넷신문. NDSoft altlist 21건 실측"),

    # ══════════════════════════════════════════════════════════════════
    # ── 2. 충남 시·군 지자체 풀뿌리 지역신문 (13곳) ──
    # ══════════════════════════════════════════════════════════════════
    _ndsoft_verified("천안아산신문", "천안·아산", "http://www.canews.kr",
                     list_item_sel="div.list-block",
                     list_title_sel="div.list-titles a",
                     note="천안·아산 대표 주간지. NDSoft list-block 20건 실측"),
    Site(
        name="천안신문",
        search_url="https://www.icj.kr/bbs/search.php?sfl=wr_subject%7C%7Cwr_content&stx={kw}&page={page}",
        list_item_sel="ul.search_list li, div.sch_res_list li, li",
        list_title_sel="a[href*='bo_table=news&wr_id=']",
        list_date_sel="span.date, .date",
        article_date_sel="ul.art_info, div.art_top, .view_info, .date",
        article_body_sel="#news_body_area, #bo_v_con, div.view_con, div.content",
        link_contains="bo_table=news&wr_id=",
        homepage_url="https://www.icj.kr",
        default_area="천안시",
        fetch="requests",
        enabled=True,
        note="천안시 대표 지역신문. 그누보드 stx 검색 10건 실측 통과",
    ),
    _sn_search_verified("아산투데이", "아산시", "http://www.asantoday.com", note="아산시 대표 지역신문. search.html 60건 실측 통과"),
    _ndsoft_verified("당진시대", "당진시", "http://www.djtimes.co.kr",
                     list_item_sel="#section-list li",
                     note="충남 당진시 대표 주간지(바지연). NDSoft POST 20건 실측"),
    Site(
        name="서산타임즈",
        search_url="http://www.seosantimes.com/news/search.php?q={kw}&page={page}",
        list_item_sel="ul.news-list li, div.news_list li, table tr, li",
        list_title_sel="a[href*='view.php?no=']",
        list_date_sel="span.date, .date",
        article_date_sel=".date, span.date, ul.infomation",
        article_body_sel="#news_body_area, #articleBody, div.content",
        link_contains="view.php?no=",
        homepage_url="http://www.seosantimes.com",
        default_area="서산시",
        fetch="requests",
        enabled=True,
        note="서산시 대표 지역신문. search.php 146건 실측 통과",
    ),
    Site(
        name="공주신문",
        search_url="http://www.e-gongju.com/news/articleList.html",
        search_method="POST",
        encoding="euc-kr",
        search_form_data=(
            ("sc_area", "A"),
            ("view_type", "sm"),
            ("sc_word", "{kw}"),
            ("page", "{page}"),
        ),
        list_item_sel="table tr td, table tr, div.list-block, #section-list li",
        list_title_sel="a[href*='articleView.html']",
        list_date_sel="span.byline em:last-child",
        # 표 레이아웃이라 날짜 칸에 클래스가 없다: [호수] 2026년 08월 27일 (목) 17:40:07 (회색 배경 칸).
        # 예전 선택자 td.com 은 머리말의 갱신 시각(2026.10.26 월 22:19)을 잡아 모든 기사가 최근 날짜로 읽혔다.
        article_date_sel='td[bgcolor="EFEFEF"]',
        article_body_sel="#articleBody, td.view_r",
        link_contains="articleView.html",
        homepage_url="http://www.e-gongju.com",
        default_area="공주시",
        fetch="requests",
        enabled=True,
        note="공주시 대표 주간지(바지연). NDSoft EUC-KR POST 86건 실측 통과",
    ),
    Site(
        name="금산신문",
        search_url="http://www.igsnews.co.kr/news/articleList.html",
        search_method="POST",
        search_form_data=(
            ("sc_area", "A"),
            ("view_type", "sm"),
            ("sc_word", "{kw}"),
            ("page", "{page}"),
        ),
        list_item_sel="div.body_new_3, div.auto-body, div.list-block, #section-list li, div.item",
        list_title_sel="strong a, a[href*='articleView.html']",
        list_date_sel="span.byline em:last-child",
        article_date_sel="div, ul.infomation",
        article_body_sel="#article-view-content-div, div.content.border-box, #articleBody",
        link_contains="articleView.html",
        homepage_url="http://www.igsnews.co.kr",
        default_area="금산군",
        fetch="requests",
        enabled=True,
        note="금산군 대표 지역신문. NDSoft POST 4건 실측 통과",
    ),
    Site(
        name="홍성신문",
        search_url="http://www.hsnews.co.kr/news/articleList.html?sc_area=A&view_type=sm&sc_word={kw}&page={page}",
        list_item_sel="div.item, #section-list li, div.list-block",
        list_title_sel="h4.titles a, a.links, h2.titles a",
        list_date_sel="span.byline em:last-child",
        article_date_sel="ul.infomation, ul.info",
        article_body_sel="#article-view-content-div",
        link_contains="articleView.html",
        homepage_url="http://www.hsnews.co.kr",
        default_area="홍성군",
        fetch="requests",
        enabled=True,
        note="충남 홍성군 대표 주간지(바지연). NDSoft GET sc_word 20건 실측 통과",
    ),
    _ndsoft_verified("계룡일보", "계룡시", "http://www.gyeryongilbo.com",
                     list_item_sel="#section-list li",
                     note="충남 계룡시 대표 지역신문. NDSoft POST 58건 실측"),
    _ndsoft_verified("보령뉴스", "보령시", "http://www.brnews.co.kr",
                     list_item_sel="li.altlist-webzine-item",
                     list_title_sel="h2.altlist-subject a",
                     article_date_sel="div.info-update-origin, ul.infomation",
                     note="충남 보령시 대표 인터넷신문. NDSoft altlist 21건 실측"),
    _ndsoft_verified("뉴스서천", "서천군", "http://www.newssc.co.kr",
                     list_item_sel="div.list-block",
                     list_title_sel="div.list-titles a",
                     note="충남 서천군 대표 주간지(바지연). NDSoft list-block 20건 실측"),
    _ndsoft_verified("청양신문", "청양군", "http://www.cynews.co.kr",
                     list_item_sel="div.list-block",
                     list_title_sel="div.list-titles a",
                     note="충남 청양군 대표 주간지(바지연). NDSoft list-block 20건 실측"),
    _ndsoft_verified("태안신문", "태안군", "http://www.taeannews.co.kr",
                     list_item_sel="ul.type2 li",
                     list_title_sel="h2.titles a, a.titles",
                     note="충남 태안군 대표 주간지(바지연). NDSoft type2 20건 실측"),

    # ══════════════════════════════════════════════════════════════════
    # ── 3. 충북 시·군 지자체 풀뿌리 지역신문 (7곳) ──
    # ══════════════════════════════════════════════════════════════════
    _sn_search_verified("충주신문", "충주시", "http://www.cjwn.com", note="충주시 대표 지역신문. search.html 60건 실측 통과"),
    _ndsoft_verified("제천단양뉴스", "제천·단양", "http://www.jdnews.kr",
                     list_item_sel="#section-list li",
                     note="충북 제천·단양 대표 주간지. NDSoft POST 20건 실측"),
    _ndsoft_verified("옥천신문", "옥천군", "http://www.okinews.com",
                     list_item_sel="li.altlist-webzine-item",
                     list_title_sel="h2.altlist-subject a",
                     article_date_sel="ul.breadcrumbs, ul.infomation",
                     note="충북 옥천군 대표 풀뿌리 주간지(바지연). NDSoft altlist 21건 실측"),
    _ndsoft_verified("보은사람들", "보은군", "http://www.boeunpeople.com",
                     list_item_sel="li.altlist-webzine-item",
                     list_title_sel="h2.altlist-subject a",
                     article_date_sel="ul.breadcrumbs, ul.infomation",
                     note="충북 보은군 대표 풀뿌리 주간지(바지연). NDSoft altlist 21건 실측"),
    Site(
        name="주간영동",
        search_url="https://www.weeklyyd.com/news/articleList.html?sc_area=A&view_type=sm&sc_word={kw}&page={page}",
        list_item_sel="div.list-block, #section-list li, ul.type1 li",
        list_title_sel="h4.titles a, a[href*='articleView.html']",
        list_date_sel="span.byline em:last-child",
        article_date_sel="ul.infomation, ul.info",
        article_body_sel="#article-view-content-div",
        link_contains="articleView.html",
        homepage_url="https://www.weeklyyd.com",
        default_area="영동군",
        fetch="requests",
        enabled=True,
        note="충북 영동군 대표 지역신문. NDSoft GET sc_word 20건 실측 통과",
    ),
    _ndsoft_verified("음성신문", "음성군", "http://www.usnews.co.kr",
                     list_item_sel="ul.types li",
                     list_title_sel="h2.titles a, h4.titles a",
                     article_date_sel="div.user-intro, ul.infomation, ul.info",
                     note="충북 음성군 대표 지역신문. NDSoft types 20건 실측"),

    # ══════════════════════════════════════════════════════════════════
    # ── 4. 실측 검증 완료 신규 활성화 매체 (3곳 전원 활성화) ──
    # ══════════════════════════════════════════════════════════════════
    _ndsoft_verified("세종포스트", "세종특별자치시", "http://www.sjpost.co.kr",
                     list_item_sel="#section-list li, div.list-block, table tr",
                     list_title_sel="h4.titles a, a[href*='articleView.html']",
                     article_date_sel="ul.infomation, ul.info",
                     article_body_sel="#article-view-content-div",
                     note="세종시 대표 인터넷언론. NDSoft POST sc_word 20건 실측 통과"),
    Site(
        name="괴산타임즈",
        search_url="https://www.goesantimes.com/news/articleList.html?sc_area=A&view_type=sm&sc_word={kw}&page={page}",
        list_item_sel="div.list-block, #section-list li, ul.type1 li, table tr",
        list_title_sel="h4.titles a, a[href*='articleView.html']",
        list_date_sel="span.byline em:last-child",
        article_date_sel="ul.infomation, ul.info",
        article_body_sel="#article-view-content-div",
        link_contains="articleView.html",
        homepage_url="https://www.goesantimes.com",
        default_area="괴산군",
        fetch="requests",
        enabled=True,
        note="괴산군 대표 지역신문. 공식도메인(goesantimes.com) NDSoft GET 20건 실측 통과",
    ),
    Site(
        name="논산포커스",
        search_url="http://www.nsf.kr/news/search_list.asp?msection=0&searchstr={kw}&page={page}",
        encoding="euc-kr",
        list_item_sel="td[height='25'], tr[height='25'], table tr td",
        list_title_sel="a[href*='view.asp?idx=']",
        list_date_sel="",
        article_date_sel="td.photo1_1",
        article_body_sel="font#content, #content, font[id='content']",
        link_contains="view.asp?idx=",
        homepage_url="http://www.nsf.kr",
        default_area="논산시",
        fetch="requests",
        enabled=True,
        note="논산시 대표 지역매체. ASP 솔루션(msection=0) EUC-KR GET 164건 실측 통과",
    ),
]

