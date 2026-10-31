"""
run_eiass.py - 환경영향평가 초안공람 사업지구를 자동 추출한다.

  python run_eiass.py                  # 목록 1~2쪽(최신 20건) 중 아직 안 한 사업
  python run_eiass.py --pages 5        # 목록 5쪽까지
  python run_eiass.py --codes GG2026B008:45831,YS2025L001:45619 --force   # 지정 사업 다시
  python run_eiass.py --retry-review   # 검토대기(review) 사업도 다시 시도

흐름: 목록 -> 상세(사업지위치, 평가서 파일) -> '사업의 개요' PDF 에서 도면 쪽 찾기 -> 경계 추출
      -> 좌표 맞춤(항공사진: 위성영상 SIFT / 선 도면: 연속지적도 chamfer) -> 품질검사
      -> 통과: projects/·parcels/(PNU)·preview/ 저장,  실패: review/ 에 남김
"""
import argparse
import datetime
import json
import math
import re
import sys
import time
import traceback

import cv2
import numpy as np

from core import extract as ex
from core import anchor, figure, georef, kakao, manual, site, store, vworld

FIG_KEYS = [("토지이용계획", 3), ("항공사진", 2), ("중첩", 2), ("배치도", 1), ("지구계", 1)]
TODAY = datetime.date.today().isoformat()
NOSAVE = False
RUNNER = "actions" if __import__("os").environ.get("GITHUB_ACTIONS") else (__import__("os").environ.get("GOSI_PC_NAME") or __import__("platform").node())


def log(*a):
    print(*a, flush=True)


def find_overview(files):
    for f in files:
        if re.search(r"사업\s*의?\s*개요", f["name"]):
            return f
    return None


def figure_pages(E, sid, n):
    """그림 쪽 후보(점수순)와 글 전체."""
    texts, cands = [], []
    for p in range(n):
        try:
            t = E.page_text(sid, p)
        except Exception:
            t = ""
        texts.append(t)
        s = 0
        for k, w in FIG_KEYS:
            if k in t:
                s += w
        if "그림" in t and s > 0:
            cands.append((s, p))
    cands.sort(key=lambda x: (-x[0], x[1]))
    return [p for _, p in cands[:6]], texts


def to5186(A, contour, crs=3857):
    from pyproj import Transformer
    from shapely.geometry import Polygon
    XY = georef.apply(A, contour)
    if crs == 5186:
        x, y = XY[:, 0], XY[:, 1]
    else:
        x, y = Transformer.from_crs(crs, 5186, always_xy=True).transform(XY[:, 0], XY[:, 1])
    return Polygon(np.c_[x, y]).buffer(0).simplify(0.3)


def pnu_rows(poly5186, parcels=None):
    from pyproj import Transformer
    from shapely.geometry import shape
    from shapely.ops import transform
    to4326 = Transformer.from_crs(5186, 4326, always_xy=True).transform
    to5186 = Transformer.from_crs(4326, 5186, always_xy=True).transform
    p4 = transform(to4326, poly5186)
    minx, miny, maxx, maxy = p4.bounds
    pad = 0.0005
    if parcels is None:
        parcels = vworld.parcels_bbox(minx - pad, miny - pad, maxx + pad, maxy + pad, cell=0.01)
    rows = []
    for f in parcels:
        try:
            g = transform(to5186, shape(f["geometry"])).buffer(0)
        except Exception:
            continue
        if not g.intersects(poly5186):
            continue
        ov = g.intersection(poly5186).area
        if ov < 1:
            continue
        ratio = ov / g.area if g.area else 0
        rows.append({"pnu": f["pnu"], "jibun": f["jibun"], "addr": f["addr"], "parcel_m2": round(g.area, 1),
                     "overlap_m2": round(ov, 1), "ratio": round(ratio, 3), "구분": "편입" if ratio >= 0.05 else "경계접촉(확인필요)"})
    rows.sort(key=lambda r: (-r["ratio"], r["pnu"]))
    return rows


def preview(poly5186, path, page_img=None, contour=None):
    """위성영상 위 경계(작게). 실패해도 넘어간다."""
    try:
        from pyproj import Transformer
        from shapely.ops import transform
        p4 = transform(Transformer.from_crs(5186, 4326, always_xy=True).transform, poly5186)
        c = p4.centroid
        half = max(300, math.sqrt(poly5186.area) * 0.9)
        S, x0, y0, res, z, ok = vworld.satellite_mosaic(c.x, c.y, half, max(1.0, half / 450), max_tiles=80)
        pts = []
        for lon, lat in p4.exterior.coords:
            X, Y = vworld.ll2merc(lon, lat); pts.append(((X - x0) / res, (y0 - Y) / res))
        img = S[:, :, ::-1].copy()
        cv2.polylines(img, [np.int32(pts)], True, (255, 0, 255), 3)
        P = np.int32(pts); bx0, by0 = np.maximum(P.min(0) - 80, 0); bx1, by1 = P.max(0) + 80
        img = img[by0:by1, bx0:bx1]
        k = min(1.0, 1100 / max(img.shape[:2]))
        cv2.imwrite(str(path), cv2.resize(img, None, fx=k, fy=k, interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 80])
    except Exception as e:
        log("    미리보기 실패:", e)


def save_figure(img, path, long_side=2400):
    """평가서 도면 쪽을 PNG 로 남긴다(지리참조자 작업용). 쪽 px -> PNG px 배율 k 를 돌려준다(실패하면 None)."""
    try:
        k = min(1.0, long_side / max(img.shape[:2]))
        v = cv2.resize(img[:, :, ::-1], None, fx=k, fy=k, interpolation=cv2.INTER_AREA) if k < 1 else img[:, :, ::-1]
        path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), v)
        return k
    except Exception as err:
        log("    도면 PNG 저장 실패:", err)
        return None


def review_image(img, e, path):
    try:
        v = img[:, :, ::-1].copy()
        if e is not None:
            cv2.polylines(v, [np.int32(e["contour"])], True, (255, 0, 255), 6)
        k = min(1.0, 1400 / max(v.shape[:2]))
        cv2.imwrite(str(path), cv2.resize(v, None, fx=k, fy=k, interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 75])
    except Exception:
        pass


def judge(r, area_m2, plan):
    """품질검사. (통과여부, 정확도 추정 m, 사유)"""
    diff = (area_m2 / plan - 1) * 100 if plan else None
    if r["method"] == "anchor":
        reasons = []
        if r["inliers"] < 6: reasons.append(f"지번 대응 {r['inliers']}<6")
        if r["rms_m"] > 12: reasons.append(f"지번 잔차 {r['rms_m']:.1f}m")
        if r["spread"] < 0.25: reasons.append(f"지번 분포 {r['spread']:.2f}")
        if not (0.75 <= r["scale_ratio"] <= 1.35): reasons.append(f"축척비 {r['scale_ratio']:.2f}")
        if diff is not None and abs(diff) > 6: reasons.append(f"면적차 {diff:+.1f}%")
        if plan is None: reasons.append("계획면적 모름")
        # 잔차에는 '필지 중심 vs 도면 글자 위치' 차이가 섞여 있어 실제 오차보다 큰 편이다
        return (not reasons), max(3.0, r["rms_m"]), "; ".join(reasons)
    if r["method"] == "sift":
        reasons = []
        if r["inliers"] < 12: reasons.append(f"대응점 {r['inliers']}<12")
        if not (0.8 <= r["scale_ratio"] <= 1.25): reasons.append(f"축척비 {r['scale_ratio']:.2f}")
        if r["spread"] < 0.25: reasons.append(f"대응점 분포 {r['spread']:.2f}")
        if diff is not None and abs(diff) > 6: reasons.append(f"면적차 {diff:+.1f}%")
        if plan is None: reasons.append("계획면적 모름")
        acc = max(1.0, (r["rms_m"] or 5) * 2)
        return (not reasons), acc, "; ".join(reasons)
    reasons = []
    if r["peak_ratio"] < 1.15: reasons.append(f"봉우리비 {r['peak_ratio']:.2f}")
    if r["coincide"] < 0.15: reasons.append(f"선 일치율 {r['coincide']:.2f}")
    if r["local_max_m"] is not None and r["local_max_m"] > 5: reasons.append(f"국소 어긋남 {r['local_max_m']:.1f}m")
    acc = max(1.0, (r["local_max_m"] or 3) + 1)
    return (not reasons), acc, "; ".join(reasons)


def process(E, row, state, force=False):
    cd = row["biz_cd"]
    log(f"\n=== {cd} {row.get('biz_nm','')}")
    d = E.detail(cd, row["biz_seq"])
    meta = {"biz_cd": cd, "biz_nm": d["biz_nm"] or row.get("biz_nm"), "biz_type": d["biz_type"] or row.get("biz_type"),
            "location": d["location"], "choan_period": d["choan_period"] or row.get("choan_period"), "extracted": TODAY}
    if not d["files"]:
        return "skip", "평가서 파일 링크 없음(공람이 끝나면 비공개)", meta, None
    ov = find_overview(d["files"])
    if not ov:
        return "review", "'사업의 개요' 파일을 못 찾음(파일 이름 확인 필요)", meta, "human"
    # 사업 상세 화면 영구 링크(GET 으로 열린다)와 평가서 파일 식별자: 제목으로 다시 찾지 않아도 된다
    meta.update({"eiass_url": f"{site.BASE}/partcptn/choan/choanEiassView.do?BIZ_CD={cd}&BIZ_SEQ={row['biz_seq']}",
                 "report_file": ov["name"], "report_file_seq": ov["seq"]})
    sid = E.streamdocs_id(ov["seq"], ov["name"])
    n = E.page_count(sid)
    pages, texts = figure_pages(E, sid, n)
    plan = site.parse_plan_area(texts)
    meta["plan_m2"] = plan
    log(f"  위치: {d['location']} | 계획면적 {plan} | 도면 후보 쪽 {pages}")
    if store.too_large(plan):   # 대규모 사업(당진 석산·새만금 등): 도면 한 장으로 경계를 맞출 수 없고 대략위치 원도 의미가 없다
        return "skip", f"대규모 사업(계획면적 {plan:,}㎡ > 약 140만㎡): 자동 추출 대상 아님", meta, None
    VW = vworld.available()
    PC = "pc" if not VW else "human"   # 브이월드가 막힌 곳(Actions)의 좌표 맞춤 실패는 PC 에서 다시 해 볼 만하다
    loc = vworld.locate(d["location"]) if VW else kakao.locate(d["location"], vworld.address_variants)
    if not loc:
        return "review", "사업지위치 좌표 못 찾음", meta, PC
    lon, lat, how = loc
    log(f"  대략 위치 {lon:.5f},{lat:.5f} ({how})")
    route = site.route_parts(d["location"])   # 노선형 사업(도로 등): 시점·종점 좌표
    route_pts, route_km = None, None
    if route:
        loc_fn = vworld.locate if VW else (lambda t: kakao.locate(t, vworld.address_variants))
        pts = [loc_fn(t) for t in route]
        if all(pts):
            from pyproj import Geod
            route_pts = [(pts[0][0], pts[0][1]), (pts[1][0], pts[1][1])]
            straight = Geod(ellps="WGS84").inv(*route_pts[0], *route_pts[1])[2] / 1000
            route_km = site.parse_route_km(texts)
            L = max(route_km or 0, straight)
            log(f"  노선형 사업: 시점~종점 직선 {straight:.1f}km, 평가서 연장 {route_km}km")
            if L > site.ROUTE_MAX_KM:
                return "skip", f"노선형 사업이 너무 김({L:.1f}km > {site.ROUTE_MAX_KM:.0f}km): 자동 추출 대상 아님", meta, None
    fails, first_img = [], None          # (사유, 필요(pc|human), 그림, 경계)
    anchor_by_page = {}                  # 쪽 -> 지번 정합 결과(성공·실패 모두)
    page_of = {}                         # id(그림) -> 쪽(0부터). 사람 요청용 꾸러미에 쓴다
    for p in pages:
        try:
            img = E.render(sid, p)
            page_of[id(img)] = p
        except Exception as err:
            log(f"  쪽 {p} 그림 실패: {err}"); continue
        cands = ex.extract_candidates(img, max_n=3)
        if first_img is None:
            first_img = img
        if not cands:
            log(f"  쪽 {p}: 경계 못 찾음(빨강·자주·파랑·노랑·흰 선, 채색 면 모두)"); continue
        for e in cands:
          kind, white, box = ex.background_kind(img, e["mask"])
          s_est = math.sqrt(plan / e["area_px"]) if plan else None
          log(f"  쪽 {p} [{e['color']}]: 경계 {len(e['contour'])}점 면적 {e['area_px']:.0f}px 추종 {e['red_frac']:.2f} 배경 {kind}(흰 {white:.2f}) px≈{s_est and round(s_est,3)}m")
          if not s_est:
              fails.append(("계획면적을 평가서에서 못 읽음", "human", img, e)); continue
          if not (0.02 <= s_est <= 200):  # 도면 한 픽셀이 2cm 미만이거나 200m 초과면 계획면적·경계 읽기가 틀린 것(좌표 맞춤에서 수학 오류가 난다)
              log(f"  척도 이상(px≈{s_est:.3g}m): 계획면적 또는 경계 읽기 오류로 보고 건너뜀")
              fails.append((f"척도 이상 px≈{s_est:.3g}m(계획면적 {plan} 확인)", "human", img, e)); continue
          half = max(1500.0, 2.5 * math.sqrt(plan))
          try:
              r = None
              if VW:   # 1순위: 도면의 지번 글자를 지적도와 맞춘다(쪽 단위라 후보마다 다시 읽지 않는다)
                  if p not in anchor_by_page:
                      anchor_by_page[p] = anchor.anchor_georef(img, s_est, lon, lat, half, log)
                      if not anchor_by_page[p].get("ok"):
                          log(f"  지번 정합 안 됨: {anchor_by_page[p].get('reason')}")
                  if anchor_by_page[p].get("ok"):
                      r = anchor_by_page[p]
                      ar = to5186(r["A"], e["contour"], r["crs"]).area
                      if not judge(r, ar, plan)[0]:    # 이 후보 경계와는 면적이 안 맞음 -> 다른 방법으로
                          r = None
              if r is not None:
                  pass
              elif kind == "line" and not VW:
                  log("  선 도면은 연속지적도가 필요한데 이 환경에서 브이월드가 막힘 -> 국내 IP PC 에서 처리")
                  fails.append(("선 도면: 국내 IP PC(브이월드) 필요", "pc", img, e)); continue
              elif kind == "aerial":
                  r = georef.sift_georef(img, ex.aerial_feature_mask(img, e["mask"], box), box, s_est, lon, lat, half, log)
              else:
                  r = georef.chamfer_georef(ex.line_points(img, e["mask"], box), e["contour"], s_est, lon, lat, half, log)
          except Exception as err:
              log("  좌표 맞춤 오류:", err); traceback.print_exc()
              fails.append((f"좌표 맞춤 오류 {err}", PC, img, e)); continue
          if not r.get("ok"):
              log("  좌표 맞춤 실패:", r.get("reason")); fails.append((f"좌표 맞춤 실패: {r.get('reason')}", PC, img, e)); continue
          poly = to5186(r["A"], e["contour"], r.get("crs", 3857))
          ok, acc, why = judge(r, poly.area, plan)
          stats = {k: v for k, v in r.items() if k in ("inliers", "matches", "rms_m", "scale_ratio", "spread", "rot_deg",
                                                        "peak_ratio", "coincide", "local_max_m", "cost")}
          log(f"  {r['method']}: {json.dumps(stats, ensure_ascii=False, default=float)} 면적 {poly.area:.0f}㎡ -> {'통과' if ok else '검토: ' + why}")
          if not ok:
              fails.append((f"{r['method']} 품질검사 탈락: {why}", PC, img, e))
              continue
          if NOSAVE:
              log(f"  [시험] eiass/_test/ 에 저장. 면적 {poly.area:.0f}㎡ 중심 {poly.centroid.x:.1f},{poly.centroid.y:.1f}(EPSG:5186)")
          from pyproj import Transformer
          from shapely.ops import transform
          meta.update({"area_m2": round(poly.area, 1), "area_diff_pct": round((poly.area / plan - 1) * 100, 2),
                       "accuracy_m": f"약 {acc:.0f}", "georef": f"자동 {r['method']}{'(' + r['imagery'] + ')' if r.get('imagery') else ''} {json.dumps(stats, ensure_ascii=False, default=lambda x: round(float(x), 3))}",
                       "src": f"{ov['name']} {p + 1}쪽", "grade": "A" if r["method"] == "anchor" else "B"})
          # 사업지구만 남긴(바깥 투명) 도면 PNG + 월드파일: QGIS 에 끌어 넣으면 제 위치에 놓인다
          try:
              if figure.write_site_png(img, e["contour"], r["A"], r.get("crs", 3857), store.DATA / "figures" / f"{cd}_site.png"):
                  meta["figure_png"] = f"figures/{cd}_site.png"
          except Exception as err:
              log("    사업지구 PNG 저장 실패:", err)
          (store.DATA / "figures" / f"{cd}_review.png").unlink(missing_ok=True)
          store.write_project(cd, meta, transform(Transformer.from_crs(5186, 4326, always_xy=True).transform, poly))
          if vworld.available():
              rows = pnu_rows(poly, r.get("parcels")); how_pnu = "브이월드 연속지적도"
          elif kakao.KEY:
              rows, npts, stp = kakao.pnu_grid(poly); how_pnu = f"카카오 격자 {npts}점({stp:.0f}m)"
          else:
              rows, how_pnu = [], "PNU 생략(키 없음)"
          store.write_parcels(cd, rows)
          log(f"  PNU: {how_pnu}")
          preview(poly, store.DATA / "preview" / f"{cd}.jpg")
          for f in (store.DATA / "review").glob(f"{cd}.*"):
              f.unlink()
          store.clear_approx(cd)
          log(f"  저장: 필지 {len(rows)}건 (편입 {sum(1 for x in rows if x['구분'].startswith('편입'))})")
          if NOSAVE:
              return "test", f"{r['method']} 시험 통과(_test 저장)", meta, None
          return "ok", f"{r['method']}·{e['color']} 정확도 약 {acc:.0f}m", meta, None
    if fails:
        need = "pc" if any(f[1] == "pc" for f in fails) else "human"
        why = "; ".join(dict.fromkeys(f[0] for f in fails))[:300]
        img, e = next(((f[2], f[3]) for f in fails if f[1] == need), (fails[0][2], fails[0][3]))
    else:
        need, why, img, e = "human", "도면에서 사업지구 경계를 못 찾음", first_img, None
    if NOSAVE:
        return "test", f"[{need}] {why}", meta, need
    if img is not None:
        review_image(img, e, store.DATA / "review" / f"{cd}.jpg")
        k = save_figure(img, store.DATA / "figures" / f"{cd}_review.png")   # 사람이 지리참조자에 올릴 도면(쪽 전체)
        if k:   # 지리참조 결과(.points)를 쪽 px 로 되돌리고 경계를 옮기는 데 필요한 정보
            manual.write_request(store.DATA, cd, meta, k=k, page=page_of.get(id(img)), contour=None if e is None else e["contour"],
                                 plan=plan, lonlat=(lon, lat), size=img.shape[:2])
    try:   # 단서가 부족해도 대표지번 주변 원과 대표지번 필지는 QGIS 에 남긴다
        pg = None
        if str(how).startswith("PARCEL"):
            from shapely.geometry import Point, shape
            for f in vworld.parcels_bbox(lon - 0.0004, lat - 0.0004, lon + 0.0004, lat + 0.0004, cell=0.01):
                if shape(f["geometry"]).buffer(0).contains(Point(lon, lat)):
                    pg = shape(f["geometry"]).buffer(0); break
        store.write_approx(cd, meta, lon, lat, how, plan, pg, route=route_pts, km=route_km)
    except Exception as err:
        log("    대략위치 저장 실패:", err)
    store.write_review_candidate(cd, meta, None)   # 품질검사 탈락 후보 폴리곤은 믿을 수 없어 목록·gpkg 에 넣지 않는다(예전 파일만 지운다)
    (store.DATA / "review" / f"{cd}.json").write_text(json.dumps({**meta, "reason": why, "need": need, "pages": pages,
                                                                 "file": ov["name"]}, ensure_ascii=False, indent=1), encoding="utf-8")
    return "review", why, meta, need


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--codes", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--retry-review", action="store_true")
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--test", action="store_true", help="결과를 저장하지 않고 로그만(수동 결과와 비교용)")
    a = ap.parse_args()
    global NOSAVE
    NOSAVE = a.test
    log(f"Tesseract(kor) {'있음 - 지번 앵커 정합 사용' if anchor.available() else '없음 - 지번 앵커 정합은 건너뜀(README 의 PC 설치 참고)'}")
    log(f"브이월드 {'사용 가능' if vworld.available() else '막힘(위성영상 Esri, 위치·PNU 카카오로 대신)'} / 카카오 키 {'있음' if kakao.KEY else '없음'}")
    if not vworld.available() and not kakao.KEY:
        log("::error::브이월드도 막히고 KAKAO_REST_API_KEY 도 없음"); return 2
    store.ensure_dirs()
    state = store.load_state()
    store.seed_from_gpkg(state)
    if NOSAVE:   # 시험: 결과는 eiass/_test/ 에만(본 레이어·state 는 건드리지 않는다)
        store.DATA = store.DATA / "_test"
        store.ensure_dirs()
    E = site.Eiass()
    if a.codes:
        rows = [{"biz_cd": c.split(":")[0], "biz_seq": c.split(":")[1]} for c in a.codes.split(",") if ":" in c]
    else:
        rows = []
        for pg in range(1, a.pages + 1):
            rows += E.list_page(pg)
    todo = []
    if a.retry_review and not a.codes:
        # 목록 쪽 밖으로 밀려난 PC 대기 사업도 다시(공람 중이면 파일이 열린다)
        listed = {r["biz_cd"] for r in rows}
        rows += [{"biz_cd": k, "biz_seq": v["biz_seq"], "biz_nm": v.get("biz_nm", "")} for k, v in state.items()
                 if isinstance(v, dict) and v.get("status") == "review" and v.get("need") == "pc" and v.get("biz_seq") and k not in listed]
    for r in rows:
        st = state.get(r["biz_cd"], {}).get("status")
        if state.get(r["biz_cd"], {}).get("manual") and not a.codes:
            continue   # 손으로 맞춘 사업은 --codes 로 지정할 때만 다시 한다
        need = state.get(r["biz_cd"], {}).get("need")
        retry = a.retry_review and (need != "human" or a.force)   # 사람 확인 대기는 기계가 다시 해도 같으므로 건너뛴다
        if a.codes or a.force or st is None or (st == "review" and retry) or st == "error":
            todo.append(r)
    log(f"목록 {len(rows)}건, 처리할 사업 {len(todo)}건")
    summary = {"ok": 0, "review": 0, "skip": 0, "error": 0}
    t0 = time.time()
    for r in todo[:a.limit]:
        try:
            status, note, meta, need = process(E, r, state, a.force)
        except Exception as err:
            traceback.print_exc()
            status, note, meta, need = "error", f"{type(err).__name__}: {err}"[:200], {}, None
        if status == "test":
            log(f"  -> 시험: {note}"); continue
        if status != "ok" and state.get(r["biz_cd"], {}).get("status") == "ok":
            log("  (이전 결과가 있어 그대로 둔다)"); continue
        prev = state.get(r["biz_cd"], {})
        state[r["biz_cd"]] = {"status": status, "note": note, "date": TODAY, "biz_seq": r["biz_seq"], "runner": RUNNER,
                              "need": need, "biz_nm": meta.get("biz_nm") or r.get("biz_nm") or prev.get("biz_nm", ""),
                              "choan_period": meta.get("choan_period") or prev.get("choan_period", ""),
                              "issue": prev.get("issue")}
        summary[status] = summary.get(status, 0) + 1
        store.save_state(state)
        log(f"  -> {status}: {note}")
        if time.time() - t0 > 3 * 3600:
            log("시간 제한으로 중단"); break
    n = store.rebuild_gpkg() if not NOSAVE else 0
    log(f"\n요약 {summary} / 레이어 사업지구 {n}건")
    hum = [(k, v) for k, v in state.items() if v.get("status") == "review" and v.get("need") == "human"]
    if hum:
        log(f"\n※ 사람 확인이 필요한 사업 {len(hum)}건 (review/ 폴더, GitHub 이슈로도 알림):")
        for k, v in hum:
            log(f"   - {k} {v.get('biz_nm','')}: {v.get('note','')}")
    if "GITHUB_STEP_SUMMARY" in __import__("os").environ:
        with open(__import__("os").environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fp:
            fp.write(f"### EIASS 초안공람 사업지구\n\n{summary}, 레이어 {n}건\n\n| 사업코드 | 결과 | 비고 |\n|---|---|---|\n")
            for r in todo[:a.limit]:
                s = state.get(r["biz_cd"], {})
                tag = {"pc": " (PC 대기)", "human": " (**사람 확인**)"}.get(s.get("need"), "")
                fp.write(f"| {r['biz_cd']} | {s.get('status')}{tag} | {s.get('note','')} |\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
