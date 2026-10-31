"""
run_manual.py - 사람이 지리참조자로 찍은 기준점(.points)으로 검토대기 사업을 확정한다.

  python run_manual.py ND2026D003                   # DB 저장소 eiass/manual/ND2026D003.points 사용
  python run_manual.py ND2026D003 --points 경로.points
  python run_manual.py                              # manual/ 에 .points 가 있는 사업을 모두

요청 꾸러미: figures/{코드}_review.png (+ _review.json). 기준점은 이 PNG 위에서 찍어야 한다.
결과: projects/·parcels/·preview/ 저장, georef '수동 지리참조 N점', grade C, state manual=True. 점이 1개면 계획면적에서 구한 축척·회전 0 으로.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

import run_eiass as R
from core import figure, kakao, manual, store, vworld


def apply_one(cd, points_path, state):
    req_p = store.DATA / "figures" / f"{cd}_review.json"
    if not req_p.exists():
        raise SystemExit(f"{cd}: 요청 꾸러미({req_p.name})가 없음 - run_eiass.py 가 검토대기로 만든 사업이어야 함")
    req = json.loads(req_p.read_text(encoding="utf-8"))
    if not req.get("contour_page_px"):
        raise SystemExit(f"{cd}: 자동 경계 윤곽이 없음(도면에서 경계를 못 찾은 사업) - 경계를 QGIS 에서 직접 그려 projects/ 에 넣어 주세요")
    crs_s, pts = manual.parse_points(points_path)
    epsg = manual.epsg_of(crs_s) or 5186
    if len(pts) < 1:
        raise SystemExit(f"{cd}: 쓸 수 있는 기준점이 없음")
    k = req["png_scale"]
    from pyproj import Transformer
    tr = Transformer.from_crs(epsg, 5186, always_xy=True).transform
    pairs = []
    for sx, sy, X, Y in pts:
        X5, Y5 = tr(X, Y)
        pairs.append((sx / k, sy / k, X5, Y5))             # PNG px -> 쪽 px
    contour = np.array(req["contour_page_px"], float)
    plan = req.get("plan_m2")
    fixed = None
    if len(pairs) == 1:
        # 쪽 px 하나의 지상 길이: 계획면적 / 경계 폴리곤 px 면적
        import cv2
        a_px = cv2.contourArea(contour.astype(np.float32))
        fixed = math.sqrt(plan / a_px) if plan else None
    A, res = manual.fit_similarity(pairs, fixed)
    poly = R.to5186(A, contour, 5186)
    diff = (poly.area / plan - 1) * 100 if plan else None
    scale = float(np.hypot(A[0, 0], A[1, 0]))
    print(f"  {cd}: 기준점 {len(pairs)}개 / 잔차 {['%.1f' % r for r in res]} m / 축척 {scale:.3f} m/px / 면적 {poly.area:.0f}㎡"
          + (f" (계획 대비 {diff:+.1f}%)" if diff is not None else ""))
    warn = []
    if len(pairs) >= 2 and max(res) > 15:
        warn.append(f"잔차 {max(res):.0f}m")
    if diff is not None and abs(diff) > 10:
        warn.append(f"면적차 {diff:+.0f}%")
    if warn:
        print("  ※ 확인 필요:", ", ".join(warn), "- 점 위치나 점 사이 거리(최소 도면 폭의 1/3 이상)를 확인해 주세요")
    meta = {k_: req.get(k2) for k_, k2 in (("biz_nm", "biz_nm"), ("location", "location"), ("eiass_url", "eiass_url"))}
    old = {}
    pj = store.DATA / "review" / f"{cd}.json"
    if pj.exists():
        old = json.loads(pj.read_text(encoding="utf-8"))
    meta = {**{k_: old.get(k_) for k_ in ("biz_cd", "biz_nm", "biz_type", "location", "choan_period", "plan_m2", "report_file", "report_file_seq", "eiass_url")},
            **{k_: v for k_, v in meta.items() if v}, "biz_cd": cd, "extracted": R.TODAY}
    meta.update({"area_m2": round(poly.area, 1), "area_diff_pct": round(diff, 2) if diff is not None else None,
                 "accuracy_m": f"약 {max(3, max(res) if len(pairs) >= 2 else 20):.0f}",
                 "georef": f"수동 지리참조 {len(pairs)}점(잔차 최대 {max(res):.1f}m)", "grade": "C",
                 "src": f"{old.get('file', '')} {(req.get('page') or 0) + 1}쪽"})
    page_img = R_img(cd, req)
    fig_png = figure.write_site_png(page_img, contour, A, 5186, store.DATA / "figures" / f"{cd}_site.png") if page_img is not None else None
    if fig_png:
        meta["figure_png"] = f"figures/{cd}_site.png"
    from shapely.ops import transform
    store.write_project(cd, meta, transform(Transformer.from_crs(5186, 4326, always_xy=True).transform, poly))
    if vworld.available():
        rows = R.pnu_rows(poly)
    elif kakao.KEY:
        rows, _, _ = kakao.pnu_grid(poly)
    else:
        rows = []
    store.write_parcels(cd, rows)
    R.preview(poly, store.DATA / "preview" / f"{cd}.jpg")
    for f in (store.DATA / "review").glob(f"{cd}.*"):
        f.unlink()
    store.clear_approx(cd)
    st = state.setdefault(cd, {})
    st.update({"status": "ok", "note": f"수동 지리참조 {len(pairs)}점", "need": None, "manual": True, "date": R.TODAY})
    print(f"  저장: 필지 {len(rows)}건")


def R_img(cd, req):
    """_site.png 용 원본 쪽 그림: 다시 내려받지 않고 review PNG 를 쪽 px 크기로 되돌려 쓴다(해상도는 PNG 만큼)."""
    import cv2
    p = store.DATA / "figures" / f"{cd}_review.png"
    if not p.exists():
        return None
    im = cv2.imread(str(p))
    if im is None:
        return None
    h, w = req["page_size_hw"]
    return cv2.resize(im, (w, h), interpolation=cv2.INTER_CUBIC)[:, :, ::-1].copy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("codes", nargs="*")
    ap.add_argument("--points", default="")
    a = ap.parse_args()
    store.ensure_dirs()
    state = store.load_state()
    mdir = store.DATA / "manual"
    codes = a.codes or [p.stem for p in sorted(mdir.glob("*.points"))]
    if not codes:
        print("처리할 기준점 파일이 없음 (eiass/manual/{코드}.points)"); return 0
    for cd in codes:
        pp = Path(a.points) if a.points else mdir / f"{cd}.points"
        if not pp.exists():
            print(f"{cd}: {pp} 없음"); continue
        apply_one(cd, pp, state)
        store.save_state(state)
    n = store.rebuild_gpkg()
    print(f"레이어 사업지구 {n}건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
