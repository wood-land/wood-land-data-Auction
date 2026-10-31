"""
core/store.py - 결과 저장(비공개 DB 저장소 wood-land-data-db 의 eiass/).

eiass/
  projects/{사업코드}.geojson   사업지구 1건(EPSG:4326). 사업마다 파일 하나라 git 변경이 작다
  parcels/{사업코드}.csv        편입 필지(PNU, 지번, 편입면적·비율)
  preview/{사업코드}.jpg        위성영상 위 경계(확인용, 작게)
  review/{사업코드}.json|.jpg   자동 품질검사를 통과 못 한 사업(사람이 확인)
  state.json                    처리 이력(같은 사업을 매일 다시 하지 않게)
  EIASS_초안사업지.gpkg         QGIS 용 묶음: 레이어 '사업지구' + 표 '편입필지' (매 실행 projects/·parcels/ 로 다시 만든다)
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
          "accuracy_m", "georef", "src", "extracted"]


def ensure_dirs():
    for d in ("projects", "parcels", "preview", "review"):
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
    g = gpd.read_file(GPKG, layer="사업지구").to_crs(4326)
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
    """품질검사에서 탈락했지만 좌표는 나온 후보 중 계획면적과 가장 가까운 폴리곤을 review/{사업코드}.geojson(EPSG:4326)에 남긴다.
    QGIS 에서 '검토후보' 레이어로 보고 맞으면 projects/ 로 옮겨 확정한다. 후보가 없으면 예전 파일을 지운다."""
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


def rebuild_gpkg():
    import geopandas as gpd
    import pandas as pd
    files = sorted((DATA / "projects").glob("*.geojson"))
    if not files:
        return 0
    g = pd.concat([gpd.read_file(f) for f in files], ignore_index=True)
    g = gpd.GeoDataFrame(g, crs=4326).to_crs(5186)
    tmp = GPKG.with_suffix(".tmp.gpkg")
    if tmp.exists():
        tmp.unlink()
    g.to_file(tmp, layer="사업지구", driver="GPKG")
    rfiles = sorted((DATA / "review").glob("*.geojson"))
    if rfiles:  # 검토후보 레이어: 품질검사에 탈락한 후보 폴리곤(사람이 확인 전). 확정되면 projects/ 로 옮기고 이 파일은 지워진다
        gr = pd.concat([gpd.read_file(f) for f in rfiles], ignore_index=True)
        gpd.GeoDataFrame(gr, crs=4326).to_crs(5186).to_file(tmp, layer="검토후보", driver="GPKG")
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
    return len(g)
