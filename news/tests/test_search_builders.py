import os, sys, base64
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from urllib.parse import quote
from common.crawler_core import Crawler, Settings, Site, parse_list
from common.search_builders import iksan_package
from common.verified_selectors import VERIFIED_SELECTORS as V


def site(**kw):
    base = dict(name="레지스트리에 없는 신문", search_url="http://www.iksannews.com/default/search_list.php?search_order={kw}&page={page}",
                list_item_sel="x", list_title_sel="a", list_date_sel="", article_date_sel="x", article_body_sel="b")
    base.update(kw)
    return Site(**base)


def test_first_page_uses_the_keyword_in_the_sites_encoding():
    # 사용자가 알려 준 익산신문의 실제 검색 주소와 같아야 한다
    u = iksan_package(site(search_encoding="euc-kr"), "보상", 1)
    assert u == ("http://www.iksannews.com/default/search_list.php?s_mode=1&area_part=&time=1&start_day=&end_day=&part_idx="
                 "&search_order=%BA%B8%BB%F3")
    assert "search_order=" + quote("보상") in iksan_package(site(search_encoding="utf-8"), "보상", 1)


def test_later_pages_use_base64_board_data_with_20_per_page():
    u = iksan_package(site(search_encoding="euc-kr"), "보상", 2)
    # 사이트가 만든 '[2]' 링크와 같은 board_data / search_items 여야 한다
    assert "board_data=c3RhcnRQYWdlJTNEMjA=||" in u
    items = u.split("search_items=")[1].rstrip("|")
    assert base64.b64decode(items).decode() == ("part_idx%3D%26mult%3D%26group_id%3D%26s_mode%3D1%26reporter%3D%26start_day%3D%26end_day%3D"
                                                "%26search_order%3D%BA%B8%BB%F3%26area_part%3D")
    assert "board_data=c3RhcnRQYWdlJTNENDA=||" in iksan_package(site(search_encoding="euc-kr"), "보상", 3)       # startPage 40
    assert "board_data=c3RhcnRQYWdlJTNEMA==||" not in u


def test_search_encoding_falls_back_to_encoding_then_euc_kr():
    assert "%BA%B8%BB%F3" in iksan_package(site(), "보상", 1)
    assert "%BA%B8%BB%F3" in iksan_package(site(encoding="euc-kr"), "보상", 1)


class Cap:
    def __init__(self):
        self.urls = []

    def get(self, url, wait_selector=None, timeout=10, strict=False, encoding=""):
        self.urls.append(url)
        return "<html></html>"


def test_fetch_search_page_uses_the_builder():
    c = Crawler(Settings(save_directory=os.devnull, keywords=["보상"]))
    cap = Cap()
    url, _ = c.fetch_search_page(site(search_builder="iksan_package", search_encoding="euc-kr"), "보상", 2, cap)
    assert url == cap.urls[0] and "board_data=" in url


# 결과 항목 구조 (익산신문 계열 두 가지: td.f10_b / td.title_S07)
def item(cls, idx, title, date):
    return (f'<table><tr><td class="{cls}"><a href="index_view_page.php?part_idx=170&idx={idx}">{title}</a></td></tr>'
            f'<tr><td>요약 …<br/><font color="#517B26">[ {date}]</font></td></tr></table>')


WIDGET = '<div id="hot_issue_rolling"><span><a href="index_view_page.php?part_idx=265&idx=1">위젯 기사</a></span></div>'


def test_result_items_ignore_home_widgets_and_read_dates():
    for name, cls in (("익산신문", "f10_b"), ("경산신문", "title_S07")):
        s = site(**{k: v for k, v in V[name].items() if k in ("list_item_sel", "list_title_sel", "list_date_sel")})
        page = f"<html><body>{WIDGET}<table><tr><td>{item(cls, 10, '결과 하나', '2026년 10월 15일')}{item(cls, 11, '결과 둘', '2026년 10월 14일')}</td></tr></table></body></html>"
        items = parse_list(page, "http://t/default/search_list.php", s)
        assert [i["title"] for i in items] == ["결과 하나", "결과 둘"], name         # 위젯 기사는 빠진다
        assert "2026년 10월 15일" in items[0]["list_date"]


def test_family_registry_entries():
    for name in ("익산신문", "의령신문", "경산신문", "고성신문", "청도신문", "창녕신문", "횡성뉴스"):
        assert V[name]["search_builder"] == "iksan_package", name
    assert V["익산신문"]["search_encoding"] == "euc-kr" and V["의령신문"]["search_encoding"] == "utf-8"


# ---- 칠곡신문 (ismartnews.com) ----
from common.search_builders import ismart_package
from common.crawler_core import parse_article


def test_chilgok_urls_match_the_site():
    s = site(search_url="https://www.ismartnews.com/news/search.php?search_order={kw}&page={page}", search_encoding="utf-8")
    assert ismart_package(s, "보상", 1) == "https://www.ismartnews.com/news/search.php?search_order=" + quote("보상")
    u = ismart_package(s, "보상", 2)
    assert "board_data=c3RhcnRQYWdlJTNEMjA=||" in u                       # 사이트의 '[2]' 링크와 같은 값
    items = base64.b64decode(u.split("search_items=")[1].rstrip("|")).decode()
    assert items == ("part_idx%3D%26mult%3D%26group_id%3D%26s_mode%3D%26reporter%3D%26start_day%3D%26end_day%3D%26search_order%3D"
                     "%EB%B3%B4%EC%83%81%26area_part%3D%26search_old%3D%26writer%3D%26writer_name%3D%26day_auto%3D")


CARD = ('<div class="article_type15"><div class="news_cate1_6"><div class="title"><strong>보상</strong> 검색</div></div><ul class="list_news2_4">'
        '<li><a href="https://www.ismartnews.com/news/view.php?idx=53167"><div class="thumbnail"></div><div class="txt_news">'
        '<div class="news_tit"><strong>칠곡군, 제1회 추경 편성</strong></div><p>요약 문장입니다 …</p>'
        '<div class="news_date"><span>스마트뉴스 편집국 기자</span> 2026/09/03 18:35</div></div></a></li></ul></div>')


def test_card_link_title_comes_from_the_title_element_only():
    from common.crawler_core import parse_list_date
    s = site(**{k: V["칠곡신문"][k] for k in ("list_item_sel", "list_title_sel", "list_title_text_sel", "list_date_sel")})
    items = parse_list(f"<html><body>{CARD}</body></html>", "https://www.ismartnews.com/news/search.php", s)
    assert items[0]["title"] == "칠곡군, 제1회 추경 편성"                  # 요약·날짜까지 섞이면 안 된다
    assert parse_list_date(items[0]["list_date"]) == "2026-09-03"


def test_chilgok_article_date_and_body_from_raw_html():
    # 서버가 주는 원본 HTML 에는 눈에 보이는 날짜 블록이 없고 메타 태그만 있다
    html = ("<html><head><meta property='article:published_time' content='2026-08-03T20:13:54+00:00' />"
            "<meta property='article:modified_time' content='2026-08-03T20:13:54+00:00' /></head><body>"
            "<div itemprop='articleBody'>&nbsp;칠곡군은 지난달 31일 약목면사무소에서 보상 설명회를 열었다. 후용리 1153번지 일원이다.</div></body></html>")
    s = site(**{k: V["칠곡신문"][k] for k in ("article_date_sel", "article_body_sel")})
    art = parse_article(html, s)
    assert art["input_date"] == "2026-08-03" and "후용리 1153번지" in art["body"]


def test_geumsan_uses_euc_kr_get_like_estimes():
    g = V["금산신문"]
    assert g["encoding"] == "euc-kr" and g["search_method"] == "GET" and "{kw}" in g["search_url"] and "{page}" in g["search_url"]
