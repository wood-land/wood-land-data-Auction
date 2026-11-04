"""
run_manual.py - 사람이 지리참조자로 찍은 기준점(.points)으로 검토대기 사업을 확정한다.

  python run_manual.py                              # manual/ 에 .points 가 있는 사업을 모두(Actions·PC 가 매 실행 처음에 돈다)
  python run_manual.py ND2026D003                   # DB 저장소 eiass/manual/ND2026D003.points 사용
  python run_manual.py ND2026D003 --points 경로.points
  python run_manual.py ND2026D003 --force           # 경고(잔차·면적차·점 간격)를 무시하고 확정

요청 꾸러미: figures/{코드}_review.png (+ _review.json). 기준점은 이 PNG 위에서 찍어야 한다.
처리 순서: 점 읽기 -> 검증 -> 닮음변환 맞춤 -> 경계·필지·미리보기·투명 PNG 저장 -> 상태 ok(등급 C) -> .points 를 manual/done/ 으로 보관.
검증(통과해야 확정): 점이 2개 이상이면 서로 가장 먼 두 점의 거리가 PNG 폭의 1/3 이상, 잔차 15m 이하, 계획면적과 ±10% 이내.
실패하면 확정하지 않고 사유를 state.json 의 manual_fail 에 적는다(notify.py 가 이슈에 댓글). 같은 .points 는 다시 처리하지 않는다 -
점을 고쳐 다시 올리면(내용이 바뀌면) 다시 처리한다. 점이 1개면 계획면적에서 구한 축척·회전 0 으로 맞춘다.
"""
import argparse
import hashlib
import json
import math
import shutil
import sys
import traceback
from pathlib import Path

import numpy as np

import run_eiass as R
from core import figure, kakao, manual, store, vworld

MIN_SPREAD = 1 / 3        # 가장 먼 두 점의 거리 / PNG 폭
MAX_RES_M = 15.0
MAX_AREA_DIFF = 10.0


class Rejected(Exception):
    """사람이 고쳐야 하는 문제(확정하지 않고 사유만 남긴다)"""


def file_hash(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()[:12]


def apply_one(cd, points_path, state, force=False):
    req_p = store.DATA / "figures" / f"{cd}_review.json"
    if not req_p.exists():
        raise Rejected(f"요청 꾸러미({req_p.name})가 없음 - 자동 추출이 검토대기로 만든 사업이어야 함")
    req = json.loads(req_p.read_text(encoding="utf-8"))
    if not req.get("contour_page_px"):
        raise Rejected("자동 경계 윤곽이 없음(도면에서 경계를 못 찾은 사업) - 경계를 QGIS 에서 직접 그려 projects/%s.geojson 으로 넣어 주세요" % cd)
    crs_s, pts = manual.parse_points(points_path)
    epsg = manual.epsg_of(crs_s) or 5186
    if len(pts) < 1:
        raise Rejected("쓸 수 있는 기준점이 없음(.points 에 켜 둔 점이 없음)")
    k = req["png_scale"]
    png_w = req["page_size_hw"][1] * k
    problems = []
    if len(pts) >= 2:
        far = max(math.hypot(a[0] - b[0], a[1] - b[1]) for a in pts for b in pts)
        if far < png_w * MIN_SPREAD:
            problems.append(f"기준점이 서로 너무 가까움(가장 먼 두 점 {far:.0f}px < PNG 폭의 1/3 = {png_w * MIN_SPREAD:.0f}px) - 도면 양끝 쪽 점을 더해 주세요")
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
        if fixed is None:
            raise Rejected("점이 1개인데 계획면적이 없어 축척을 정할 수 없음 - 점을 2개 이상 찍어 주세요")
    A, res = manual.fit_similarity(pairs, fixed)
    poly = R.to5186(A, contour, 5186)
    diff = (poly.area / plan - 1) * 100 if plan else None
    scale = float(np.hypot(A[0, 0], A[1, 0]))
    print(f"  {cd}: 기준점 {len(pairs)}개 / 잔차 {['%.1f' % r for r in res]} m / 축척 {scale:.3f} m/px / 면적 {poly.area:.0f}㎡"
          + (f" (계획 대비 {diff:+.1f}%)" if diff is not None else ""), flush=True)
    if len(pairs) >= 2 and max(res) > MAX_RES_M:
        problems.append(f"기준점 잔차가 큼(최대 {max(res):.0f}m > {MAX_RES_M:.0f}m) - 어긋난 점이 있는지 확인해 주세요")
    if diff is not None and abs(diff) > MAX_AREA_DIFF:
        problems.append(f"경계 면적이 계획면적과 {diff:+.0f}% 차이(±{MAX_AREA_DIFF:.0f}% 초과) - 점 위치나 점 사이 거리를 확인해 주세요")
    if problems and not force:
        raise Rejected("; ".join(problems))
    if problems:
        print("  ※ 경고를 무시하고 확정:", "; ".join(problems))
    old = {}
    pj = store.DATA / "review" / f"{cd}.json"
    if pj.exists():
        old = json.loads(pj.read_text(encoding="utf-8"))
    meta = {k_: req.get(k_) for k_ in ("biz_nm", "location", "eiass_url")}
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
    st.update({"status": "ok", "note": f"수동 지리참조 {len(pairs)}점", "need": None, "manual": True, "manual_fail": None, "date": R.TODAY})
    print(f"  저장: 필지 {len(rows)}건")


def archive_points(cd, points_path):
    """확정한 .points 를 manual/done/ 으로 옮겨 다시 처리하지 않게 하고, 나중에 같은 결과를 다시 만들 수 있게 보관한다."""
    done = store.DATA / "manual" / "done"
    done.mkdir(parents=True, exist_ok=True)
    shutil.move(str(points_path), str(done / f"{cd}.points"))


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
    ap.add_argument("--force", action="store_true", help="검증 경고(잔차·면적차·점 간격)를 무시하고 확정")
    a = ap.parse_args()
    store.ensure_dirs()
    state = store.load_state()
    mdir = store.DATA / "manual"
    codes = a.codes or [p.stem for p in sorted(mdir.glob("*.points"))]
    if not codes:
        print("처리할 기준점 파일이 없음 (eiass/manual/{코드}.points)"); return 0
    n_ok = n_fail = n_skip = 0
    for cd in codes:
        pp = Path(a.points) if a.points else mdir / f"{cd}.points"
        if not pp.exists():
            print(f"{cd}: {pp} 없음"); continue
        h = file_hash(pp)
        prev = (state.get(cd) or {}).get("manual_fail") or {}
        if prev.get("hash") == h and not a.force:
            print(f"{cd}: 이미 같은 점으로 실패함({prev.get('reason', '')[:60]}) - 점을 고쳐 다시 올려 주세요"); n_skip += 1; continue
        try:
            apply_one(cd, pp, state, a.force)
            if not a.points:
                archive_points(cd, pp)
            n_ok += 1
        except Rejected as e:
            print(f"  {cd}: 확정하지 않음 - {e}")
            state.setdefault(cd, {})["manual_fail"] = {"reason": str(e), "hash": h, "date": R.TODAY, "commented": False}
            n_fail += 1
        except Exception as e:
            traceback.print_exc()
            state.setdefault(cd, {})["manual_fail"] = {"reason": f"처리 중 오류 {type(e).__name__}: {e}"[:300], "hash": h,
                                                       "date": R.TODAY, "commented": False}
            n_fail += 1
        store.save_state(state)
    n = store.rebuild_gpkg() if n_ok else None
    print(f"\n요약 확정 {n_ok} / 확정 안 함 {n_fail} / 이미 실패한 점 {n_skip}" + (f" / 레이어 사업지구 {n}건" if n is not None else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
