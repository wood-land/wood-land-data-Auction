import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from clean_news_csv import deduplicate_news_records


def row(paper, addr, hint="", title="t", body="본문 " * 20):
    return {"신문사": paper, "주소추출": addr, "지역힌트": hint, "제목": title, "본문": body, "날짜": "2026-10-20", "링크": f"http://{paper}/1"}


def test_same_address_in_two_papers_is_merged_when_region_is_known():
    recs, removed = deduplicate_news_records([row("A신문", "후용리 1153", "원주시", body="길게 " * 50), row("B신문", "후용리 1153", "원주시")])
    assert removed == 1 and len(recs) == 1 and recs[0]["신문사"] == "A신문"


def test_regionless_addresses_are_not_merged_across_papers():
    # 지역 단서가 없으면 '마산리 46-1' 이 어느 지역인지 모른다 -> 서로 다른 곳일 수 있으니 합치지 않는다
    recs, removed = deduplicate_news_records([row("A신문", "마산리 46-1"), row("B신문", "마산리 46-1")])
    assert removed == 0 and len(recs) == 2
