import sys, json, math
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np, cv2
from core import extract as ex, vworld
from pyproj import Transformer
from shapely.geometry import Polygon, mapping
from shapely.ops import transform

f = json.load(open('proto/anchor_fit.json'))
z = complex(*f['z']); pc = f['pc']; qc = f['qc']
s, th = abs(z), np.angle(z)
c, sn = math.cos(th), math.sin(th)
def pix2m(col, row):
    u, v = col - pc[0], -row - pc[1]
    return qc[0] + s * (c * u - sn * v), qc[1] + s * (sn * u + c * v)
A, B = s * c, s * sn
Cc = qc[0] - s * c * pc[0] + s * sn * pc[1]
D, E = s * sn, -s * c
F = qc[1] - s * sn * pc[0] - s * c * pc[1]
open('proto/p11.pgw', 'w').write('\n'.join(repr(v) for v in (A, D, B, E, Cc, F)))   # 월드파일 순서: A D B E C F
open('proto/p11.prj', 'w').write(open('proto/p11.prj').read() if False else 'PROJCS["Korea_2000_Central_Belt_2010",GEOGCS["GCS_Korea_2000",DATUM["D_Korea_2000",SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",200000.0],PARAMETER["False_Northing",600000.0],PARAMETER["Central_Meridian",127.0],PARAMETER["Scale_Factor",1.0],PARAMETER["Latitude_Of_Origin",38.0],UNIT["Meter",1.0]]')
img = cv2.imread('proto/p11.png')[:, :, ::-1].copy()
cands = ex.extract_candidates(img, max_n=4)
for e in cands: print(e['color'], round(e['area_px']), round(e['red_frac'], 2))
e = next((e for e in cands if e['color'] in ('magenta', 'red')), cands[0])
pts = [pix2m(x, y) for x, y in e['contour']]
poly = Polygon(pts).buffer(0)
print('색', e['color'], '면적 %.0f ㎡ (계획 247641, %+.1f%%)' % (poly.area, (poly.area / 247641 - 1) * 100))
t4326 = Transformer.from_crs(5186, 4326, always_xy=True).transform
p4 = transform(t4326, poly)
fc = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"biz_cd": "DG2026A006", "method": "anchor_ocr", "anchors": f['n'], "rms_m": f['rms']}, "geometry": mapping(p4)}]}
json.dump(fc, open('proto/DG2026A006_anchor.geojson', 'w'), ensure_ascii=False)
# 위성 위 미리보기
cen = p4.centroid; half = max(300, math.sqrt(poly.area) * 0.9)
S, x0, y0, res, zz, ok = vworld.satellite_mosaic(cen.x, cen.y, half, max(1.0, half / 450), max_tiles=80)
vis = S[:, :, ::-1].copy()
ring = [((vworld.ll2merc(*xy)[0] - x0) / res, (y0 - vworld.ll2merc(*xy)[1]) / res) for xy in p4.exterior.coords]
cv2.polylines(vis, [np.int32(ring)], True, (255, 0, 255), 3)
P = np.int32(ring); bx0, by0 = np.maximum(P.min(0) - 80, 0); bx1, by1 = P.max(0) + 80
vis = vis[by0:by1, bx0:bx1]; k = min(1.0, 1100 / max(vis.shape[:2]))
cv2.imwrite('proto/preview_anchor.jpg', cv2.resize(vis, None, fx=k, fy=k, interpolation=cv2.INTER_AREA))
print('done')
