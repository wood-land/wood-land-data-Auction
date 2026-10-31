"""
run_approx.py - 검토대기 사업의 '대략위치'(대표지번 주변 원)와 '대표지번필지'를 만든다(이미 검토대기인 사업 보충용).

  python run_approx.py            # state 의 검토대기(review) 사업 전부
  python run_approx.py GW2026K002 # 지정 사업
새로 검토대기가 되는 사업은 run_eiass.py 가 자동으로 만든다. 결과는 approx/ 와 gpkg 레이어 '대략위치'·'대표지번필지'.
"""
import json
import sys

from core import site, store, vworld


def main():
    store.ensure_dirs()
    st = store.load_state()
    codes = sys.argv[1:] or [k for k, v in st.items() if isinstance(v, dict) and v.get("status") == "review"]
    for cd in codes:
        rp = store.DATA / "review" / f"{cd}.json"
        if not rp.exists():
            print(f"{cd}: review/{cd}.json 없음 - 건너뜀"); continue
        meta = json.loads(rp.read_text(encoding="utf-8"))
        if store.too_large(meta.get("plan_m2")):
            print(f"{cd}: 대규모 사업({meta.get('plan_m2'):,}㎡) - 대략위치·검토 대상에서 제외(skip 처리)")
            st[cd] = {**st.get(cd, {}), "status": "skip", "need": None, "note": f"대규모 사업(계획면적 {meta.get('plan_m2'):,}㎡ > 약 140만㎡): 자동 추출 대상 아님"}
            for f in (store.DATA / "review").glob(f"{cd}.*"):
                f.unlink()
            store.clear_approx(cd)
            store.save_state(st)
            continue
        route = site.route_parts(meta.get("location"))
        if route:   # 노선형 사업(도로 등): 시점~종점을 직선으로 잇는다. 10km 넘으면 제외
            from pyproj import Geod
            pts = [vworld.locate(t) for t in route]
            if not all(pts):
                print(f"{cd}: 노선 시점/종점 위치를 못 찾음 ({route})"); continue
            rp2 = [(pts[0][0], pts[0][1]), (pts[1][0], pts[1][1])]
            km = Geod(ellps="WGS84").inv(*rp2[0], *rp2[1])[2] / 1000
            if km > site.ROUTE_MAX_KM:
                print(f"{cd}: 노선형 사업 직선 {km:.1f}km > {site.ROUTE_MAX_KM:.0f}km - skip 처리")
                st[cd] = {**st.get(cd, {}), "status": "skip", "need": None, "note": f"노선형 사업이 너무 김({km:.1f}km > {site.ROUTE_MAX_KM:.0f}km): 자동 추출 대상 아님"}
                for f in (store.DATA / "review").glob(f"{cd}.*"):
                    f.unlink()
                store.clear_approx(cd); store.save_state(st); continue
            store.write_approx(cd, meta, 0, 0, "", meta.get("plan_m2"), route=rp2, km=round(km, 2))
            print(f"{cd}: 노선형 사업 시점~종점 직선 {km:.1f}km")
            continue
        loc = vworld.locate(meta.get("location") or "")
        if not loc:
            print(f"{cd}: 위치를 못 찾음 ({meta.get('location')})"); continue
        lon, lat, how = loc
        pg = None
        if str(how).startswith("PARCEL"):
            from shapely.geometry import Point, shape
            for f in vworld.parcels_bbox(lon - 0.0004, lat - 0.0004, lon + 0.0004, lat + 0.0004, cell=0.01):
                if shape(f["geometry"]).buffer(0).contains(Point(lon, lat)):
                    pg = shape(f["geometry"]).buffer(0); break
        store.write_approx(cd, meta, lon, lat, how, meta.get("plan_m2"), pg)
        print(f"{cd}: {lon:.5f},{lat:.5f} ({how}) 반경 {store.approx_radius(meta.get('plan_m2')):.0f}m 대표필지 {'있음' if pg is not None else '없음'}")
    print(f"레이어 사업지구 {store.rebuild_gpkg()}건")


if __name__ == "__main__":
    main()
