"""
core/extract.py - 평가서 도면(쪽 그림)에서 사업지구 경계 폴리곤을 뽑는다.

토지이용계획도는 보통 빨간 경계선(실선/점선/일점쇄선) 안쪽을 용도별 색으로 칠한다.
  1) 빨간 선을 굵혀 끊긴 점선을 잇고, 채색 영역과 합쳐 '벽'을 만든다
  2) 쪽 가장자리에서 바깥을 채워(flood fill) 벽 안쪽을 얻는다
  3) 빨간 선을 가장 많이 품은 덩어리를 사업지구로 고르고, 굵힌 만큼 다시 깎아 경계선 중심에 맞춘다
  4) 가는 돌출부(부지 밖 연결도로 점선)는 열림(opening)으로 떼어낸다
"""
import cv2
import numpy as np


def _sq(r):
    return cv2.getStructuringElement(cv2.MORPH_RECT, (2 * r + 1, 2 * r + 1))


def red_mask(img):
    r, g, b = img[:, :, 0].astype(np.int16), img[:, :, 1].astype(np.int16), img[:, :, 2].astype(np.int16)
    return ((r > 150) & (g < 100) & (b < 100)).astype(np.uint8)


def sat_mask(img, sat=90):
    mx = img.max(2).astype(np.int16); mn = img.min(2).astype(np.int16)
    return ((mx - mn) > sat).astype(np.uint8)


def extract(img, di=8, sat=90, prune=6, use_fill=True):
    """img: RGB. 반환 dict(mask, contour(Nx2, 쪽 px), area_px, red_frac) 또는 None"""
    H, W = img.shape[:2]
    R = red_mask(img)
    if R.sum() < 200:
        return None
    B = cv2.dilate(R, _sq(di))
    if use_fill:
        B = B | sat_mask(img, sat)
    free = (1 - B).astype(np.uint8)
    n, lab = cv2.connectedComponents(free, connectivity=4)
    border = np.unique(np.r_[lab[0, :], lab[-1, :], lab[:, 0], lab[:, -1]])
    outside = np.isin(lab, border[border > 0]) & (free > 0)
    inside = (~outside).astype(np.uint8)
    n2, lab2, st, _ = cv2.connectedComponentsWithStats(inside, connectivity=4)
    if n2 <= 1:
        return None
    # 빨간 선을 가장 많이 품은 덩어리(쪽 전체를 덮는 덩어리는 제외)
    redcnt = np.bincount(lab2.ravel(), weights=R.ravel(), minlength=n2)
    best, bestv = -1, 0
    for k in range(1, n2):
        if st[k, cv2.CC_STAT_AREA] > 0.85 * H * W or st[k, cv2.CC_STAT_AREA] < 0.002 * H * W:
            continue
        if redcnt[k] > bestv:
            best, bestv = k, redcnt[k]
    if best < 0:
        return None
    L = (lab2 == best).astype(np.uint8)
    P = cv2.erode(L, _sq(di + 1))
    P = cv2.morphologyEx(P, cv2.MORPH_CLOSE, _sq(12))
    if prune > 0:
        O = cv2.morphologyEx(P, cv2.MORPH_OPEN, _sq(prune))
        P = P & cv2.dilate(O, _sq(prune + 3))
    n3, lab3, st3, _ = cv2.connectedComponentsWithStats(P, connectivity=4)
    if n3 <= 1:
        return None
    k = 1 + int(np.argmax(st3[1:, cv2.CC_STAT_AREA]))
    P = (lab3 == k).astype(np.uint8)
    cs, _ = cv2.findContours(P, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cs, key=cv2.contourArea)
    c = cv2.approxPolyDP(c, 1.2, True)[:, 0, :].astype(float)
    # 윤곽 중 빨간 선 가까이(굵힌 폭 안)에 있는 비율: 경계를 제대로 따라갔는지
    near = cv2.dilate(R, _sq(di + 4))
    cc = np.clip(c.astype(int), 0, [W - 1, H - 1])
    red_frac = float(near[cc[:, 1], cc[:, 0]].mean())
    return {"mask": P, "contour": c, "area_px": float(P.sum()), "red_frac": red_frac, "di": di}


def best_extract(img):
    """여러 설정으로 뽑아 경계를 가장 잘 따르는 것을 고른다."""
    res = []
    for di in (6, 9, 12):
        for fill in (True, False):
            try:
                e = extract(img, di=di, use_fill=fill)
            except Exception:
                e = None
            if e and e["red_frac"] >= 0.55:
                e["fill"] = fill
                res.append(e)
    if not res:
        return None
    # 경계 추종이 좋은 것 중 면적이 큰 것(끊긴 선 때문에 일부만 잡히는 것을 피한다)
    top = max(r["red_frac"] for r in res)
    good = [r for r in res if r["red_frac"] >= top - 0.08]
    return max(good, key=lambda r: r["area_px"])


def background_kind(img, mask, pad=0.3):
    """경계 바깥 배경이 항공사진인지 선 도면인지. 흰 픽셀 비율로 가른다."""
    H, W = img.shape[:2]
    ys, xs = np.nonzero(mask)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    dx, dy = int((x1 - x0) * pad), int((y1 - y0) * pad)
    x0, x1, y0, y1 = max(0, x0 - dx), min(W, x1 + dx), max(0, y0 - dy), min(H, y1 + dy)
    sub = img[y0:y1, x0:x1]; m = mask[y0:y1, x0:x1] == 0
    px = sub[m]
    white = (px.min(1) > 230).mean() if len(px) else 1
    return ("aerial" if white < 0.35 else "line"), float(white), (x0, y0, x1, y1)


def line_points(img, mask, box, step=1):
    """선 도면 배경의 회색·검은 선 픽셀(사업지구 안 제외)."""
    x0, y0, x1, y1 = box
    sub = img[y0:y1, x0:x1]
    mx = sub.max(2).astype(np.int16); mn = sub.min(2).astype(np.int16)
    L = ((mx - mn) < 30) & (mx < 225)
    inside = cv2.dilate(mask[y0:y1, x0:x1], _sq(25)) > 0
    L &= ~inside
    v, u = np.nonzero(L)
    pts = np.c_[u + x0, v + y0].astype(float)
    return pts[::step]


def aerial_feature_mask(img, mask, box):
    """항공사진 배경에서 특징점을 찾을 영역: 사업지구 채색·글자·경계선 제외."""
    x0, y0, x1, y1 = box
    sub = img[y0:y1, x0:x1]
    hsv = cv2.cvtColor(sub[:, :, ::-1].copy(), cv2.COLOR_BGR2HSV)
    m = np.full(sub.shape[:2], 255, np.uint8)
    strong = (hsv[:, :, 1] > 150) & (hsv[:, :, 2] > 120)     # 범례·글자·채색
    m[cv2.dilate(strong.astype(np.uint8), _sq(4)) > 0] = 0
    m[cv2.dilate(mask[y0:y1, x0:x1], _sq(15)) > 0] = 0
    m[(sub.min(2) > 245)] = 0                                 # 흰 바탕(표·여백)
    return m
