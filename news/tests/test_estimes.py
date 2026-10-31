import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import importlib
from common.crawler_core import parse_list

mod = importlib.import_module("regions.12_4_chungcheong_daejeon_sejong")
S = {s.name: s for s in mod.SITES}

# estimes.co.kr 실제 검색 결과 항목 구조(기사 1건 = table 1개)
ITEM = ('<table border="0" cellpadding="0" cellspacing="0" width="100%%"><tr><td class="list-titles">'
        '<a href="articleView.html?idxno=%d">%s</a></td></tr><tr><td class="list-summary"><a href="articleView.html?idxno=%d">요약 …</a></td></tr>'
        '<tr><td class="list-times list-pad-10">음성타임즈 <i>|</i> %s</td></tr></table>')
PAGE = "<html><body><table><tr><td>" + ITEM % (34112, "김기창 의원, 5분발언", 34112, "2026-10-13 15:36") + ITEM % (33828, "평곡2리 화장장 동의서 의혹", 33828, "2026-09-02 10:01") + "</td></tr></table></body></html>"


def test_umsung_times_is_enabled_and_umsung_shinmun_is_not():
    assert S["음성타임즈"].enabled and not S["음성신문"].enabled
    assert "estimes.co.kr" in S["음성타임즈"].homepage_url and "교체" in S["음성신문"].disabled_reason


def test_estimes_is_searched_in_euc_kr():
    # UTF-8 로 보내면 '전체 0건'이 되고 키워드와 무관한 홈 기사만 돌아온다
    assert S["음성타임즈"].encoding.lower() == "euc-kr"


def test_estimes_list_items_title_and_date():
    items = parse_list(PAGE, "http://www.estimes.co.kr/news/articleList.html", S["음성타임즈"])
    assert [i["title"] for i in items] == ["김기창 의원, 5분발언", "평곡2리 화장장 동의서 의혹"]
    assert items[0]["link"] == "http://www.estimes.co.kr/news/articleView.html?idxno=34112"
    assert "2026-10-13" in items[0]["list_date"]


def test_umsung_times_is_part_of_the_chungbuk_group():
    run_crawl = importlib.import_module("run_crawl")
    group = run_crawl.PART_GROUPS["충청·대전·세종"]["충북"]
    assert "음성타임즈" in group and "음성신문" not in group


def test_registry_reference_date_policies():
    from common.verified_selectors import VERIFIED_SELECTORS as V
    assert V["대구신문"]["date_basis"] == "input" and V["경남일보"]["date_basis"] == "modified_first"
    assert "음성신문" not in V
