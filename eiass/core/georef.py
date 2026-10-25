"""
core/georef.py - 도면 좌표(쪽 px)를 실제 좌표(EPSG:3857)로 맞춘다.

- aerial: 도면 배경 항공사진 <-> 브이월드 위성영상, SIFT 특징점 + RANSAC(닮음변환)
- line  : 도면 배경 선(지형·지적) <-> 연속지적도 경계선, 거리변환 정합(chamfer). 축척은 계획면적으로 고정.
결과는 2x3 행렬 A: 쪽 px (x,y,1) -> 3857 (X,Y)
"""
import math

import cv2
import numpy as np
from scipy import ndimage, optimize

from . import vworld


def _compose(Mds, f, off, x0, y0, res):
    """쪽 px -> (축소 px) -> 위성 px(Mds) -> 3857"""
    # 축소: u = (x - offx)/f
    T1 = np.array([[1 / f, 0, -off[0] / f], [0, 1 / f, -off[1] / f], [0, 0, 1]])
    T2 = np.vstack([Mds, [0, 0, 1]])
    T3 = np.array([[res, 0, x0], [0, -res, y0], [0, 0, 1]])
    return (T3 @ T2 @ T1)[:2]


def apply(A, pts):
    return pts @ A[:, :2].T + A[:, 2]


# ---------------- 항공사진 배경 ----------------
def _sift_once(img, feat_mask, box, s_est, lon, lat, half_m, target, log=print):
    """s_est: 도면 쪽 px 하나의 지상 길이(m) 추정(계획면적/추출면적). 반환 dict 또는 None"""
    x0b, y0b, x1b, y1b = box
    f = target / s_est                                  # 쪽 px -> 축소 px 배율(>=1 이면 줄임)
    sub = img[y0b:y1b, x0b:x1b]
    D = cv2.resize(sub, None, fx=1 / f, fy=1 / f, interpolation=cv2.INTER_AREA)
    Dm = cv2.resize(feat_mask, (D.shape[1], D.shape[0]), interpolation=cv2.INTER_NEAREST)
    S, sx0, sy0, sres, z, okfrac = vworld.satellite_mosaic(lon, lat, half_m, target)
    src = "vworld" if vworld.available() else "esri"
    log(f"    위성영상({src}) z={z} {S.shape[1]}x{S.shape[0]} 타일성공 {okfrac:.0%}")
    if okfrac < 0.5:
        return {"ok": False, "reason": f"위성영상 타일 실패({okfrac:.0%})"}
    cl = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    g1 = cl.apply(cv2.cvtColor(D, cv2.COLOR_RGB2GRAY)); g2 = cl.apply(cv2.cvtColor(S, cv2.COLOR_RGB2GRAY))
    sift = cv2.SIFT_create(nfeatures=40000, contrastThreshold=0.02)
    ka, da = sift.detectAndCompute(g1, Dm)
    kb, db = sift.detectAndCompute(g2, None)
    if da is None or db is None or len(ka) < 20:
        return {"ok": False, "reason": "특징점 부족"}
    m = cv2.BFMatcher().knnMatch(da, db, k=2)
    good = [a for a, b in (x for x in m if len(x) == 2) if a.distance < 0.8 * b.distance]
    if len(good) < 8:
        return {"ok": False, "reason": f"대응점 부족({len(good)})"}
    pa = np.float32([ka[g.queryIdx].pt for g in good]); pb = np.float32([kb[g.trainIdx].pt for g in good])
    M, inl = cv2.estimateAffinePartial2D(pa, pb, method=cv2.RANSAC, ransacReprojThreshold=4, maxIters=50000, confidence=0.999)
    if M is None:
        return {"ok": False, "reason": "RANSAC 실패"}
    inl = inl.ravel().astype(bool)
    if math.hypot(M[0, 0], M[1, 0]) < 1e-6 or inl.sum() < 4:
        return {"ok": False, "reason": "RANSAC 퇴화(대응점이 한곳에 몰림)", "inliers": int(inl.sum())}
    resid = np.hypot(*((np.c_[pa[inl], np.ones(inl.sum())] @ M.T) - pb[inl]).T)
    scale = math.hypot(M[0, 0], M[1, 0])
    exp_scale = (s_est * f) / (sres * math.cos(math.radians(lat)))
    # 정합 근거가 넓게 퍼져 있는지(한쪽에 몰리면 회전·축척이 불안정)
    spread = np.ptp(pa[inl], axis=0) / np.array(D.shape[1::-1]) if inl.sum() else np.zeros(2)
    A = _compose(M, f, (x0b, y0b), sx0, sy0, sres)
    out = {"ok": True, "method": "sift", "imagery": src, "A": A, "inliers": int(inl.sum()), "matches": len(good),
           "rms_m": float(np.sqrt(np.mean(resid ** 2)) * sres * math.cos(math.radians(lat))) if len(resid) else None,
           "scale_ratio": float(scale / exp_scale), "spread": float(spread.min()),
           "rot_deg": float(math.degrees(math.atan2(M[1, 0], M[0, 0]))),
           "sat": (S, sx0, sy0, sres)}
    return out


def sift_georef(img, feat_mask, box, s_est, lon, lat, half_m, log=print):
    """해상도를 바꿔 가며(도면 화질·영상 차이에 따라 잘 맞는 배율이 다르다) 가장 믿을 만한 결과를 고른다."""
    best = None
    for k in (1.5, 3.0, 1.0):
        target = max(1.0, min(8.0, s_est * k))
        r = _sift_once(img, feat_mask, box, s_est, lon, lat, half_m, target, log)
        if not r.get("ok"):
            log(f"    SIFT x{k}: {r.get('reason')}")
            continue
        good = r["inliers"] >= 12 and 0.8 <= r["scale_ratio"] <= 1.25 and r["spread"] >= 0.25
        log(f"    SIFT x{k}: 대응점 {r['inliers']}/{r['matches']} 축척비 {r['scale_ratio']:.3f}")
        if good:
            return r
        if best is None or r["inliers"] > best["inliers"]:
            best = r
    return best or {"ok": False, "reason": "SIFT 실패"}


# ---------------- 선 도면 배경 ----------------
def cadastral_raster(parcels, x0, y0, res, W, H):
    img = np.zeros((H, W), np.uint8)
    for p in parcels:
        g = p.get("geometry") or {}
        polys = g.get("coordinates", [])
        if g.get("type") == "Polygon":
            polys = [polys]
        for poly in polys:
            for ring in poly:
                pts = []
                for lon, lat in ring:
                    X, Y = vworld.ll2merc(lon, lat)
                    pts.append(((X - x0) / res, (y0 - Y) / res))
                cv2.polylines(img, [np.int32(np.round(pts))], True, 1, 1)
    return img


def chamfer_georef(line_pts, ring, s_est, lon, lat, half_m, log=print):
    """line_pts: 도면 선 픽셀(쪽 px). 축척 고정(s_est), 회전·이동만 찾는다."""
    coslat = math.cos(math.radians(lat))
    res_g = max(1.0, min(4.0, s_est * 1.2))            # 지적 래스터 해상도(지상 m)
    res = res_g / coslat                                # 3857 m/px
    cx, cy = vworld.ll2merc(lon, lat)
    hm = half_m / coslat
    x0, y0 = cx - hm, cy + hm
    W = H = int(2 * hm / res)
    lo0, la0 = vworld.merc2ll(cx - hm, cy - hm); lo1, la1 = vworld.merc2ll(cx + hm, cy + hm)
    parcels = vworld.parcels_bbox(lo0, la0, lo1, la1, cell=max(0.006, min(0.02, half_m / 111000 / 3)))
    log(f"    연속지적도 {len(parcels)}필지, 래스터 {W}x{H} @ {res_g:.1f}m")
    if len(parcels) < 50:
        return {"ok": False, "reason": f"지적 필지 부족({len(parcels)})"}
    ref = cadastral_raster(parcels, x0, y0, res, W, H)
    dist = ndimage.distance_transform_edt(1 - ref)
    P = line_pts
    if len(P) > 150000:
        P = P[np.random.default_rng(0).choice(len(P), 150000, replace=False)]
    c = P.mean(0)
    s_m = s_est / coslat                                # 쪽 px -> 3857 m
    refb = cv2.GaussianBlur(ref.astype(np.float32), (0, 0), 2.0)

    def tf(q, pts):
        sc, th, tx, ty = q; ct, st = math.cos(th), math.sin(th)
        x = pts[:, 0] - c[0]; y = pts[:, 1] - c[1]
        return sc * (ct * x - st * y) + tx, -sc * (st * x + ct * y) + ty

    def cost(q, tr):
        X, Y = tf(q, P)
        d = ndimage.map_coordinates(dist, [(y0 - Y) / res, (X - x0) / res], order=1, mode="constant", cval=tr)
        return float(np.mean(np.minimum(d, tr)))

    cands = []
    for k in (0.97, 1.0, 1.03):
        for thd in (-3, -1.5, 0, 1.5, 3):
            q = [s_m * k, math.radians(thd), 0, 0]
            X, Y = tf(q, P)
            px = np.round(X / res).astype(int); py = np.round(-Y / res).astype(int)
            mx, my = px.min(), py.min(); px -= mx; py -= my
            if py.max() + 1 >= H or px.max() + 1 >= W:
                continue
            T = np.zeros((py.max() + 1, px.max() + 1), np.float32); T[py, px] = 1
            r = cv2.matchTemplate(refb, T, cv2.TM_CCORR)
            _, mv, _, ml = cv2.minMaxLoc(r)
            # 두 번째 봉우리(30px 밖)와의 비
            r2 = r.copy(); cv2.circle(r2, ml, 30, 0, -1)
            sv = float(r2.max())
            cands.append((mv, mv / max(sv, 1e-6), [q[0], q[1], x0 + (ml[0] - mx) * res, y0 - (ml[1] - my) * res]))
    if not cands:
        return {"ok": False, "reason": "검색 범위 부족"}
    cands.sort(key=lambda t: -t[0])
    mv, peak_ratio, q = cands[0]
    q = np.array(q, float)
    for tr in (10, 6, 3):
        q = optimize.minimize(lambda z: cost(z, tr), q, method="Nelder-Mead",
                              options={"xatol": 1e-7, "fatol": 1e-7, "maxiter": 3000}).x
    # 4구역 각각 이동만 다시 맞춰 보며 국소 어긋남(m)을 본다
    x = P[:, 0] - c[0]; y = P[:, 1] - c[1]; local = []
    for idx in ((x < 0) & (y < 0), (x >= 0) & (y < 0), (x < 0) & (y >= 0), (x >= 0) & (y >= 0)):
        if idx.sum() < 500:
            continue
        Pi = P[idx]

        def ci(t):
            X, Y = tf(q, Pi); X = X + t[0]; Y = Y + t[1]
            d = ndimage.map_coordinates(dist, [(y0 - Y) / res, (X - x0) / res], order=1, mode="constant", cval=2)
            return float(np.mean(np.minimum(d, 2)))
        rr = optimize.minimize(ci, [0, 0], method="Nelder-Mead")
        local.append(float(math.hypot(*rr.x) * coslat))
    X, Y = tf(q, P)
    d = ndimage.map_coordinates(dist, [(y0 - Y) / res, (X - x0) / res], order=1, mode="constant", cval=99)
    coincide = float((d <= 1.5).mean())
    sc, th, tx, ty = q; ct, st = math.cos(th), math.sin(th)
    A = np.array([[sc * ct, -sc * st, tx - sc * (ct * c[0] - st * c[1])],
                  [-sc * st, -sc * ct, ty + sc * (st * c[0] + ct * c[1])]])
    return {"ok": True, "method": "chamfer", "A": A, "peak_ratio": float(peak_ratio), "coincide": coincide,
            "local_max_m": max(local) if local else None, "rot_deg": float(math.degrees(th)),
            "cost": cost(q, 3), "parcels": parcels}
