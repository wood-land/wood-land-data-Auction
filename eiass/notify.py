"""
notify.py - 사람이 개입해야 할 때 GitHub 이슈로 알린다(Actions 에서 run_eiass.py 다음에 실행).

1) 사람 확인 필요(need=human): 사업마다 이슈 1건 '[eiass 확인필요] 사업코드 사업명'
   - 도면에서 경계를 못 찾음, 계획면적을 못 읽음, PC(브이월드)에서도 좌표 맞춤 실패 등
   - 나중에 그 사업이 완료(ok)되거나 공람 종료로 건너뜀(skip)이 되면 이슈를 닫는다
2) PC 실행 필요: 'PC 대기' 사업 중 공람 마감이 5일 이내로 남은 것이 있으면 이슈 1건(내용을 갱신)
   - 공람이 끝나면 평가서 파일이 닫혀서 더는 처리할 수 없다. 대기 사업이 없어지면 닫는다
이슈 번호는 DB 저장소 eiass/state.json 에 적어 두어 중복으로 만들지 않는다.

환경변수: GH_TOKEN(=github.token, issues: write), GITHUB_REPOSITORY
이슈는 공개 저장소에 생기므로 공개 정보(사업코드·사업명·공람기간·사유)만 적고, 결과 파일은 비공개 DB 저장소 링크로만 건다.
"""
import datetime
import os
import re
import sys

import requests

from core import store

API = "https://api.github.com"
REPO = os.environ.get("GITHUB_REPOSITORY", "wood-land/wood-land-data-Auction")
TOKEN = os.environ.get("GH_TOKEN", "")
DB_URL = "https://github.com/wood-land/wood-land-data-db/blob/main/eiass"
EIASS_URL = "https://www.eiass.go.kr/partcptn/choan/choanEiassList.do"
S = requests.Session()
S.headers.update({"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"})
PC_KEY = "_pc_reminder"


def end_date(period):
    m = re.findall(r"(\d{4})\.(\d{2})\.(\d{2})", period or "")
    return datetime.date(*map(int, m[-1])) if m else None


def create(title, body):
    r = S.post(f"{API}/repos/{REPO}/issues", json={"title": title, "body": body})
    r.raise_for_status()
    return r.json()["number"]


def update(num, body=None, state=None, comment=None):
    if comment:
        S.post(f"{API}/repos/{REPO}/issues/{num}/comments", json={"body": comment})
    data = {}
    if body is not None:
        data["body"] = body
    if state:
        data["state"] = state
    if data:
        S.patch(f"{API}/repos/{REPO}/issues/{num}", json=data)


def main():
    if not TOKEN:
        print("GH_TOKEN 없음 - 알림 생략"); return 0
    st = store.load_state()
    today = datetime.date.today()
    changed = False
    for cd, v in list(st.items()):
        if not isinstance(v, dict) or cd.startswith("_"):
            continue
        need_human = v.get("status") == "review" and v.get("need") == "human"
        num = v.get("issue")
        if need_human and not num:
            body = (f"사람 확인이 필요한 환경영향평가 초안공람 사업입니다.\n\n"
                    f"- 사업코드: `{cd}`\n- 사업명: {v.get('biz_nm','')}\n- 공람기간: {v.get('choan_period','')}\n"
                    f"- 사유: {v.get('note','')}\n- 처리: {v.get('runner','')} / {v.get('date','')}\n\n"
                    f"확인 자료(비공개 DB 저장소): [{cd}.jpg]({DB_URL}/review/{cd}.jpg) · [{cd}.json]({DB_URL}/review/{cd}.json)\n"
                    f"EIASS 초안공람: {EIASS_URL}\n\n"
                    f"**지리참조 요청**: 도면 PNG [{cd}_review.png]({DB_URL}/figures/{cd}_review.png) 를 QGIS 지리참조자에 올려 "
                    f"기준점(도로 교차점·시설 모서리 등)을 **2점 이상** 찍고, GCP 점을 `eiass/manual/{cd}.points` 로 저장해 주세요. "
                    f"그다음 `python run_manual.py {cd}` 를 실행하면 경계·PNU 가 만들어집니다(등급 C). 요청 정보: `figures/{cd}_review.json`.\n"
                    f"(경계를 직접 맞췄다면 `eiass/projects/{cd}.geojson` 을 넣어도 됩니다. 공람이 끝나기 전에 처리해야 평가서를 볼 수 있습니다.)")
            v["issue"] = create(f"[eiass 확인필요] {cd} {v.get('biz_nm','')}"[:120], body)
            print(f"이슈 생성 #{v['issue']} {cd}"); changed = True
        elif num and not need_human:
            why = {"ok": "완료되어", "skip": "자동 추출 대상이 아니거나 공람이 끝나(파일 비공개)"}.get(v.get("status"), f"상태가 {v.get('status')}(으)로 바뀌어")
            update(num, state="closed", comment=f"{why} 닫습니다. ({v.get('note','')})")
            print(f"이슈 닫음 #{num} {cd}"); v["issue"] = None; changed = True
    # PC 대기 중 공람 마감 임박
    pend = []
    for cd, v in st.items():
        if isinstance(v, dict) and v.get("status") == "review" and v.get("need") == "pc":
            e = end_date(v.get("choan_period"))
            if e and 0 <= (e - today).days <= 5:
                pend.append((e, cd, v))
    meta = st.get(PC_KEY) or {}
    if pend:
        pend.sort()
        body = ("국내 IP PC 에서 처리해야 하는 사업(선 도면 등) 중 **공람 마감이 5일 이내**인 것이 있습니다.\n"
                "PC 에서 `★PC수집_전체_더블클릭_v….bat`(저장소 최상위) 을 실행해 주세요. 마감이 지나면 평가서를 볼 수 없습니다.\n\n"
                "| 공람 마감 | 사업코드 | 사업명 |\n|---|---|---|\n" +
                "".join(f"| {e.isoformat()} | `{cd}` | {v.get('biz_nm','')} |\n" for e, cd, v in pend))
        if meta.get("issue"):
            update(meta["issue"], body=body)
        else:
            meta["issue"] = create("[eiass] 국내 IP PC 실행 필요 (공람 마감 임박)", body)
            print(f"PC 실행 알림 이슈 #{meta['issue']}")
        st[PC_KEY] = meta; changed = True
    elif meta.get("issue"):
        update(meta["issue"], state="closed", comment="마감 임박한 PC 대기 사업이 없어 닫습니다.")
        st[PC_KEY] = {}; changed = True
    if changed:
        store.save_state(st)
    return 0


if __name__ == "__main__":
    sys.exit(main())
