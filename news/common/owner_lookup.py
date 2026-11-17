"""필지 소유 구분 조회(VWorld 토지소유정보 dt_d160). 신문기사 필지에서 국유지·시도유지·군유지를 가려내는 데 쓴다(사용자 지시 2026-11-17).

신문기사에는 고시문 표와 달리 소유자 칸이 없다. 대신 주소를 PNU 로 바꿀 때 좌표(x=경도, y=위도)를 이미 받으므로,
그 좌표 주변(약 30m)의 소유 정보를 WFS 로 읽어 PNU 가 같은 필지의 소유 구분 코드를 얻는다.
posesn_se_code: 02 국유지 · 04 시도유지 · 05 군유지 · 06 법인 (MUMU MAP 과 같은 기준). 소유 정보는 현재 기준이다.
조회가 실패하거나 필지를 못 찾으면 None(= 판단 불가, 제외하지 않는다).
"""
import os
from typing import Optional

import requests

WFS_URL = "https://map.vworld.kr/js/wfs.do"
PUBLIC_CODES = {"02": "국유지", "04": "시도유지", "05": "군유지"}
DELTA = 0.0003  # 약 30m


def _key() -> str:
    return os.environ.get("VWORLD_API_KEY", "")


def lookup_owner_code(pnu: str, x: Optional[float], y: Optional[float], session: Optional[requests.Session] = None) -> Optional[str]:
    """PNU 의 소유 구분 코드('02' 등). 판단 불가(키·좌표 없음, 오류, 필지 없음)면 None."""
    key = _key()
    if not (key and pnu and x and y):
        return None
    s = session or requests.Session()
    params = {
        "apiKey": key, "domain": os.environ.get("VWORLD_DOMAIN", "http://localhost:8080"), "service": "WFS", "version": "1.1.0",
        "request": "GetFeature", "typename": "dt_d160", "srsname": "EPSG:4326",
        "bbox": f"{y - DELTA},{x - DELTA},{y + DELTA},{x + DELTA}",  # WFS 1.1.0 은 위도,경도 순서
        "maxfeatures": 50, "output": "application/json",
    }
    try:
        r = s.get(WFS_URL, params=params, timeout=20)
        r.raise_for_status()
        for f in r.json().get("features", []):
            p = f.get("properties") or {}
            if str(p.get("pnu") or "") == pnu:
                return str(p.get("posesn_se_code") or "") or None
    except Exception:
        return None
    return None


def public_label(code: Optional[str]) -> str:
    """공공 소유 코드면 '국유지' 같은 이름, 아니면 ''."""
    return PUBLIC_CODES.get(code or "", "")
