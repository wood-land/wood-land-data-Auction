"""
audit_parcels.py - DB 에 저장된 필지(parcels)의 소재지 글자와 PNU 가 서로 맞는지 카카오로 다시 확인하고 바로잡는다.

배경(2026-10-27): 옛 코드로 저장된 행은 소재지 글자가 표 열 섞임으로 깨져 있는데('경기도 수원시 없음이동면 노곡리', '용인특례시 인구이동읍 천리')
PNU 는 카카오가 이동면 노곡리·이동읍 천리를 찾아 맞게 나왔다. 그래서 소재지를 주소 검색창에 넣으면 안 나온다. 2026-10-18 이후 행은 카카오가
돌려준 정식 주소로 저장하지만, 그 전 행(first_seen_at 이 비어 있음)은 깨진 글자가 그대로 남아 있다.
이 스크립트는 검사 대상 행을 새 규칙(AI 보정 제외)으로 다시 변환해 비교한다:
  SAME_FIXED   같은 PNU 가 나오고 소재지 글자만 다름 -> 카카오 정식 주소로 교체(--apply 일 때)
  SAME         같은 PNU, 소재지도 같음(문제 없음)
  CONFLICT     다른 PNU 가 나옴 -> 둘 중 하나가 틀렸다. 고치지 않고 보고서에만 남긴다(사람이 확인)
  UNRESOLVED   이번에는 PNU 를 못 구함(조립된 verified=0 행이거나 지번 소멸) -> 고치지 않고 보고서에만 남긴다
검사 대상(기본): ① first_seen_at 이 빈 옛 행 ② verified=0(리 코드 조립, 지번 존재 미확인) ③ 소재지에 이상한 글자('없음' 등)가 든 행.
  python audit_parcels.py                    # 보고서만(DB 는 안 바꿈)
  python audit_parcels.py --apply            # SAME_FIXED 의 소재지를 정식 주소로 교체
  python audit_parcels.py --files 경기.sqlite 강원.sqlite --scope all
"""
import argparse
import csv
import re
import sqlite3
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from core import sqlite_store as S  # noqa: E402
from core.paths import DATA_DIR  # noqa: E402
from core.pnu import PnuResolver  # noqa: E402

ODD_RE = re.compile(r"없음|인구|종시|기타|\d{4,}")


def suspect(row, scope):
    pnu, soj, jibun, verified, first_seen = row[:5]
    if scope == "all":
        return True
    return (not first_seen) or verified == 0 or bool(ODD_RE.search(soj or ""))


def audit_file(path, resolver, scope, apply, limit=None, fix_conflicts=False):
    con = sqlite3.connect(path)
    cols = [r[1] for r in con.execute("PRAGMA table_info(parcels)")]
    if "pnu" not in cols:
        con.close()
        return []
    ncols = [r[1] for r in con.execute("PRAGMA table_info(notices)")]

    def col(table, cols, name, default="NULL"):  # 아주 옛 스키마(전국.sqlite 등)에는 없는 열이 있다
        return f"{table}.{name}" if name in cols else default

    rows = con.execute(
        f"SELECT p.pnu, p.sojaeji, p.jibun, {col('p', cols, 'verified', '1')}, {col('p', cols, 'first_seen_at')}, "
        f"{col('p', cols, 'jimok')}, n.id, {col('n', ncols, 'title', chr(39) + chr(39))}, {col('n', ncols, 'project_name')}, "
        f"{col('n', ncols, 'city')} FROM parcels p JOIN notices n ON n.id = p.notice_id").fetchall()
    out = []
    for row in rows:
        if not suspect(row, scope):
            continue
        if limit and len(out) >= limit:
            break
        pnu, soj, jibun, verified, first_seen, jimok, nid, title, project, city = row
        pnu2, why = resolver.resolve_full(soj, jibun, f"{title or ''} {project or ''}", city or "", title or "", project or "", jimok or "")
        full = resolver.last_full
        if pnu2 == pnu:
            kind = "SAME" if (full or soj) == soj or not full else "SAME_FIXED"
        elif pnu2:
            kind = "CONFLICT"
        else:
            kind = "UNRESOLVED"
        out.append({"file": Path(path).name, "kind": kind, "why": why, "pnu": pnu, "pnu_new": pnu2 or "", "sojaeji": soj, "full": full,
                    "jibun": jibun, "verified": verified, "city": city, "title": (title or "")[:60]})
        if apply and kind == "SAME_FIXED" and why in ("ok", "ok_ri_only", "ok_abbrev", "ok_repair", "ok_san") and full:
            con.execute("UPDATE parcels SET sojaeji=? WHERE pnu=? AND notice_id=?", (full, pnu, nid))
        if apply and fix_conflicts and kind == "CONFLICT" and full and PnuResolver.region_ok_for(soj, full):
            # 옛 코드가 소재지의 시군과 다른 지역의 같은 이름 동·리를 받아 저장한 행: 지금 규칙이 소재지와 맞는 PNU 를 구했으면 그것으로 바꾼다
            try:
                con.execute("UPDATE parcels SET pnu=?, sojaeji=?, verified=? WHERE pnu=? AND notice_id=?",
                            (pnu2, full, 0 if why == "ok_ri" else 1, pnu, nid))
            except sqlite3.IntegrityError:  # 이 공고에 새 PNU 가 이미 있으면 틀린 쪽 행만 지운다
                con.execute("DELETE FROM parcels WHERE pnu=? AND notice_id=?", (pnu, nid))
            out[-1]["kind"] = "CONFLICT_FIXED"
    if apply:
        con.commit()
    con.close()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-dir", default=str(DATA_DIR))
    ap.add_argument("--files", nargs="*", help="검사할 sqlite 파일 이름(기본: db-dir 의 전부)")
    ap.add_argument("--scope", choices=["suspect", "all"], default="suspect")
    ap.add_argument("--apply", action="store_true", help="SAME_FIXED 의 소재지를 카카오 정식 주소로 교체")
    ap.add_argument("--fix-conflicts", action="store_true", help="--apply 와 함께: 소재지 시군과 맞는 새 PNU 로 충돌 행을 바꾼다")
    ap.add_argument("--limit", type=int, default=None, help="파일마다 이 개수까지만(시험용)")
    ap.add_argument("--report", default="audit_parcels_report.csv")
    a = ap.parse_args()
    files = [Path(a.db_dir) / f for f in a.files] if a.files else sorted(Path(a.db_dir).glob("*.sqlite"))
    tmp = tempfile.mkdtemp()
    rcon = S.connect(str(Path(tmp) / "audit.sqlite"))  # 변환 캐시용 임시 DB(실제 DB 는 건드리지 않는다)
    resolver = PnuResolver(rcon)
    resolver.ai.enabled = False  # AI 비용 없이 규칙만으로 비교
    if not resolver.key:
        raise SystemExit("카카오 키를 찾지 못했습니다(core/pnu.py load_key).")
    allrows = []
    for f in files:
        rows = audit_file(f, resolver, a.scope, a.apply, a.limit, a.fix_conflicts)
        c = Counter(r["kind"] for r in rows)
        print(f"{f.name}: 검사 {len(rows)}건 {dict(c)}", flush=True)
        allrows += rows
    with open(a.report, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(allrows[0].keys()) if allrows else ["file"])
        w.writeheader()
        w.writerows(allrows)
    total = Counter(r["kind"] for r in allrows)
    print("\n합계:", dict(total), "| 보고서:", a.report, "| 적용:", "예" if a.apply else "아니오(보고서만)")


if __name__ == "__main__":
    main()
