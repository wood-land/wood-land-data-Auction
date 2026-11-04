"""
core/manual.py - 자동으로 못 맞춘 사업을 사람이 지리참조자로 2점 이상 찍어 확정하는 흐름.

요청(자동): 검토대기가 되면 figures/{코드}_review.png(도면 쪽 전체)와 figures/{코드}_review.json(쪽 px<->PNG px 배율, 경계, 대략 위치)을 남긴다.
응답(사람): QGIS 지리참조자에 _review.png 를 올려 기준점을 찍고 'GCP 점 저장(.points)'을 DB 저장소 eiass/manual/{코드}.points 로 둔다.
확정(자동): run_manual.py 가 .points 로 닮음변환(2점) 또는 최소제곱 닮음변환(3점 이상)을 만들어 경계·PNU·미리보기를 저장한다(등급 C).
"""
import json
import math
import re
from pathlib import Path

import numpy as np


def write_request(data_dir, cd, meta, k, page, contour, plan, lonlat, size):
    p = data_dir / "figures" / f"{cd}_review.json"
    p.write_text(json.dumps({
        "biz_cd": cd, "biz_nm": meta.get("biz_nm"), "location": meta.get("location"), "eiass_url": meta.get("eiass_url"),
        "png": f"figures/{cd}_review.png", "png_scale": k, "page": page, "page_size_hw": list(size), "plan_m2": plan,
        "approx_lonlat": list(lonlat) if lonlat else None,
        "contour_page_px": None if contour is None else [[round(float(x), 1), round(float(y), 1)] for x, y in contour],
        "how": "QGIS 지리참조자에 png 를 올려 기준점 2점 이상(도로 교차점·시설 모서리 등)을 찍고 GCP 를 eiass/manual/%s.points 로 저장" % cd,
    }, ensure_ascii=False), encoding="utf-8")


def parse_points(path):
    """QGIS 지리참조자 .points -> (crs 문구, [(sx, sy_png, X, Y)]). sourceY 는 위로 갈수록 +(이미지 좌표의 음수)로 저장된다."""
    crs, pts = "", []
    # QGIS 가 좌표계 문구에 cp949 문자(예: 도 기호)를 섞어 저장하기도 해서 utf-8 로 못 읽는 바이트는 대체한다(좌표 숫자는 영향 없음)
    for ln in Path(path).read_bytes().decode("utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if ln.startswith("#CRS:"):
            crs = ln[5:].strip(); continue
        if ln.startswith("#") or ln.lower().startswith("mapx"):
            continue
        f = ln.split(",")
        if len(f) < 4:
            continue
        if len(f) >= 5 and f[4].strip() in ("0", "false", "False"):
            continue                                    # 사용 안 함으로 꺼 둔 점
        X, Y, sx, sy = (float(v) for v in f[:4])
        pts.append((sx, -sy, X, Y))
    return crs, pts


def epsg_of(crs):
    m = re.search(r"EPSG:(\d+)", crs or "", re.I)
    if m:
        return int(m.group(1))
    if "5186" in (crs or ""):
        return 5186
    return None


def fit_similarity(pairs, fixed_scale=None):
    """pairs: [(x, y, X, Y)] 닮음변환(축척·회전·이동). 1점이면 fixed_scale 필요(회전 0). 2점 이상이면 최소제곱.
    반환 (2x3 A: (x,y)->(X,Y), 잔차 m 목록)"""
    P = np.array([[x, -y] for x, y, _, _ in pairs], float); Q = np.array([[X, Y] for _, _, X, Y in pairs], float)
    pc, qc = P.mean(0), Q.mean(0)
    Pz = (P - pc)[:, 0] + 1j * (P - pc)[:, 1]; Qz = (Q - qc)[:, 0] + 1j * (Q - qc)[:, 1]
    if len(pairs) == 1:
        if not fixed_scale:
            raise ValueError("점이 1개면 축척을 알아야 함")
        z = complex(fixed_scale, 0)
    else:
        z = (np.conj(Pz) @ Qz) / (np.conj(Pz) @ Pz)
    res = np.abs(Qz - z * Pz)
    s, th = abs(z), float(np.angle(z)); c, sn = math.cos(th), math.sin(th)
    A = np.array([[s * c, s * sn, qc[0] - s * c * pc[0] + s * sn * pc[1]],
                  [s * sn, -s * c, qc[1] - s * sn * pc[0] - s * c * pc[1]]])
    return A, res.tolist()


def safe_name(location, limit=60):
    """대표 지번(사업지 위치 글)을 파일 이름에 쓸 수 있게 다듬는다."""
    import re
    s = re.sub(r"[\/:*?\"<>|\r\n\t]", " ", (location or "").replace("\xa0", " "))
    s = re.sub(r"\s+", " ", s).strip()
    return s[:limit].strip() or "위치미상"


def make_cutout(data_dir, cd):
    """_review.png 에서 사업지구만 오려 figures/georef/{코드}_{대표지번}_site.png 로 만들고, 요청(_review.json)에 오프셋을 적는다.
    사람은 이 오려낸 그림을 지리참조자에 올려 점을 찍는다(run_manual.py 가 오프셋을 더해 원래 그림 좌표로 되돌린다)."""
    import cv2
    import numpy as np
    from . import figure
    rp = data_dir / "figures" / f"{cd}_review.json"
    pp = data_dir / "figures" / f"{cd}_review.png"
    if not rp.exists() or not pp.exists():
        return None
    req = json.loads(rp.read_text(encoding="utf-8"))
    if not req.get("contour_page_px"):
        return None
    img = cv2.imread(str(pp), cv2.IMREAD_COLOR)
    if img is None:
        return None
    k = req["png_scale"]
    contour = np.array(req["contour_page_px"], float) * k
    gdir = data_dir / "figures" / "georef"
    for old in gdir.glob(f"{cd}_*_site.png"):
        old.unlink()
    out = gdir / f"{cd}_{safe_name(req.get('location'))}_site.png"
    off = figure.cutout_png(img, contour, out)
    if off is None:
        return None
    req["cutout"] = {"png": f"figures/georef/{out.name}", "offset_png_px": [off[0], off[1]]}
    req["how"] = ("QGIS 지리참조자에 cutout.png(오려낸 그림, 파일 이름에 대표 지번)를 올려 기준점 2점 이상(도로 교차점·시설 모서리·경계 꼭짓점 등)을 찍고 "
                  "GCP 를 eiass/manual/%s.points 로 저장" % cd)
    rp.write_text(json.dumps(req, ensure_ascii=False), encoding="utf-8")
    return out
