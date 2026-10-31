"""
core/store.py - 결과 저장(비공개 DB 저장소 wood-land-data-db 의 eiass/).

eiass/
  projects/{사업코드}.geojson   사업지구 1건(EPSG:4326). 사업마다 파일 하나라 git 변경이 작다
  parcels/{사업코드}.csv        편입 필지(PNU, 지번, 편입면적·비율)
  preview/{사업코드}.jpg        위성영상 위 경계(확인용, 작게)
  figures/{사업코드}.png        평가서의 토지이용계획도 쪽 그림(지리참조자·사람 확인용. 공람이 끝나면 원본이 비공개라 보존)
  review/{사업코드}.json|.jpg   자동 품질검사를 통과 못 한 사업(사람이 확인)
  state.json                    처리 이력(같은 사업을 매일 다시 하지 않게)
  EIASS_초안사업지.gpkg         QGIS 용 묶음: 레이어 'EIASS_초안사업지' 하나(필드 '구분'으로 사업지구·대략위치·대표지번필지 구분) + 표 '편입필지' (매 실행 projects/·parcels/ 로 다시 만든다)
"""
import csv
import json
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _db_repo_dir():
    env = os.environ.get("WOOD_LAND_DB_DIR", "").strip()
    if env:
        return Path(env)
    # gosi(core/paths.py)와 같은 자리: 코드 저장소 안 wood-land-data-db/ (PC 에서 두 크롤러가 한 DB 저장소를 함께 쓴다), 그다음 코드 저장소 옆 폴더
    for sib in (ROOT.parent / "wood-land-data-db", ROOT.parent.parent / "wood-land-data-db"):
        if (sib / ".git").exists():
            return sib
    return ROOT / "data"


DATA = Path(os.environ.get("EIASS_DATA_DIR") or _db_repo_dir() / "eiass")
GPKG = DATA / "EIASS_초안사업지.gpkg"
FIELDS = ["biz_cd", "biz_nm", "biz_type", "location", "choan_period", "plan_m2", "area_m2", "area_diff_pct",
          "accuracy_m", "georef", "grade", "src", "extracted", "eiass_url", "report_file", "report_file_seq", "figure_png"]


def ensure_dirs():
    for d in ("projects", "parcels", "preview", "review", "figures", "approx"):
        (DATA / d).mkdir(parents=True, exist_ok=True)


def load_state():
    p = DATA / "state.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def save_state(st):
    (DATA / "state.json").write_text(json.dumps(st, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def seed_from_gpkg(state):
    """처음 실행: 손으로 만든 gpkg 의 사업들을 projects/ 로 옮기고 state 에 '완료'로 적는다.
    projects/ 에 있는데 state 에 없는 사업도 '완료'로 적는다(이력 파일이 늦게 생긴 경우)."""
    for f in (DATA / "projects").glob("*.geojson"):
        try:
            props = json.loads(f.read_text(encoding="utf-8"))["features"][0]["properties"]
        except Exception:
            props = {}
        auto = str(props.get("georef", "")).startswith("자동")
        if not auto and not state.get(f.stem, {}).get("manual"):
            # 사람이 손으로 맞춰 넣은 결과. 이슈 번호 등 기존 기록은 남겨 알림이 이슈를 닫을 수 있게 한다
            state[f.stem] = {**state.get(f.stem, {}), "status": "ok", "note": "수동 추출 결과", "manual": True, "need": None}
        elif f.stem not in state:
            state[f.stem] = {"status": "ok", "note": "기존 결과"}
    if not GPKG.exists() or any((DATA / "projects").glob("*.geojson")):
        return
    import geopandas as gpd
    import pyogrio
    layers = [l[0] for l in pyogrio.list_layers(GPKG)]
    g = gpd.read_file(GPKG, layer=LAYER if LAYER in layers else "사업지구")
    if "구분" in g.columns:
        g = g[g["구분"] == "사업지구"]
    g = g.to_crs(4326)
    for _, r in g.iterrows():
        props = {k: (None if str(r.get(k)) == "nan" else r.get(k)) for k in FIELDS if k in g.columns}
        write_project(r["biz_cd"], props, r.geometry)
        state[r["biz_cd"]] = {"status": "ok", "note": "수동 추출(2026-10-25)", "date": str(r.get("extracted", "")), "manual": True}


def write_project(biz_cd, props, geom4326):
    from shapely.geometry import mapping
    fc = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": props, "geometry": mapping(geom4326)}]}
    p = DATA / "projects" / f"{biz_cd}.geojson"
    p.write_text(json.dumps(fc, ensure_ascii=False, default=lambda o: float(o) if hasattr(o, "__float__") else str(o)),
                 encoding="utf-8")


def write_parcels(biz_cd, rows):
    p = DATA / "parcels" / f"{biz_cd}.csv"
    with open(p, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=["biz_cd", "pnu", "jibun", "addr", "parcel_m2", "overlap_m2", "ratio", "구분"])
        w.writeheader()
        for r in rows:
            w.writerow({"biz_cd": biz_cd, **r})


def write_review_candidate(biz_cd, meta, cand):
    """(품질검사 탈락 후보 폴리곤은 믿을 수 없어 목록·gpkg 에 넣지 않는다. cand=None 으로 불러 예전 review/{사업코드}.geojson 만 지운다.
    cand 가 있으면 예전 방식대로 그 폴리곤을 review/{사업코드}.geojson(EPSG:4326)에 쓴다)"""
    p = DATA / "review" / f"{biz_cd}.geojson"
    if not cand:
        if p.exists():
            p.unlink()
        return
    import geopandas as gpd
    from pyproj import Transformer
    from shapely.ops import transform
    poly, props = cand
    g4326 = transform(Transformer.from_crs(5186, 4326, always_xy=True).transform, poly)
    gdf = gpd.GeoDataFrame([{**{k: meta.get(k) for k in ("biz_cd", "biz_nm", "biz_type", "location", "choan_period", "plan_m2")},
                             **props, "상태": "검토후보(자동 품질검사 탈락)"}], geometry=[g4326], crs=4326)
    p.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(p, driver="GeoJSON")


APPROX_MAX_M = 1000.0


def approx_radius_raw(plan_m2):
    """대략 위치 원 반지름(m): 계획면적과 같은 면적 원 반지름의 1.5배(대표지번이 사업지 가장자리일 수 있다), 최소 300. 면적을 모르면 500"""
    import math
    return 500.0 if not plan_m2 else max(300.0, 1.5 * math.sqrt(plan_m2 / math.pi))


def too_large(plan_m2):
    """원 반지름이 APPROX_MAX_M(1km)를 넘는 대규모 사업(약 140만㎡ 초과)은 자동 추출 대상에서 뺀다"""
    return bool(plan_m2) and approx_radius_raw(plan_m2) > APPROX_MAX_M


def approx_radius(plan_m2):
    return min(APPROX_MAX_M, approx_radius_raw(plan_m2))


def write_approx(biz_cd, meta, lon, lat, how, plan_m2, parcel_geom4326=None, route=None, km=None, radius_m=None, extra=None):
    """도면 단서로 못 맞춘 사업: 대표지번(주소) 위치 주변 반경 원 + 대표지번 필지를 approx/ 에 남긴다. QGIS '대략위치'·'대표지번필지' 레이어."""
    import geopandas as gpd
    from pyproj import Transformer
    from shapely.geometry import Point
    from shapely.ops import transform
    r = radius_m if radius_m else approx_radius(plan_m2)   # radius_m: 소규모환경영향평가는 면적과 같은 넓이의 원 반지름을 직접 준다
    extra = extra or {}
    if route:   # 노선형 사업: 반경을 정하기 어렵다 -> 시점과 종점을 실선으로 이을 뿐이다(폴리곤 한 종류로 두려고 12m 폭으로 부풀린다)
        from shapely.geometry import LineString
        t1 = Transformer.from_crs(4326, 5186, always_xy=True).transform
        t2 = Transformer.from_crs(5186, 4326, always_xy=True).transform
        line = transform(t2, transform(t1, LineString(route)).buffer(12, cap_style=2))
        props = {**{k: meta.get(k) for k in ("biz_cd", "biz_nm", "location", "eiass_url", "plan_m2")}, "형태": "노선", "연장_km": km, **extra,
                 "상태": "대략위치(노선형 사업: 시점~종점 직선, 지리참조 필요)"}
        props["biz_cd"] = biz_cd
        (DATA / "approx").mkdir(parents=True, exist_ok=True)
        gpd.GeoDataFrame([props], geometry=[line], crs=4326).to_file(DATA / "approx" / f"{biz_cd}.geojson", driver="GeoJSON")
        (DATA / "approx" / f"{biz_cd}_parcel.geojson").unlink(missing_ok=True)
        return
    to5186 = Transformer.from_crs(4326, 5186, always_xy=True).transform
    to4326 = Transformer.from_crs(5186, 4326, always_xy=True).transform
    circle = transform(to4326, transform(to5186, Point(lon, lat)).buffer(r, 64))
    props = {**{k: meta.get(k) for k in ("biz_cd", "biz_nm", "location", "eiass_url", "plan_m2")}, "형태": "원", "radius_m": round(r), "위치근거": how, **extra,
             "상태": "대략위치(도면 단서 부족: 대표지번 주변 원, 지리참조 필요)"}
    props["biz_cd"] = biz_cd
    (DATA / "approx").mkdir(parents=True, exist_ok=True)
    gpd.GeoDataFrame([props], geometry=[circle], crs=4326).to_file(DATA / "approx" / f"{biz_cd}.geojson", driver="GeoJSON")
    pp = DATA / "approx" / f"{biz_cd}_parcel.geojson"
    if parcel_geom4326 is not None:
        gpd.GeoDataFrame([{**{k: props[k] for k in ("biz_cd", "biz_nm", "location")}, **{k: extra[k] for k in ("평가종류", "접수일", "진행현황") if k in extra}}], geometry=[parcel_geom4326], crs=4326).to_file(pp, driver="GeoJSON")
    elif pp.exists():
        pp.unlink()


def clear_approx(biz_cd):
    for f in (DATA / "approx").glob(f"{biz_cd}*.geojson"):
        f.unlink()


LAYER = "EIASS_초안사업지"   # gpkg 안의 레이어는 하나. 종류는 필드 '구분'(사업지구·대략위치·대표지번필지)


def rebuild_gpkg():
    import geopandas as gpd
    import pandas as pd
    parts = []
    for kind, files in (
            ("사업지구", sorted((DATA / "projects").glob("*.geojson"))),
            ("대략위치", [f for f in sorted((DATA / "approx").glob("*.geojson")) if not f.stem.endswith("_parcel")]),   # 도면 단서 부족: 대표지번 주변 원
            ("대표지번필지", sorted((DATA / "approx").glob("*_parcel.geojson")))):
        for f in files:
            g = gpd.read_file(f)
            g.insert(0, "구분", kind)
            parts.append(g)
    if not parts:
        return 0
    g = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=4326).to_crs(5186)
    if "평가종류" not in g.columns:
        g["평가종류"] = None
    g["평가종류"] = g["평가종류"].fillna("환경영향평가")
    n_main = int((g["구분"] == "사업지구").sum())
    tmp = GPKG.with_suffix(".tmp.gpkg")
    if tmp.exists():
        tmp.unlink()
    g.to_file(tmp, layer=LAYER, driver="GPKG")
    rows = []
    for f in sorted((DATA / "parcels").glob("*.csv")):
        with open(f, encoding="utf-8-sig") as fp:
            rows += list(csv.DictReader(fp))
    if rows:
        con = sqlite3.connect(tmp)
        pd.DataFrame(rows).to_sql("편입필지", con, index=False, if_exists="replace")
        con.execute("INSERT OR REPLACE INTO gpkg_contents(table_name,data_type,identifier,description) "
                    "VALUES('편입필지','attributes','편입필지','사업지구와 겹치는 연속지적도 필지(PNU)')")
        con.commit(); con.close()
    try:
        os.replace(tmp, GPKG)
    except PermissionError:
        # QGIS 등이 gpkg 를 열어 둔 상태(Windows 는 열린 파일을 바꿀 수 없다). projects/ 는 이미 저장돼 있어 gpkg 는 다음 실행에서 다시 만들면 된다.
        # tmp 파일을 남기면 git 에 올라가므로 지운다.
        tmp.unlink(missing_ok=True)
        print(f"[주의] {GPKG.name} 이 다른 프로그램(QGIS 등)에서 열려 있어 새로 만들지 못했습니다. 닫고 다시 실행하거나 다음 실행(Actions 포함)에서 만들어집니다.")
    return n_main
