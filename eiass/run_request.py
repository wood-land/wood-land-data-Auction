"""
run_request.py - 지리참조용 전체 도면(eiass_check plz/{코드}_{대표지번}_도면.png)을 (다시) 만든다.

  python run_request.py                       # 검토대기 사업 전부(글자 방향으로 회전을 자동 판별)
  python run_request.py HG2026A008            # 한 사업
  python run_request.py HG2026A008 --rot 90   # 시계 방향 90도로 돌려 만든다(0/90/180/270, 북쪽이 위가 되게)
돌린 각도는 figures/{코드}_review.json 의 georef_rot 에 남고, run_manual.py 가 점을 원래 그림 좌표로 되돌린다.
이미 올린 .points 가 있으면 도면을 새로 만들기 전의 점이라 쓸 수 없으니 새 도면으로 다시 찍어야 한다.
"""
import argparse
import sys

from core import manual, store


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("codes", nargs="*")
    ap.add_argument("--rot", type=int, choices=(0, 90, 180, 270), default=None)
    a = ap.parse_args()
    codes = a.codes or sorted(p.name.replace("_review.json", "") for p in (store.DATA / "figures").glob("*_review.json"))
    for cd in codes:
        out = manual.make_request_image(store.DATA, cd, a.rot)
        if out is None:
            print(f"{cd}: 요청 꾸러미(figures/{cd}_review.png·json)가 없음"); continue
        import json
        rot = json.loads((store.DATA / "figures" / f"{cd}_review.json").read_text(encoding="utf-8")).get("georef_rot")
        print(f"{cd}: 시계 방향 {rot}도 -> {out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
