"""
core/paths.py - 수집 결과 DB 위치.

DB 는 여러 크롤러가 함께 쓰는 비공개 저장소 `wood-land-data-db` 에 있다. 이 크롤러(고시공고)의 몫은 그 저장소의 gosi/ 폴더다.
DB 저장소(clone)를 찾는 순서:
  1) 환경변수 WOOD_LAND_DB_DIR              (예: D:/200_MuMu-Auction/wood-land-data-db — 크롤러가 여러 개일 때 하나를 같이 쓰는 방법)
  2) 코드 저장소 옆 폴더 <코드 저장소>/../wood-land-data-db  (표준 위치: D:/wood-land-data-Auction 옆의 D:/wood-land-data-db)
  3) 코드 저장소 안 <코드 저장소>/wood-land-data-db           (예전 방식, 있으면)
  4) 이 폴더 안의 data/                      (GitHub Actions 는 DB 저장소를 여기로 checkout 한다)
실제 DB 파일: <DB 저장소>/gosi/{지역}.sqlite   (뉴스·환경영향평가 크롤러는 같은 저장소의 news/, eiass/)
환경변수 GOSI_DATA_DIR 로 gosi 폴더 자체를 바꿀 수도 있다(시험용).
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _db_repo_dir():
    env = os.environ.get("WOOD_LAND_DB_DIR", "").strip()
    if env:
        return Path(env)
    for cand in (ROOT.parent.parent / "wood-land-data-db", ROOT.parent / "wood-land-data-db"):
        if (cand / ".git").exists():
            return cand
    return ROOT / "data"


DB_REPO_DIR = _db_repo_dir()
DATA_DIR = Path(os.environ.get("GOSI_DATA_DIR") or DB_REPO_DIR / "gosi")
