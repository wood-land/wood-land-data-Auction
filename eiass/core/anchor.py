"""
core/anchor.py - 도면에 찍힌 지번(예: 482-11, 산52-26)을 제어점으로 쓰는 좌표 맞춤.

  1) 도면 쪽을 타일로 잘라 Tesseract(kor+eng)로 읽고 지번 꼴 글자의 쪽 px 위치를 얻는다
  2) 브이월드 연속지적도의 같은 지번 필지(중심점)를 후보로 두고, 두 점 쌍으로 닮음변환을 세워 RANSAC
     (축척은 계획면적 추정값 근처, 회전은 ±6° 이내 - 도면은 거의 북쪽이 위)
  3) 인라이어로 최소제곱 재추정 -> 잔차(m)가 곧 정확도
등고선·표고가 많은 지형도 배경(선 정합이 안 되는 도면)에서도 된다. Tesseract 가 없거나 지번이 적으면 ok=False 로 돌려
호출한 쪽이 SIFT·chamfer 로 넘어가게 한다. 결과 A 는 쪽 px (x,y) -> EPSG:5186 (X,Y) 2x3 행렬.
"""
import csv
import io
import itertools
import math
import os
import re
import shutil
import subprocess
import tempfile

import cv2
import numpy as np

from . import vworld

JIBUN = re.compile(r"^(산)?(\d{1,4})(?:-(\d{1,3}))?([가-힣])?$")
CRS = 5186


def tesseract_path():
    p = os.environ.get("TESSERACT_CMD") or shutil.which("tesseract")
    if p:
        return p
    for c in (r"C:\Program Files\Tesseract-OCR\tesseract.exe", r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"):
        if os.path.exists(c):
            return c
    return None


def available():
    exe = tesseract_path()
    if not exe:
        return False
    try:
        r = subprocess.run([exe, "--list-langs"], capture_output=True, text=True, encoding="utf-8", timeout=20)
        return "kor" in r.stdout
    except Exception:
        return False


def ocr_tiles(img, tile=1000, pad=60, up=2.0, psm=11):
    """RGB 도면 -> [(text, cx, cy, conf)] (쪽 px)"""
    exe = tesseract_path()
    H, W = img.shape[:2]
    out = []
    for y in range(0, H, tile):
        for x in range(0, W, tile):
            x0, y0 = max(0, x - pad), max(0, y - pad)
            x1, y1 = min(W, x + tile + pad), min(H, y + tile + pad)
            sub = cv2.resize(cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_RGB2GRAY), None, fx=up, fy=up, interpolation=cv2.INTER_CUBIC)
            with tempfile.TemporaryDirectory() as d:
                p = os.path.join(d, "t.png")
                cv2.imwrite(p, sub)
                r = subprocess.run([exe, p, "stdout", "-l", "kor+eng", "--psm", str(psm), "tsv"],
                                   capture_output=True, text=True, encoding="utf-8", timeout=120)
            for row in csv.DictReader(io.StringIO(r.stdout), delimiter="\t", quoting=csv.QUOTE_NONE):
                t = (row.get("text") or "").strip()
                try:
                    conf = float(row.get("conf") or -1)
                    l, tp, w, h = (float(row[k]) for k in ("left", "top", "width", "height"))
                except (TypeError, ValueError):
                    continue
                if t and conf >= 0:
                    out.append((t, x0 + (l + w / 2) / up, y0 + (tp + h / 2) / up, conf))
    return out


def jibun_tokens(toks, min_conf=60):
    res = []
    for t, cx, cy, c in toks:
        if c < min_conf:
            continue
        t2 = t.replace(" ", "").replace("—", "-").replace("–", "-").replace("_", "-")
        m = JIBUN.match(t2)
        if m and (m.group(3) or m.group(4) or m.group(1)):     # 숫자만 있는 글자(표고 등)는 제외
            res.append({"txt": t2, "san": bool(m.group(1)), "bon": int(m.group(2)), "bu": int(m.group(3) or 0),
                        "jimok": m.group(4) or "", "x": cx, "y": cy, "conf": c})
    return res


_JR = re.compile(r"^(산)?\s*(\d+)(?:-(\d+))?\s*([가-힣])?")


def _parcel_index(parcels):
    from pyproj import Transformer
    from shapely.geometry import shape
    t = Transformer.from_crs(4326, CRS, always_xy=True).transform
    idx = {}
    for p in parcels:
        m = _JR.match((p.get("jibun") or "").strip())
        if not m:
            continue
        try:
            c = shape(p["geometry"]).centroid
        except Exception:
            continue
        X, Y = t(c.x, c.y)
        idx.setdefault((bool(m.group(1)), int(m.group(2)), int(m.group(3) or 0)), []).append((X, Y, m.group(4) or "", p["jibun"]))
    return idx


def _fit(pairs):
    """pairs: [(px, py, X, Y)] -> z, pc, qc, 잔차. 닮음변환 최소제곱, 쪽 좌표는 (x, -y) 복소수"""
    P = np.array([[a, -b] for a, b, _, _ in pairs]); Q = np.array([[c, d] for _, _, c, d in pairs])
    pc, qc = P.mean(0), Q.mean(0)
    Pz = (P - pc)[:, 0] + 1j * (P - pc)[:, 1]; Qz = (Q - qc)[:, 0] + 1j * (Q - qc)[:, 1]
    z = (np.conj(Pz) @ Qz) / (np.conj(Pz) @ Pz)
    return z, pc, qc, Qz - z * Pz


def _matrix(z, pc, qc):
    s, th = abs(z), float(np.angle(z)); c, sn = math.cos(th), math.sin(th)
    return np.array([[s * c, s * sn, qc[0] - s * c * pc[0] + s * sn * pc[1]],
                     [s * sn, -s * c, qc[1] - s * sn * pc[0] - s * c * pc[1]]])


def anchor_georef(img, s_est, lon, lat, half_m, log=print, min_inliers=6, tol=25.0):
    """s_est: 도면 쪽 px 하나의 지상 길이(m) 추정. 반환 dict(ok, A(->5186), ...)"""
    if not available():
        return {"ok": False, "reason": "Tesseract(kor) 없음"}
    toks = jibun_tokens(ocr_tiles(img))
    log(f"    지번 OCR: 지번꼴 글자 {len(toks)}개")
    if len(toks) < min_inliers:
        return {"ok": False, "reason": f"지번 글자 부족({len(toks)})"}
    pad = min(0.03, max(0.008, half_m / 111000))
    parcels = vworld.parcels_bbox(lon - pad, lat - pad, lon + pad, lat + pad, cell=0.008)
    idx = _parcel_index(parcels)
    cand = []
    for t in toks:
        cs = idx.get((t["san"], t["bon"], t["bu"]), [])
        if t["jimok"]:
            cs = [c for c in cs if not c[2] or c[2] == t["jimok"]]
        if 0 < len(cs) <= 8:
            cand.append((t, cs))
    log(f"    지적 필지 {len(parcels)}건, 지번이 짝지어진 글자 {len(cand)}개")
    if len(cand) < min_inliers:
        return {"ok": False, "reason": f"지적 필지와 짝지어진 지번 부족({len(cand)})"}
    lo, hi = s_est * 0.75, s_est * 1.35
    best = None
    for (ti, ci), (tj, cj) in itertools.combinations(cand, 2):
        dpx = math.hypot(ti["x"] - tj["x"], ti["y"] - tj["y"])
        if dpx < 150:
            continue
        angp = math.atan2(-(tj["y"] - ti["y"]), tj["x"] - ti["x"])
        for a in ci:
            for b in cj:
                s = math.hypot(a[0] - b[0], a[1] - b[1]) / dpx
                if not lo <= s <= hi:
                    continue
                th = math.atan2(b[1] - a[1], b[0] - a[0]) - angp
                if abs(math.degrees((th + math.pi) % (2 * math.pi) - math.pi)) > 6:
                    continue
                c, sn = math.cos(th), math.sin(th)
                n = 0
                for t, cs in cand:
                    x, y = t["x"] - ti["x"], -(t["y"] - ti["y"])
                    X, Y = a[0] + s * (c * x - sn * y), a[1] + s * (sn * x + c * y)
                    if min(math.hypot(X - q[0], Y - q[1]) for q in cs) < tol:
                        n += 1
                if best is None or n > best[0]:
                    best = (n, s, th, ti, a)
    if best is None or best[0] < min_inliers:
        return {"ok": False, "reason": f"지번 정합 대응 부족({best[0] if best else 0})"}
    n, s, th, ti, a = best
    c, sn = math.cos(th), math.sin(th)
    pairs = []
    for t, cs in cand:
        x, y = t["x"] - ti["x"], -(t["y"] - ti["y"])
        X, Y = a[0] + s * (c * x - sn * y), a[1] + s * (sn * x + c * y)
        q = min(cs, key=lambda q: math.hypot(X - q[0], Y - q[1]))
        if math.hypot(X - q[0], Y - q[1]) < tol:
            pairs.append((t["x"], t["y"], q[0], q[1]))
    for _ in range(2):                       # 재추정 후 잔차가 큰 짝을 빼고 다시
        z, pc, qc, res = _fit(pairs)
        keep = [p for p, r in zip(pairs, abs(res)) if r <= max(12.0, 2.0 * float(np.sqrt(np.mean(abs(res) ** 2))))]
        if len(keep) < min_inliers or len(keep) == len(pairs):
            break
        pairs = keep
    z, pc, qc, res = _fit(pairs)
    rms = float(np.sqrt(np.mean(abs(res) ** 2)))
    xs = np.array([p[0] for p in pairs]); ys = np.array([p[1] for p in pairs])
    spread = float(max(np.ptp(xs), np.ptp(ys)) / max(img.shape[:2]))
    return {"ok": True, "method": "anchor", "crs": CRS, "A": _matrix(z, pc, qc), "inliers": len(pairs), "matches": len(cand),
            "rms_m": rms, "scale_ratio": float(abs(z) / s_est), "spread": spread, "rot_deg": float(math.degrees(np.angle(z)))}
