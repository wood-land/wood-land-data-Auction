import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import glob, importlib
from bs4 import BeautifulSoup
from common.crawler_core import Site, date_from_element, parse_article, MAX_DATE_ELEMENT_TEXT
from common.verified_selectors import VERIFIED_SELECTORS

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def all_site_names():
    names = []
    for f in sorted(glob.glob(os.path.join(HERE, "regions", "12_*.py"))):
        mod = importlib.import_module(f"regions.{os.path.basename(f)[:-3]}")
        names += [s.name for s in mod.SITES]
    return names


def test_every_registry_name_is_a_real_site():
    # 오타가 있으면 조용히 적용되지 않으므로 이름을 검사한다
    names = set(all_site_names())
    assert not [n for n in VERIFIED_SELECTORS if n not in names]


def test_registry_selectors_are_valid_css():
    soup = BeautifulSoup("<html></html>", "html.parser")
    for name, ov in VERIFIED_SELECTORS.items():
        for key, sel in ov.items():
            assert key in Site.__dataclass_fields__, (name, key)
            if key.endswith("_sel") and key != "search_form_data":
                if sel:                       # 빈 문자열은 '끔'
                    soup.select(sel)          # 잘못된 선택자면 예외
            elif key == "fetch":
                assert sel in ("requests", "selenium"), (name, sel)
            elif key == "link_contains":
                assert isinstance(sel, str), (name, sel)
            elif key == "search_adapter":
                from common.search_adapters import ADAPTERS
                assert sel in ADAPTERS, (name, sel)
            elif key == "homepage_url":
                assert sel.startswith("http"), (name, sel)
            elif key == "search_builder":
                from common.search_builders import BUILDERS
                assert sel in BUILDERS, (name, sel)
            elif key == "encoding":
                assert sel in ("utf-8", "euc-kr"), (name, sel)
            elif key == "search_encoding":
                assert sel in ("utf-8", "euc-kr"), (name, sel)
            elif key == "search_method":
                assert sel in ("GET", "POST"), (name, sel)
            elif key == "search_url":
                # 키워드가 URL 에 없어도 되는 경우: POST(폼으로 보냄), 또는 사이트 정의가 이미 POST 이고 레지스트리는 도메인만 바꾸는 경우
                assert sel.startswith("http"), (name, sel)
                if "search_method" in ov and ov["search_method"] == "GET":
                    assert "{kw}" in sel, (name, sel)
            elif key == "search_form_data":
                assert all(len(x) == 2 for x in sel), (name, sel)
            elif key == "date_basis":
                assert sel in ("modified_first", "input"), (name, sel)
            else:
                assert isinstance(sel, bool), (name, key, sel)       # newest_first


def test_registry_overrides_the_region_definition():
    name = next(iter(VERIFIED_SELECTORS))
    s = Site(name=name, search_url="u", list_item_sel="x", list_title_sel="x", list_date_sel="x",
             article_date_sel="td, span, div", article_body_sel="b")
    assert s.article_date_sel == VERIFIED_SELECTORS[name]["article_date_sel"]
    other = Site(name="레지스트리에 없는 신문", search_url="u", list_item_sel="x", list_title_sel="x", list_date_sel="x",
                 article_date_sel="td, span, div", article_body_sel="b")
    assert other.article_date_sel == "td, span, div"


# ---- 페이지 전체를 감싼 요소를 잡았을 때 (익산신문 계열: 청도신문·영덕신문·포항신문) ----
def _site(sel):
    return Site(name="레지스트리에 없는 신문", search_url="u", list_item_sel="x", list_title_sel="x", list_date_sel="x",
                article_date_sel=sel, article_body_sel="#b")


def test_giant_wrapper_element_is_not_trusted_and_meta_wins():
    sidebar = "<div>" + "관련기사 " * 10 + "입력 2010-12-06 " + "다른 기사 " * 60 + "</div>"        # 사이드바에 있는 옛 기사 날짜
    html = ("<html><head><meta property='article:published_time' content='2026-10-06T09:00:00+09:00'></head>"
            f"<body><div class='wrap'>최종편집:2026-10-31 18:42:01 {sidebar}<div id='b'>본문 {'내용 ' * 30}</div></div></body></html>")
    art = parse_article(html, _site("td, span, div"))
    assert art["input_date"] == "2026-10-06" and art["date_source"] == "메타"


def test_giant_element_without_meta_yields_no_date_instead_of_a_wrong_one():
    html = f"<html><body><div class='wrap'>입력 2010-12-06 {'다른 기사 ' * 80}<div id='b'>본문 {'내용 ' * 30}</div></div></body></html>"
    art = parse_article(html, _site("div"))
    assert art["input_date"] is None


def test_date_from_element_size_limit():
    soup = BeautifulSoup(f"<p>입력 2026-10-20 {'가' * (MAX_DATE_ELEMENT_TEXT + 10)}</p><span>입력 2026-10-20</span>", "html.parser")
    assert date_from_element(soup.select_one("p")) == (None, None, False)
    assert date_from_element(soup.select_one("span"))[0] == "2026-10-20"


def test_registry_value_kinds():
    keys = {k for ov in VERIFIED_SELECTORS.values() for k in ov}
    assert keys <= {"article_date_sel", "list_date_sel", "newest_first", "date_basis", "search_method", "search_url", "search_form_data", "search_builder", "search_encoding", "list_item_sel", "list_title_sel", "list_title_text_sel", "article_body_sel", "encoding", "search_adapter", "homepage_url", "fetch", "link_contains"}


def test_unsorted_flag_reaches_the_site_object():
    names = [n for n, ov in VERIFIED_SELECTORS.items() if ov.get("newest_first") is False]
    assert names, "최신순이 아닌 신문사가 하나도 없다면 이 기능이 쓰이지 않는다"
    s = Site(name=names[0], search_url="u", list_item_sel="x", list_title_sel="x", list_date_sel="x",
             article_date_sel="x", article_body_sel="b")
    assert s.newest_first is False


def test_search_fixes_make_the_keyword_reach_the_server():
    # 키워드/페이지가 요청에 실제로 실리는지 (GET 이면 URL 에, POST 면 폼 데이터에 {kw}/{page})
    for name in ("홍성신문", "주간영동", "괴산타임즈", "울진뉴스", "경남도민일보"):
        ov = VERIFIED_SELECTORS[name]
        assert ov["search_method"] == "POST"
        keys = dict(ov["search_form_data"])
        assert "{kw}" in keys.values() and "{page}" in keys.values(), name
    g = VERIFIED_SELECTORS["거제신문"]
    assert g["search_method"] == "GET" and "{kw}" in g["search_url"] and "{page}" in g["search_url"]
