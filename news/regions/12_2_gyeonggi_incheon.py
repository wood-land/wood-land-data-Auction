"""Verified crawler settings for Gyeonggi and Incheon local newspapers.

Only outlets whose live search and article pages were checked are enabled.
The other municipality outlets remain listed with their homepages and an
explicit reason until their search flow and extraction selectors are verified.
"""
from crawler_core import Site

REGION_NAME = "경기·인천"

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
        list_date_sel="",  # Verified sites expose the canonical date on article pages.
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


def _icms_verified(name: str, area: str, homepage: str, menu_id: str, note: str = "") -> Site:
    search_url = f"{homepage.rstrip('/')}/index.do?menu_id={menu_id}"
    return Site(
        name=name,
        search_url=search_url,
        list_item_sel="ul#newsList > li",
        list_title_sel="a[href*='ARTICLE_']",
        list_date_sel="",
        article_date_sel="#newsView p.date",
        article_body_sel="#newsView div.news",
        link_contains="ARTICLE_",
        fetch="requests",
        search_method="POST",
        search_form_data=(("q", "{kw}"), ("pageIndex", "{page_index}")),
        homepage_url=homepage,
        default_area=area,
        enabled=True,
        note=note or "POST q 검색 결과 및 기사 날짜(#newsView p.date)/본문(#newsView div.news) 확인",
    )


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


# Live verified: keyword search, first result article date and article body.
SITES: list[Site] = [
    # 광역 대표 신문 (레거시 이식)
    Site(
        name="경기신문",
        search_url="https://www.kgnews.co.kr/news/search_result.html?search={kw}&page={page}",
        list_item_sel="ul.art_list_all li",
        list_title_sel="a[href*='article.html?no=']",
        list_date_sel="",
        article_date_sel="ul.art_info",
        article_body_sel="#news_body_area",
        homepage_url="https://www.kgnews.co.kr/",
        default_area="경기도",
        fetch="requests",
        search_method="GET",
        enabled=True,
        note="경기 전역 대표 일간지 (레거시 12_202 이식). GET search 검색 결과 및 ul.art_info 등록일, #news_body_area 본문 추출 확인",
    ),
    Site(
        name="기호일보",
        search_url="https://www.kihoilbo.co.kr/news/articleList.html?sc_area=A&view_type=sm&sc_word={kw}&page={page}",
        list_item_sel="li.altlist-webzine-item",
        list_title_sel="h2.altlist-subject a",
        list_date_sel="",
        article_date_sel="meta[property='article:published_time']",
        article_body_sel="#article-view-content-div",
        homepage_url="https://www.kihoilbo.co.kr/",
        default_area="인천·경기",
        fetch="selenium",
        search_method="GET",
        enabled=True,
        note="인천·경기 대표 일간지 (레거시 12_201 이식). 동적 렌더링으로 fetch='selenium' 사용; li.altlist-webzine-item 및 기사 published_time/본문 확인",
    ),

    # 시·군별 지역신문
    _pending("인천in", "인천광역시", "https://www.incheonin.com/",
             "HTTP/HTTPS POST가 시간 초과되고 홈페이지에 CAPTCHA 위젯이 표시됨; 풀지 않고 중단"),
    _verified("용인시민신문", "용인시", "https://www.yongin21.co.kr/", "POST",
              "#section-list li", "POST sc_word 검색 결과(보상 1,986건/대조 0건) 및 기사 published_time/본문 확인"),
    Site(
        name="수원신문",
        search_url="http://www.suwon.com/news/articleList.html",
        list_item_sel="div.list-block",
        list_title_sel="div.list-titles a",
        list_date_sel="div.list-dated",
        article_date_sel="meta[property='article:published_time']",
        article_body_sel="#article-view-content-div",
        homepage_url="http://www.suwon.com/",
        default_area="수원시",
        fetch="requests",
        search_method="POST",
        search_form_data=(("sc_area", "A"), ("view_type", "sm"),
                          ("sc_word", "{kw}"), ("page", "{page}")),
        enabled=True,
        note="일반 브라우저에서 검색 폼 클릭 확인. HTTPS 인증서 오류로 공식 HTTP 홈페이지 사용; POST 보상 20건/대조 0건, 기사 날짜·본문 확인",
    ),
    _verified("고양신문", "고양시", "https://www.mygoyang.com/", "POST",
              "#section-list ul.type2 > li",
              "POST 검색 결과 및 기사 published_time/본문 확인"),
    _pending("화성신문", "화성시", "https://www.sydmznews.com/", "HTTP/HTTPS 접속 불가(404); 도메인/서버 확인 필요"),
    Site(
        name="성남도시신문",
        search_url=("http://www.sungnammail.co.kr/bbs/search.php"
                    "?sfl=wr_subject%7C%7Cwr_content&sop=and&stx={kw}"),
        list_item_sel="div.sch_tit",
        list_title_sel="a[href*='wr_id=']",
        list_date_sel="",
        article_date_sel="strong.if_date",
        article_body_sel="#bo_v_con",
        link_contains="wr_id=",
        homepage_url="http://www.sungnammail.co.kr/",
        default_area="성남시",
        fetch="requests",
        search_method="GET",
        max_pages=1,
        enabled=True,
        note="일반 브라우저에서 게시판 폼 클릭 확인. HTTPS 자체서명으로 공식 HTTP 홈페이지 사용; GET 보상 10건/대조 0건, 2자리 연도 날짜 및 본문 확인",
    ),
    _pending("더부천", "부천시", "https://www.thebucheon.com/", "HTTPS 403, HTTP 응답은 빈 페이지(검색 폼/기사 없음)"),
    _icms_verified("남양주신문", "남양주시", "http://www.nyji.co.kr", "00000521",
                   "POST q 검색 결과(보상 34건) 및 기사 날짜/본문(#newsView div.news) 확인"),
    _pending("안산신문", "안산시", "https://www.ansansm.co.kr/", "도메인 접속 불가(404)"),
    _verified("평택시민신문", "평택시", "https://www.pttimes.com/", "POST",
              "#section-list ul.type2 > li",
              "POST 검색 결과 및 기사 published_time/본문 확인"),
    _icms_verified("안양광역신문", "안양시", "http://www.anyangnews.net", "00000561",
                   "POST q 검색 결과(보상 34건) 및 기사 날짜/본문(#newsView div.news) 확인"),
    Site(
        name="시흥뉴스라인",
        search_url="https://newsline.seoul.kr/?s={kw}",
        list_item_sel="article",
        list_title_sel="h2.entry-title a",
        list_date_sel="",
        article_date_sel="meta[property='article:published_time']",
        article_body_sel=".entry-content",
        homepage_url="https://newsline.seoul.kr/",
        default_area="시흥시",
        fetch="requests",
        search_method="GET",
        max_pages=1,
        enabled=True,
        note="WordPress 공개 검색 10건/대조 0건; 기사 published_time 및 entry-content 추출 확인",
    ),
    _verified("김포신문", "김포시", "https://www.igimpo.com/", list_selector="#section-list ul.type2 > li",
              note="POST sc_word 검색 결과 및 기사 published_time/본문 확인"),
    _verified("파주타임스", "파주시", "https://www.pajutimes.com/", "POST",
              "#section-list li", "POST sc_word 검색 결과(보상 20건/대조 0건) 및 기사 published_time/본문 확인"),
    Site(
        name="의정부신문",
        search_url="https://www.ujbnews.net/news/search_result.html?search={kw}&page={page}",
        list_item_sel="ul.art_list_all li",
        list_title_sel="a[href*='article.html?no=']",
        list_date_sel="",
        article_date_sel="ul.art_info",
        article_body_sel="#news_body_area",
        homepage_url="https://www.ujbnews.net/",
        default_area="의정부시",
        fetch="requests",
        search_method="GET",
        enabled=True,
        note="GET search 검색 결과(토지 54건) 및 ul.art_info 날짜, #news_body_area 본문 추출 확인",
    ),
    _pending("광주시민저널", "광주시(경기)", "http://www.gjcitizen.com/", "검색 search.php 엔드포인트에서 기사 결과 미출력"),
    _verified("광명시민신문", "광명시", "https://www.kmtimes.net/", "POST",
              "div.list-block",
              "POST 검색 결과 및 기사 published_time/본문 확인"),
    _verified("하남신문", "하남시", "https://www.ehanam.net/",
              note="POST sc_word 검색 결과 및 기사 published_time/본문 확인"),
    _icms_verified("군포신문", "군포시", "http://www.gunponews.net", "00000581",
                   "POST q 검색 결과(보상 34건) 및 기사 날짜(#newsView p.date)/본문(#newsView div.news) 확인"),
    _pending("오산신문", "오산시", "http://www.osannews.co.kr/", "HTTPS 인증서 오류, HTTP 응답은 제목/검색 폼 없는 빈 페이지"),
    _verified("이천설봉신문", "이천시", "https://www.2000news.com/",
              note="POST sc_word 검색 결과 및 기사 published_time/본문 확인"),
    Site(
        name="민안신문",
        search_url="https://www.minan21c.com/news/search_result.html?search={kw}",
        list_item_sel="ul.art_list_all li",
        list_title_sel="a[href*='article.html?no=']",
        list_date_sel="",
        article_date_sel="ul.art_info",
        article_body_sel="div.bw_last .column.col73",
        homepage_url="https://www.minan21c.com/",
        default_area="안성시",
        fetch="requests",
        search_method="GET",
        max_pages=1,
        enabled=True,
        note="자체 검색 20건/대조 0건; 등록일과 기사 본문 컨테이너 추출 확인",
    ),
    _verified("구리남양주뉴스", "구리시", "https://www.gnnews.org/",
              note="POST sc_word 검색 결과 및 기사 published_time/본문 확인"),
    _verified("의왕미디어저널", "의왕시", "https://www.uiwangmedia.com/", "POST",
              "div.list-block",
              "POST 검색 결과 및 기사 published_time/본문 확인"),
    _pending("포천신문", "포천시", "http://www.ipcs21.com/", "HTTP 검색 폼(search_list.php)에서 기사 결과 미출력"),
    Site(
        name="양주시민방송 YCN",
        search_url="https://www.ycn.ne.kr/search?q={kw}",
        list_item_sel="div.post-outer",
        list_title_sel="h3.post-title a",
        list_date_sel="",
        article_date_sel="time.published",
        article_body_sel=".post-body",
        homepage_url="https://www.ycn.ne.kr/",
        default_area="양주시",
        fetch="requests",
        search_method="GET",
        max_pages=1,
        enabled=True,
        note="Blogger 검색 1건/대조 0건; time[datetime] 게시일과 post-body 본문 확인",
    ),
    _verified("여주신문", "여주시", "https://www.yeojunews.co.kr/",
              note="POST sc_word 검색 결과 및 기사 published_time/본문 확인"),
    _verified("양평시민의소리", "양평군", "https://www.ypsori.com/",
              note="POST sc_word 검색 결과 및 기사 published_time/본문 확인"),
    _icms_verified("가평타임즈", "가평군", "http://www.gp21.com", "00000541",
                   "POST q 검색 결과(보상 34건) 및 기사 날짜(#newsView p.date)/본문(#newsView div.news) 확인"),
    _verified("연천뉴스", "연천군", "https://www.yeoncheonnews.com/",
              note="POST sc_word 검색 결과 및 기사 published_time/본문 확인"),
    _verified("한북신문(동두천권)", "동두천시", "https://www.hbnews.kr/", "POST",
              "div.list-block",
              "POST 검색 결과 및 기사 published_time/본문 확인"),
    _pending("과천문화신문", "과천시", "https://gcmunhwa.com/", "도메인이 호스팅 서비스의 기간 만료 안내로 이동"),
]
