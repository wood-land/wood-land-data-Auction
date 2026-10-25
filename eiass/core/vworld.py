"""
core/vworld.py - 브이월드(Vworld) API.

환경변수
  VWORLD_API_KEY   (필수)  news/ 와 같은 키
  VWORLD_DOMAIN    (선택)  키를 발급받을 때 적은 서비스 URL. 데이터 API·WMTS 가 도메인을 확인하면 필요하다.

- 주소 -> 좌표: /req/address (getcoord, PARCEL/ROAD)
- 위성영상 타일: /req/wmts/1.0.0/{key}/Satellite/{z}/{y}/{x}.jpeg  (EPSG:3857 표준 XYZ)
- 연속지적도(필지 경계+PNU): /req/data  data=LP_PA_CBND_BUBUN
"""
import math
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import requests

KEY = os.environ.get("VWORLD_API_KEY", "").strip()
DOMAIN = os.environ.get("VWORLD_DOMAIN", "").strip()
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
R_EARTH = 6378137.0
ORIGIN = math.pi * R_EARTH          # 20037508.34


def _session():
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    if DOMAIN:
        s.headers["Referer"] = DOMAIN if DOMAIN.startswith("http") else "https://" + DOMAIN
    return s


S = _session()


def _get(url, params=None, timeout=30, tries=3):
    last = None
    for i in range(tries):
        try:
            r = S.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


# ---------------- 좌표 변환(EPSG:3857) ----------------
def ll2merc(lon, lat):
    x = lon * ORIGIN / 180.0
    y = math.log(math.tan((90 + lat) * math.pi / 360.0)) * R_EARTH
    return x, y


def merc2ll(x, y):
    lon = x / ORIGIN * 180.0
    lat = math.degrees(2 * math.atan(math.exp(y / R_EARTH)) - math.pi / 2)
    return lon, lat


# ---------------- 주소 -> 좌표 ----------------
def geocode(address, kind="PARCEL"):
    p = {"service": "address", "request": "getcoord", "version": "2.0", "crs": "epsg:4326", "address": address,
         "refine": "true", "simple": "false", "format": "json", "type": kind, "key": KEY}
    try:
        j = _get("https://api.vworld.kr/req/address", p, timeout=15).json()
        resp = j.get("response", {})
        if resp.get("status") == "OK":
            pt = resp["result"]["point"]
            return float(pt["x"]), float(pt["y"])
    except Exception:
        pass
    return None


def search_place(query):
    """주소가 안 맞을 때: 검색 API(행정구역/지명)로 대략 위치."""
    for cat in ("district", "place"):
        p = {"service": "search", "request": "search", "version": "2.0", "crs": "EPSG:4326", "size": 1, "page": 1,
             "query": query, "type": cat, "format": "json", "errorformat": "json", "key": KEY}
        if cat == "district":
            p["category"] = "L4"
        try:
            j = _get("https://api.vworld.kr/req/search", p, timeout=15).json()
            items = j.get("response", {}).get("result", {}).get("items", [])
            if items:
                pt = items[0]["point"]
                return float(pt["x"]), float(pt["y"])
        except Exception:
            pass
    return None


SIDO_ALIAS = {"전남광주통합특별시": ["전라남도", "광주광역시", ""], "강원특별자치도": ["강원특별자치도", "강원도"],
              "전북특별자치도": ["전북특별자치도", "전라북도"]}


def locate(location_text):
    """초안공람 '사업지위치' 글 -> (lon, lat, 방법). 예: '강원특별자치도 원주시 지정면 (저금어지길 102) 신평리 산57번지 일원'"""
    t = re.sub(r"\s+", " ", location_text or "").strip()
    road = re.search(r"\(([^)]*\d[^)]*)\)", t)
    base = re.sub(r"\([^)]*\)", " ", t)
    base = re.sub(r"(일원|일대|외\s*\d+\s*필지|등).*$", "", base)
    base = re.sub(r"번지", "", base)
    base = re.sub(r"\s+", " ", base).strip()
    toks = base.split(" ")
    sido = toks[0] if toks else ""
    variants = [base]
    for alt in SIDO_ALIAS.get(sido, []):
        variants.append((alt + " " + " ".join(toks[1:])).strip())
    cands = []
    for v in variants:
        cands.append((v, "PARCEL"))
        if road:
            # 도로명은 '시군구 + 도로명 + 번호'. 시군구까지 앞부분을 붙인다.
            pre = " ".join(w for w in v.split(" ") if re.search(r"(시|군|구|읍|면)$", w))
            cands.append((pre + " " + road.group(1), "ROAD"))
    for addr, kind in cands:
        r = geocode(addr, kind)
        if r:
            return r[0], r[1], f"{kind}:{addr}"
    # 마지막: 리/동 이름으로 검색
    words = [w for w in base.split(" ") if re.search(r"(리|동|면|읍)$", w)]
    for w in reversed(words):
        q = " ".join(base.split(" ")[:3]) + " " + w if len(base.split(" ")) > 3 else w
        r = search_place(q)
        if r:
            return r[0], r[1], f"search:{q}"
    return None


# ---------------- 위성영상 ----------------
def ground_res(z, lat):
    return 2 * ORIGIN / (256 * 2 ** z) * math.cos(math.radians(lat))


def satellite_mosaic(lon, lat, half_m, target_res, max_tiles=400):
    """중심(lon,lat) 주변 half_m(m) 를 덮는 위성영상. target_res(m/px)에 가까운 줌.
    반환: (img_rgb, x0, y0, res_merc)  픽셀(px,py) -> 3857 (x0+px*res, y0-py*res)"""
    import cv2
    z = int(round(math.log2(2 * ORIGIN * math.cos(math.radians(lat)) / (256 * target_res))))
    z = max(10, min(19, z))
    while True:
        res = 2 * ORIGIN / (256 * 2 ** z)
        cx, cy = ll2merc(lon, lat)
        hm = half_m / math.cos(math.radians(lat))           # 지상 m -> 3857 m
        tx0 = int((cx - hm + ORIGIN) / (256 * res)); tx1 = int((cx + hm + ORIGIN) / (256 * res))
        ty0 = int((ORIGIN - (cy + hm)) / (256 * res)); ty1 = int((ORIGIN - (cy - hm)) / (256 * res))
        n = (tx1 - tx0 + 1) * (ty1 - ty0 + 1)
        if n <= max_tiles or z <= 10:
            break
        z -= 1
    W = (tx1 - tx0 + 1) * 256; H = (ty1 - ty0 + 1) * 256
    img = np.zeros((H, W, 3), np.uint8)

    def fetch(t):
        tx, ty = t
        url = f"https://api.vworld.kr/req/wmts/1.0.0/{KEY}/Satellite/{z}/{ty}/{tx}.jpeg"
        try:
            b = _get(url, timeout=20).content
            a = cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR)
            return t, a
        except Exception:
            return t, None

    tiles = [(tx, ty) for tx in range(tx0, tx1 + 1) for ty in range(ty0, ty1 + 1)]
    ok = 0
    with ThreadPoolExecutor(8) as ex:
        for (tx, ty), a in ex.map(fetch, tiles):
            if a is not None and a.shape[:2] == (256, 256):
                img[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = a[:, :, ::-1]
                ok += 1
    x0 = tx0 * 256 * res - ORIGIN
    y0 = ORIGIN - ty0 * 256 * res
    return img, x0, y0, res, z, ok / max(1, len(tiles))


# ---------------- 연속지적도(PNU) ----------------
def parcels_bbox(minlon, minlat, maxlon, maxlat, cell=0.01, max_pages=20):
    """bbox 안의 필지(연속지적도). [{pnu, jibun, addr, geometry(GeoJSON, EPSG:4326)}]"""
    feats = {}
    nx = max(1, math.ceil((maxlon - minlon) / cell)); ny = max(1, math.ceil((maxlat - minlat) / cell))
    for i in range(nx):
        for j in range(ny):
            b = (minlon + i * (maxlon - minlon) / nx, minlat + j * (maxlat - minlat) / ny,
                 minlon + (i + 1) * (maxlon - minlon) / nx, minlat + (j + 1) * (maxlat - minlat) / ny)
            page = 1
            while page <= max_pages:
                p = {"service": "data", "request": "GetFeature", "data": "LP_PA_CBND_BUBUN", "key": KEY, "format": "json",
                     "errorformat": "json", "size": 1000, "page": page, "geometry": "true", "attribute": "true",
                     "crs": "EPSG:4326", "geomFilter": "BOX(%.7f,%.7f,%.7f,%.7f)" % b}
                if DOMAIN:
                    p["domain"] = DOMAIN
                j = _get("https://api.vworld.kr/req/data", p, timeout=40).json()
                resp = j.get("response", {})
                if resp.get("status") != "OK":
                    if resp.get("status") == "NOT_FOUND":
                        break
                    raise RuntimeError(f"Vworld data API: {resp.get('status')} {resp.get('error')}")
                for f in resp["result"]["featureCollection"]["features"]:
                    pr = f.get("properties", {})
                    feats[pr.get("pnu")] = {"pnu": pr.get("pnu"), "jibun": pr.get("jibun", ""), "addr": pr.get("addr", ""),
                                            "geometry": f.get("geometry")}
                total = int(resp.get("page", {}).get("total", 1))
                if page >= total:
                    break
                page += 1
    return list(feats.values())
