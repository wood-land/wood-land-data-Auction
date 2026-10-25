"""
core/kakao.py - 브이월드가 막힌 곳(GitHub Actions 미국 IP)에서 쓰는 대안.

- 위치 찾기: 카카오 주소검색 / 키워드검색
- PNU: 사업지구 안에 격자 점을 찍어 좌표->지번주소(coord2address) + 법정동코드(coord2regioncode)로 필지를 모은다.
  필지 경계가 없어 편입면적은 '점 개수 x 격자면적' 근사다(경계에 걸친 작은 필지는 빠질 수 있음).
  정확한 편입면적·비율은 국내 IP PC 에서 브이월드 연속지적도로 다시 구한다.
환경변수 KAKAO_REST_API_KEY (news/·gosi/ 와 같은 키)
"""
import math
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

import requests

from .keys import load as _load_key

KEY = _load_key("KAKAO_REST_API_KEY")
API = "https://dapi.kakao.com/v2/local"
S = requests.Session()


def _get(path, params):
    for i in range(4):
        try:
            r = S.get(API + path, headers={"Authorization": f"KakaoAK {KEY}"}, params=params, timeout=10)
            if r.status_code == 429:
                time.sleep(1.5 * (i + 1)); continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            time.sleep(1 + i)
    return {}


def geocode(q):
    j = _get("/search/address.json", {"query": q})
    for d in j.get("documents", []):
        return float(d["x"]), float(d["y"])
    return None


def keyword(q):
    j = _get("/search/keyword.json", {"query": q})
    for d in j.get("documents", []):
        return float(d["x"]), float(d["y"])
    return None


def locate(location_text, variants_fn):
    """variants_fn: vworld.address_variants 와 같은 후보 생성기"""
    for addr, kind in variants_fn(location_text):
        r = geocode(addr)
        if r:
            return r[0], r[1], f"kakao:{addr}"
    t = re.sub(r"\([^)]*\)", " ", location_text or "")
    words = [w for w in t.split() if re.search(r"(리|동|면|읍)$", w)]
    for w in reversed(words):
        r = keyword(" ".join(t.split()[:2]) + " " + w)
        if r:
            return r[0], r[1], f"kakao-keyword:{w}"
    return None


def pnu_grid(poly5186, max_points=2500):
    """사업지구 안 격자 점 -> 필지(PNU). 반환 rows(parcels.csv 형식)"""
    from pyproj import Transformer
    from shapely.geometry import Point
    from shapely.prepared import prep
    to4326 = Transformer.from_crs(5186, 4326, always_xy=True).transform
    area = poly5186.area
    step = max(6.0, math.sqrt(area / max_points))
    minx, miny, maxx, maxy = poly5186.bounds
    P = prep(poly5186)
    pts = []
    y = miny + step / 2
    while y < maxy:
        x = minx + step / 2
        while x < maxx:
            if P.contains(Point(x, y)):
                pts.append(to4326(x, y))
            x += step
        y += step

    def one(pt):
        j = _get("/geo/coord2address.json", {"x": pt[0], "y": pt[1]})
        for d in j.get("documents", []):
            a = d.get("address")
            if a:
                return pt, a
        return pt, None

    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(one, pts))
    bcode_cache, cnt, info = {}, {}, {}
    for pt, a in res:
        if not a or not a.get("main_address_no"):
            continue
        reg = (a.get("region_1depth_name"), a.get("region_2depth_name"), a.get("region_3depth_name"))
        if reg not in bcode_cache:
            j = _get("/geo/coord2regioncode.json", {"x": pt[0], "y": pt[1]})
            bcode_cache[reg] = next((d["code"] for d in j.get("documents", []) if d.get("region_type") == "B"), None)
        b = bcode_cache[reg]
        if not b:
            continue
        mnt = a.get("mountain_yn") == "Y"
        pnu = f"{b}{'2' if mnt else '1'}{int(a['main_address_no']):04d}{int(a.get('sub_address_no') or 0):04d}"
        cnt[pnu] = cnt.get(pnu, 0) + 1
        jb = f"{'산' if mnt else ''}{a['main_address_no']}" + (f"-{a['sub_address_no']}" if a.get("sub_address_no") else "")
        info[pnu] = (jb, a.get("address_name", ""))
    cell = step * step
    rows = [{"pnu": p, "jibun": info[p][0], "addr": info[p][1], "parcel_m2": "", "overlap_m2": round(n * cell, 1),
             "ratio": "", "구분": "편입(격자근사)" if n >= 2 else "경계접촉(확인필요)"} for p, n in cnt.items()]
    rows.sort(key=lambda r: (-r["overlap_m2"], r["pnu"]))
    return rows, len(pts), step
