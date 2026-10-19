# 자동 수집 (GitHub Actions -> SQLite)

> 2026-10-18: 저장소를 둘로 나눴다. 이 저장소(공개)는 코드만, `data/*.sqlite` 는 비공개 저장소 `wood-land-data-db` 의 `gosi/` 에 있다(Actions 가 그 저장소를 `data/` 로 받아 커밋). 아래 `data/…` 경로는 모두 `data/gosi/…` 를 뜻한다.

- 워크플로: `.github/workflows/collect-gosigongo.yml` — 매일 06:30 KST 자동 실행, Actions 탭에서 수동 실행(`only`: gosigongo/gazette)도 가능.
- 실행기: `run_scheduled.py` — 고시공고(cities/*.py, 12일) + 공보 시보·군보(`output/시군구_공보게시판_목록_new.xlsx`, 15일).
- 지역 18개(지자체 16개 + 전국1=중앙기관, 전국2=공기업+관보)를 matrix 로 병렬 실행하고, 지역마다 `data/{지역}.sqlite` 를 자동 커밋한다. 다른 PC는 `git pull` 만 하면 같은 DB를 이어 받는다. 수동 실행 때 `regions`(예: 강원,충북)로 일부만 돌릴 수 있다.
- 카카오 키는 GitHub Secret `KAKAO_REST_API_KEY` (값은 `KakaoAK ` 접두어 없이 키만). 로컬은 환경변수 또는 500_local/103 파일.
- 테이블: parcels(PNU가 있는 필지만) / pnu_cache / gosigongo_notices / gazette_notices / gazette_board_status / runs
- 수집 대상(게시판 목록)을 바꾸려면 엑셀 `공보게시판` 시트(L열 사용자 입력 URL)나 cities/*.py 를 수정해 push.

로컬 실행(Tesseract 필요, 공보 OCR용):
    pip install -r requirements.txt
    python run_scheduled.py --region 강원

## 실패 주소 자동 복구
- PNU로 못 바꾼 주소는 버리지 않고 `parcels_unresolved` 표에 사유(reason)와 함께 저장한다.
- 매 실행 시작 때 미해결 주소를 먼저 다시 시도한다(문서 재다운로드 없음). 다시 시도하는 경우: 일시 오류 / `core/pnu.py`의 `RESOLVER_VERSION`을 올림(변환 규칙을 고쳤을 때) / AI 보정이 새로 가능해짐 / 마지막 시도 후 30일 경과.
- 규칙 변환이 모두 실패하면 DeepSeek(`core/ai_fix.py`)이 소재지를 정리하고, 카카오가 지번·지자체 일치를 검증한 것만 저장한다. Secret `DEEPSEEK_API_KEY` 필요(없으면 건너뜀).
- 변환 규칙을 개선했다면 `RESOLVER_VERSION`을 1 올려서 push 하면, 다음 스케줄 때 과거 실패분이 한 번에 재처리된다.

## 실행 주기와 저장 최소화 (2026-10-16 변경)
- (2026-10-18) 전국은 기관이 많아 `전국1`(중앙기관 14곳)·`전국2`(공기업 13곳+관보)로 나눠 **5일에 한 번**씩 돈다(`(날짜+0) % 5`, `(날짜+2) % 5`). 수집 기간 7일이라 2일이 겹친다. 지자체 16곳은 아래대로 3일 주기. 옛 `전국.sqlite` 는 DB 저장소에 그대로 남는다.
- 스케줄은 매일 06:30 KST 이지만, 그날 돌 지역은 `(날짜 + 지역 번호) % 3 == 0` 인 약 1/3(5~6곳)뿐이다. 지역마다 3일에 한 번 돈다. 수동 실행(`regions` 비움)은 17개 전체.
- 수집 기간은 고시공고·공보 모두 최근 7일(3일 주기라 4일씩 겹쳐 누락 방지).
- git 의 `data/{지역}.sqlite` 에는 `parcels(pnu, title, url)` 와 재시도용 `parcels_unresolved`, 점검용 `gazette_board_status`, `runs` 만 남긴다. 변환/AI 캐시는 `data/.cache/` (git 제외, Actions 는 actions/cache) 에 둔다. 예전 DB는 다음 실행 때 자동으로 이 구조로 바뀐다.

## SQLite 구조 (2026-10-16 최종)
- `notices(id, url, title, post_date, city, source_type)` — 공고 1건 = 1행(제목·링크는 여기에만).
- `parcels(pnu, notice_id, sojaeji, jibun, jimok, area_incl)` — PNU 가 있는 필지만. 공고 정보는 notice_id 로 연결:
  `SELECT p.*, n.title, n.url, n.post_date FROM parcels p JOIN notices n ON n.id = p.notice_id`
- `parcels_unresolved`(재시도용), `gazette_board_status`, `runs`(점검용).
- 예전 DB(넓은 형태/최소 형태)는 열 때 자동으로 이 구조로 옮겨진다(`core/sqlite_store.py` `_migrate`).

## verified 열 (지번 존재 확인 여부)
- `parcels.verified = 1`: 카카오가 그 지번을 직접 확인한 PNU.
- `parcels.verified = 0`: 리/동은 확인됐지만 지번이 지도 DB 에 없어(분할·신규·말소 필지 등) **리 법정동코드(10자리) + 지번으로 조립**한 PNU(`core/pnu.py` `_from_ri_code`). 정밀 분석에서는 필요하면 `WHERE verified = 1` 로 거를 수 있다.
