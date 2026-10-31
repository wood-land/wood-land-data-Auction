import os, sys, tempfile, re
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.crawler_core import Crawler, RegionRun, Settings, Site, SiteStats

OLD, NEW = "2020-01-01", "2026-10-30"
# 검색 결과: 최신순이 아니다. 1쪽 [옛, 옛, 옛, 최근], 2쪽 [옛, 옛, 옛, 최근], 3~6쪽은 전부 옛
PAGES = {1: [OLD, OLD, OLD, NEW], 2: [OLD, OLD, OLD, NEW], 3: [OLD] * 4, 4: [OLD] * 4, 5: [OLD] * 4, 6: [OLD] * 4}
ID = {}


class Fake:
    def __init__(self):
        self.pages_fetched = []
        self.opened = []

    def get(self, url, wait_selector=None, timeout=10, strict=False, encoding=""):
        m = re.search(r"/a/(\d+)", url)
        if m:
            i = int(m.group(1)); self.opened.append(i)
            body = "토지 보상 협의 대상은 후용리 1153번지 일원이며 편입토지 소유자 주민설명회를 연다. " * 3
            return f"<html><body><div class='dt'>입력 {ID[i]} 10:00</div><div id='b'>{body}</div></body></html>"
        p = int(re.search(r"p=(\d+)", url).group(1)); self.pages_fetched.append(p)
        items = "".join(f"<li class='it'><a href='/a/{k}'>토지 보상 협의 {k}</a><span class='d'>{d}</span></li>"
                        for k, d in zip(range((p - 1) * 10, (p - 1) * 10 + 10), PAGES.get(p, [])))
        for k, d in zip(range((p - 1) * 10, (p - 1) * 10 + 10), PAGES.get(p, [])):
            ID[k] = d
        return f"<ul>{items}</ul>"

    def close(self):
        pass


def run(newest_first):
    ID.clear()
    site = Site(name="t", search_url="http://t/s?q={kw}&p={page}", list_item_sel="li.it", list_title_sel="a",
                list_date_sel="span.d", article_date_sel="div.dt", article_body_sel="#b", link_contains="/a/",
                fetch="requests", delay_article=(0, 0), delay_page=(0, 0), newest_first=newest_first)
    f = Fake()
    with tempfile.TemporaryDirectory() as d:
        c = Crawler(Settings(save_directory=d, keywords=["보상"], workers=1, search_period_days=8, today=datetime(2026, 10, 31),
                             max_pages_per_keyword=30), fetcher_factory=lambda k: f, sleep=lambda s: None)
        stats = SiteStats("t")
        RegionRun(c, "t").collect_keyword(site, "보상", stats)
    return f, stats


def test_sorted_assumption_misses_recent_articles_in_unsorted_results():
    f, stats = run(newest_first=True)
    assert stats.saved == 0 and f.pages_fetched == [1]          # 옛 기사 3건 연속에서 멈춰 4번째(최근)를 놓친다


def test_unsorted_mode_finds_recent_articles_and_still_stops():
    f, stats = run(newest_first=False)
    assert stats.saved == 2                                       # 1쪽과 2쪽의 최근 기사 2건을 모두 찾는다
    assert f.pages_fetched == [1, 2, 3, 4, 5]                     # 3쪽부터 최근 기사 없는 페이지가 3쪽 연속(3,4,5)이면 종료
    assert sorted(f.opened) == [3, 13]                            # 옛 기사는 목록 날짜로 판단해 열지 않는다


def test_unsorted_mode_respects_page_cap():
    global PAGES
    saved = PAGES
    try:
        PAGES = {p: [NEW, OLD, OLD, OLD] for p in range(1, 31)}  # 매 페이지 최근 기사가 있어 stale 로는 안 멈춤
        f, _ = run(newest_first=False)
        assert len(f.pages_fetched) == 8                          # max_pages_unsorted
    finally:
        PAGES = saved


def test_unsorted_page_cap_is_smaller_when_list_has_no_date():
    # 목록에서 날짜를 못 읽는 신문사는 기사를 열어야 해서 상한이 더 작다 (5쪽)
    global PAGES
    saved = PAGES
    try:
        PAGES = {p: [NEW, OLD, OLD, OLD] for p in range(1, 31)}
        ID.clear()
        site = Site(name="t", search_url="http://t/s?q={kw}&p={page}", list_item_sel="li.it", list_title_sel="a",
                    list_date_sel="", article_date_sel="div.dt", article_body_sel="#b", link_contains="/a/",
                    fetch="requests", delay_article=(0, 0), delay_page=(0, 0), newest_first=False)
        f = Fake()
        with tempfile.TemporaryDirectory() as d:
            c = Crawler(Settings(save_directory=d, keywords=["보상"], workers=1, search_period_days=8, today=datetime(2026, 10, 31)),
                        fetcher_factory=lambda k: f, sleep=lambda s: None)
            RegionRun(c, "t").collect_keyword(site, "보상", SiteStats("t"))
        assert len(f.pages_fetched) == 5
    finally:
        PAGES = saved
