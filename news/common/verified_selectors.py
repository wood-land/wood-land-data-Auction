# -*- coding: utf-8 -*-
"""검증된 신문사별 설정 레지스트리 (diagnose_dates.py --emit-registry 로 생성, 기존 항목에 합쳐진다. 필요하면 손으로 다듬는다).

Site(name=...) 가 만들어질 때 이 이름이 있으면 여기 값으로 덮어쓴다 (crawler_core.Site.__post_init__).
  article_date_sel : 기사 페이지의 날짜. 기사 N개를 실제로 열어 메타 태그/라벨 날짜와 100% 일치함을 확인했다.
                     메타 선택자가 앞에 오고, 메타가 없는 기사를 위해 눈에 보이는 날짜 요소가 뒤에 올 수 있다(문서에서 먼저 나오는 것이 선택됨).
  list_date_sel    : 검색 목록의 날짜 칸. 표본 기사의 정답 날짜와 100% 일치할 때만 넣었다. 빈 문자열은 "틀린 날짜를 읽으므로 끔".
  newest_first     : False 면 검색 결과가 최신순이 아니라는 뜻 (오래된 기사 연속 종료 규칙을 쓰지 않는다).
"""
from typing import Dict

VERIFIED_SELECTORS: Dict[str, Dict[str, object]] = {
    #  | 2026-10-31 진단
    "무등일보": {"fetch": "requests", "search_method": "GET", "search_url": "https://mdilbo.com/search.html?keyword={kw}&p={page}", "search_form_data": (), "list_item_sel": "ul.headline_lst li", "list_title_sel": "a", "list_title_text_sel": "strong", "list_date_sel": "div.date", "link_contains": "/detail/", "article_date_sel": "span.info_view", "date_basis": "input", "homepage_url": "https://mdilbo.com"},
    # 강원 | 2026-10-31 진단
    "횡성뉴스": {"article_date_sel": "span.view_title_info", "search_builder": "iksan_package", "list_item_sel": "table:has(td.f10_b, td.title_S07):not(:has(table td.f10_b, table td.title_S07))", "list_title_sel": "td.f10_b a, td.title_S07 a", "list_date_sel": "font[color='#517B26']", "search_encoding": "utf-8"},
    # 경기·인천 | 2026-10-31 진단
    "경기신문": {"list_date_sel": "li.date"},
    # 경기·인천 | 2026-10-31 진단
    "고양신문": {"list_date_sel": "span.byline"},
    # 경기·인천 | 2026-10-31 진단
    "광명시민신문": {"list_date_sel": "div.list-dated"},
    # 경기·인천 | 2026-10-31 진단
    "구리남양주뉴스": {"list_date_sel": "em.replace-date"},
    # 경기·인천 | 2026-10-31 진단
    "김포신문": {"list_date_sel": "span.byline"},
    # 경기·인천 | 2026-10-31 진단
    "민안신문": {"list_date_sel": "li.date"},
    # 경기·인천 | 2026-10-31 진단
    "시흥뉴스라인": {"newest_first": False},
    # 경기·인천 | 2026-10-31 진단
    "양주시민방송 YCN": {"newest_first": False},
    # 경기·인천 | 2026-10-31 진단
    "용인시민신문": {"list_date_sel": "span.byline"},
    # 경기·인천 | 2026-10-31 진단
    "의정부신문": {"list_date_sel": "li.date"},
    # 경기·인천 | 2026-10-31 진단
    "이천설봉신문": {"list_date_sel": "span.byline"},
    # 경기·인천 | 2026-10-31 진단
    "파주타임스": {"list_date_sel": "span.byline"},
    # 경기·인천 | 2026-10-31 진단
    "평택시민신문": {"list_date_sel": "span.byline"},
    # 경기·인천 | 2026-10-31 진단
    "하남신문": {"list_date_sel": "span.byline"},
    # 경남·부산 | 2026-10-31 진단
    "거제신문": {"article_date_sel": "meta[property='article:published_time']", "search_method": "GET", "search_url": "http://www.geojenews.co.kr/news/articleList.html?sc_area=A&view_type=sm&sc_word={kw}&page={page}", "search_form_data": ()},
    # 경남·부산 | 2026-10-31 진단
    "경남도민일보": {"article_date_sel": "meta[property='article:published_time']", "search_method": "POST", "search_url": "https://www.idomin.com/news/articleList.html", "search_form_data": (('sc_area', 'A'), ('view_type', 'sm'), ('sc_word', '{kw}'), ('page', '{page}'))},
    # 경남·부산 | 2026-10-31 진단
    "경남매일": {"article_date_sel": "meta[property='article:published_time']", "list_date_sel": "div.list-dated"},
    # 경남·부산 | 2026-10-31 진단
    "경남신문": {"article_date_sel": "li.loca_left", "search_adapter": "knnews_json", "list_item_sel": "li.it", "list_title_sel": "a", "list_date_sel": "span.d"},
    # 경남·부산 | 2026-10-31 진단
    "경남일보": {"article_date_sel": "ul.article-info.no-bullet", "date_basis": "modified_first"},
    # 경남·부산 | 2026-10-31 진단
    "고성신문": {"article_date_sel": "span.view_title_info", "search_builder": "iksan_package", "list_item_sel": "table:has(td.f10_b, td.title_S07):not(:has(table td.f10_b, table td.title_S07))", "list_title_sel": "td.f10_b a, td.title_S07 a", "list_date_sel": "font[color='#517B26']", "search_encoding": "utf-8"},
    # 경남·부산 | 2026-10-31 진단
    "뉴스사천": {"list_date_sel": "em.replace-date"},
    # 경남·부산 | 2026-10-31 진단
    "밀양신문": {"article_date_sel": "meta[property='article:published_time'], p.date"},
    # 경남·부산 | 2026-10-31 진단
    "산청투데이": {"article_date_sel": "meta[property='article:published_time']"},
    # 경남·부산 | 2026-10-31 진단
    "양산신문": {"article_date_sel": "meta[property='article:published_time']"},
    # 경남·부산 | 2026-10-31 진단
    "의령신문": {"search_builder": "iksan_package", "list_item_sel": "table:has(td.f10_b, td.title_S07):not(:has(table td.f10_b, table td.title_S07))", "list_title_sel": "td.f10_b a, td.title_S07 a", "list_date_sel": "font[color='#517B26']", "search_encoding": "utf-8"},
    # 경남·부산 | 2026-10-31 진단
    "주간함양": {"article_date_sel": "meta[property='article:published_time']", "list_date_sel": "div.news_date"},
    # 경남·부산 | 2026-10-31 진단
    "진주신문": {"article_date_sel": "meta[property='article:published_time']"},
    # 경남·부산 | 2026-10-31 진단
    "창녕신문": {"article_date_sel": "span.view_title_info", "search_builder": "iksan_package", "list_item_sel": "table:has(td.f10_b, td.title_S07):not(:has(table td.f10_b, table td.title_S07))", "list_title_sel": "td.f10_b a, td.title_S07 a", "list_date_sel": "font[color='#517B26']", "search_encoding": "utf-8"},
    # 경남·부산 | 2026-10-31 진단
    "함안뉴스": {"list_date_sel": "span.sch_datetime"},
    # 경남·부산 | 2026-10-31 진단
    "합천신문": {"article_date_sel": "p.farm-A-news-view-date"},
    # 경북·대구·울산 | 2026-10-31 진단
    "경북일보": {"list_date_sel": ""},
    # 경북·대구·울산 | 2026-10-31 진단
    "경산신문": {"article_date_sel": "meta[property='article:published_time']", "search_builder": "iksan_package", "list_item_sel": "table:has(td.f10_b, td.title_S07):not(:has(table td.f10_b, table td.title_S07))", "list_title_sel": "td.f10_b a, td.title_S07 a", "list_date_sel": "font[color='#517B26']", "search_encoding": "utf-8"},
    # 경북·대구·울산 | 2026-10-31 진단
    "경상일보": {"article_date_sel": "meta[property='article:published_time']"},
    # 경북·대구·울산 | 2026-10-31 진단
    "경주신문": {"list_date_sel": "div.news_date"},
    # 경북·대구·울산 | 2026-10-31 진단
    "고령신문": {"list_date_sel": "div:nth-child(4)"},
    # 경북·대구·울산 | 2026-10-31 진단
    "구미뉴스": {"newest_first": False},
    # 경북·대구·울산 | 2026-10-31 진단
    "대경일보": {"article_date_sel": "meta[property='article:published_time']"},
    # 경북·대구·울산 | 2026-10-31 진단
    "대구신문": {"article_date_sel": "ul.infomation", "date_basis": "input"},
    # 경북·대구·울산 | 2026-10-31 진단
    "매일신문": {"list_date_sel": "span.wGun"},
    # 경북·대구·울산 | 2026-10-31 진단
    "문경시민신문": {"newest_first": False},
    # 경북·대구·울산 | 2026-10-31 진단
    "봉화일보": {"article_date_sel": "meta[property='article:published_time']"},
    # 경북·대구·울산 | 2026-10-31 진단
    "성주신문": {"article_date_sel": "meta[property='article:published_time']"},
    # 경북·대구·울산 | 2026-10-31 진단
    "안동인터넷뉴스": {"article_date_sel": "meta[property='article:published_time']"},
    # 경북·대구·울산 | 2026-10-31 진단
    "영덕신문(고향신문)": {"article_date_sel": "meta[property='article:published_time']"},
    # 경북·대구·울산 | 2026-10-31 진단
    "영주시민신문": {"article_date_sel": "meta[property='article:published_time']", "list_date_sel": "em:nth-child(3)"},
    # 경북·대구·울산 | 2026-10-31 진단
    "영천시민신문": {"list_date_sel": "div.list-dated"},
    # 경북·대구·울산 | 2026-10-31 진단
    "예천신문": {"article_date_sel": "meta[property='article:published_time']", "list_date_sel": "div.list-dated"},
    # 경북·대구·울산 | 2026-10-31 진단
    "울산제일일보": {"article_date_sel": "meta[property='article:published_time']", "list_date_sel": "div.list-dated"},
    # 경북·대구·울산 | 2026-10-31 진단
    "울진뉴스": {"search_method": "POST", "search_url": "http://www.uljinnews.co.kr/news/articleList.html", "search_form_data": (('sc_word', '{kw}'), ('page', '{page}'))},
    # 경북·대구·울산 | 2026-10-31 진단
    "의성군민신문": {"article_date_sel": "span.view_title_info"},
    # 경북·대구·울산 | 2026-10-31 진단
    "청도신문": {"article_date_sel": "meta[property='article:published_time']", "search_builder": "iksan_package", "list_item_sel": "table:has(td.f10_b, td.title_S07):not(:has(table td.f10_b, table td.title_S07))", "list_title_sel": "td.f10_b a, td.title_S07 a", "list_date_sel": "font[color='#517B26']", "search_encoding": "utf-8"},
    # 경북·대구·울산 | 2026-10-31 진단
    "칠곡신문": {"article_date_sel": "meta[property='article:published_time']", "search_builder": "ismart_package", "search_encoding": "utf-8", "list_item_sel": "div.article_type15 ul.list_news2_4 li", "list_title_sel": "a", "list_title_text_sel": "div.news_tit", "list_date_sel": "div.news_date", "article_body_sel": "[itemprop='articleBody']"},
    # 경북·대구·울산 | 2026-10-31 진단
    "포항신문": {"article_date_sel": "meta[property='article:published_time']"},
    # 전라·광주 | 2026-10-31 진단
    "광양신문": {"list_date_sel": "div.list-dated"},
    # 전라·광주 | 2026-10-31 진단
    "목포시민신문": {"list_date_sel": "div.list-dated"},
    # 전라·광주 | 2026-10-31 진단
    "부안독립신문": {"list_date_sel": "em.replace-date"},
    # 전라·광주 | 2026-10-31 진단
    "완도신문": {"list_date_sel": "span.byline"},
    # 전라·광주 | 2026-10-31 진단
    "익산신문": {"search_builder": "iksan_package", "list_item_sel": "table:has(td.f10_b, td.title_S07):not(:has(table td.f10_b, table td.title_S07))", "list_title_sel": "td.f10_b a, td.title_S07 a", "list_date_sel": "font[color='#517B26']", "search_encoding": "euc-kr"},
    # 전라·광주 | 2026-10-31 진단
    "전북일보": {"search_adapter": "jjan_rest", "article_date_sel": "div.byline_info_wrap", "list_item_sel": "li.it", "list_title_sel": "a", "list_date_sel": "span.d"},
    # 전라·광주 | 2026-10-31 진단
    "정읍신문": {"list_date_sel": "div.byline"},
    # 전라·광주 | 2026-10-31 진단
    "해남신문": {"list_date_sel": "em.replace-date"},
    # 충청·대전·세종 | 2026-10-31 진단
    "계룡일보": {"list_date_sel": "em.replace-date", "homepage_url": "https://www.krdaily.co.kr", "search_url": "https://www.krdaily.co.kr/news/articleList.html?sc_area=A&view_type=sm", "article_date_sel": "ul.info.no-bullet"},
    # 충청·대전·세종 | 2026-10-31 진단
    "괴산타임즈": {"article_date_sel": "meta[property='article:published_time']", "search_method": "POST", "search_url": "https://www.goesantimes.com/news/articleList.html", "search_form_data": (('sc_area', 'A'), ('view_type', 'sm'), ('sc_word', '{kw}'), ('page', '{page}'))},
    # 충청·대전·세종 | 2026-10-31 진단
    "금산신문": {"article_date_sel": "li.date", "search_method": "GET", "search_url": "http://www.igsnews.co.kr/news/articleList.html?sc_area=A&view_type=sm&sc_word={kw}&page={page}", "search_form_data": (), "encoding": "euc-kr", "list_item_sel": "table:has(td.list-titles):not(:has(table td.list-titles))", "list_title_sel": "td.list-titles a", "list_date_sel": "td.list-times", "article_body_sel": "#articleBody"},
    # 충청·대전·세종 | 2026-10-31 진단
    "논산포커스": {"newest_first": False},
    # 충청·대전·세종 | 2026-10-31 진단
    "대전일보": {"list_date_sel": "span.byline"},
    # 충청·대전·세종 | 2026-10-31 진단
    "세종포스트": {"article_date_sel": "meta[property='article:published_time']"},
    # 충청·대전·세종 | 2026-10-31 진단
    "아산투데이": {"article_date_sel": "meta[property='article:published_time'], div.writer_time", "list_date_sel": "dd.etc"},
    # 충청·대전·세종 | 2026-10-31 진단
    "주간영동": {"search_method": "POST", "search_url": "https://www.weeklyyd.com/news/articleList.html", "search_form_data": (('sc_area', 'A'), ('view_type', 'sm'), ('sc_word', '{kw}'), ('page', '{page}'))},
    # 충청·대전·세종 | 2026-10-31 진단
    "천안신문": {"article_date_sel": "ul.art_info"},
    # 충청·대전·세종 | 2026-10-31 진단
    "충북일보": {"article_date_sel": "meta[property='article:published_time']", "list_date_sel": "", "newest_first": False},
    # 충청·대전·세종 | 2026-10-31 진단
    "충주신문": {"article_date_sel": "div.writer_time", "list_date_sel": "dd.etc"},
    # 충청·대전·세종 | 2026-10-31 진단
    "충청투데이": {"list_date_sel": "span.byline"},
    # 충청·대전·세종 | 2026-10-31 진단
    "태안신문": {"list_date_sel": "span.byline"},
    # 충청·대전·세종 | 2026-10-31 진단
    "홍성신문": {"article_date_sel": "meta[property='article:published_time']", "search_method": "POST", "search_url": "http://www.hsnews.co.kr/news/articleList.html", "search_form_data": (('sc_area', 'A'), ('view_type', 'sm'), ('sc_word', '{kw}'), ('page', '{page}'))},
}
