import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.crawler_core import Crawler, RegionRun, Settings, Site, SiteStats

LIST = "<ul>" + "".join(f"<li class='it'><a href='/a/{i}'>기사 {i}</a><span class='d'>2026-10-30</span></li>" for i in range(5)) + "</ul>"
ART = "<html><body><div class='dt'>입력 2026-10-30 10:00</div><div id='b'>본문 " + "내용 " * 30 + "</div></body></html>"


class FakeFetcher:
    def __init__(self):
        self.opened = 0

    def get(self, url, wait_selector=None, timeout=10, strict=False, encoding=""):
        if "/a/" in url:
            self.opened += 1
            return ART
        return LIST

    def close(self):
        pass


def make(tmp, budget):
    site = Site(name="t", search_url="http://t/s?q={kw}&p={page}", list_item_sel="li.it", list_title_sel="a",
                list_date_sel="span.d", article_date_sel="div.dt", article_body_sel="#b", link_contains="/a/",
                fetch="requests", delay_article=(0, 0), delay_page=(0, 0))
    ff = FakeFetcher()
    c = Crawler(Settings(save_directory=tmp, keywords=["보상", "사업"], time_budget_min=budget, workers=1, max_pages_per_keyword=2),
                fetcher_factory=lambda kind: ff, sleep=lambda s: None)
    return site, ff, c


def test_no_budget_means_no_limit():
    with tempfile.TemporaryDirectory() as d:
        site, ff, c = make(d, 0)
        assert c.deadline is None and not c.expired()
        run = RegionRun(c, "t"); stats = SiteStats("t")
        run._collect_site_keywords(site, stats)
        assert stats.keywords_total == 2 and not stats.timed_out and ff.opened > 0


def test_expired_budget_stops_before_opening_articles():
    with tempfile.TemporaryDirectory() as d:
        site, ff, c = make(d, 1)
        c._now = lambda: c.deadline + 1                  # 이미 예산을 넘긴 시계
        assert c.expired()
        run = RegionRun(c, "t"); stats = SiteStats("t")
        run._collect_site_keywords(site, stats)
        assert stats.timed_out and ff.opened == 0 and stats.keywords_total == 0


def test_budget_runs_out_midway_and_partial_results_are_kept():
    with tempfile.TemporaryDirectory() as d:
        site, ff, c = make(d, 1)
        clock = {"t": c.deadline - 100}
        c._now = lambda: clock["t"]
        orig = ff.get

        def get(url, **kw):                              # 기사 2건을 연 뒤 예산 소진
            r = orig(url, **kw)
            if "/a/" in url and ff.opened >= 2:
                clock["t"] = c.deadline + 1
            return r
        ff.get = get
        run = RegionRun(c, "t"); stats = SiteStats("t")
        run._collect_site_keywords(site, stats)
        assert stats.timed_out and ff.opened == 2
