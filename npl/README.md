# npl

옥션원 NPL 물건의 사건번호를 모아 두인 상세(필지·지분·등기부·채권 추정)를 구글시트에 저장합니다.

- 실행: `.github/workflows/npl.yml` (매주 목요일 22:00 KST 예약 + 수동 실행)
- 흐름: 옥션원 NPL 목록 → 두인 구글시트 주차 탭에서 사건번호 매칭(감정가·매각기일·소재지로 확인) → 매칭된 물건만 두인 상세 추출
- 결과: 구글시트 탭 `NPL_YYYYMMDD_상세`(YYYYMMDD = 그 주 토요일), 실행 기록 탭 `NPL_로그`. 이 저장소에는 올리지 않습니다.
- 열: 앞 19열은 두인 주차 탭과 같고 AC열이 토지등기 요약이라 PNU/QGIS 단계가 그대로 이어받습니다. 필지가 여러 개면 필지마다 한 행입니다.
- 미매칭 물건은 `매칭상태=미매칭`으로 옥션원 값(소재지 등)을 채워 남깁니다.
- Secrets: auction 워크플로와 같은 값 + `A1_LOGIN_ID`, `A1_LOGIN_PW`(옥션원).
- 두인 목록 수집(auction-weekly) 이후에 돌리면 매칭이 가장 잘 됩니다. 두인 시트에 없는 물건은 미매칭으로 남습니다.

## PC 실행 (옥션원이 GitHub 서버 IP를 403으로 막아 PC에서 돌린다)
- `python run_pc.py` (폴더 `npl`): 전체 실행. `--max-detail 5` 시험, `--show` 옥션원 브라우저 창 표시.
- 로그인 정보는 환경변수 또는 `D:\npl_env.txt`(형식: `npl_env.example.txt`). 저장소 밖에 둔다.
- 구글 서비스계정 키는 `500_local\100. Google_credentials\google_credentials_편집자.json` 을 자동으로 읽는다.
- `000_할일_바로가기\5_NPL_수집_실행.bat` 더블클릭으로 실행. 매주 목요일 밤은 Windows 작업 스케줄러에 이 bat 을 등록한다.
- GitHub 워크플로 `npl-weekly` 는 수동 시험용으로만 남긴다(예약은 끔).
