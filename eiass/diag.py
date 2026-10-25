"""
diag.py - 이 실행 환경(IP)에서 EIASS·브이월드가 열리는지 확인한다.  python diag.py
키 값은 출력하지 않는다.
"""
import sys
import time

import requests

from core import site, vworld


def step(name, fn):
    t = time.time()
    try:
        r = fn()
        print(f"[OK]   {name} ({time.time()-t:.1f}s) {r}")
        return True
    except Exception as e:
        print(f"[FAIL] {name} ({time.time()-t:.1f}s) {type(e).__name__}: {str(e)[:200]}")
        return False


def main():
    E = site.Eiass(timeout=25)
    ok = {}
    rows = []
    ok["eiass_list"] = step("EIASS 초안공람 목록", lambda: (rows.extend(E.list_page(1)), f"{len(rows)}건, 첫 건 {rows[0]['biz_cd'] if rows else '-'}")[1])
    if rows:
        d = {}
        ok["eiass_detail"] = step("EIASS 상세", lambda: (d.update(E.detail(rows[0]['biz_cd'], rows[0]['biz_seq'])), f"파일 {len(d['files'])}개, 위치 {d['location'][:30]}")[1])
        if d.get("files"):
            f = d["files"][0]; sid = []
            ok["streamdocs"] = step("평가서 뷰어 id", lambda: (sid.append(E.streamdocs_id(f['seq'], f['name'])), bool(sid[0]))[1])
            if sid and sid[0]:
                ok["render"] = step("쪽 그림(zoom 800)", lambda: E.render(sid[0], 0).shape)
    print("VWORLD_API_KEY:", "있음" if vworld.KEY else "없음", "/ VWORLD_DOMAIN:", vworld.DOMAIN or "(없음)")
    ok["vw_address"] = step("브이월드 주소->좌표", lambda: vworld.geocode("강원특별자치도 원주시 지정면 신평리 산57"))
    def tile():
        url = f"https://api.vworld.kr/req/wmts/1.0.0/{vworld.KEY}/Satellite/15/12712/28024.jpeg"
        r = vworld.S.get(url, timeout=20); return f"HTTP {r.status_code} {r.headers.get('content-type')} {len(r.content)}B"
    ok["vw_wmts"] = step("브이월드 위성 타일", tile)
    ok["vw_data"] = step("브이월드 연속지적도(data API)", lambda: f"{len(vworld.parcels_bbox(127.884, 37.376, 127.888, 37.380))}필지")
    bad = [k for k, v in ok.items() if not v]
    print("결과:", "모두 정상" if not bad else "실패 " + ", ".join(bad))
    return 0


if __name__ == "__main__":
    sys.exit(main())
