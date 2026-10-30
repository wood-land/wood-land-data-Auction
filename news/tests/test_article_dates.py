import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.crawler_core import Site, parse_article, parse_article_dates, parse_article_dates_ex


def site(date_sel):
    return Site(name="t", search_url="u", list_item_sel="x", list_title_sel="x", list_date_sel="x",
                article_date_sel=date_sel, article_body_sel="#body")


BODY = "<div id='body'>본문 " + "가나다라마바사 " * 10 + "</div>"


def page(header_clock="", meta="", article_info="", extra=""):
    return f"<html><head>{meta}</head><body><p><span class='clock'>{header_clock}</span></p>{article_info}{BODY}{extra}</body></html>"


# ---- 실제로 잘못 읽히던 구조 (충주신문·아산투데이: 머리말 시계가 먼저 잡힘) ----
def test_header_clock_is_not_the_article_date_when_meta_exists():
    html = page(header_clock="2026.10.30 [14:44]",
                meta="<meta property='article:published_time' content='2024-01-05T09:25:00+09:00'>"
                     "<meta property='article:modified_time' content='2024-01-05T09:25:00+09:00'>",
                article_info="<ul class='info'><li>기자</li></ul>")
    art = parse_article(html, site("span, td, div"))            # 선택자가 넓어서 머리말 시계(span.clock)가 먼저 잡힌다
    assert art["input_date"] == "2024-01-05"
    assert art["date_source"] == "메타"
    assert art["date_conflict"] == "선택자 날짜 2026-10-30 ≠ 메타 날짜 2024-01-05"


def test_labeled_date_in_selected_element_wins():
    html = page(header_clock="2026.10.30 [14:44]",
                meta="<meta property='article:published_time' content='2020-01-01T00:00:00+09:00'>",
                article_info="<ul class='infomation'><li>입력 2026.10.28 16:45</li><li>수정 2026.10.29 09:00</li></ul>")
    art = parse_article(html, site("ul.infomation"))
    assert (art["input_date"], art["modified_date"], art["date_source"]) == ("2026-10-28", "2026-10-29", "선택자(라벨)")
    assert art["date_conflict"] == ""


def test_unlabeled_selector_date_used_only_as_last_resort():
    html = page(article_info="<span class='date'>2026-10-20 10:00</span>")
    art = parse_article(html, site("span.date"))
    assert art["input_date"] == "2026-10-20" and art["date_source"] == "선택자(라벨 없음)"


def test_meta_selector_itself_still_works():
    # article_date_sel 이 메타 태그인 신문사(경기 30곳)
    html = page(meta="<meta property='article:published_time' content='2026-10-15T08:00:00+09:00'>")
    art = parse_article(html, site("meta[property='article:published_time']"))
    assert art["input_date"] == "2026-10-15" and art["date_conflict"] == ""


def test_json_ld_is_a_meta_source():
    ld = '<script type="application/ld+json">{"@type":"NewsArticle","datePublished":"2023-05-02T10:00:00+09:00","dateModified":"2023-05-03T10:00:00+09:00"}</script>'
    art = parse_article(page(header_clock="2026.10.30", extra=ld), site("span.clock"))
    assert (art["input_date"], art["modified_date"]) == ("2023-05-02", "2023-05-03")


def test_no_date_anywhere():
    art = parse_article(page(), site("ul.nothing"))
    assert art["input_date"] is None and art["date_source"] == ""


def test_parse_article_dates_backward_compatible_and_label_flag():
    assert parse_article_dates("입력 : 2026-09-17 00:05:00 수정 : 2026-09-17 00:06:17") == ("2026-09-17", "2026-09-17")
    assert parse_article_dates_ex("입력 2026.09.18 16:45")[2] is True
    assert parse_article_dates_ex("2026.10.30 [14:44]") == ("2026-10-30", None, False)


# ---- 공주신문: 클래스 없는 표 레이아웃 (실제 페이지의 날짜 줄 그대로) ----
GONGJU_DATE_ROW = '''<table><tbody><tr>
<td width="5"><img src="x.gif" width="11" height="25"></td>
<td bgcolor="EFEFEF"><span style="font-size:8pt;"><font face="돋움" color="#666666">[1535호] 2026년 08월 27일 (목) 17:40:07</font></span></td>
<td align="right" bgcolor="EFEFEF"> <span><font face="돋움" color="#666666">이석하 기자</font>
<a href="mailto.html?mail=lshview@hanmail.net"><font face="arial">lshview@hanmail.net</font></a></span></td>
<td width="5"><img src="y.gif" width="11" height="25"></td></tr></tbody></table>'''


def test_gongju_date_cell_not_header_clock_and_not_reporter_cell():
    header = "<table><tr><td><b>2026.10.26 월 22:19</b></td></tr></table>"      # 머리말의 갱신 시각 (예전 선택자가 잡던 것)
    art = parse_article(f"<html><body>{header}{GONGJU_DATE_ROW}{BODY}</body></html>", site('td[bgcolor="EFEFEF"]'))
    assert art["input_date"] == "2026-08-27"


def test_guminews_art_info_label():
    info = '<ul class="art_info"><li><a><span class="sv_member">임양춘 대표기자</span></a></li><li>등록 2023.12.11 14:15</li><li>조회수 307</li></ul>'
    nav = '<p class="today_text">2026.10.30 (금)</p>'                           # 상단 메뉴의 오늘 날짜 (예전 선택자가 잡던 것)
    art = parse_article(f"<html><body>{nav}{info}{BODY}</body></html>", site("ul.art_info"))
    assert (art["input_date"], art["date_source"]) == ("2023-12-11", "선택자(라벨)")


# ---- 라벨 뒤에 '일'이 붙는 표기 (경북매일 '등록일', 함안뉴스 '작성일') ----
def test_label_with_il_suffix_is_recognized():
    assert parse_article_dates_ex("등록일 2026-10-20 14:24 게재일 2026-10-21 9면") == ("2026-10-20", None, True)
    assert parse_article_dates_ex("작성일 2026-07-27 17:32") == ("2026-07-27", None, True)


def test_kbmaeil_uses_registration_date_not_print_date():
    info = '<div class="news_date"><span>등록일\n 2026-10-20 14:24</span><span>게재일\n 2026-10-21</span><span class="myun">9면</span></div>'
    nav = "<span class='clock'>2026.10.30</span>"
    art = parse_article(f"<html><body>{nav}{info}{BODY}</body></html>", site("div.news_date"))
    assert (art["input_date"], art["date_source"]) == ("2026-10-20", "선택자(라벨)")      # 게재일(지면 날짜)이 아니라 등록일


def test_uiryeong_view_title_info():
    info = '<span class="view_title_info"><span class="view_title_name">의령신문</span> 기자 / urnews21@hanmail.net 입력 : 2026년 09월 28일 </span>'
    nav = "<td>2026.10.30</td><div>2026.10.30</div>"            # 예전 선택자('td, span, div')가 먼저 잡던 것
    art = parse_article(f"<html><body>{nav}{info}{BODY}</body></html>", site("span.view_title_info"))
    assert art["input_date"] == "2026-09-28"


def test_hamannews_icon_between_label_and_date():
    info = '<strong class="if_date"><span class="sound_only">작성일</span><i class="fa fa-clock-o" aria-hidden="true"></i> 2026-07-27 17:32</strong>'
    art = parse_article(f"<html><body>{info}{BODY}</body></html>", site("strong.if_date"))
    assert (art["input_date"], art["date_source"]) == ("2026-07-27", "선택자(라벨)")
