"""
core/blocked_sites.py - GitHub 호스티드 러너(미국 Azure IP)에서 재현되게 막히는 게시판 목록.

2026-10-17 접속 테스트(history/15 7절)에서 러너가 실제로 못 읽은 곳만 넣는다. 일시적으로 실패한 곳(전북 eminwon 등)은 넣지 않는다.
  - 충청북도청: 고시공고·도보 모두 연결이 끊김(curl 56)
  - 청송군: eminwon.cs.go.kr 시간초과, 공보 404
  - 구미시: 첨부 서버 eminwon.gumi.go.kr 시간초과
  - 영천시·김천시·고령군·영양군: 목록이 러너에서만 404(국내 IP 에서는 200)

이 게시판은 국내 IP 에서 도는 PC 에서만 수집한다:
  - GitHub Actions(호스티드 러너)는 `run_scheduled.py --blocked skip` 으로 이 목록을 건너뛴다(워크플로에 이미 적용).
  - PC 는 `★PC수집_막힌지자체_더블클릭_v….bat`(251_gosi-gongo-crawle 폴더)을 더블클릭하면 `--blocked only` 로 이 목록만 수집한다.
  - 직접 실행: python run_scheduled.py --region 경북 --blocked only --db data/국내IP_경북.sqlite   (기본 all = 구분 없이 전부)

**새로 막히는 지자체**(아직 모든 시군구를 시도한 게 아니라 계속 생길 수 있다)는 두 가지로 들어간다:
  (자동) PC 수집 스크립트가 수집 로그(구글시트)를 분석해 Actions 가 반복해서 못 읽고 이 PC 에서는 읽히는 곳을 core/blocked_sites_auto.json 에 등록한다(detect_blocked.py).
  (수동) 아래 딕셔너리에 한 줄만 추가하고 커밋·푸시한다.
  "지역그룹": ["지자체", ...]   예) "전북": ["남원시"]
그러면 Actions 는 자동으로 그곳을 건너뛰고, PC 수집은 자동으로 그 지역·지자체를 포함한다(다른 수정 불필요).
키는 run_scheduled.py 의 --region 이름(경북·충북 등 REGIONS)이며 공보의 '권역(파일)'과 같다.
막혔는지 가리는 법: 같은 URL 을 국내 IP(이 PC)와 Actions 러너에서 열어 본다(history/15 7절). 수집 로그 시트의 '오류(목록)'·DL_FAIL 이 후보.
"""

import datetime as dt
import json
from pathlib import Path

BLOCKED_ON_HOSTED = {
    # 2026-10-25 추가(history/19): 수집 로그에서 러너가 반복해서 못 읽고(경남은 10-18~24 매번 다른 러너 IP 로 TCP 시간초과), 같은 곳이 이 PC(국내 IP)에서는
    #   목록과 첨부 모두 정상으로 읽힌 지자체. 계룡시(PC 에서도 403 세션 문제)·곡성군(중간 인증서 보완으로 러너에서도 풀림)은 넣지 않았다.
    "충북": ["충청북도청", "청주시"],  # 청주시: 첨부 서버 SSLEOFError 13회(러너), PC 정상
    "경북": ["청송군", "구미시", "영천시", "김천시", "고령군", "영양군", "봉화군", "안동시"],  # 봉화군·안동시: 첨부 시간초과/SSL(러너)
    # 2026-10-23 러너 9대 진단(history/17): 러너 9대 모두 TCP/DNS 실패, 국내 IP 는 정상. 전남·대구 전체가 막힌 것이 아니라(8/9 러너는 22/25 접속) 이 3곳만 상시 차단
    # 함평군·나주시·담양군·장성군(2026-10-25): 첨부 서버 시간초과가 로그에 반복(9·11·6·3회), PC 정상
    "전남": ["순천시", "강진군", "구례군", "함평군", "나주시", "담양군", "장성군"],
    "경남": ["거제시", "거창군", "경상남도청", "고성군", "남해군", "산청군", "의령군", "진주시", "창녕군", "하동군", "함안군", "합천군",
           "양산시", "밀양시"],  # 앞 12곳: 목록 TCP 시간초과 5일 연속, 양산시·밀양시: 첨부 서버 시간초과(18·3회)
    "충남": ["아산시"],  # 첨부 서버 SSL 오류 7회(러너), PC 정상
}

# 특별시·광역시 자치구·군은 PC 전용 후보로 올리지 않는다(사용자 지시 2026-10-25, law.md 1-1: 자치구는 신규 추가 금지).
# 본청(예: 대구광역시청)은 '구·군' 으로 끝나지 않으므로 해당하지 않는다.
METRO_MODULES = ("서울", "부산", "대구", "인천", "광주", "대전", "울산")


def is_metro_district(region, city):
    return region in METRO_MODULES and city.endswith(("구", "군"))


# 서울·부산·인천의 자치구·군은 PC 전용 후보로 올리지 않는다(사용자 지시 2026-10-25). 대구·대전·광주·울산·세종은 일반 지자체처럼 후보가 될 수 있다.
# 본청(예: 부산광역시청)은 '구·군' 으로 끝나지 않으므로 해당하지 않는다.
EXCLUDED_DISTRICT_MODULES = ("서울", "부산", "인천")


def is_excluded_district(region, city):
    return region in EXCLUDED_DISTRICT_MODULES and city.endswith(("구", "군"))


AUTO_FILE = Path(__file__).with_name("blocked_sites_auto.json")  # detect_blocked.py 가 등록: {지역: {지자체: {"since", "evidence"}}}


def _auto():
    try:
        return json.loads(AUTO_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def all_blocked():
    """수동 목록 + 자동 등록 목록 -> {지역: [지자체, ...]} (호출할 때마다 파일을 다시 읽는다)."""
    out = {r: list(cs) for r, cs in BLOCKED_ON_HOSTED.items()}
    for region, cities in _auto().items():
        for city in cities:
            if city not in out.setdefault(region, []):
                out[region].append(city)
    return out


def register_auto(region, city, evidence=""):
    """자동 등록 목록(blocked_sites_auto.json)에 지자체를 추가한다. 이미 있으면 그대로 둔다."""
    data = _auto()
    if city not in data.get(region, {}):
        data.setdefault(region, {})[city] = {"since": dt.date.today().isoformat(), "evidence": evidence}
        AUTO_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


REJECTED_FILE = Path(__file__).with_name("blocked_sites_rejected.json")  # 사용자가 등록을 거절한 후보: {"지역/지자체": "거절한 날짜"}


def reject_auto(region, city):
    """등록 후보를 거절했다고 기억한다(일정 기간 다시 묻지 않기 위해)."""
    try:
        data = json.loads(REJECTED_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data[f"{region}/{city}"] = dt.date.today().isoformat()
    REJECTED_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def recently_rejected(region, city, days=7):
    try:
        day = json.loads(REJECTED_FILE.read_text(encoding="utf-8")).get(f"{region}/{city}")
        return bool(day) and (dt.date.today() - dt.date.fromisoformat(day)).days < days
    except (OSError, ValueError):
        return False


def is_blocked(module, city):
    return city in all_blocked().get(module, ())


def should_run(mode, module, city):
    """mode: 'all'(전부) / 'skip'(막힌 곳 건너뜀) / 'only'(막힌 곳만)."""
    if mode == "skip":
        return not is_blocked(module, city)
    if mode == "only":
        return is_blocked(module, city)
    return True
