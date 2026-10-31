import os, sys, csv, glob, tempfile
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.crawler_core import Crawler, RegionRun, Settings, Site, SiteStats, parse_article, parse_list


def site(**kw):
    base = dict(name="t", search_url="http://t/s?q={kw}&p={page}", list_item_sel="li.it", list_title_sel="a[href*='/a/']",
                list_date_sel="span.d", article_date_sel="div.dt", article_body_sel="#b", link_contains="/a/",
                fetch="requests", delay_article=(0, 0), delay_page=(0, 0))
    base.update(kw)
    return Site(**base)


def test_text_link_is_preferred_over_the_thumbnail_link():
    # 남도일보·전남일보: 썸네일 이미지 링크(글자 없음)가 먼저 잡혀 목록 20건 전부 제목이 비던 문제
    html = ("<ul><li class='it'><a class='altlist-image' href='/a/1'><img alt='이미지 대체글'></a>"
            "<a href='/a/1'>글자 제목</a></li></ul>")
    assert parse_list(html, "http://t/", site())[0]["title"] == "글자 제목"


def test_image_alt_is_the_fallback_title():
    html = "<ul><li class='it'><a class='altlist-image' href='/a/1'><img alt='이미지 대체글'></a></li></ul>"
    items = parse_list(html, "http://t/", site())
    assert items[0]["title"] == "이미지 대체글" and items[0]["link"] == "http://t/a/1"


def test_article_title_from_og_then_h1_then_title_tag():
    s = site()
    page = lambda head, body="": f"<html><head>{head}</head><body>{body}<div id='b'>본문</div></body></html>"
    assert parse_article(page("<meta property='og:title' content='OG 제목'>"), s)["title"] == "OG 제목"
    assert parse_article(page("", "<h1>H1 제목</h1>"), s)["title"] == "H1 제목"
    assert parse_article(page("<title>태그 제목</title>"), s)["title"] == "태그 제목"


LIST = "<ul><li class='it'><a href='/a/1'><img src='x.jpg'></a><span class='d'>2026-10-30</span></li></ul>"       # 제목도 alt 도 없음


def article(title):
    body = "토지 보상 협의 대상은 후용리 1153번지 일원이며 편입토지 소유자 주민설명회를 연다. " * 3
    return (f"<html><head><meta property='og:title' content='{title}'></head><body>"
            f"<div class='dt'>입력 2026-10-30 10:00</div><div id='b'>{body}</div></body></html>")


class Fake:
    def __init__(self, title):
        self.title = title

    def get(self, url, wait_selector=None, timeout=10, strict=False, encoding=""):
        return article(self.title) if "/a/" in url else (LIST if "p=1" in url else "<ul></ul>")

    def close(self):
        pass


def crawl(title):
    with tempfile.TemporaryDirectory() as d:
        c = Crawler(Settings(save_directory=d, keywords=["보상"], workers=1, search_period_days=8, today=datetime(2026, 10, 31),
                             blacklist_keywords=("행사",)), fetcher_factory=lambda k: Fake(title), sleep=lambda s: None)
        stats = SiteStats("t")
        run = RegionRun(c, "t")
        run.collect_keyword(site(), "보상", stats)
        rows = list(csv.DictReader(open(glob.glob(os.path.join(d, "*.csv"))[0], encoding="utf-8-sig")))
    return stats, rows


def test_blank_list_title_is_filled_from_the_article_page():
    stats, rows = crawl("토지 보상 협의 착수")
    assert stats.saved == 1 and rows[0]["제목"] == "토지 보상 협의 착수"


def test_title_blacklist_is_applied_after_the_title_is_recovered():
    stats, rows = crawl("마을 행사 안내 토지 보상")
    assert stats.saved == 0 and stats.blacklist_skipped == 1 and rows == []
