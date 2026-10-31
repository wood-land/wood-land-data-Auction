import os, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import common.pnu_resolver as pr
from common.pnu_resolver import PNUResolver, PNUResult, LotExpect


# ---------------- 가짜 HTTP 세션 / 가짜 조회 함수 ----------------
class FakeResp:
    def __init__(self, data, status=200):
        self._d, self.status_code = data, status

    def json(self):
        return self._d


class FakeSession:
    def __init__(self, data=None, status=200):
        self.data, self.status, self.calls = data, status, 0

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls += 1
        return FakeResp(self.data, self.status)


def kakao_doc(name, mountain, main, sub="", b_code="4833011900"):
    return {"address_type": "REGION_ADDR", "x": "129.1", "y": "35.3",
            "address": {"address_name": name, "mountain_yn": mountain, "main_address_no": main,
                        "sub_address_no": sub, "b_code": b_code}}


def kakao_ok(monkeypatch):
    monkeypatch.setenv("KAKAO_REST_API_KEY", "dummy")


# ---------------- Kakao 응답 필지 검증 ----------------
def test_kakao_accepts_exact_lot_and_builds_pnu(monkeypatch):
    kakao_ok(monkeypatch)
    s = FakeSession({"documents": [kakao_doc("경남 양산시 평산동 산 40-3", "Y", "40", "3")]})
    r = pr.get_pnu_from_kakao("경상남도 양산시 평산동 산 40-3", s, LotExpect(True, 40, 3, ("양산시",)))
    assert r.status == "SUCCESS" and r.pnu == "4833011900" + "2" + "0040" + "0003"


def test_kakao_rejects_neighbour_lot(monkeypatch):
    # 요청 134 인데 비슷한 135 를 돌려주면 다른 필지의 PNU 가 저장되므로 거부해야 한다
    kakao_ok(monkeypatch)
    s = FakeSession({"documents": [kakao_doc("경남 김해시 어방동 135", "N", "135")]})
    r = pr.get_pnu_from_kakao("경상남도 김해시 어방동 134", s, LotExpect(False, 134, 0, ("김해시",)))
    assert r.status == "NOT_FOUND" and r.pnu is None and "다름" in r.error_message


def test_kakao_rejects_mountain_mismatch(monkeypatch):
    kakao_ok(monkeypatch)
    s = FakeSession({"documents": [kakao_doc("경남 양산시 평산동 40-3", "N", "40", "3")]})
    r = pr.get_pnu_from_kakao("경상남도 양산시 평산동 산 40-3", s, LotExpect(True, 40, 3, ("양산시",)))
    assert r.status == "NOT_FOUND"


def test_kakao_rejects_other_sigungu(monkeypatch):
    kakao_ok(monkeypatch)
    s = FakeSession({"documents": [kakao_doc("충남 서산시 부석면 북지리 548", "N", "548")]})
    r = pr.get_pnu_from_kakao("경상북도 영주시 부석면 북지리 548", s, LotExpect(False, 548, 0, ("영주시",)))
    assert r.status == "NOT_FOUND"


def test_kakao_takes_first_matching_document_not_just_first(monkeypatch):
    kakao_ok(monkeypatch)
    docs = [kakao_doc("경남 김해시 어방동 135", "N", "135"), kakao_doc("경남 김해시 어방동 134", "N", "134")]
    r = pr.get_pnu_from_kakao("경상남도 김해시 어방동 134", FakeSession({"documents": docs}),
                              LotExpect(False, 134, 0, ("김해시",)))
    assert r.status == "SUCCESS" and r.pnu.endswith("1" + "0134" + "0000")


def test_kakao_ambiguous_same_lot_in_several_regions_is_rejected(monkeypatch):
    # 시군구 없이 조회해 서로 다른 두 지역의 같은 지번이 나오면 어느 쪽인지 알 수 없다
    kakao_ok(monkeypatch)
    docs = [kakao_doc("경남 양산시 평산동 산 40-3", "Y", "40", "3", b_code="4833011900"),
            kakao_doc("경남 김해시 평산동 산 40-3", "Y", "40", "3", b_code="4825011900")]
    r = pr.get_pnu_from_kakao("경상남도 평산동 산 40-3", FakeSession({"documents": docs}),
                              LotExpect(True, 40, 3, (), "경상남도"))
    assert r.status == "NOT_FOUND" and "여러 곳" in r.error_message


def test_kakao_same_lot_listed_twice_is_not_ambiguous(monkeypatch):
    kakao_ok(monkeypatch)
    d = kakao_doc("경남 양산시 평산동 산 40-3", "Y", "40", "3")
    r = pr.get_pnu_from_kakao("경상남도 평산동 산 40-3", FakeSession({"documents": [d, dict(d)]}),
                              LotExpect(True, 40, 3, (), "경상남도"))
    assert r.status == "SUCCESS"


def test_kakao_province_must_match_when_no_city_given(monkeypatch):
    # '마산리 46-1' 을 경남으로 조회했는데 경기 파주 필지가 오면 안 된다
    kakao_ok(monkeypatch)
    docs = [kakao_doc("경기 파주시 마산리 46-1", "N", "46", "1", b_code="4148036023")]
    r = pr.get_pnu_from_kakao("경상남도 마산리 46-1", FakeSession({"documents": docs}), LotExpect(False, 46, 1, (), "경상남도"))
    assert r.status == "NOT_FOUND"
    docs = [kakao_doc("경남 함양군 마산리 46-1", "N", "46", "1", b_code="4887035024")]
    assert pr.get_pnu_from_kakao("경상남도 마산리 46-1", FakeSession({"documents": docs}),
                                 LotExpect(False, 46, 1, (), "경상남도")).status == "SUCCESS"


def test_expect_from_address_sets_province_only_without_city():
    assert pr.expect_from_address("경상남도 풍류동 179").province == "경상남도"
    e = pr.expect_from_address("경상남도 김해시 풍류동 179")
    assert e.province == "" and e.sigungu == ("김해시",)


def test_kakao_auth_error_is_error_not_not_found_and_not_retried(monkeypatch):
    kakao_ok(monkeypatch)
    s = FakeSession({}, status=401)
    r = pr.get_pnu_from_kakao("경상남도 김해시 어방동 134", s, None)
    assert r.status == "ERROR" and s.calls == 1


def test_kakao_missing_key_is_error(monkeypatch):
    monkeypatch.delenv("KAKAO_REST_API_KEY", raising=False)
    r = pr.get_pnu_from_kakao("경상남도 김해시 어방동 134", FakeSession({"documents": []}), None)
    assert r.status == "ERROR"


def test_vworld_verifies_lot_from_pnu(monkeypatch):
    monkeypatch.setenv("VWORLD_API_KEY", "dummy")
    pnu = "4833011900" + "2" + "0040" + "0003"
    ok = {"response": {"status": "OK", "refined": {"text": "경상남도 양산시 평산동 산 40-3", "structure": {"level4LC": pnu}},
                       "result": {"point": {"x": "129.1", "y": "35.3"}}}}
    assert pr.get_pnu_from_vworld("a", FakeSession(ok), LotExpect(True, 40, 3, ("양산시",))).pnu == pnu
    assert pr.get_pnu_from_vworld("a", FakeSession(ok), LotExpect(True, 41, 3, ("양산시",))).status == "NOT_FOUND"


# ---------------- 후보 재시도 / 캐시 ----------------
def fake_kakao_factory(success_for, error_for=()):
    calls = []

    def fn(address, session=None, expect=None):
        calls.append(address)
        if address in error_for:
            return PNUResult(address, address, None, "kakao", "ERROR", error_message="HTTP 503")
        if address in success_for:
            return PNUResult(address, address, success_for[address], "kakao", "SUCCESS", 127.0, 37.0, address)
        return PNUResult(address, address, None, "kakao", "NOT_FOUND", error_message="검색 결과 없음")
    fn.calls = calls
    return fn


def no_vworld(address, session=None, expect=None):
    return PNUResult(address, address, None, "vworld", "NOT_FOUND", error_message="없음")


def make(tmp_path, kakao):
    return PNUResolver(str(tmp_path / "t.db"), kakao_fn=kakao, vworld_fn=no_vworld)


def test_retries_candidates_until_one_verifies(tmp_path):
    # 1순위(읍/면 포함)가 없고, 읍/면을 뺀 후보가 있을 때
    ok = {"경상남도 궁류면 평촌리 9": "4872031022100090000"}
    k = fake_kakao_factory(ok)
    res = make(tmp_path, k).resolve("궁류면 평촌리 9", area_hint="진주시")
    assert res.status == "SUCCESS" and res.completed_address == "경상남도 궁류면 평촌리 9" and res.basis == "province"
    assert k.calls == ["경상남도 진주시 궁류면 평촌리 9", "경상남도 궁류면 평촌리 9"]


def test_returns_first_failure_when_all_fail(tmp_path):
    res = make(tmp_path, fake_kakao_factory({})).resolve("부석면 북지리 548", area_hint="영주시")
    assert res.status == "NOT_FOUND" and res.completed_address == "경상북도 영주시 부석면 북지리 548"


def test_garbage_address_makes_no_api_call(tmp_path):
    k = fake_kakao_factory({})
    res = make(tmp_path, k).resolve("충주상가 1", area_hint="충주시")
    assert res.status == "NOT_FOUND" and k.calls == [] and "형식" in res.error_message


def test_address_without_any_region_clue_makes_no_api_call(tmp_path):
    k = fake_kakao_factory({"마산리 46-1": "4148036023100460001"})
    res = make(tmp_path, k).resolve("마산리 46-1", area_hint="")
    assert res.status == "NOT_FOUND" and k.calls == [] and "단서" in res.error_message


def test_error_is_not_cached_and_is_retried(tmp_path):
    addr = "경상북도 영주시 가흥동 676-2"
    k1 = fake_kakao_factory({}, error_for={addr})
    r = make(tmp_path, k1)
    assert r.resolve("가흥동 676-2", area_hint="영주시").status == "ERROR"
    assert r.get_cached_pnu(addr) is None                       # 일시 오류는 캐시에 없다
    k2 = fake_kakao_factory({addr: "4721010100106760002"})
    r.kakao_fn = k2
    assert r.resolve("가흥동 676-2", area_hint="영주시").status == "SUCCESS"


def test_error_among_candidates_wins_over_not_found(tmp_path):
    # 한 후보가 일시 오류였다면 '없음'으로 확정하면 안 된다 (나중에 다시 시도되도록 ERROR)
    k = fake_kakao_factory({}, error_for={"경상북도 부석면 북지리 548"})
    assert make(tmp_path, k).resolve("부석면 북지리 548", area_hint="영주시").status == "ERROR"


def test_success_is_cached_and_not_requeried(tmp_path):
    addr = "경상북도 영주시 가흥동 676-2"
    k = fake_kakao_factory({addr: "4721010100106760002"})
    r = make(tmp_path, k)
    r.resolve("가흥동 676-2", area_hint="영주시")
    n = len(k.calls)
    res = r.resolve("가흥동 676-2", area_hint="영주시")
    assert len(k.calls) == n and res.source == "cache(kakao)" and res.status == "SUCCESS"


def _age_cache(db, days=None, ver=None, status=None):
    with sqlite3.connect(db) as c:
        if days is not None:
            c.execute("UPDATE address_pnu_cache SET updated_at = datetime('now', ?)", (f"-{days} days",))
        if ver is not None:
            c.execute("UPDATE address_pnu_cache SET ver = ?", (ver,))
        c.commit()


def test_not_found_cache_expires_after_ttl_and_on_version_change(tmp_path):
    addr = "경상북도 영주시 가흥동 676-2"
    k = fake_kakao_factory({})
    r = make(tmp_path, k)
    r.resolve("가흥동 676-2", area_hint="영주시")
    assert r.get_cached_pnu(addr) is not None                   # 방금 실패 -> 믿는다
    _age_cache(r.db_path, days=40)
    assert r.get_cached_pnu(addr) is None                       # 30일 지남 -> 다시 조회
    _age_cache(r.db_path, days=1)
    assert r.get_cached_pnu(addr) is not None
    _age_cache(r.db_path, ver=pr.NEWS_RESOLVER_VERSION - 1)
    assert r.get_cached_pnu(addr) is None                       # 로직이 바뀐 뒤에는 옛 실패를 믿지 않는다


def test_old_schema_db_is_migrated_and_old_failures_are_ignored(tmp_path):
    db = str(tmp_path / "old.db")
    with sqlite3.connect(db) as c:           # 컬럼 ver / basis 가 없던 옛 DB
        c.execute("CREATE TABLE address_pnu_cache (completed_address TEXT PRIMARY KEY, pnu TEXT, source TEXT, "
                  "standard_name TEXT, x REAL, y REAL, status TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        c.execute("INSERT INTO address_pnu_cache (completed_address, pnu, source, status) VALUES ('a', NULL, 'kakao', 'NOT_FOUND')")
        c.execute("INSERT INTO address_pnu_cache (completed_address, pnu, source, status) VALUES ('b', '123', 'kakao', 'SUCCESS')")
        c.execute("CREATE TABLE article_addresses (id INTEGER PRIMARY KEY AUTOINCREMENT, article_link TEXT, raw_address TEXT, "
                  "completed_address TEXT, pnu TEXT, source TEXT, status TEXT, standard_name TEXT, x REAL, y REAL, "
                  "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        c.commit()
    r = PNUResolver(db, kakao_fn=fake_kakao_factory({}), vworld_fn=no_vworld)
    with sqlite3.connect(db) as c:
        assert "ver" in [x[1] for x in c.execute("PRAGMA table_info(address_pnu_cache)")]
        assert "basis" in [x[1] for x in c.execute("PRAGMA table_info(article_addresses)")]
    assert r.get_cached_pnu("a") is None            # 옛 로직의 NOT_FOUND 는 다시 시도
    assert r.get_cached_pnu("b").status == "SUCCESS"


# ---------------- DB 재처리 ----------------
def test_repair_fixes_failed_rows_and_keeps_good_ones(tmp_path):
    good = "경상북도 영주시 부석면 북지리 548"
    k = fake_kakao_factory({good: "4721039022105480000"})
    r = make(tmp_path, k)
    with sqlite3.connect(r.db_path) as c:
        c.execute("INSERT INTO articles (link, paper, title, area_hint) VALUES ('L1', '영주시민신문', '제목', '영주시')")
        c.execute("INSERT INTO article_addresses (article_link, raw_address, completed_address, status, source) "
                  "VALUES ('L1', '부석면 북지리 548', '충청남도 서산시 부석면 북지리 548', 'NOT_FOUND', 'kakao')")
        c.execute("INSERT INTO article_addresses (article_link, raw_address, completed_address, pnu, status, source) "
                  "VALUES ('L1', '다른 주소', 'x', '999', 'SUCCESS', 'kakao')")
        c.commit()
    logs = []
    dry = r.repair_failed_addresses(dry_run=True, log=logs.append)
    assert dry["fixed"] == 1
    with sqlite3.connect(r.db_path) as c:
        assert c.execute("SELECT status FROM article_addresses WHERE id=1").fetchone()[0] == "NOT_FOUND"   # dry-run 은 저장 안 함
    stats = r.repair_failed_addresses(log=logs.append)
    assert stats == {"checked": 1, "fixed": 1, "still_failed": 0, "duplicates_removed": 0}
    with sqlite3.connect(r.db_path) as c:
        row = c.execute("SELECT completed_address, pnu, status, basis FROM article_addresses WHERE id=1").fetchone()
        assert row == (good, "4721039022105480000", "SUCCESS", "hint")
        assert c.execute("SELECT pnu FROM article_addresses WHERE id=2").fetchone()[0] == "999"   # 성공 행은 건드리지 않음


def test_repair_removes_row_duplicating_same_pnu_in_same_article(tmp_path):
    good = "경상북도 영주시 부석면 북지리 548"
    r = make(tmp_path, fake_kakao_factory({good: "4721039022105480000"}))
    with sqlite3.connect(r.db_path) as c:
        c.execute("INSERT INTO articles (link, paper, title, area_hint) VALUES ('L1', 'p', 't', '영주시')")
        c.execute("INSERT INTO article_addresses (article_link, raw_address, completed_address, pnu, status) "
                  "VALUES ('L1', '북지리 548', 'z', '4721039022105480000', 'SUCCESS')")
        c.execute("INSERT INTO article_addresses (article_link, raw_address, completed_address, status) "
                  "VALUES ('L1', '부석면 북지리 548', 'bad', 'NOT_FOUND')")
        c.commit()
    stats = r.repair_failed_addresses(log=lambda s: None)
    assert stats["duplicates_removed"] == 1
    with sqlite3.connect(r.db_path) as c:
        assert c.execute("SELECT COUNT(*) FROM article_addresses").fetchone()[0] == 1


# ---------------- 기사 재저장 ----------------
def _article(**kw):
    a = {"link": "http://x/1", "paper": "p", "keyword": "k", "title": "제목", "date": "2026-10-20", "area": "영주시",
         "address_extracted": "a", "body": "본문 " * 20}
    a.update(kw)
    return a


def test_resaving_an_article_keeps_id_and_first_collected_time(tmp_path):
    r = make(tmp_path, fake_kakao_factory({}))
    r.save_article_and_addresses(_article(), [])
    with sqlite3.connect(r.db_path) as c:
        c.execute("UPDATE articles SET created_at = '2026-10-01 00:00:00'")
        c.commit()
        first_id = c.execute("SELECT id FROM articles").fetchone()[0]
    r.save_article_and_addresses(_article(date="2026-10-22", title="바뀐 제목"), [])
    with sqlite3.connect(r.db_path) as c:
        row = c.execute("SELECT id, created_at, article_date, title FROM articles").fetchone()
        assert c.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 1
    assert row == (first_id, "2026-10-01 00:00:00", "2026-10-22", "바뀐 제목")   # 최초 수집 시각 유지, 내용은 갱신
