"""개발구역만 남기고 바깥은 투명하게 한 PNG + 월드파일(QGIS 에서 바로 제 위치)"""
import sys, json, math
sys.path.insert(0, '.')
import numpy as np, cv2
from core import extract as ex

f = json.load(open('proto/anchor_fit.json'))
z = complex(*f['z']); pc = f['pc']; qc = f['qc']
s, th = abs(z), float(np.angle(z)); c, sn = math.cos(th), math.sin(th)
A, B = s * c, s * sn
C = qc[0] - s * c * pc[0] + s * sn * pc[1]
D, E = s * sn, -s * c
F = qc[1] - s * sn * pc[0] - s * c * pc[1]

img = cv2.imread('proto/p11.png')                       # BGR
cands = ex.extract_candidates(img[:, :, ::-1].copy(), max_n=4)
e = next(e for e in cands if e['color'] in ('red', 'magenta'))
H, W = img.shape[:2]
m = np.zeros((H, W), np.uint8)
cv2.fillPoly(m, [np.int32(np.round(e['contour']))], 255)
m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13)))   # 경계선 자체가 잘리지 않게
m = cv2.GaussianBlur(m, (0, 0), 1.2)                                         # 가장자리 부드럽게
ys, xs = np.nonzero(m > 0)
x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
rgba = np.dstack([img, m])[y0:y1, x0:x1]
cv2.imwrite('proto/p11_site.png', rgba)
Cn, Fn = A * x0 + B * y0 + C, D * x0 + E * y0 + F
open('proto/p11_site.pgw', 'w').write('\n'.join(repr(float(v)) for v in (A, D, B, E, Cn, Fn)))
import shutil; shutil.copy('proto/p11.prj', 'proto/p11_site.prj')
print('크기', rgba.shape, '지상 %.0f x %.0f m' % ((x1 - x0) * s, (y1 - y0) * s))
# 확인용: 흰 배경 합성
bg = np.full(rgba.shape[:2] + (3,), (60, 90, 60), np.uint8)
a = rgba[:, :, 3:] / 255.0
cv2.imwrite('proto/p11_site_check.jpg', cv2.resize((rgba[:, :, :3] * a + bg * (1 - a)).astype(np.uint8), None, fx=0.3, fy=0.3, interpolation=cv2.INTER_AREA))
