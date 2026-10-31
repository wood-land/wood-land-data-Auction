"""DEM 대략 위치 -> 도로(브이월드 도로 레이어) 기준 정밀화 시험"""
import sys, math, json
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np, cv2
from core import extract as ex, vworld
from pyproj import Transformer
from shapely.geometry import shape

page, plan, jf = sys.argv[1], float(sys.argv[2]), sys.argv[3]
R = float(sys.argv[4]) if len(sys.argv) > 4 else 500.0
coarse = json.load(open(jf))
img = cv2.imread(page)[:, :, ::-1].copy(); H, W = img.shape[:2]
e = ex.extract_candidates(img, 3)[0]
s_est = math.sqrt(plan / e['area_px'])
t = Transformer.from_crs(4326, 5186, always_xy=True).transform
tb = Transformer.from_crs(5186, 4326, always_xy=True).transform
cpts = np.array([t(*p) for p in coarse['poly']])                 # 5186 대략 위치의 경계
# 도면 px -> 5186: X = a + s*x, Y = b - s*y  (a,b 는 경계 중심을 대략 위치에 맞춰 정한다)
cen_px = e['contour'].mean(0); cen_m = cpts.mean(0)
a = cen_m[0] - s_est * cen_px[0]; b = cen_m[1] + s_est * cen_px[1]
# 도로 레이어
lon, lat = tb(*cen_m)
pad = (R + 400) / 90000
feats = []
def fetch(layer):
    out = []; page_n = 1
    while page_n <= 10:
        p = {"service": "data", "request": "GetFeature", "data": layer, "key": vworld.KEY, "format": "json", "errorformat": "json",
             "size": 1000, "page": page_n, "geometry": "true", "attribute": "true", "crs": "EPSG:4326",
             "geomFilter": "BOX(%f,%f,%f,%f)" % (lon - pad, lat - pad, lon + pad, lat + pad)}
        if vworld.DOMAIN: p["domain"] = vworld.DOMAIN
        j = vworld._get("https://api.vworld.kr/req/data", p, timeout=40).json()["response"]
        if j.get("status") != "OK": break
        out += j["result"]["featureCollection"]["features"]
        if page_n >= int(j.get("page", {}).get("total", 1)): break
        page_n += 1
    return out
CH = {'road': ['LT_C_UPISUQ151'], 'line': ['LT_L_MOCTLINK', 'LT_L_SPRD'], 'bld': ['LT_C_BLDGINFO'], 'river': ['LT_C_WKMSTRM']}
USE = sys.argv[5].split(',') if len(sys.argv) > 5 else ['road', 'bld', 'river']
for ch in USE:
    for L in CH[ch]:
        fs = fetch(L); print(ch, L, len(fs)); feats += [(L, f) for f in fs]
G = 3.0                                                              # 기준 격자 해상도(m)
gx0, gy1 = cen_m[0] - R - 500, cen_m[1] + R + 500
GW = int((2 * R + 1000) / G); GH = GW
ref = np.zeros((GH, GW), np.uint8)
for layer, f in feats:
    g = f['geometry']
    if g['type'] == 'MultiPolygon': lines = [r for poly in g['coordinates'] for r in poly]
    elif g['type'] == 'Polygon': lines = list(g['coordinates'])
    elif g['type'] == 'MultiLineString': lines = g['coordinates']
    else: lines = [g['coordinates']]
    for ln in lines:
        pts = np.array([t(x, y) for x, y in [c[:2] for c in ln]])
        px = np.c_[(pts[:, 0] - gx0) / G, (gy1 - pts[:, 1]) / G]
        cv2.polylines(ref, [np.int32(np.round(px))], False, 1, 1)
# 도면의 검은 가는 선(도로 가장자리·차선) -> 같은 격자
dark = (img.max(2) < 110).astype(np.uint8)
dark = ex.thin_lines(dark, 2)
site = cv2.dilate(e['mask'], np.ones((41, 41), np.uint8))
ys, xs = np.nonzero(e['mask']); x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
fr = np.zeros_like(dark); fr[max(0, y0 - 900):y1 + 900, max(0, x0 - 900):x1 + 900] = 1
valid = fr.copy(); valid[site > 0] = 0
dark[valid == 0] = 0
n, lab, st, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)
keep = np.isin(lab, [i for i in range(1, n) if max(st[i, cv2.CC_STAT_WIDTH], st[i, cv2.CC_STAT_HEIGHT]) > 120])   # 글자·기호 제거
dark = keep.astype(np.uint8)
f = s_est / G
sig = 4.0                                                            # ~12 m 번짐
dens = cv2.GaussianBlur(cv2.resize(dark.astype(np.float32), None, fx=f, fy=f, interpolation=cv2.INTER_AREA), (0, 0), sig)
vm = (cv2.resize(valid.astype(np.float32), (dens.shape[1], dens.shape[0]), interpolation=cv2.INTER_AREA) > 0.9).astype(np.float32)
refb = cv2.GaussianBlur(ref.astype(np.float32), (0, 0), sig)
bx0, by0, bx1, by1 = [int(v * f) for v in (max(0, x0 - 900), max(0, y0 - 900), min(W, x1 + 900), min(H, y1 + 900))]
T = dens[by0:by1, bx0:bx1]; M = vm[by0:by1, bx0:bx1]
N = float(M.sum()); mu = float((T * M).sum() / N); Tc = (T - mu) * M
num = cv2.matchTemplate(refb, Tc.astype(np.float32), cv2.TM_CCORR)
sM = cv2.matchTemplate(refb, M, cv2.TM_CCORR); sM2 = cv2.matchTemplate(refb * refb, M, cv2.TM_CCORR)
den = np.sqrt(np.maximum(sM2 - sM * sM / N, 1e-9)) * math.sqrt(float((Tc * Tc).sum()))
r_ = num / den
# 현재(대략) 위치에서의 템플릿 좌상단 격자 좌표
cur = ((a + s_est * bx0 / f - gx0) / G, (gy1 - (b) - s_est * by0 / f * 0 ) / G)
# 템플릿 좌상단의 도면 px = (bx0/f, by0/f) -> 5186
def tpl_corner(dx=0, dy=0):
    X = a + s_est * (bx0 / f) + dx; Y = b - s_est * (by0 / f) + dy
    return (X - gx0) / G, (gy1 - Y) / G
c0 = tpl_corner()
ii, jj = np.mgrid[0:r_.shape[0], 0:r_.shape[1]]
dist = np.hypot((jj - c0[0]) * G, (ii - c0[1]) * G)
rr = np.where(dist < R, r_, -1)
_, mv, _, ml = cv2.minMaxLoc(rr)
r2 = rr.copy(); cv2.circle(r2, ml, int(40 / G), -1, -1); sv = float(r2.max())
r0 = float(r_[int(round(c0[1])), int(round(c0[0]))]) if 0 <= int(round(c0[1])) < r_.shape[0] and 0 <= int(round(c0[0])) < r_.shape[1] else float('nan')
dxm, dym = (ml[0] - c0[0]) * G, -(ml[1] - c0[1]) * G
print('상관 %.3f (현재 위치 %.3f) 2등 %.3f 비 %.2f / 이동 dx=%.0f m dy=%.0f m' % (mv, r0, sv, mv / max(sv, 1e-6), dxm, dym))
# 결과 경계
poly5186 = np.array([[a + s_est * x + dxm, b - s_est * y + dym] for x, y in e['contour']])
ring4326 = [tb(*p) for p in poly5186]
json.dump({'poly': ring4326, 'dx': dxm, 'dy': dym, 'ratio': mv / max(sv, 1e-6), 'corr': mv}, open(page.replace('.png', '_multi.json'), 'w'))
cen = np.mean(ring4326, 0)
S, sx0, sy0, sres, zz, ok = vworld.satellite_mosaic(cen[0], cen[1], 600, 1.2, max_tiles=80)
vis = S[:, :, ::-1].copy()
for p in ring4326[:0]: pass
mk = lambda pts: np.int32([((vworld.ll2merc(*p)[0] - sx0) / sres, (sy0 - vworld.ll2merc(*p)[1]) / sres) for p in pts])
cv2.polylines(vis, [mk(ring4326)], True, (255, 0, 255), 3)
old = [tb(*p) for p in cpts]
cv2.polylines(vis, [mk(old)], True, (0, 255, 255), 2)               # 노랑: DEM 대략 위치
for layer, f_ in feats:
    g = f_['geometry']
    lines = [r for poly in g['coordinates'] for r in poly] if g['type'] == 'MultiPolygon' else (g['coordinates'] if g['type'] == 'MultiLineString' else [g['coordinates']])
    for ln in lines: cv2.polylines(vis, [mk([c[:2] for c in ln])], False, (0, 200, 0), 1)
k = min(1.0, 1100 / max(vis.shape[:2]))
cv2.imwrite(page.replace('.png', '_multi.jpg'), cv2.resize(vis, None, fx=k, fy=k, interpolation=cv2.INTER_AREA))
