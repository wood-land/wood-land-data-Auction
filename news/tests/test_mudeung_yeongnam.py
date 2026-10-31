import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.crawler_core import Site, parse_article, parse_article_dates_ex, parse_list, parse_list_date, pick_reference_date
from common.verified_selectors import VERIFIED_SELECTORS as V
import importlib, glob


def sites():
    out = {}
    for f in sorted(glob.glob(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "regions", "12_*.py"))):
        for s in importlib.import_module(f"regions.{os.path.basename(f)[:-3]}").SITES:
            out[s.name] = s
    return out


S = sites()
BODY = "<div class='article_body'>본문 " + "내용 " * 30 + "</div>"


def test_gangneung_news_is_excluded():
    assert not S["강릉뉴스"].enabled and "제외" in S["강릉뉴스"].disabled_reason


def test_mudeung_uses_requests_and_input_date_basis():
    m = S["무등일보"]
    assert m.fetch == "requests" and m.date_basis == "input" and "{kw}" in m.search_url and "{page}" in m.search_url


CARD = ('<ul class="headline_lst"><li><a href="/detail/760131"><div class="gd_a"><div class="gd_mw"><img src="x.jpg"></div></div>'
        '<div class="desc"><div class="gd_a"><strong>친인척 특혜 의혹 신안군 안심숙소</strong><div class="info">… 토지<mark>보상</mark>비를 먼저 …</div>'
        '<div class="date"><span>2026.10.30. 10:18</span><span></span> <span>@ 박소영</span></div></div></div></a></li></ul>')


def test_mudeung_card_title_and_date():
    items = parse_list(f"<html><body>{CARD}</body></html>", "https://mdilbo.com/search.html", S["무등일보"])
    assert items[0]["title"] == "친인척 특혜 의혹 신안군 안심숙소"          # 요약(mark 강조 포함)과 날짜가 섞이지 않는다
    assert items[0]["link"] == "https://mdilbo.com/detail/760131"
    assert parse_list_date(items[0]["list_date"]) == "2026-10-30"


def test_mudeung_article_date_with_trailing_dot_is_input_date():
    html = ("<html><body><span class='info_view'><span class='txt_info'>입력 2025.11.12. 21:01</span></span>" + BODY + "</body></html>")
    art = parse_article(html, S["무등일보"])
    assert art["input_date"] == "2025-11-12"
    assert pick_reference_date(art["input_date"], art["modified_date"], S["무등일보"].date_basis) == ("2025-11-12", "입력")


def test_yeongnam_article_uses_modified_date():
    li = ("<ul class='article-bottom-left'><li class='article-bottom-input'>입력 2026-10-30 10:36&nbsp;&nbsp;|&nbsp;&nbsp;수정 2026-10-31 11:21"
          "&nbsp;&nbsp;|&nbsp;&nbsp;발행일 2026-10-30</li></ul>")
    art = parse_article(f"<html><body>{li}{BODY}</body></html>", S["영남일보"])
    assert (art["input_date"], art["modified_date"]) == ("2026-10-30", "2026-10-31")
    assert pick_reference_date(art["input_date"], art["modified_date"], S["영남일보"].date_basis) == ("2026-10-31", "수정")   # 수정일 기준


def test_yeongnam_ilbo_is_excluded_but_keeps_its_date_selector():
    y = S["영남일보"]
    assert not y.enabled and "제외" in y.disabled_reason
    assert "article-bottom-input" in y.article_date_sel            # 나중에 다시 켤 때를 위해 날짜 선택자는 그대로 둔다
