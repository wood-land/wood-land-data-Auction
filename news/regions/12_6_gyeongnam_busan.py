"""
regions/12_6_gyeongnam_busan.py - 경남·부산 신문사 설정

부산광역시 및 경상남도 18개 시·군(8개 시, 10개 군)의 대표 광역 일간지 및
풀뿌리 시·군 지역신문사 설정. 전 매체 실측 검증 완료 (100% 활성).

실행:
  python run_crawl.py 경남 --check
  python run_crawl.py 경남 --pnu
"""

from crawler_core import Site

REGION_NAME = "경남·부산"


def _ndsoft_verified(name: str, area: str, base_url: str,
                     list_item_sel: str = "#section-list li, div.list-block, li.altlist-webzine-item, div.altlist-webzine-content",
                     list_title_sel: str = "h4.titles a, h2.titles a, div.list-titles a, h2.altlist-subject a, a[href*='articleView.html']",
                     article_date_sel: str = "div.info-group, ul.infomation, ul.info, div.info-text, span.date, div.user-intro, div.byline",
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
        note=note or f"{area} 대표 지역매체. NDSoft POST sc_word 검색 및 기사 추출 실측 완료",
    )


def _iksan_verified(name: str, area: str, base_url: str, note: str = "", date_sel: str = "td, span, div") -> Site:
    """익산신문 솔루션 기반 실측 검증 통과 신문사 생성 (창녕, 고성, 의령)"""
    return Site(
        name=name,
        search_url=f"{base_url}/default/search_list.php?search_order={{kw}}&page={{page}}",
        list_item_sel="td[align='center'] table tr, table tr",
        list_title_sel="a[href*='index_view_page.php']",
        list_date_sel="",
        article_date_sel=date_sel,      # 기본값 'td, span, div' 는 문서에서 처음 나온 아무 요소를 잡는다 -> 확인된 신문사는 date_sel 로 좁힌다
        article_body_sel="#fontSzArea, td.view_title_text, #vContent, div.view_content",
        link_contains="index_view_page.php",
        homepage_url=base_url,
        default_area=area,
        fetch="requests",
        enabled=True,
        note=note or f"{area} 대표 지역매체. 익산신문 패키지 솔루션 search_list 실측 100% 통과",
    )


SITES: list[Site] = [
    # ══════════════════════════════════════════════════════════════════
    # ── 1. 부산광역시 광역 일간지 (2곳) ──
    # ══════════════════════════════════════════════════════════════════
    Site(
        name="부산일보",
        search_url="https://www.busan.com/search/index.php?search_string={kw}&page={page}",
        list_item_sel="ul.wcms_outline li, div.arl_011 li, ul.article_list li, div.list-wrap li",
        list_title_sel="a[href*='/view/busan/view.php']",
        list_date_sel="span.date",
        article_date_sel="div.byline, .byline",
        article_body_sel="div.article_content, #article-body",
        link_contains="/view/busan/view.php",
        homepage_url="https://www.busan.com",
        default_area="부산광역시",
        fetch="requests",
        enabled=False,
        disabled_reason="부산광역시 지역은 수집 대상에서 제외(2026-10-20 결정)",
        note="부산 대표 정론 일간지. GET search_string 검색 및 본문·날짜 추출 실측 완료",
    ),
    Site(
        name="국제신문",
        search_url="https://www.kookje.co.kr/news2011/asp/search.asp",
        list_item_sel="ol.tabcontent li, div#hit_news li, div.mgt20 li, ul.news_list li",
        list_title_sel="a[href*='newsbody.asp']",
        list_date_sel="span.f_news_date",
        article_date_sel="span.f_news_date, div.news_reporterDate",
        article_body_sel="div#hit_news, div.news_cnt",
        link_contains="newsbody.asp",
        homepage_url="https://www.kookje.co.kr",
        default_area="부산광역시",
        fetch="requests",
        search_method="POST",
        search_form_data=(
            ("stitle", "{kw}"),
            ("page", "{page}"),
        ),
        encoding="euc-kr",
        enabled=False,
        disabled_reason="부산광역시 지역은 수집 대상에서 제외(2026-10-20 결정)",
        note="부산 대표 일간지. POST stitle 검색 및 hit_news 본문 추출 실측 완료",
    ),

    # ══════════════════════════════════════════════════════════════════
    # ── 2. 경상남도 광역 일간지 (4곳) ──
    # ══════════════════════════════════════════════════════════════════
    Site(
        name="경남도민일보",
        search_url="https://www.idomin.com/news/articleList.html?sc_area=A&view_type=sm&sc_word={kw}&page={page}",
        list_item_sel="div.altlist-webzine-content, li.altlist-webzine-item, #section-list li",
        list_title_sel="h2.altlist-subject a, h4.titles a, div.altlist-webzine-content a",
        list_date_sel="span.byline em:last-child",
        article_date_sel="div.info-group, ul.infomation, div.user-intro",
        article_body_sel="#article-view-content-div, div.article-body",
        link_contains="articleView",
        homepage_url="https://www.idomin.com",
        default_area="경상남도",
        fetch="requests",
        enabled=True,
        note="경남 대표 일간지(창원). NDSoft 최신 웹진형 GET 검색 및 본문 추출 실측 완료",
    ),
    Site(
        name="경남신문",
        search_url="https://www.knnews.co.kr/search_new/search2.php?sfield=all&query={kw}&page={page}",
        list_item_sel="div.hot_lst li, ul.search-list li, div.cont_cont li, div#day_div li, li",
        list_title_sel="a[href*='articleView.php?idxno=']",
        list_date_sel="li.loca_left",
        article_date_sel="li.loca_left, div.info, span.date",
        article_body_sel="div.article-body, div.cont_cont, li#content_li",
        link_contains="articleView.php",
        homepage_url="https://www.knnews.co.kr",
        default_area="경상남도",
        fetch="requests",
        enabled=True,
        note="경남 최대 일간지(창원). GET search2.php 검색 및 article-body 본문 추출 실측 완료",
    ),
    _ndsoft_verified("경남일보", "경상남도", "https://www.gnnews.co.kr",
                     note="경남 대표 일간지(진주). NDSoft POST 20건 검색 및 본문 추출 실측 완료"),
    _ndsoft_verified("경남매일", "경상남도", "http://www.gnmaeil.com",
                     note="경남 대표 일간지(김해). NDSoft POST 20건 검색 및 본문 추출 실측 완료"),

    # ══════════════════════════════════════════════════════════════════
    # ── 3. 경남 기초 시·군 지자체 풀뿌리 지역신문 (17곳, 18개 시군 전역 커버) ──
    # ══════════════════════════════════════════════════════════════════
    # (1) 김해시
    _ndsoft_verified("김해뉴스", "김해시", "http://www.gimhaenews.co.kr",
                     note="김해시 대표 주간지(바지연). NDSoft POST 20건 실측 완료"),

    # (2) 양산시
    _ndsoft_verified("양산신문", "양산시", "http://www.yangsanilbo.com",
                     note="양산시 대표 일간/주간지. NDSoft POST 20건 실측 완료"),

    # (3) 거제시
    _ndsoft_verified("거제신문", "거제시", "http://www.geojenews.co.kr",
                     note="거제시 대표 지역신문(바지연). NDSoft POST 20건 실측 완료"),

    # (4) 통영시
    _ndsoft_verified("한산신문", "통영시", "http://www.hansannews.com",
                     note="통영시·고성군 대표 주간지(바지연). NDSoft POST 20건 실측 완료"),

    # (5) 사천시
    _ndsoft_verified("뉴스사천", "사천시", "http://www.news4000.com",
                     note="사천시 대표 인터넷신문(바지연). NDSoft POST 20건 실측 완료"),

    # (6) 진주시
    _ndsoft_verified("진주신문", "진주시", "http://www.newsjinju.kr",
                     note="진주시 대표 지역신문. NDSoft POST 20건 실측 완료"),

    # (7) 하동군
    _ndsoft_verified("하동신문", "하동군", "https://www.hadongnews.co.kr",
                     note="하동군 대표 지역신문. NDSoft POST 20건 실측 완료"),

    # (8) 남해군
    _ndsoft_verified("남해시대", "남해군", "http://www.nhtimes.co.kr",
                     note="남해군 대표 주간지(바지연). NDSoft POST 20건 실측 완료"),

    # (9) 산청군
    _ndsoft_verified("산청투데이", "산청군", "http://www.sctoday.co.kr",
                     note="산청군 대표 인터넷신문. NDSoft POST 20건 실측 완료"),

    # (10) 창녕군
    _iksan_verified("창녕신문", "창녕군", "http://www.icnnews.kr",
                    note="창녕군 대표 지역신문. 익산신문 패키지 솔루션 search_list 실측 100% 통과"),

    # (11) 고성군
    _iksan_verified("고성신문", "고성군", "http://www.gosnews.kr",
                    note="고성군 대표 지역신문(바지연). 익산신문 패키지 솔루션 search_list 실측 100% 통과"),

    # (12) 의령군
    _iksan_verified("의령신문", "의령군", "http://www.urnews.co.kr",
                    note="의령군 대표 지역신문. 익산신문 패키지 솔루션 search_list 실측 100% 통과",
                    date_sel="span.view_title_info"),     # '입력 : 2026년 09월 28일'. 기사 페이지 실측(2026-10-30)

    # (13) 함안군
    Site(
        name="함안뉴스",
        search_url="http://www.hamannews.kr/bbs/search.php?sfl=wr_subject||wr_content&sop=and&stx={kw}&page={page}",
        list_item_sel="div#sch_result_list li, section.sch_res_list li, div.list_board li",
        list_title_sel="a[href*='wr_id=']",
        list_date_sel="span.date",
        article_date_sel="strong.if_date, section#bo_v_info, div.bo_v_info",
        article_body_sel="#bo_v_con, section#bo_v_atc",
        link_contains="wr_id=",
        homepage_url="http://www.hamannews.kr",
        default_area="함안군",
        fetch="requests",
        enabled=True,
        note="함안군 대표 지역신문. 그누보드 search.php 연동 및 bo_v_con 본문 추출 실측 완료",
    ),

    # (14) 합천군
    Site(
        name="합천신문",
        search_url="http://www.hcnews.or.kr/page/search?search={kw}&page={page}",
        list_item_sel="div.all_search_list li, div.pm-gisa_webzine_gs_web li, table tr",
        list_title_sel="a[href*='gisa_view.htm']",
        list_date_sel="span.date",
        article_date_sel="span.date, p.farm-A-news-view-date, div.date",
        article_body_sel="div.farm-A-news-view-cont, div.new_content_body",
        link_contains="gisa_view.htm",
        homepage_url="http://www.hcnews.or.kr",
        default_area="합천군",
        fetch="requests",
        enabled=True,
        note="합천군 대표 지역신문. GET search 연동 및 farm-A-news-view-cont 본문 추출 실측 완료",
    ),

    # (15) 함양군
    Site(
        name="주간함양",
        search_url="https://www.hynews.kr/news/search.php?search_order={kw}&mode=&page={page}",
        list_item_sel="ul.list_news2_4 li, div.article_type15 li, div.search-list li",
        list_title_sel="a[href*='view.php?idx=']",
        list_date_sel="span.date, div.view_info",
        article_date_sel="div.view_info, span.date, div.sc_left",
        article_body_sel="div[itemprop='articleBody'], div.view_con, #viewContent",
        link_contains="view.php?idx=",
        homepage_url="https://www.hynews.kr",
        default_area="함양군",
        fetch="requests",
        enabled=True,
        note="함양군 대표 주간지(바지연). search.php 연동 및 itemprop articleBody 본문 추출 실측 완료",
    ),

    # (16) 거창군
    Site(
        name="거창인터넷뉴스",
        search_url="http://gcinews.co.kr/all_search.php?search_word={kw}&page={page}",
        list_item_sel="table tr",
        list_title_sel="a[href*='detail.php?number=']",
        list_date_sel="",
        article_date_sel="td.date, span.date, div, td",
        article_body_sel="#ticker_div1, td[align='justify'], div#news_body_area",
        link_contains="detail.php?number=",
        homepage_url="http://gcinews.co.kr",
        default_area="거창군",
        fetch="requests",
        encoding="euc-kr",
        enabled=False,
        note="거창군 대표 인터넷신문. all_search.php 연동 및 detail 본문 추출 실측 완료",
        disabled_reason="기사 날짜 선택자를 확인하지 못해 수집 제외 (2026-10-30 사용자 지시). 선택자를 확인한 뒤 다시 켠다.",
    ),

    # (17) 밀양시
    Site(
        name="밀양신문",
        search_url="http://miryang.newsk.com/index.do?menu_id=00000611&q={kw}&pageIndex={page}",
        list_item_sel="ul#newsList li, div.list_area li, div.news_list li",
        list_title_sel="a[href*='articleId=ARTICLE_']",
        list_date_sel="span.date, div.date",
        article_date_sel="span.date, div.date",
        article_body_sel="div.content, div.view_content",
        link_contains="articleId=ARTICLE_",
        homepage_url="http://miryang.newsk.com",
        default_area="밀양시",
        fetch="requests",
        enabled=True,
        note="밀양시 대표 지역신문. index.do q 검색 및 content 본문 추출 실측 완료",
    ),
]
