"""
region_gangwon.py - 강원도 신문사 설정

결과 파일: 강원_YYYY-MM-DD.csv (이 파일에 적힌 신문사 전부가 한 CSV에 모인다)
신문사를 추가하려면 SITES 리스트에 Site(...) 블록을 하나 더 적으면 된다.
추가 후에는  python run_crawl.py 강원 --check  로 선택자가 맞는지 먼저 점검할 것.

2026-09-26 이식·실측 메모
--------------------------------------------------
2026-09-26에는 실제 HTML과 검색폼을 직접 요청해 보상 검색과 불가능 대조 검색을 비교했고,
크롤러 `--check`를 현재 활성 사이트에 실행했다. 검색 목록·기사 링크·기사 날짜·본문 선택자는
각 Site 블록의 현재 note와 `LIVE_VALIDATION.md`에 실측 근거를 남겼다. 검색폼 POST 방식인
원주신문·태백인터넷신문은 공통 엔진에 POST 제출을 추가해 검색 결과를 확인했다.

또 하나 중요한 구조적 한계: 지금 엔진은 fetch="selenium"이어도 SeleniumFetcher가 하는 일은
`driver.get(search_url)` + 요소 대기뿐이고, 검색창에 값을 입력하거나 버튼을 클릭하는 동작은
하지 않는다. 즉 검색이 "URL의 GET 파라미터만으로" 되지 않고 반드시 입력→버튼 클릭 같은 JS
상호작용이 있어야 필터링되는 사이트는, fetch를 selenium으로 두더라도 지금 구조 그대로는
검색이 되지 않는다. 서버가 검증된 GET/POST를 받으면 `search_method`와 `search_form_data`로
설정하고, 클라이언트 JavaScript 상호작용이 꼭 필요한 사이트는 아직 별도 자동화가 필요하다.
"""
from crawler_core import Site, TEMPLATE_ARTICLEVIEW, site_from

REGION_NAME = "강원"

SITES = [
    # 강원일보 (kwnews.co.kr) - 72_101_강원일보_0919_v2.py 의 설정을 그대로 옮김
    # 검색: 띄어쓴 단어를 모두 포함(AND) / 최신순(sort=post) / 페이지당 20건
    # 2026-09-20: 검색 결과·기사 페이지 모두 서버가 완성된 HTML을 그대로 주는 것을 확인해
    # fetch="requests" 로 변경 (요청 15회 연속 200 OK, 0.2~0.3초/건). 브라우저(Selenium) 렌더링이
    # 필요 없는 사이트라 굳이 Selenium을 쓰면 페이지 로딩/요소 대기 타임아웃 등으로
    # '기사 열기 오류'가 잦았는데, requests로 바꾸면 그 원인 자체가 사라진다.
    Site(
        name="강원일보",
        default_area="강원특별자치도",     # 지역힌트: 기사 주소의 시군구를 정하는 1순위 단서
        search_url=(
            "https://www.kwnews.co.kr/search/detailSearch?searchType=detail&organization="
            "&searchRange=title_subtitle_body_reporterName&storyClass=&searchMedia=all"
            "&reporterName=&from=&to=&searchWord1={kw}&searchCondition=and"
            "&searchWord2=&sort=post&page={page}"
        ),
        list_item_sel="div.regular-story-list div.story-item-box",
        list_title_sel="div.story-heading a",
        list_date_sel="span.date_txt",              # 예: 2026-09-17 [12:05:00]
        article_date_sel="div.date-info",           # 입력 : ... 수정 : ... 지면 : ...
        article_body_sel="[itemprop='articleBody']",
        link_contains="/article/",
        fetch="requests",
    ),

    # 강원도민일보 (kado.net) - 12_101 강원도민일보 0504.py 를 이식
    # 2026-09-26 live check: current homepage is reachable, but the verified form submits to
    # /engine_yonhap/search.php. Official robots.txt disallows /engine_yonhap/ and /search_yonhap/;
    # no allowed keyword-search route has been verified, so keep disabled.
    site_from(
        TEMPLATE_ARTICLEVIEW,
        name="강원도민일보",
        enabled=False,
        disabled_reason="Current homepage search submits to /engine_yonhap/search.php, disallowed by robots.txt; no allowed search endpoint verified.",
        article_date_sel="meta[property='article:published_time']",  # Live DOM contains publication date.
        search_url=(
            "https://prt.kado.net/engine_yonhap/search.php"
            "?picktab=article&searchcont=article&searchword={kw}&page={page}&sort="
        ),
        list_item_sel="div.list div.txtbox",
        list_title_sel="div.title a",
        list_date_sel="ul.info",   # 레거시는 li:nth-child(3)만 읽었지만 날짜는 정규식으로 찾으므로 ul.info 전체로 충분
        link_contains="articleView.html",
        fetch="selenium",
        homepage_url="https://www.kado.net/",
        note=("2026-09-26: current homepage is live and its search form submits to /engine_yonhap/search.php. "
              "Current robots.txt disallows /engine_yonhap/ and /search_yonhap/; do not crawl that route. "
              "No allowed keyword-search endpoint has been verified, so this site remains disabled."),
    ),

    # 원주신문 (iwjnews.com) - 12_111 원주신문 0504.py 를 이식
    # 2026-09-26 실측: GET 검색은 필터링하지 않지만 사이트 폼은 POST를 사용한다.
    # 보상 검색은 20건, 무작위 대조 검색은 0건이었고 목록·기사 날짜·본문 선택자를 확인했다.
    Site(
        name="원주신문",
        default_area="원주시",     # 지역힌트: 기사 주소의 시군구를 정하는 1순위 단서
        search_url="https://www.iwjnews.com/news/articleList.html",
        list_item_sel="div.list-block",
        list_title_sel="div.list-titles a",
        list_date_sel="div.list-dated",             # 실측: 위치 | 기자 | 2026-09-16 19:46
        article_date_sel="div.info-text ul.no-bullet.auto-marbtm-0.line-height-6",
        article_body_sel="div#article-view-content-div",  # 레거시 스크립트 기준(검증됨)
        link_contains="/news/articleView.html",
        fetch="requests",
        search_method="POST",
        search_form_data=(("sc_area", "A"), ("view_type", "sm"),
                          ("sc_word", "{kw}"), ("page", "{page}")),
        homepage_url="https://www.iwjnews.com/",
        note=("2026-09-26 live POST check: the website form uses POST; 보상 returned 20 linked results "
              "and the impossible control returned 0. List date, article date container, and "
              "#article-view-content-div matched. RequestsFetcher submits the verified form."),
    ),

    # 홍천뉴스투데이 (hongcheonnewstoday.kr) - 12_112 홍천뉴스투데이 0504.py 를 이식
    # 2026-09-25 확인: search.html?submit=submit&search_and=1&search_exec=all&search_section=all
    #   &news_order=1&search={kw} 를 실제로 열어본 결과, 검색어 '보상'에 대해 실제로 필터링된
    #   결과(1788건, 상단에 "공무원 초과근무 ... 일한 만큼 보상", "... 사망조위금 인상 ... 보상 예우
    #   강화" 등 '보상' 포함 기사들)가 나오는 것을 확인했다. &page=2 를 붙였을 때도 "현재페이지 2/60"
    #   로 정상적으로 다음 페이지가 나와 페이지네이션도 GET 파라미터만으로 동작함을 확인했다.
    #   목록에서 링크를 열어 기사 페이지(예: https://www.hongcheonnewstoday.kr/101124)도 자바스크립트
    #   렌더링 없이(정적 HTML 조회 도구로) 제목/날짜/본문이 그대로 보이는 것을 확인했다.
    #   → 이 사이트는 requests만으로 검색·페이지네이션·기사 열람이 모두 가능함을 실측으로 확인했다.
    #   다만 이 세션에서는 원본 HTML의 정확한 class/id 문자열을 볼 수 없어(위 파일 상단 메모 참고),
    #   목록 선택자(div.search_result_list_box / dt a / dd.etc)는 레거시 스크립트의 검증된 값을
    #   그대로 옮겼지만, 본문 선택자는 레거시가 "h1 다음의 모든 p 태그"를 이어 붙이는 방식이라
    #   고정된 CSS 컨테이너가 원래 없었다. 아래 article_body_sel은 흔한 패턴을 임시로 넣은
    #   추정값이며 미검증이다 — 로컬에서 --check로 반드시 실제 본문이 읽히는지 확인하고,
    #   틀리면 브라우저 개발자도구로 실제 컨테이너를 찾아 교체할 것.
    Site(
        name="홍천뉴스투데이",
        default_area="홍천군",     # 지역힌트: 기사 주소의 시군구를 정하는 1순위 단서
        search_url=(
            "https://www.hongcheonnewstoday.kr/search.html"
            "?submit=submit&search_and=1&search_exec=all&search_section=all"
            "&news_order=1&search={kw}&page={page}"
        ),
        list_item_sel="div.search_result_list_box",
        list_title_sel="dt a",
        list_date_sel="dd.etc",                      # 예: "기자명 | 2026.08.13 19:43"
        article_date_sel=".writer_time",                    # 미검증(추정) - 실패 시 목록 날짜로 자동 대체됨
        article_body_sel="td.td_sub_read_contents",         # ⚠ 미검증(추정값). 레거시는 "h1 다음 모든 p"라 고정 선택자가 없었음
        link_contains="hongcheonnewstoday.kr",
        fetch="requests",
        note='2026-09-25 live check: query returned 30 items and the impossible control returned 0; .writer_time and td.td_sub_read_contents matched; crawler --check passed.',
    ),

    # 홍천뉴스 (hcsinmoon.co.kr) - 12_113 홍천뉴스 0504.py 를 이식
    # 2026-09-25 확인: articleList.html?sc_area=A&view_type=sm&sc_word={kw} 를 열어봤으나 검색어를
    #   '일대' → '보상'으로 바꿔도 상단 "전체기사 목록 (총 79,695건)"이 동일하고 목록 제목에도
    #   '보상'이 전혀 없어 필터링이 안 되는 것을 확인(원주신문과 같은 증상). 이 사이트의 실제
    #   검색 폼 action은 "/news/search.html" (GET, input name="query")로 보였으나
    #   search.html?query={kw} 로 직접 접속하면 404가 나서(2026-09-25 확인) 이 값도 틀린 것으로
    #   보인다. → 이 사이트의 진짜 검색 엔드포인트를 이번 세션에서는 찾지 못했다.
    #   레거시 선택자(목록/본문)는 원 개발자가 Selenium으로 확인한 값이므로 그대로 옮기되,
    #   검색 URL은 레거시와 동일하게 두고 fetch="selenium" 유지.
    Site(
        name="홍천뉴스",
        enabled=False,
        disabled_reason='Current GET form returns the same 20 items for 보상 and impossible control; query is not filtering.',
        search_url="https://www.hcsinmoon.co.kr/news/articleList.html?sc_area=A&view_type=sm&sc_word={kw}&page={page}",
        list_item_sel="section#section-list ul.type1 > li",
        list_title_sel="h4.titles a",
        list_date_sel="li",
        article_date_sel="ul.infomation",
        article_body_sel="#article-view-content-div",
        link_contains="/news/articleView.html",
        fetch="requests",
        homepage_url="https://www.hcsinmoon.co.kr/",
        note=("2026-09-26 live check: current form action is GET /news/articleList.html and current list/article "
              "selectors were confirmed. However, 보상 and impossible-control requests both returned the same "
              "20 list items, so keyword search is not filtering; keep disabled until a working search route is found."),
    ),

    # 횡성뉴스 (hsgnews.net) - 12_114 횡성뉴스 0504.py 를 이식
    # 2026-09-25 확인: 이 세션의 웹 조회 도구가 http://www.hsgnews.net/ 에 HTTPS로 업그레이드해
    #   접속을 시도하다 SSL 오류(wrong version number)로 실패했다. 즉 이 사이트는 HTTPS를 제대로
    #   지원하지 않을 가능성이 있다(레거시 스크립트도 http:// 로만 접속). 이 세션에서는 http:// 그대로
    #   접속하는 조회 수단이 없어 페이지 자체를 열어보지 못했다.
    #   레거시 스크립트를 보면 검색은 입력창(name=search_order)에 값을 넣고
    #   href="javascript:powersearch();" 링크를 눌러야 실행되는 JS 함수 호출 방식이라, GET
    #   파라미터만으로 되는 URL이 원래 없다(검색 URL 자체가 불명).
    #   → requests는 물론 지금 구조의 selenium(URL만 여는 방식)으로도 검색이 될 가능성이 낮다.
    #   아래 search_url은 흔한 파라미터명을 임시로 넣은 추정값(미검증)이며, 실제로는 동작하지
    #   않을 확률이 높다. 로컬에서 브라우저로 검색 시 진짜 요청 URL을 확인해서 교체할 것.
    Site(
        name="횡성뉴스",
        default_area="횡성군",     # 지역힌트: 기사 주소의 시군구를 정하는 1순위 단서
        search_url="http://www.hsgnews.net/default/search_list.php?search_order={kw}&page={page}",  # ⚠ 미검증 추정 URL
        list_item_sel="td.f10_b",
        list_title_sel="a",
        list_date_sel="font[color='#517B26']",        # 주의: 날짜가 "2026년 4월 15일" 형식이면 crawler_core 정규식(YYYY-MM-DD/.)이 못 읽음
        article_date_sel='tr:has(td.f09_s) > td[width="600"]',      # 미검증(추정)
        article_body_sel="#fontSzArea",                # 레거시 스크립트 기준(검증됨, 단 접속 자체를 재확인 못함)
        link_contains="",
        fetch="requests",
        note='2026-09-25 live check: query returned 20 items and the impossible control returned 0; date and body selectors matched. Plain HTTP works with requests.',
    ),

    # 강릉뉴스 (gangneungnews.kr) - 12_115 강릉뉴스 0511.py 를 이식
    # 2026-09-25 확인: articleList.html?page={page}&sc_area=A&view_type=sm&sc_word={kw} (레거시가
    #   이미 GET 파라미터 형태로 쓰던 URL)를 검색어 '보상'으로 열어봤으나, 결과가 "전체기사 목록
    #   (총 29,674건)"이라는 표시와 함께 강릉/홍천과 전혀 무관한 해외 홍보성 기사들(신화통신
    #   실크로드 등)이 나왔다 → sc_word 파라미터가 실제로는 필터링에 작동하지 않고, 단순 최신
    #   기사(또는 제휴 송고 기사) 목록을 보여주는 것으로 보인다(원주신문·홍천뉴스와 동일 증상).
    #   → 레거시 스크립트가 Selenium으로 성공했던 것은 페이지 로드 후 실제로는 클라이언트 쪽에서
    #   추가 상호작용이 있었거나, 애초에 검증이 느슨했을 가능성이 있다. 이 세션에서는 진짜 검색
    #   메커니즘을 확인하지 못했다.
    Site(
        name="강릉뉴스",
        default_area="강릉시",     # 지역힌트: 기사 주소의 시군구를 정하는 1순위 단서
        search_url="https://www.gangneungnews.kr/news/articleList.html?page={page}&sc_area=A&view_type=sm&sc_word={kw}",
        list_item_sel="#section-list ul.type2 > li",
        list_title_sel="h4.titles a",
        list_date_sel="span.byline",                  # 레거시는 em 3개 중 3번째만 썼지만 정규식이 첫 날짜를 찾으므로 span.byline 전체로 시도
        article_date_sel="ul.infomation",                 # 미검증(추정)
        article_body_sel="#article-view-content-div",
        link_contains="",
        fetch="selenium",
        note='2026-09-25 live check: keyword search returned 20 items and the impossible control returned 0; list, date, and body selectors matched. Earlier no-filter observation should be monitored.',
    ),

    # 삼척동해신문 (sdnews.co.kr / m.sdnews.co.kr) - 12_116 삼척동해신문 0511.py 를 이식
    # 2026-09-26 실측: 사용자 제공 HTTP 홈페이지와 POST 폼은 열리지만, 보상 검색을 제출해도
    # 기사 링크가 반환되지 않았다. 검색 목록 선택자를 검증하지 못해 비활성 유지.
    Site(
        name="삼척동해신문",
        enabled=False,
        disabled_reason='HTTP homepage works, but submitted search form returns no article links; result selector remains unverified.',
        search_url="http://www.sdnews.co.kr/news/articleList.html",
        list_item_sel="ul#articleContainer li.item",
        list_title_sel="div.description h3",           # 주의: 이 선택자에는 <a>가 없을 수 있음 - parse_list()는 a.get("href")가 필요하므로 로컬에서 실제 구조(어느 태그가 링크인지) 재확인 필요
        list_date_sel="p.info span.date",
        article_date_sel="p.info span.date",             # 미검증(추정)
        article_body_sel="div.body.word_break",
        link_contains="",
        fetch="requests",
        search_method="POST",
        search_form_data=(("sc_area", "A"), ("view_type", "sm"), ("sc_word", "{kw}")),
        homepage_url="http://www.sdnews.co.kr/",
        note=("2026-09-26 live check: the user-provided HTTP homepage is reachable (200), and the form submits "
              "POST to /news/articleList.html. Direct POST and headless-browser form submission both returned "
              "no article links for 보상; result selectors are not confirmed. Keep disabled until a real result is found."),
    ),

    # 태백인터넷신문 (tjinews.co.kr) - 12_117 태백인터넷신문 0511.py 를 이식
    # 2026-09-26 재확인: 기존 /default/index.php는 code404로 이동한다. 현행 홈페이지의
    # POST 검색(q)에서 키워드 결과와 기사 본문·날짜를 확인해 새 경로·선택자로 이식했다.
    Site(
        name="태백인터넷신문",
        default_area="태백시",     # 지역힌트: 기사 주소의 시군구를 정하는 1순위 단서
        search_url="http://tjinews.co.kr/index.do?menu_id=00000121",
        list_item_sel="ul#newsList > li",
        list_title_sel="a[href*='ARTICLE_']",
        list_date_sel="",
        article_date_sel="#newsView p.date",
        article_body_sel="#hwpEditorBoardContent",
        link_contains="ARTICLE_",
        fetch="requests",
        search_method="POST",
        search_form_data=(("q", "{kw}"), ("pageIndex", "{page_index}")),
        homepage_url="http://tjinews.co.kr/",
        note=("2026-09-26 live check: the former /default/index.php URL now redirects to code404; "
              "the current homepage POST form at /index.do?menu_id=00000121 uses q. 보상 returned "
              "17 results and the impossible control returned 0. ul#newsList, #newsView p.date, "
              "and #hwpEditorBoardContent matched. The list has no date, so article date is used."),
    ),

    # 영월신문 (yeongwol-news.com) - 12_118 영월신문 0503.py 를 이식
    # 2026-09-25 확인: articleList.html?sc_area=A&view_type=sm&sc_word={kw} 를 검색어 '보상'으로
    #   열어봤으나 상단 "총 34,124건"과 목록(낙화암 복원, 장릉 관람객 등 지역 소식들)이 검색어와
    #   무관하게 항상 동일해 필터링이 안 되는 것을 확인(원주신문 등과 동일 증상). 레거시 스크립트도
    #   검색 아이콘 클릭 → JS로 입력창에 값 채우기 → 버튼 클릭까지 해야 결과가 좁혀지는 방식이라,
    #   지금 구조(URL만 여는 selenium)로는 재현이 안 될 가능성이 높다.
    Site(
        name="영월신문",
        enabled=False,
        disabled_reason='GET sc_word search is ignored; control and keyword searches return same 20 items.',
        search_url="https://www.yeongwol-news.com/news/articleList.html?sc_area=A&view_type=sm&sc_word={kw}&page={page}",
        list_item_sel="section#section-list ul.lists li",
        list_title_sel="h2.titles a",
        list_date_sel="div.byline > div:last-child",    # 주의: "MM-DD" 짧은 형식이면 연도가 없어 crawler_core 날짜 정규식이 못 읽을 수 있음(레거시는 올해 연도를 직접 붙였음)
        article_date_sel="ul.infomation",
        article_body_sel="#article-view-content-div",
        link_contains="",
        fetch="selenium",
        homepage_url="https://www.yeongwol-news.com/",
        note=("2026-09-26 live check: GET form/list/article paths and article date/body selectors are live, but "
              "keyword and impossible-control searches return the same 20 articles. Keep disabled until search filters."),
    ),
]
