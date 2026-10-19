"""
core/sqlite_store.py - 수집 결과를 SQLite(data/{지역}.sqlite)에 누적 저장한다. git 에 올라가는 파일이라 중복 없이 담는다.

- notices(id, url, title, post_date, city, source_type, project_name): 고시공고/공보 공고 1건 = 1행. 제목·링크·공사명은 여기에만 둔다.
- parcels(pnu, notice_id, sojaeji, jibun, jimok, area_incl, verified, first_seen_at): PNU 가 있는 필지만(verified=0 은 리 코드로 조립한 것). 공고 정보는 notice_id 로 연결.
  조회: SELECT * FROM v_parcels (parcels + notices 를 합친 뷰: pnu, sojaeji, verified, first_seen_at, title, project_name, url, post_date ...)
- parcels_unresolved: PNU 변환에 실패한 주소. 다음 실행 때 자동 재시도, 성공하면 parcels 로 이동.
- gazette_board_status / runs: 점검용 작은 표.
- 변환/AI 캐시(pnu_cache, ai_cache)는 data/.cache/{지역}_cache.sqlite 로 분리해 git 에 올리지 않는다
  (GitHub Actions 는 actions/cache 로 보존). 파일이 없어도 동작하며, 그때는 카카오를 다시 호출할 뿐이다.
"""
import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.pnu import RESOLVER_VERSION
from core.run_log import LOG

SCHEMA = """
CREATE TABLE IF NOT EXISTS notices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    post_date TEXT,
    city TEXT,
    source_type TEXT,
    project_name TEXT,  -- 공사·사업명(조서/제목에서 읽음). 경공매 물건과 겹쳤을 때 어떤 사업인지 바로 보려고 둔다
    UNIQUE (url, title)
);
CREATE TABLE IF NOT EXISTS parcels (
    pnu TEXT NOT NULL,
    notice_id INTEGER NOT NULL REFERENCES notices(id),
    sojaeji TEXT, jibun TEXT, jimok TEXT, area_incl TEXT,
    verified INTEGER NOT NULL DEFAULT 1,  -- 1: 카카오가 그 지번을 확인 / 0: 리 법정동코드+지번으로 조립(존재 미확인)
    first_seen_at TEXT,  -- 이 필지를 처음 수집한 시각(UTC). 경공매와 '새로 겹친' 물건만 고를 때 쓴다(예전 행은 NULL)
    ocr INTEGER NOT NULL DEFAULT 0,  -- 1: 글자 층이 없는 이미지 문서를 OCR 로 읽은 행(숫자 오인식 위험, 약 70% 정확). 0: 문서 글자 층에서 읽음(2026-10-18 이전 행은 구분 없이 0)
    UNIQUE (pnu, notice_id)
);
CREATE TABLE IF NOT EXISTS parcels_unresolved (
    sojaeji TEXT, jibun TEXT, jimok TEXT, area_incl TEXT, city TEXT, source_type TEXT,
    title TEXT NOT NULL DEFAULT '', url TEXT NOT NULL DEFAULT '', post_date TEXT,
    reason TEXT, attempts INTEGER DEFAULT 1, resolver_version INTEGER, ai_tried INTEGER DEFAULT 0,
    last_tried_at TEXT, project_name TEXT, ocr INTEGER DEFAULT 0,
    UNIQUE (sojaeji, jibun, url, title)
);
CREATE TABLE IF NOT EXISTS seen_posts (  -- 처리를 끝낸 게시글 기록: 7일 창에서 같은 글을 매번 다시 받지 않으려고 둔다
    source TEXT NOT NULL, city TEXT NOT NULL, key TEXT NOT NULL,  -- key = 글 URL|제목 (post_key)
    title TEXT, post_date TEXT,
    status TEXT,   -- ok: 필지가 나옴 / empty: 오류 없이 읽었으나 필지 없음
    rows INTEGER DEFAULT 0, tries INTEGER DEFAULT 1, version INTEGER, last_at TEXT,
    PRIMARY KEY (source, city, key)
);
CREATE TABLE IF NOT EXISTS gazette_board_status (
    module TEXT, city TEXT, kind TEXT, url TEXT, status TEXT, detail TEXT,
    posts INTEGER, attachments INTEGER, notices INTEGER, comp_notices INTEGER, rows INTEGER,
    errors TEXT, run_at TEXT,
    PRIMARY KEY (module, city)
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT, finished_at TEXT, job TEXT, days INTEGER, summary TEXT
);
CREATE INDEX IF NOT EXISTS ix_parcels_pnu ON parcels(pnu);
CREATE INDEX IF NOT EXISTS ix_parcels_notice ON parcels(notice_id);
CREATE INDEX IF NOT EXISTS ix_notices_date ON notices(post_date);
-- 경공매 PNU 와 비교할 때 쓰는 조회용 뷰: SELECT * FROM v_parcels WHERE pnu IN (...)
CREATE VIEW IF NOT EXISTS v_parcels AS
SELECT p.pnu, p.sojaeji, p.jibun, p.jimok, p.area_incl, p.verified, p.ocr, p.first_seen_at,
       n.title, n.project_name, n.url, n.post_date, n.city, n.source_type
FROM parcels p JOIN notices n ON n.id = p.notice_id;
"""


# 추출 규칙·문서 해석 코드를 고쳐 이미 처리한 글도 다시 읽어야 할 때 올린다(기록의 version 이 다르면 건너뛰지 않는다)
EXTRACT_VERSION = 2  # 2(2026-10-18): 표 머리글·소재지 조립·입찰 위치 규칙 개선분을 반영해 이미 처리한 글도 한 번 다시 읽는다
EMPTY_RETRIES = 2  # 필지 없이 끝난 글은 이 횟수만큼 읽은 뒤에야 건너뛴다(한 번은 더 시도해 해석 개선을 반영)
SEEN_KEEP_DAYS = 30


def post_key(url, title):
    return f"{url or ''}|{' '.join((title or '').split())[:120]}"


def load_seen(con, source, city):
    """건너뛸 글의 키 집합. ok(필지 나옴) 또는 empty 를 EMPTY_RETRIES 번 읽은 글, 단 추출 버전이 같은 것만."""
    return {r[0] for r in con.execute(
        "SELECT key FROM seen_posts WHERE source=? AND city=? AND version=? AND (status='ok' OR (status='empty' AND tries>=?))",
        (source, city, EXTRACT_VERSION, EMPTY_RETRIES))}


def record_seen(con, source, city, outcomes):
    """outcomes: [{key, title, post_date, status('ok'/'empty'), rows}] -> seen_posts. 같은 버전으로 또 읽었으면 tries 를 올린다.
    호출 전에 그 글의 필지를 DB 에 저장해 둬야 한다(저장 전에 죽으면 기록이 없어 다음에 다시 읽는다)."""
    t = now()
    for o in outcomes or []:
        con.execute(
            "INSERT INTO seen_posts (source, city, key, title, post_date, status, rows, tries, version, last_at) "
            "VALUES (?,?,?,?,?,?,?,1,?,?) ON CONFLICT(source, city, key) DO UPDATE SET "
            "tries = CASE WHEN version = excluded.version THEN tries + 1 ELSE 1 END, "
            "title=excluded.title, post_date=excluded.post_date, status=excluded.status, rows=excluded.rows, "
            "version=excluded.version, last_at=excluded.last_at",
            (source, city, o["key"], (o.get("title") or "")[:200], o.get("post_date"), o["status"], o.get("rows", 0),
             EXTRACT_VERSION, t))
    con.commit()


RUNS_KEEP_DAYS = 60          # runs(실행 기록)는 최근 이만큼만. 전체 이력은 구글시트 수집 로그에 있다
UNRESOLVED_KEEP_DAYS = 90    # PNU 로 못 바꾼 주소는 글 날짜 기준 이 기간만 둔다(30일마다 3번 재시도한 뒤에도 안 되면 버린다)


def prune_old(con):
    """DB 가 끝없이 커지지 않게 오래된 점검용 행을 정리한다. 필지(parcels)·공고(notices)는 지우지 않는다.
    VACUUM 은 하지 않는다: 파일을 통째로 다시 쓰면 git 이 바뀐 부분만 저장하는 효율이 깨져 저장소가 더 빨리 커진다(지워진 자리는 다음 행이 재사용)."""
    now_dt = datetime.now(timezone.utc)
    con.execute("DELETE FROM runs WHERE started_at < ?", ((now_dt - timedelta(days=RUNS_KEEP_DAYS)).isoformat(timespec="seconds"),))
    con.execute("DELETE FROM parcels_unresolved WHERE post_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]*' AND post_date < ?",
                ((now_dt - timedelta(days=UNRESOLVED_KEEP_DAYS)).date().isoformat(),))  # 날짜 모르는 행·다른 형식은 그대로 둔다
    con.commit()
    prune_seen(con)


def reset_recent_unresolved(con, keep_days=4):
    """EXTRACT_VERSION 이 올라가면(추출 규칙을 고쳤으면) 최근 글에서 나온 미해결 행을 비운다. 그 글은 곧 다시 읽혀(seen_posts 버전이 다름)
    고친 규칙으로 새로 만들어지므로, 예전 규칙이 만든 가짜 소재지 행이 남아 있지 않게 한다. 다음 실행이 3일 뒤라도 7일 창 안에 드는 글(keep_days 이내)만 비운다.
    DB 의 PRAGMA user_version 에 적용한 버전을 기억해 버전당 한 번만 한다. 지운 행 수를 돌려준다."""
    if con.execute("PRAGMA user_version").fetchone()[0] >= EXTRACT_VERSION:
        return 0
    cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).date().isoformat()
    n = con.execute("DELETE FROM parcels_unresolved WHERE post_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]*' AND post_date >= ?",
                    (cutoff,)).rowcount
    con.execute(f"PRAGMA user_version = {int(EXTRACT_VERSION)}")
    con.commit()
    return n


def prune_seen(con, days=SEEN_KEEP_DAYS):
    con.execute("DELETE FROM seen_posts WHERE last_at < ?", (
        (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds"),))
    con.commit()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _cols(con, table):
    return [r[1] for r in con.execute(f"PRAGMA table_info({table})")]


def _migrate(con):
    """예전 스키마 DB 를 현재 구조(notices + parcels)로 옮긴다. 두 가지 예전 형태를 모두 처리:
    (넓은) parcels(region, post_title, post_url, post_date, sojaeji ...)  (최소) parcels(pnu, title, url)"""
    cols = _cols(con, "parcels")
    migrated = False
    if cols and "notice_id" not in cols:
        con.execute("ALTER TABLE parcels RENAME TO parcels_old")
        con.executescript(SCHEMA)
        if "region" in cols:  # 넓은 형태
            con.execute(
                "INSERT OR IGNORE INTO notices (url, title, post_date, city, source_type) "
                "SELECT COALESCE(post_url,''), substr(COALESCE(NULLIF(notice_title,''), post_title, ''),1,200), "
                "MIN(post_date), MIN(city), MIN(source_type) FROM parcels_old "
                "GROUP BY COALESCE(post_url,''), substr(COALESCE(NULLIF(notice_title,''), post_title, ''),1,200)")
            con.execute(
                "INSERT OR IGNORE INTO parcels (pnu, notice_id, sojaeji, jibun, jimok, area_incl) SELECT o.pnu, n.id, o.sojaeji, o.jibun, o.jimok, o.area_incl "
                "FROM parcels_old o JOIN notices n ON n.url = COALESCE(o.post_url,'') AND "
                "n.title = substr(COALESCE(NULLIF(o.notice_title,''), o.post_title, ''),1,200)")
        else:  # 최소 형태(pnu, title, url)
            con.execute("INSERT OR IGNORE INTO notices (url, title) SELECT DISTINCT url, title FROM parcels_old")
            con.execute(
                "INSERT OR IGNORE INTO parcels (pnu, notice_id) SELECT o.pnu, n.id FROM parcels_old o "
                "JOIN notices n ON n.url = o.url AND n.title = o.title")
        con.execute("DROP TABLE parcels_old")
        migrated = True
    if "notice_id" in _cols(con, "parcels") and "verified" not in _cols(con, "parcels"):
        con.execute("ALTER TABLE parcels ADD COLUMN verified INTEGER NOT NULL DEFAULT 1")
        migrated = True
    pu = _cols(con, "parcels_unresolved")
    if pu and "post_date" not in pu:
        con.execute("DROP TABLE parcels_unresolved")  # 재시도용 임시 표라 형태가 바뀌면 새로 만든다
        migrated = True
    for t in ("gosigongo_notices", "gazette_notices", "gazette_addresses", "pnu_cache", "ai_cache"):
        if _cols(con, t):
            con.execute(f"DROP TABLE {t}")
            migrated = True
    con.commit()
    if migrated:
        con.execute("VACUUM")  # 파일 크기를 실제로 줄인다


def _ensure_columns(con):
    """예전 DB 에 새 열(project_name, first_seen_at)을 덧붙인다. 표가 아직 없으면(새 DB) 건너뛴다."""
    for table, col, ddl in (("notices", "project_name", "TEXT"), ("parcels", "first_seen_at", "TEXT"),
                            ("parcels_unresolved", "project_name", "TEXT"),
                            ("parcels", "ocr", "INTEGER NOT NULL DEFAULT 0"), ("parcels_unresolved", "ocr", "INTEGER DEFAULT 0")):
        cols = _cols(con, table)
        if cols and col not in cols:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
    con.execute("DROP VIEW IF EXISTS v_parcels")  # 뷰는 열이 바뀌면 다시 만든다(SCHEMA 가 곧 만든다)
    con.commit()


def cache_path(db_path):
    base = os.environ.get("GOSI_CACHE_DIR") or str(Path(db_path).parent / ".cache")
    return Path(base) / (Path(db_path).stem + "_cache.sqlite")


def connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=DELETE")
    cp = cache_path(path)
    cp.parent.mkdir(parents=True, exist_ok=True)
    con.execute("ATTACH DATABASE ? AS cache", (str(cp),))
    _migrate(con)
    _ensure_columns(con)
    con.executescript(SCHEMA)
    return con


def _title(a):
    """공고 제목: 공보는 공고 단위 제목(notice_title)을, 없으면 게시글 제목을 쓴다."""
    return " ".join(((a.get("notice_title") or a.get("post_title") or "")).split())[:200]


def _notice_id(con, a, city, source_type):
    url, title = a.get("post_url") or "", _title(a)
    project = " ".join((a.get("project_name") or "").split())[:100]
    con.execute("INSERT OR IGNORE INTO notices (url, title, post_date, city, source_type, project_name) VALUES (?,?,?,?,?,?)",
                (url, title, a.get("post_date"), city, source_type, project))
    nid = con.execute("SELECT id FROM notices WHERE url=? AND title=?", (url, title)).fetchone()[0]
    if project:  # 예전에 공사명 없이 저장된 공고를 채운다
        con.execute("UPDATE notices SET project_name=? WHERE id=? AND COALESCE(project_name,'')=''", (project, nid))
    return nid


def _insert_parcel(con, pnu, a, city, source_type, verified=1):
    nid = _notice_id(con, a, city, source_type)
    cur = con.execute(
        "INSERT OR IGNORE INTO parcels (pnu, notice_id, sojaeji, jibun, jimok, area_incl, verified, first_seen_at, ocr) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (pnu, nid, a.get("sojaeji"), a.get("jibun"), a.get("jimok"), a.get("area_incl"), verified, now(),
         1 if a.get("ocr") else 0))
    if not cur.rowcount and not a.get("ocr"):  # 같은 필지를 글자 층에서 다시 읽었다면 OCR 표시를 푼다(더 믿을 수 있는 출처)
        con.execute("UPDATE parcels SET ocr=0 WHERE pnu=? AND notice_id=? AND ocr=1", (pnu, nid))
    if not cur.rowcount and verified:  # 같은 PNU 가 예전에 조립(verified=0)으로 들어갔다면 확인된 것으로 갱신
        con.execute("UPDATE parcels SET verified=1 WHERE pnu=? AND notice_id=?", (pnu, nid))
    return cur.rowcount


def save_parcels(con, resolver, city, source_type, rows):
    """주소 행(dict: sojaeji, jibun, jimok, area_incl, post_title, notice_title, post_url, post_date ...)을
    PNU로 바꿔 저장(공고는 notices, 필지는 parcels). PNU가 없는 행은 parcels_unresolved 에 사유와 함께 남겨
    다음 실행 때 자동으로 다시 시도한다. 반환: (새로 저장한 필지 수, PNU 변환 실패 수)"""
    t = now()
    new, failed = 0, 0
    for a in rows:
        pnu, reason = resolver.resolve_full(
            a.get("sojaeji"), a.get("jibun"), f'{a.get("post_title") or ""} {a.get("project_name") or ""}',
            city or "", a.get("post_title") or "", a.get("project_name") or "", a.get("jimok") or "")
        if pnu:
            if resolver.last_full:  # 카카오가 바로잡은 정식 주소(시도 시군구 읍면 리 지번)로 저장한다
                a = {**a, "sojaeji": resolver.last_full}
            new += _insert_parcel(con, pnu, a, city, source_type, 0 if reason == "ok_ri" else 1)
            continue
        failed += 1
        LOG.pnu_fail(city, source_type, a.get("sojaeji"), a.get("jibun"), a.get("jimok"), reason, _title(a),
                     a.get("post_url"))
        if reason in ("no_jibun", "no_region", "not_parcel"):
            continue  # 지번이 없거나 소재지가 없으면 주소 변환을 다시 해도 같다(문서를 다시 읽어야 한다 -> 수집 로그에 남김)
        con.execute(
            """INSERT OR IGNORE INTO parcels_unresolved
               (sojaeji, jibun, jimok, area_incl, city, source_type, title, url, post_date, reason, attempts,
                resolver_version, ai_tried, last_tried_at, project_name, ocr) VALUES (?,?,?,?,?,?,?,?,?,?,1,?,?,?,?,?)""",
            (a.get("sojaeji"), a.get("jibun"), a.get("jimok"), a.get("area_incl"), city, source_type, _title(a),
             a.get("post_url") or "", a.get("post_date"), reason, RESOLVER_VERSION,
             1 if resolver.ai.enabled else 0, t, " ".join((a.get("project_name") or "").split())[:100],
             1 if a.get("ocr") else 0),
        )
    con.commit()
    return new, failed


def retry_unresolved(con, resolver, recheck_days=30):
    """이전 실행에서 PNU로 못 바꾼 주소를 다시 시도한다(문서를 다시 받지 않는다).
    다시 시도하는 경우: 일시 오류/키 없음 / 변환 규칙 버전이 올라감 / 이번에 AI 보정이 새로 가능해짐 /
    마지막 시도가 recheck_days 일보다 오래됨(카카오 지번 DB 갱신 대비). 성공하면 parcels 로 옮긴다."""
    # 소재지 없이 지번만 저장돼 있던 예전 행은 추출 단계 문제였다. 다음 수집에서 문서를 다시 읽으므로 비운다.
    for rowid, soj in con.execute("SELECT rowid, sojaeji FROM parcels_unresolved WHERE resolver_version < ?", (RESOLVER_VERSION,)).fetchall():
        if not re.search(r"[가-힣]", re.sub(r"(?:^|\s)산(?=\s*\d)", " ", soj or "")):  # 지번('산13-4' 포함)뿐인 행
            con.execute("DELETE FROM parcels_unresolved WHERE rowid=?", (rowid,))
    rows = con.execute(
        """SELECT rowid, sojaeji, jibun, jimok, area_incl, city, source_type, title, url, post_date, project_name, ocr
           FROM parcels_unresolved
           WHERE reason IN ('transient','no_key') OR resolver_version < ?
              OR (ai_tried = 0 AND ?) OR last_tried_at < datetime('now', ?)""",
        (RESOLVER_VERSION, 1 if resolver.ai.enabled else 0, f"-{recheck_days} days"),
    ).fetchall()
    t, fixed = now(), 0
    for rowid, sojaeji, jibun, jimok, area, city, source_type, title, url, post_date, project_name, ocr in rows:
        pnu, reason = resolver.resolve_full(sojaeji, jibun, title or "", city or "", title or "", "", jimok or "")
        if reason == "not_parcel":  # 필지가 아닌 행은 재시도 대상이 아니다
            con.execute("DELETE FROM parcels_unresolved WHERE rowid=?", (rowid,))
            continue
        if not pnu:
            LOG.pnu_fail(city, source_type, sojaeji, jibun, jimok, reason, title, url)
        if pnu:
            a = {"sojaeji": resolver.last_full or sojaeji, "jibun": jibun, "jimok": jimok, "area_incl": area, "post_title": title,
                 "post_url": url, "post_date": post_date, "project_name": project_name, "ocr": ocr}
            _insert_parcel(con, pnu, a, city, source_type, 0 if reason == "ok_ri" else 1)
            con.execute("DELETE FROM parcels_unresolved WHERE rowid=?", (rowid,))
            fixed += 1
        else:
            con.execute(
                "UPDATE parcels_unresolved SET reason=?, attempts=attempts+1, resolver_version=?, ai_tried=?, "
                "last_tried_at=? WHERE rowid=?",
                (reason, RESOLVER_VERSION, 1 if resolver.ai.enabled else 0, t, rowid))
    con.commit()
    return len(rows), fixed


def save_gazette(con, results, resolver):
    """run_gazette.process_board 결과 리스트를 저장. (새 필지 수, PNU 변환 실패 수) 반환."""
    t = now()
    new_total, failed_total = 0, 0
    for r in results:
        LOG.board(r, "; ".join(r.get("errors") or []))
        new, failed = save_parcels(con, resolver, r["city"], "공보", r["addr"])
        record_seen(con, "공보", f'{r["module"]}/{r["city"]}', r.get("outcomes"))  # 필지를 저장한 뒤에 처리한 글을 기록한다
        new_total += new
        failed_total += failed
        con.execute(
            "INSERT OR REPLACE INTO gazette_board_status VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (r["module"], r["city"], r["kind"], r["url"], r["status"], r["detail"], r["posts"],
             r["attachments"], r["notices"], r["comp_notices"], r["rows"],
             json.dumps(r["errors"], ensure_ascii=False), t),
        )
    con.commit()
    return new_total, failed_total


def log_run(con, started_at, job, days, summary):
    LOG.summary(job, summary)
    con.execute("INSERT INTO runs (started_at, finished_at, job, days, summary) VALUES (?,?,?,?,?)",
                (started_at, now(), job, days, summary))
    con.commit()
