"""
run_perss.py - 소규모환경영향평가(EIASS 평가정보조회) 사업의 대략 위치를 모은다.

  python run_perss.py                 # 최근 접수 사업(목록 3쪽, 접수 30일 이내) 중 아직 안 한 것
  python run_perss.py --pages 8 --days 90
  python run_perss.py --codes ND20260270:106090 --force
  python run_perss.py --test          # 저장하지 않고 _test/ 에만

사업위치(소재지·면적)만 있다(평가서 원문은 진행현황이 '완료'인 사업에만 있고, 도면 정합은 하지 않는다).
- 면형: 대표 지번(도로명) 주소 -> 좌표, 반지름 r = √(면적/π)(면적과 같은 넓이의 원, 최소 30m). 대표지번 필지도 함께.
- 선형(도로 등): 시점·종점 주소 -> 직선. 직선이 10km 넘으면 제외(skip).
결과: approx/{사업코드}.geojson (+_parcel) -> gpkg 레이어 'EIASS_초안사업지'(구분=대략위치, 평가종류=소규모환경영향평가), 처리 이력 state_perss.json
"""
import argparse
import datetime
import json
import math
import sys
import time
import traceback

from core import kakao, perss, site, store, vworld

TODAY = datetime.date.today()
MIN_R = 30.0


def log(*a):
    print(*a, flush=True)


def load_state():
    p = store.DATA / "state_perss.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save_state(st):
    (store.DATA / "state_perss.json").write_text(json.dumps(st, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def parse_date(t):
    try:
        return datetime.datetime.strptime(t.strip(), "%Y.%m.%d").date()
    except Exception:
        return None


def process(P, row, VW, test):
    cd = row["per_cd"]
    d = P.detail(cd, row["seq"])
    meta = {"biz_cd": cd, "biz_nm": d["biz_nm"] or row["biz_nm"], "location": d["location"], "plan_m2": d["plan_m2"],
            "eiass_url": perss.detail_url(cd, row["seq"])}
    extra = {"평가종류": "소규모환경영향평가", "사업구분": d["biz_type"] or row["biz_type"], "접수일": row["recv_date"],
             "진행현황": row["status"], "협의기관": d["agency"], "사업시행자": d["applicant"], "위치형태": d["kind"]}
    if not d["location"]:
        return "skip", "사업위치(소재지)가 비어 있음", meta
    loc_fn = vworld.locate if VW else (lambda t: kakao.locate(t, vworld.address_variants))
    if d["start"] and d["end"]:      # 선형(도로 등): 시점~종점 직선
        pts = [loc_fn(d["start"]), loc_fn(d["end"])]
        if not all(pts):
            return "error", f"시점/종점 위치를 못 찾음 ({d['start']} ~ {d['end']})", meta
        from pyproj import Geod
        rp = [(pts[0][0], pts[0][1]), (pts[1][0], pts[1][1])]
        km = Geod(ellps="WGS84").inv(*rp[0], *rp[1])[2] / 1000
        if km > site.ROUTE_MAX_KM:
            return "skip", f"노선형 사업이 너무 김(직선 {km:.1f}km > {site.ROUTE_MAX_KM:.0f}km)", meta
        if not test:
            store.write_approx(cd, meta, 0, 0, "", d["plan_m2"], route=rp, km=round(km, 2), extra=extra)
        return "ok", f"노선 시점~종점 직선 {km:.1f}km", meta
    loc = loc_fn(d["location"])
    if not loc:
        return "error", f"사업위치 좌표를 못 찾음 ({d['location']})", meta
    lon, lat, how = loc
    r = max(MIN_R, math.sqrt(d["plan_m2"] / math.pi)) if d["plan_m2"] else 100.0
    pg = None
    if str(how).startswith("PARCEL") and VW:
        try:
            from shapely.geometry import Point, shape
            for f in vworld.parcels_bbox(lon - 0.0004, lat - 0.0004, lon + 0.0004, lat + 0.0004, cell=0.01):
                if shape(f["geometry"]).buffer(0).contains(Point(lon, lat)):
                    pg = shape(f["geometry"]).buffer(0); break
        except Exception as err:
            log("    대표지번 필지 조회 실패:", err)
    if not test:
        store.write_approx(cd, meta, lon, lat, how, d["plan_m2"], pg, radius_m=r, extra=extra)
    return "ok", f"{how} 반경 {r:.0f}m" + (" 대표필지 있음" if pg is not None else ""), meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=3, help="목록 몇 쪽까지(1쪽=10건)")
    ap.add_argument("--days", type=int, default=30, help="접수일이 이 일수 이내인 사업만")
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--codes", default="", help="사업코드:순번 쉼표 구분")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    VW = vworld.available()
    log(f"브이월드 {'사용 가능' if VW else '막힘(카카오로 대신)'} / 카카오 키 {'있음' if kakao.KEY else '없음'}")
    if not VW and not kakao.KEY:
        log("::error::브이월드도 막히고 KAKAO_REST_API_KEY 도 없음"); return 2
    store.ensure_dirs()
    if a.test:
        store.DATA = store.DATA / "_test"; store.ensure_dirs()
    st = load_state()
    P = perss.Perss()
    cutoff = TODAY - datetime.timedelta(days=a.days)
    todo = []
    if a.codes:
        todo = [{"per_cd": c.split(":")[0], "seq": c.split(":")[1], "biz_type": "", "biz_nm": "", "recv_date": "", "status": ""}
                for c in a.codes.split(",") if ":" in c]
    else:
        for pg in range(1, a.pages + 1):
            rows = P.list_page(pg)
            if not rows:
                break
            old = 0
            for r in rows:
                dt = parse_date(r["recv_date"])
                if dt and dt < cutoff:
                    old += 1; continue
                if a.force or r["per_cd"] not in st:
                    todo.append(r)
            if old == len(rows):       # 이 쪽은 전부 기간 밖(최신순이라 더 볼 필요 없음)
                break
    log(f"처리할 사업 {len(todo)}건")
    summary = {"ok": 0, "skip": 0, "error": 0}
    for r in todo[:a.limit]:
        try:
            status, note, meta = process(P, r, VW, a.test)
        except Exception as err:
            traceback.print_exc()
            status, note = "error", f"{type(err).__name__}: {err}"[:200]
        log(f"  {r['per_cd']} {r['biz_nm'][:30]} -> {status}: {note}")
        summary[status] = summary.get(status, 0) + 1
        if not a.test:
            st[r["per_cd"]] = {"status": status, "note": note, "date": TODAY.isoformat(), "seq": r["seq"], "biz_nm": r["biz_nm"],
                               "recv_date": r["recv_date"], "진행현황": r["status"]}
            save_state(st)
        time.sleep(0.5)
    n = store.rebuild_gpkg() if not a.test else 0
    log(f"\n요약 {summary} / 레이어 사업지구 {n}건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
