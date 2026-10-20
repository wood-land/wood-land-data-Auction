"""
regions/12_5_gyeongbuk_daegu_ulsan.py - 경북·대구·울산 신문사 설정

대구광역시, 울산광역시, 경상북도 22개 시·군의 대표 광역 일간지 및
풀뿌리 시·군 지역신문사 설정.

실행:
  python run_crawl.py 경북 --check
  python run_crawl.py 경북 --pnu
"""

from crawler_core import Site

REGION_NAME = "경북·대구·울산"


def _ndsoft_verified(name: str, area: str, base_url: str,
                     list_item_sel: str = "#section-list li, div.list-block, li.altlist-webzine-item",
                     list_title_sel: str = "h4.titles a, h2.titles a, div.list-titles a, h2.altlist-subject a",
                     article_date_sel: str = "div.info-group, ul.infomation, ul.info, div.info-text, span.date, div.user-intro",
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


def _disabled(site: Site, reason: str) -> Site:
    """수집에서 제외(사유를 남긴다)."""
    site.enabled = False
    site.disabled_reason = reason
    return site


def _iksan_verified(name: str, area: str, base_url: str, note: str = "") -> Site:
    """익산신문 솔루션 기반 실측 검증 통과 신문사 생성 (경산, 의성, 청도, 영덕, 포항)"""
    return Site(
        name=name,
        search_url=f"{base_url}/default/search_list.php?search_order={{kw}}&page={{page}}",
        list_item_sel="td[align='center'] table tr, table tr",
        list_title_sel="a[href*='index_view_page.php']",
        list_date_sel="",
        article_date_sel="td, span, div",
        article_body_sel="#fontSzArea, td.view_title_text, #vContent, div.view_content",
        link_contains="index_view_page.php",
        homepage_url=base_url,
        default_area=area,
        fetch="requests",
        enabled=True,
        note=note or f"{area} 대표 지역매체. 익산신문 패키지 솔루션 search_list 실측 100% 통과",
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
    # ── 1. 대구·경북·울산 광역 일간지 및 대표지 ──
    # ══════════════════════════════════════════════════════════════════
    _ndsoft_verified("경북도민일보", "경상북도", "http://www.hidomin.com",
                     article_date_sel="div.info-group, ul.infomation",
                     note="경북 대표 일간지. NDSoft POST 20건 및 div.info-group 날짜 추출 실측"),
    _ndsoft_verified("경북일보", "경상북도", "http://www.kyongbuk.co.kr",
                     note="경북 대표 일간지. NDSoft POST 20건 실측"),
    _ndsoft_verified("대경일보", "경북·대구", "http://www.dkilbo.com",
                     note="대구·경북 일간지. NDSoft POST 20건 실측"),
    _ndsoft_verified("대구일보", "대구광역시", "https://www.idaegu.com",
                     note="대구·경북 대표 일간지. NDSoft POST 20건 실측"),
    _ndsoft_verified("대구신문", "대구광역시", "http://www.idaegu.co.kr",
                     note="대구·경북 대표 일간지. NDSoft POST 20건 실측"),
    _ndsoft_verified("경상일보", "울산광역시", "https://www.ksilbo.co.kr",
                     note="울산 대표 일간지. NDSoft POST 20건 실측"),
    _ndsoft_verified("울산매일", "울산광역시", "http://www.iusm.co.kr",
                     note="울산 대표 일간지. NDSoft POST 20건 실측"),
    _ndsoft_verified("울산제일일보", "울산광역시", "http://www.ujeil.com",
                     note="울산 일간지. NDSoft POST 20건 실측"),

    # ══════════════════════════════════════════════════════════════════
    # ── 2. 경북 시·군 지자체 풀뿌리 지역신문 (실측 통과 15곳) ──
    # ══════════════════════════════════════════════════════════════════
    _ndsoft_verified("영주시민신문", "영주시", "http://www.yjinews.com",
                     note="경북 영주시 대표 주간지(바지연). NDSoft POST 20건 실측"),
    _ndsoft_verified("안동인터넷뉴스", "안동시", "http://www.adinews.co.kr",
                     note="경북 안동시 대표 인터넷신문. NDSoft POST 20건 실측"),
    _ndsoft_verified("영천시민신문", "영천시", "http://www.ycnews.co.kr",
                     note="경북 영천시 대표 주간지. NDSoft POST 20건 실측"),
    # 청송신문: csnews.co.kr 이 2026-10-20 현재 consumernews.co.kr(다른 사이트)로 이동해 수집 불가 -> 제외
    _disabled(_ndsoft_verified("청송신문", "청송군", "http://www.csnews.co.kr"),
              "도메인 csnews.co.kr 이 다른 사이트(consumernews.co.kr)로 연결됨. 새 주소 확인 전까지 제외(2026-10-20)"),
    _ndsoft_verified("봉화일보", "봉화군", "http://www.bonghwanews.co.kr",
                     note="경북 봉화군 대표 인터넷신문. NDSoft POST 20건 실측"),

    # 사용자 제공 10개 매체 실측 완료 및 활성화 등록
    Site(
        name="경주신문",
        search_url="https://www.gjnews.com/news/search.php?search_order={kw}",
        list_item_sel="ul.list_news2_4 li, div.section_search li, ul.list_news li, table tr",
        list_title_sel="a[href*='view.php?idx=']",
        list_date_sel="span.info_date, span.date",
        article_date_sel="span.info_date, span.info_date1, span.date, .time",
        article_body_sel="#contents, #view_content, div.section_view, #articleBody",
        link_contains="view.php?idx=",
        homepage_url="http://www.gjnews.com",
        default_area="경주시",
        fetch="requests",
        enabled=True,
        note="경주시 대표 주간지(바지연). search.php 실측 통과",
    ),
    Site(
        name="구미뉴스",
        search_url="http://www.guminews.co.kr/bbs/search.php?sfl=wr_subject%7C%7Cwr_content&stx={kw}&page={page}",
        list_item_sel="ul.search_list li, div.sch_res_list li, li",
        list_title_sel="a[href*='board.php?bo_table=news&wr_id=']",
        list_date_sel="span.date, .time",
        article_date_sel=".view_info, .date, span.date, div.art_top, p.today_text",
        article_body_sel="#news_body_area, div.cnt_view, div.arv_001, #bo_v_con, div.view_content",
        link_contains="board.php?bo_table=news&wr_id=",
        homepage_url="http://www.guminews.co.kr",
        default_area="구미시",
        fetch="requests",
        enabled=True,
        note="구미시 대표 인터넷신문. 그누보드 stx 검색 실측 통과",
    ),
    Site(
        name="상주신문",
        search_url="http://www.sangjunews.co.kr/bbs/bbs.asp?group_name=524&search_category=subject+content+writer&search_word={kw}&page={page}",
        list_item_sel="table tr",
        list_title_sel="a[href*='idx_num=']",
        list_date_sel="td.tm0",
        article_date_sel="td.tm0, td",
        article_body_sel="td.sub_content, td.view_content, td#view_text, table",
        link_contains="idx_num=",
        homepage_url="http://www.sangjunews.co.kr",
        default_area="상주시",
        encoding="euc-kr",
        fetch="requests",
        enabled=True,
        note="상주시 대표 지역신문. search_word 및 idx_num 실측 통과",
    ),
    Site(
        name="문경시민신문",
        search_url="http://m.mgnews.kr/list.php",
        search_method="POST",
        search_form_data=(
            ("search_order", "{kw}"),
            ("page", "{page}"),
        ),
        list_item_sel="ul.list_news li, li",
        list_title_sel="a[href*='view.php?idx=']",
        list_date_sel="span.info_date",
        article_date_sel="span.info_date, span.info_date1",
        article_body_sel="div.section_view, #view_con",
        link_contains="view.php?idx=",
        homepage_url="http://mgnews.kr",
        default_area="문경시",
        fetch="requests",
        enabled=True,
        note="문경시 대표 지역신문. 모바일 POST search_order 실측 통과",
    ),
    _iksan_verified("경산신문", "경산시", "http://www.gsinews.com", note="경산시 대표 지역매체. search_list 실측 통과"),
    _iksan_verified("의성군민신문", "의성군", "http://www.usgmnews.com", note="의성군 대표 지역매체. search_list 실측 통과"),
    _iksan_verified("청도신문", "청도군", "http://www.chdnews.com", note="청도군 대표 지역매체. search_list 실측 통과"),
    _iksan_verified("영덕신문(고향신문)", "영덕군", "http://www.ghcyy.kr", note="영덕군 대표 지역매체. search_list 실측 통과"),
    _iksan_verified("포항신문", "포항시", "http://www.phnews.co.kr", note="포항시 대표 지역매체. search_list 실측 통과"),
    Site(
        name="울진뉴스",
        search_url="http://www.uljinnews.co.kr/news/articleList.html?sc_word={kw}&page={page}",
        list_item_sel="ul.type1 li, #section-list li, div.list-block",
        list_title_sel="h4.titles a, a.links",
        list_date_sel="span.byline em:last-child",
        article_date_sel="ul.infomation",
        article_body_sel="#article-view-content-div",
        link_contains="articleView.html",
        homepage_url="http://www.uljinnews.co.kr",
        default_area="울진군",
        fetch="requests",
        enabled=True,
        note="경북 울진군 대표 지역신문. NDSoft GET sc_word 실측 통과",
    ),

    # ══════════════════════════════════════════════════════════════════
    # ── 3. 실측 검증 완료 신규 활성화 매체 (보류 전원 8곳 활성화) ──
    # ══════════════════════════════════════════════════════════════════
    Site(
        name="매일신문",
        search_url="https://search.imaeil.com/RSA/front_new/Search.jsp",
        search_method="POST",
        search_form_data=(
            ("qt", "{kw}"),
        ),
        list_item_sel="div.C_Cts > ul, div.C_Cts ul",
        list_title_sel="li.txt a",
        list_date_sel="",
        article_date_sel="div.date, span.date, .date",
        article_body_sel="div.article_view, div.article_view.v2",
        link_contains="page/view",
        homepage_url="https://www.imaeil.com",
        default_area="대구·경북",
        fetch="requests",
        enabled=True,
        note="대구·경북 최대 일간지. RSA 엔진 POST qt 검색 및 기사 추출 실측 통과",
    ),
    Site(
        name="영남일보",
        search_url="https://www.yeongnam.com/web/ynib/searchNew.php?searchWord={kw}&page={page}",
        list_item_sel="div.newsList01 dl, dl",
        list_title_sel="dt a",
        list_date_sel="span.date, .time",
        article_date_sel="li.article-bottom-input, .article-bottom-input, ul.article-bottom",
        article_body_sel="div.article-news-body, div.article_body, div.article-news-box",
        link_contains="view.php?key=",
        homepage_url="https://www.yeongnam.com",
        default_area="대구·경북",
        fetch="selenium",
        enabled=True,
        note="대구·경북 최고(最古) 일간지. 연합뉴스 OpenAPI 비동기 렌더링 Selenium 실측 통과",
    ),
    Site(
        name="경북매일",
        search_url="https://www.kbmaeil.com/search/detailSearch?searchType=detail&organization=&searchRange=title_subtitle_body_reporterName&storyClass=&searchMedia=all&reporterName=&from=&to=&searchWord1={kw}&searchCondition=and&searchWord2=&sort=post",
        list_item_sel="div.thum_box",
        list_title_sel="h3 a",
        list_date_sel="",
        article_date_sel="div.news_date",
        article_body_sel="div.news_content",
        link_contains="/article/",
        homepage_url="https://www.kbmaeil.com",
        default_area="경상북도",
        fetch="requests",
        enabled=True,
        note="경북 대표 일간지. 검색 결과가 정적 HTML이라 requests 로 수집(2026-10-20 Selenium 목록 0건 문제 수정)",
    ),
    Site(
        name="성주신문",
        search_url="https://www.seongjuro.co.kr/news/search.php?search_order={kw}&page={page}",
        list_item_sel="table tr td, table tr",
        list_title_sel="a[href*='view.php?idx=']",
        list_date_sel="",
        article_date_sel="td.photo1_1, td, span.date",
        article_body_sel="#textinput, #content, td[width='590'], div#content",
        link_contains="view.php?idx=",
        homepage_url="https://www.seongjuro.co.kr",
        default_area="성주군",
        fetch="requests",
        enabled=True,
        note="성주군 대표 지역신문. 공식도메인(seongjuro.co.kr) search.php 125건 실측 통과",
    ),
    Site(
        name="고령신문",
        search_url="http://www.goryeongnews.com/news/articleList.html",
        search_method="POST",
        encoding="euc-kr",
        search_form_data=(
            ("sc_area", "A"),
            ("view_type", "sm"),
            ("sc_word", "{kw}"),
            ("page", "{page}"),
        ),
        list_item_sel="table tr td, table tr, #section-list li, div.list-block",
        list_title_sel="a[href*='articleView.html']",
        list_date_sel="span.byline em:last-child",
        article_date_sel="div.View_Time, .View_Time, ul.infomation",
        article_body_sel="#articleBody, #article-view-content-div",
        link_contains="articleView.html",
        homepage_url="http://www.goryeongnews.com",
        default_area="고령군",
        fetch="requests",
        enabled=True,
        note="고령군 대표 지역신문. 공식도메인(goryeongnews.com) NDSoft EUC-KR POST 20건 실측 통과",
    ),
    Site(
        name="칠곡신문",
        search_url="https://www.ismartnews.com/news/search.php?search_order={kw}&page={page}",
        list_item_sel="ul.list_news2_4 li, div.article_type15 li, li",
        list_title_sel="a[href*='view.php?idx=']",
        list_date_sel="",
        article_date_sel="td.photo1_1, td, span.date",
        article_body_sel="#textinput, #content, div#content",
        link_contains="view.php?idx=",
        homepage_url="https://www.ismartnews.com",
        default_area="칠곡군",
        fetch="requests",
        enabled=True,
        note="칠곡군 대표 지역신문. 공식도메인(ismartnews.com) search.php 41건 실측 통과",
    ),
    Site(
        name="예천신문",
        search_url="http://www.ycnews.co.kr/news/articleList.html",
        search_method="POST",
        search_form_data=(
            ("sc_area", "A"),
            ("view_type", "sm"),
            ("sc_word", "{kw}"),
            ("page", "{page}"),
        ),
        list_item_sel="#section-list li, div.list-block, table tr",
        list_title_sel="h4.titles a, a[href*='articleView.html']",
        list_date_sel="span.byline em:last-child",
        article_date_sel="ul.infomation, ul.info",
        article_body_sel="#article-view-content-div",
        link_contains="articleView.html",
        homepage_url="http://www.ycnews.co.kr",
        default_area="예천군",
        fetch="requests",
        enabled=True,
        note="예천군 대표 지역신문. 공식도메인(ycnews.co.kr) NDSoft POST 20건 실측 통과",
    ),
    Site(
        name="포항시민신문",
        search_url="http://www.phsmnews.com/bbs/search.php?sfl=wr_subject%7C%7Cwr_content&stx={kw}&page={page}",
        list_item_sel="ul.sch_res_list li, div.sch_res_list li, ul.search_list li, li",
        list_title_sel="a[href*='wr_id=']",
        list_date_sel="span.date, .date",
        article_date_sel="ul.art_info, .art_info, div.view_info, .date, li",
        article_body_sel="#news_body_area, #bo_v_con, div.view_con",
        link_contains="wr_id=",
        homepage_url="http://www.phsmnews.com",
        default_area="포항시",
        encoding="euc-kr",
        fetch="requests",
        enabled=True,
        note="포항시 대표 지역신문. 공식도메인(phsmnews.com) 그누보드 41건 실측 통과",
    ),
]

