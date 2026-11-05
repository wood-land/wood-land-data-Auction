# scourt — 대법원 회생파산 부동산 매각공고 수집

대법원 [회생파산 재산 매각(부동산) 공고](https://www.scourt.go.kr/portal/notice/realestate/RealNoticeList.work)에서 제목에 "부동산"이 들어간 공고를 훑어, 첨부 PDF(표→문장→OCR 순)에서 매각 대상 주소·지목·면적·입찰일정을 뽑아 구글시트에 저장한다.

## 구글시트 탭 (시트 ID는 워크플로의 `GOOGLE_SHEET_ID`)
| 탭 | 내용 |
|---|---|
| `공고목록` | 공고 1건(첨부 1개)에 1행, 계속 누적. 이미 있는 공고(`seq_id`)는 다시 읽지 않는다. 매각대상·입찰일정은 JSON 열에 통째로 보관 |
| `파산공매` | `공고목록`에서 **매번 처음부터 다시 만든다**(진행 중인 공고만, 주소 중복 제거, PNU 채움). 파싱 코드를 고치면 재수집 없이 `REBUILD_MERGED`만 돌려 과거 행까지 갱신 |
| `로그기록` | 실행 1회에 1줄 — 상태·훑은 쪽수·신규 공고 수·OCR 사용·매각완료 표시·파산공매 행수·PNU 실패·소요 분·실행 링크 |

## 실행
- 매일 07:00 KST 자동(`.github/workflows/scourt.yml`), 또는 Actions 탭에서 수동 실행.
- 수동 실행 입력: `mode`(`INCREMENTAL` 새 공고 수집 / `REBUILD_MERGED` 사이트 안 가고 `파산공매`만 재구성), `max_new`(시험용으로 새로 읽을 공고 수 상한).
- 첫 실행은 전체를 읽느라 오래 걸린다. `RUN_DEADLINE_MINUTES`(320분)에 새 공고 읽기를 멈추고 정리·로그를 남기며, 다음 실행이 이어서 수집한다.
- 상태가 `경고`면 목록에서 공고를 한 건도 못 본 것(러너 IP 차단·사이트 구조 변경 의심), `오류`면 예외가 난 것이다. 이때 워크플로도 실패로 끝난다.

## Secrets
`GOOGLE_CREDENTIALS_EDITER`(서비스계정 JSON, 시트 편집자 권한 필요), `KAKAO_REST_API_KEY`(PNU, 먼저 사용), `VWORLD_API_KEY`(PNU 보조 — 러너에서는 막혀 있을 수 있음)

## 로컬 실행
```
pip install -r requirements.txt   # OCR: tesseract(+kor), poppler 별도 설치
set GOOGLE_CREDENTIALS_EDITER=<JSON 전체>  KAKAO_REST_API_KEY=...  SCOURT_MAX_NEW=2
python crawler.py
```
추출 로직은 로컬판 `02_201. 대법원 파산공매 _구글시트 26 0823.py`(v3.6.36)와 같다. Actions용으로 바꾼 것: 헤드리스 크롬, 키는 환경변수, PNU는 카카오 우선, 시간 한도·시험용 상한, `로그기록` 탭, 비PDF(hwp) 첨부는 다운로드 대기 생략.
