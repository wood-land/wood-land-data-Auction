"""소유구분(owner_kind) 저장 테스트: 국가·지자체 소유 필지도 수집하되 사유/공공/미상으로 표시한다(2026-10-26). 네트워크 없이 돈다.
실행: gosi 폴더에서 `python -m unittest discover -s tests -v`"""
import os
import sqlite3
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from core import sqlite_store as S  # noqa: E402


class FakeAi:
    enabled = False


class FakeResolver:
    """주소 -> PNU 변환 대역: 지번 숫자로 가짜 PNU 를 만든다."""
    ai = FakeAi()
    last_full = ""

    def resolve_full(self, sojaeji, jibun, *args):
        if not jibun or jibun == "0":
            return "", "no_jibun"
        if "없는곳" in (sojaeji or ""):
            return "", "no_match"
        return "4100000000" + "1" + str(jibun).replace("-", "").zfill(8)[:8], "ok"


def row(jibun, owner_type, soj="경기도 포천시 가산면 방축리"):
    return {"sojaeji": soj, "jibun": jibun, "jimok": "답", "area_incl": "100", "owner_type": owner_type,
            "post_title": "공고", "post_url": "http://x/1", "post_date": "2026-10-26"}


class OwnerKind(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "t.sqlite")
        self.cons = []

    def tearDown(self):
        for c in self.cons:  # Windows 는 열린 sqlite 파일이 있으면 임시 폴더를 지우지 못한다
            c.close()
        self.tmp.cleanup()

    def connect(self):
        con = S.connect(self.db)
        self.cons.append(con)
        return con

    def kinds(self, con):
        return dict(con.execute("SELECT jibun, owner_kind FROM parcels").fetchall())

    def test_mapping(self):
        self.assertEqual([S.owner_kind(x) for x in ("국공유", "사유", "법인", "", "확인필요", None)],
                         ["공공", "사유", "사유", "미상", "미상", "미상"])

    def test_public_parcels_are_saved_with_kind(self):
        con = self.connect()
        new, failed = S.save_parcels(con, FakeResolver(), "포천시", "고시공고",
                                     [row("1-1", "국공유"), row("2", "사유"), row("3", "법인"), row("4", ""), row("5", "확인필요")])
        self.assertEqual((new, failed), (5, 0))
        self.assertEqual(self.kinds(con), {"1-1": "공공", "2": "사유", "3": "사유", "4": "미상", "5": "미상"})
        view = con.execute("SELECT owner_kind FROM v_parcels WHERE jibun='1-1'").fetchone()
        self.assertEqual(view, ("공공",))  # 조회용 뷰에도 나온다

    def test_unknown_kind_is_filled_when_learned_later(self):
        con = self.connect()
        S.save_parcels(con, FakeResolver(), "포천시", "고시공고", [row("7", "")])
        S.save_parcels(con, FakeResolver(), "포천시", "고시공고", [row("7", "국공유")])
        self.assertEqual(self.kinds(con), {"7": "공공"})
        S.save_parcels(con, FakeResolver(), "포천시", "고시공고", [row("7", "")])  # 모르는 값으로는 덮어쓰지 않는다
        self.assertEqual(self.kinds(con), {"7": "공공"})

    def test_unresolved_keeps_kind_through_retry(self):
        con = self.connect()
        S.save_parcels(con, FakeResolver(), "포천시", "고시공고", [row("9", "국공유", soj="경기도 없는곳 가산면")])
        self.assertEqual(con.execute("SELECT owner_kind FROM parcels_unresolved").fetchone(), ("공공",))

        class Fixed(FakeResolver):
            def resolve_full(self, sojaeji, jibun, *args):
                return "4100000000100000009", "ok"

        con.execute("UPDATE parcels_unresolved SET resolver_version = 0")  # 변환 규칙 버전이 올라간 것처럼 -> 재시도 대상
        S.retry_unresolved(con, Fixed())
        self.assertEqual(self.kinds(con), {"9": "공공"})
        self.assertEqual(con.execute("SELECT count(*) FROM parcels_unresolved").fetchone(), (0,))

    def test_old_database_gets_the_column(self):
        con = sqlite3.connect(self.db)
        con.executescript("""
            CREATE TABLE notices (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL DEFAULT '', title TEXT NOT NULL DEFAULT '',
                post_date TEXT, city TEXT, source_type TEXT, project_name TEXT, UNIQUE (url, title));
            CREATE TABLE parcels (pnu TEXT NOT NULL, notice_id INTEGER NOT NULL, sojaeji TEXT, jibun TEXT, jimok TEXT, area_incl TEXT,
                verified INTEGER NOT NULL DEFAULT 1, first_seen_at TEXT, ocr INTEGER NOT NULL DEFAULT 0, UNIQUE (pnu, notice_id));
            INSERT INTO notices (url, title) VALUES ('u', 't');
            INSERT INTO parcels (pnu, notice_id, jibun) VALUES ('4100000000100000001', 1, '1');
            CREATE VIEW v_parcels AS SELECT p.pnu FROM parcels p;
        """)
        con.commit()
        con.close()
        con = self.connect()
        self.assertEqual(con.execute("SELECT owner_kind FROM parcels").fetchone(), (None,))  # 예전 행은 NULL(그때는 사유지만 수집)
        S.save_parcels(con, FakeResolver(), "포천시", "고시공고", [row("2", "국공유")])
        self.assertEqual(self.kinds(con), {"1": None, "2": "공공"})


if __name__ == "__main__":
    unittest.main()
