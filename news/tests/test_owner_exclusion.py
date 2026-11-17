"""신문기사 필지 중 국유지·시도유지·군유지는 추출에서 제외한다(2026-11-17, 사용자 지시).
고성신문 '동해면 내곡리 1536-1' 이 군·국유지라 제외 대상이었다. 소유 조회는 가짜 함수로 대체해 네트워크 없이 돈다."""
import os
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from common.owner_lookup import public_label  # noqa: E402
from common.pnu_resolver import PNUResolver, PNUResult  # noqa: E402

ARTICLE = {"link": "http://x/1", "paper": "고성신문", "keyword": "", "title": "무인기종합타운", "date": "2026-11-13", "area": "경상남도 고성군",
           "address_extracted": "", "body": "본문 " * 30}


def res(pnu, raw):
    return PNUResult(raw_address=raw, completed_address="경상남도 고성군 " + raw, pnu=pnu, source="kakao", status="SUCCESS", x=128.38, y=35.02)


def make(owner_fn):
    d = tempfile.mkdtemp()
    return PNUResolver(db_path=os.path.join(d, "n.db"), owner_fn=owner_fn)


def statuses(r):
    with sqlite3.connect(r.db_path) as c:
        return dict(c.execute("SELECT pnu, status FROM article_addresses").fetchall())


def test_labels():
    assert public_label("02") == "국유지" and public_label("04") == "시도유지" and public_label("05") == "군유지"
    assert public_label("06") == "" and public_label(None) == "" and public_label("01") == ""


def test_public_land_is_marked_and_private_is_kept():
    owners = {"A": "05", "B": "02", "C": "04", "D": "01", "E": "06"}
    r = make(lambda pnu, x, y: owners.get(pnu))
    r.save_article_and_addresses(ARTICLE, [res(p, p) for p in "ABCDE"])
    assert statuses(r) == {"A": "PUBLIC_OWNER", "B": "PUBLIC_OWNER", "C": "PUBLIC_OWNER", "D": "SUCCESS", "E": "SUCCESS"}


def test_unknown_owner_keeps_the_parcel():
    r = make(lambda pnu, x, y: None)  # 조회 실패·필지 없음 → 제외하지 않는다
    r.save_article_and_addresses(ARTICLE, [res("A", "a")])
    assert statuses(r) == {"A": "SUCCESS"}


def test_failed_addresses_are_not_looked_up():
    calls = []
    r = make(lambda pnu, x, y: calls.append(pnu))
    bad = PNUResult(raw_address="x", completed_address="x", pnu=None, source="none", status="NOT_FOUND")
    r.save_article_and_addresses(ARTICLE, [bad])
    assert calls == []


def test_owner_is_cached_per_parcel():
    calls = []

    def fn(pnu, x, y):
        calls.append(pnu)
        return "05"

    r = make(fn)
    r.save_article_and_addresses(ARTICLE, [res("A", "a")])
    r.save_article_and_addresses({**ARTICLE, "link": "http://x/2", "title": "다른 기사", "body": "다른 " * 30}, [res("A", "a")])
    assert calls == ["A"]  # 두 번째는 캐시
