"""등고선 밀도 vs DEM 경사 교차상관 (지번·지형물이 없는 지형 도면용 시험)"""
import sys, math, io
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np, cv2, requests
from core import extract as ex, vworld

page, lon, lat, plan = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
half = float(sys.argv[5]) if len(sys.argv) > 5 else 3000
DEMHALF = half + 2000
img = cv2.imread(page)[:, :, ::-1].copy()
H, W = img.shape[:2]
cands = ex.extract_candidates(img, 3)
e = cands[0]; print('경계', e['color'], e['area_px'])
s_est = math.sqrt(plan / e['area_px']); print('px=%.3f m' % s_est)
# 1) 도면 등고선: 붉은 갈색 가는 선(굵은 경계선·채색 면 제외), 사업지구 안쪽 제외
hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
r, g, b = [img[:, :, i].astype(int) for i in range(3)]
cont = ((r - g > 35) & (r - b > 25) & (r > 120) & (hsv[:, :, 1] < 200)).astype(np.uint8)
cont = ex.thin_lines(cont, 3)
site = cv2.dilate(e['mask'], np.ones((41, 41), np.uint8))
cont[site > 0] = 0
# 쪽 가장자리 틀·표 제외(도면 틀 안쪽만): 사업지구 경계상자 주변 일정 범위만
ys, xs = np.nonzero(e['mask']); x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
fr = np.zeros_like(cont); fr[max(0, y0 - 600):y1 + 600, max(0, x0 - 600):x1 + 600] = 1
cont &= fr
valid = fr.copy(); valid[site > 0] = 0
print('등고선 픽셀', int(cont.sum()))
# 2) DEM (AWS Terrarium)
z = 14
def tile_xy(lon, lat, z):
    n = 2 ** z; x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y
cx, cy = tile_xy(lon, lat, z)
res = 40075016.686 / (256 * 2 ** z); coslat = math.cos(math.radians(lat))
nt = int(math.ceil(DEMHALF / (res * coslat * 256))) + 1
tx0, ty0 = int(cx) - nt, int(cy) - nt
dem = np.zeros(((2 * nt + 1) * 256, (2 * nt + 1) * 256), np.float32)
for i in range(2 * nt + 1):
    for j in range(2 * nt + 1):
        u = f'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{tx0 + i}/{ty0 + j}.png'
        t = cv2.imdecode(np.frombuffer(requests.get(u, timeout=30).content, np.uint8), cv2.IMREAD_COLOR)[:, :, ::-1].astype(np.float32)
        dem[j * 256:(j + 1) * 256, i * 256:(i + 1) * 256] = t[:, :, 0] * 256 + t[:, :, 1] + t[:, :, 2] / 256 - 32768
print('DEM', dem.shape, '범위 %.0f~%.0fm' % (dem.min(), dem.max()))
gres = res * coslat                                    # DEM 한 픽셀의 지상 m
dem = np.where(dem < -30, 0, dem)
dem_s = cv2.GaussianBlur(dem, (0, 0), 1.0)
gx = cv2.Sobel(dem_s, cv2.CV_32F, 1, 0) / 8; gy = cv2.Sobel(dem_s, cv2.CV_32F, 0, 1) / 8
slope = np.hypot(gx, gy) / gres
slope = cv2.GaussianBlur(slope, (0, 0), 2.0)
# 3) 도면 등고선 밀도를 DEM 격자(gres)로
f = s_est / gres
dens = cv2.resize(cont.astype(np.float32), None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
dens = cv2.GaussianBlur(dens, (0, 0), 2.0)
vm = cv2.resize(valid.astype(np.float32), (dens.shape[1], dens.shape[0]), interpolation=cv2.INTER_AREA)
vm = (vm > 0.9).astype(np.uint8) * 255
bx0, by0, bx1, by1 = [int(v * f) for v in (max(0, x0 - 600), max(0, y0 - 600), min(W, x1 + 600), min(H, y1 + 600))]
T = dens[by0:by1, bx0:bx1]; M = vm[by0:by1, bx0:bx1]
print('템플릿', T.shape, '탐색', slope.shape)
dem = None
S_ = slope.astype(np.float32)
# 탐색 범위: 대략 위치(타일 중심) 주변 half 이내만
Mn = (M > 0).astype(np.float32); N = float(Mn.sum())
mu = float((T * Mn).sum() / N); Tc = (T - mu) * Mn
num = cv2.matchTemplate(S_, Tc.astype(np.float32), cv2.TM_CCORR)
sM = cv2.matchTemplate(S_, Mn, cv2.TM_CCORR); sM2 = cv2.matchTemplate(S_ * S_, Mn, cv2.TM_CCORR)
den = np.sqrt(np.maximum(sM2 - sM * sM / N, 1e-9)) * math.sqrt(float((Tc * Tc).sum()))
r_ = num / den
# 대략 위치에서 half(m) 이내
rr = np.full(r_.shape, -1, np.float32)
ccx, ccy = (cx - tx0) * 256, (cy - ty0) * 256
lim = half / gres
ii, jj = np.mgrid[0:r_.shape[0], 0:r_.shape[1]]
tpl_cx = jj + T.shape[1] / 2; tpl_cy = ii + T.shape[0] / 2
ok_ = np.hypot(tpl_cx - ccx, tpl_cy - ccy) < lim
rr[ok_] = r_[ok_]; r_ = rr
_, mv, _, ml = cv2.minMaxLoc(r_)
r2 = r_.copy(); cv2.circle(r2, ml, 15, -1, -1); sv = float(r2.max())
print('상관 %.3f 2등 %.3f 비 %.2f' % (mv, sv, mv / max(sv, 1e-6)))
# 4) 쪽 px -> 3857 변환(회전 0, 닮음): 템플릿 좌상단이 DEM (ml) 에 놓임
TX = lambda col, row: (((ml[0] + (col / f - bx0)) ) , ((ml[1] + (row / f - by0))))
def page_to_m(col, row):
    px = ml[0] + (col * f - bx0); py = ml[1] + (row * f - by0)          # DEM 픽셀
    tx = tx0 + px / 256; ty = ty0 + py / 256
    n = 2 ** z
    lo = tx / n * 360 - 180; la = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * ty / n))))
    return lo, la
cont_pts = [page_to_m(x, y) for x, y in e['contour']]
import json
json.dump({'poly': cont_pts, 'corr': mv, 'ratio': mv / max(sv, 1e-6)}, open(page.replace('.png', '_dem.json'), 'w'))
cen = np.mean(cont_pts, 0); print('중심', cen)
S, sx0, sy0, sres, zz, ok = vworld.satellite_mosaic(cen[0], cen[1], 700, 1.5, max_tiles=80)
vis = S[:, :, ::-1].copy()
ring = [((vworld.ll2merc(*p)[0] - sx0) / sres, (sy0 - vworld.ll2merc(*p)[1]) / sres) for p in cont_pts]
cv2.polylines(vis, [np.int32(ring)], True, (255, 0, 255), 3)
k = min(1.0, 1100 / max(vis.shape[:2]))
cv2.imwrite(page.replace('.png', '_dem.jpg'), cv2.resize(vis, None, fx=k, fy=k, interpolation=cv2.INTER_AREA))
