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


def detect_rot(img_bgr):
    """글자가 바로 서는 시계 방향 회전각(0/90/180/270). 문서 쪽에 도면이 누워 들어간 경우를 찾는다. 못 정하면 0.
    네 방향으로 돌려 OCR 한 한글 글자 수가 가장 많은 방향을 고른다(제목·범례 글자가 많아 대체로 맞다). 글자가 서는 방향이 북쪽 위라는 보장은 없으니 도면의 N 화살표로 확인한다."""
    import cv2
    from . import anchor
    if not anchor.available():
        return 0
    h, w = img_bgr.shape[:2]
    sc = min(1.0, 2000 / max(h, w))
    small = cv2.resize(img_bgr, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA) if sc < 1 else img_bgr
    codes = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}
    scores = {}
    for rot in (0, 90, 180, 270):
        im = small if rot == 0 else cv2.rotate(small, codes[rot])
        toks = anchor.ocr_tiles(cv2.cvtColor(im, cv2.COLOR_BGR2RGB), tile=1200, pad=40, up=1.5, psm=11)
        scores[rot] = sum(len(re.findall("[가-힣]", t)) for t, _, _, conf in toks if conf >= 60)
    order = sorted(scores, key=scores.get, reverse=True)
    best, second = order[0], order[1]
    return best if scores[best] >= 20 and scores[best] >= 1.5 * max(scores[second], 1) else 0


def rot_to_orig(rot, u, v, wo, ho):
    """시계 방향 rot 도 돌린 그림의 점(u, v; 연속 픽셀 좌표)을 원래 그림 좌표로. wo, ho = 원래 그림의 가로·세로 px"""
    if rot == 90:
        return v, ho - u
    if rot == 180:
        return wo - u, ho - v
    if rot == 270:
        return wo - v, u
    return u, v


def make_request_image(data_dir, cd, rot=None):
    """사람이 지리참조자에 올릴 전체 도면: _review.png 를 (필요하면 북쪽이 위가 되게 돌려) figures/georef/{코드}_{대표지번}_도면.png 로 만든다.
    주변 도로·지형·글자가 다 보여야 지도와 비교해 점을 찍을 수 있으므로 오려내지 않는다. rot: 시계 방향 0/90/180/270, 없으면 요청에 적힌 값, 그것도 없으면 글자 방향으로 자동 판별.
    돌린 각도는 요청(_review.json)의 georef_rot 에 적어, run_manual.py 가 점을 원래 그림 좌표로 되돌린다. 확정 결과(사업지만 오린 투명 PNG)는 run_manual.py 가 따로 만든다."""
    import cv2
    rp = data_dir / "figures" / f"{cd}_review.json"
    pp = data_dir / "figures" / f"{cd}_review.png"
    if not rp.exists() or not pp.exists():
        return None
    req = json.loads(rp.read_text(encoding="utf-8"))
    img = cv2.imread(str(pp), cv2.IMREAD_COLOR)
    if img is None:
        return None
    if rot is None:
        rot = req.get("georef_rot")
    if rot is None:
        rot = detect_rot(img)
    codes = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}
    out_img = cv2.rotate(img, codes[rot]) if rot in codes else img
    gdir = data_dir / "figures" / "georef"
    gdir.mkdir(parents=True, exist_ok=True)
    for old in list(gdir.glob(f"{cd}_*_도면.png")) + list(gdir.glob(f"{cd}_*_site.png")):
        try:
            old.unlink()
        except OSError:
            pass
    out = gdir / f"{cd}_{safe_name(req.get('location'))}_도면.png"
    ok, buf = cv2.imencode(".png", out_img)           # cv2.imwrite 는 한글 경로에 쓰지 못한다
    if not ok:
        return None
    out.write_bytes(buf.tobytes())
    req.pop("cutout", None)
    req["georef_png"] = f"figures/georef/{out.name}"
    req["georef_rot"] = int(rot)
    req["georef_orig_wh"] = [int(img.shape[1]), int(img.shape[0])]
    req["how"] = ("QGIS 지리참조자에 georef_png(전체 도면, 파일 이름에 대표 지번)를 올려 기준점 2점 이상(도로 교차점·시설 모서리 등)을 찍고 "
                  "GCP 를 저장하면 ★지리참조_반영_더블클릭.bat 이 반영한다")
    rp.write_text(json.dumps(req, ensure_ascii=False), encoding="utf-8")
    return out
