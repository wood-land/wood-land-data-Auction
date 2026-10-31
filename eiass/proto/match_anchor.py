import sys, json, math, re, itertools
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from core import vworld
from shapely.geometry import shape
from pyproj import Transformer

LOC = "경상북도 구미시 산동읍 성수리 19"
d = json.load(open('proto/ocr_p11.json', encoding='utf-8'))
toks = [t for t in d['jibun'] if t['conf'] >= 60]
print('OCR 후보', len(toks))
lon, lat, how = vworld.locate(LOC); print('위치', lon, lat, how)
to5186 = Transformer.from_crs(4326, 5186, always_xy=True).transform
cx, cy = to5186(lon, lat)
pad = 0.016
parc = vworld.parcels_bbox(lon - pad, lat - pad, lon + pad, lat + pad, cell=0.008)
print('필지', len(parc))
jr = re.compile(r"^(산)?\s*(\d+)(?:-(\d+))?")
idx = {}
for p in parc:
    m = jr.match(p['jibun'].strip()); 
    if not m: continue
    try:
        g = shape(p['geometry']); c = g.representative_point()
    except Exception: continue
    X, Y = to5186(c.x, c.y)
    key = (bool(m.group(1)), int(m.group(2)), int(m.group(3) or 0))
    idx.setdefault(key, []).append((X, Y, p['pnu'], p['jibun'], p['addr']))
print('지번 종류', len(idx))
# 후보: 토큰 i -> [(X,Y,...)]
cand = []
for t in toks:
    k = (t['san'], t['bon'], t['bu'])
    if k in idx:
        cand.append((t, idx[k]))
print('짝 후보 토큰', len(cand), [ (t['txt'], len(v)) for t, v in cand])
rng = np.random.default_rng(1)
best = None
S_LO, S_HI = 0.30, 0.70
for (ti, ci), (tj, cj) in itertools.combinations(cand, 2):
    dpx = np.hypot(ti['x'] - tj['x'], ti['y'] - tj['y'])
    if dpx < 300: continue
    for a in ci:
        for b in cj:
            dm = math.hypot(a[0] - b[0], a[1] - b[1])
            s = dm / dpx
            if not (S_LO <= s <= S_HI): continue
            # 쪽 px(y 아래로) -> 5186(y 위로): X = a + s*(R*(x,-y))
            ang_px = math.atan2(-(tj['y'] - ti['y']), tj['x'] - ti['x'])
            ang_m = math.atan2(b[1] - a[1], b[0] - a[0])
            th = ang_m - ang_px
            if abs(math.degrees((th + math.pi) % (2 * math.pi) - math.pi)) > 6: continue
            c, sn = math.cos(th), math.sin(th)
            def tf(t):
                x, y = t['x'] - ti['x'], -(t['y'] - ti['y'])
                return a[0] + s * (c * x - sn * y), a[1] + s * (sn * x + c * y)
            inl = []
            for t, cs in cand:
                X, Y = tf(t)
                dd = [(math.hypot(X - q[0], Y - q[1]), q) for q in cs]
                m = min(dd, key=lambda z: z[0])
                if m[0] < 25: inl.append((t, m[1], m[0]))
            if best is None or len(inl) > len(best[0]): best = (inl, s, th)
inl, s, th = best
print('인라이어', len(inl), 's=%.4f m/px rot=%.2f°' % (s, math.degrees(th)))
# 최소제곱 닮음변환 재추정
P = np.array([[t['x'], -t['y']] for t, q, e in inl]); Q = np.array([[q[0], q[1]] for t, q, e in inl])
pc, qc = P.mean(0), Q.mean(0)
Pz = (P - pc)[:, 0] + 1j * (P - pc)[:, 1]; Qz = (Q - qc)[:, 0] + 1j * (Q - qc)[:, 1]
z = (np.conj(Pz) @ Qz) / (np.conj(Pz) @ Pz)
res = Qz - z * Pz
print('재추정 s=%.4f rot=%.2f° 잔차 rms=%.1fm max=%.1fm' % (abs(z), math.degrees(np.angle(z)), np.sqrt(np.mean(abs(res) ** 2)), abs(res).max()))
for (t, q, e), r in zip(inl, abs(res)): print('  ', t['txt'], '->', q[3], q[4][-12:], '%.1fm' % r)
json.dump({'z': [z.real, z.imag], 'pc': pc.tolist(), 'qc': qc.tolist(), 'n': len(inl), 'rms': float(np.sqrt(np.mean(abs(res) ** 2)))}, open('proto/anchor_fit.json', 'w'))
