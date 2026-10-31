# wood-land-data-Auction

공개 크롤러 코드 모음입니다. 크롤링 결과는 이 저장소에 올리지 않고, 비공개 DB 저장소(`wood-land-data-db`)나 구글시트에 저장합니다.
작업 이력·진행 기록은 이 저장소에 두지 않습니다.

| 폴더 | 내용 | 실행 |
|---|---|---|
| `auction/` | 경공매 물건 수집 → 구글시트 | `.github/workflows/auction.yml` |
| `news/` | 지역신문 기사에서 주소(필지) 추출 | `.github/workflows/news.yml` |
| `gosi/` | 지자체·공공기관 고시공고·공보에서 보상 필지 추출 | `.github/workflows/collect-gosigongo.yml` |
| `eiass/` | 환경영향평가 초안공람 사업지구 경계·편입 필지(PNU) 추출 | `.github/workflows/eiass.yml` |

각 폴더에 독립된 `requirements.txt`와 `README.md`가 있고, 명령은 해당 폴더 안에서 실행합니다.
GitHub Actions 시크릿은 저장소 설정(Settings > Secrets)에 등록합니다.

- `auction/`: `SITE_DOMAIN`, `SITE_LOGIN_ID`, `SITE_LOGIN_PW`, `TYPE_A_LABEL`, `TYPE_B_LABEL`, `GOOGLE_SHEET_ID`, `SHARE_EMAIL`, `GOOGLE_SA_KEY_JSON_ADMIN`, `KAKAO_REST_API_KEY`
- `news/`: `DATA_DB_TOKEN`, `KAKAO_REST_API_KEY`, `VWORLD_API_KEY`
- `gosi/`: `GOSI_DB_TOKEN`, `KAKAO_REST_API_KEY`, `DEEPSEEK_API_KEY`, `GOOGLE_CREDENTIALS_EDITER`, `GOSI_GOOGLE_SHEET_ID`
- `eiass/`: `DATA_DB_TOKEN`, `VWORLD_API_KEY`, `VWORLD_DOMAIN`(선택)

## 새 PC(예: PCyw)에서 PC 수집 준비 — 처음 한 번
git 에 있는 것은 pull 만 하면 되고(코드, 공보 게시판 목록 xlsx, 차단 목록 json, 추가 인증서 등), **git 에 없는 것**(키·외부 프로그램)만 PC 마다 준비한다.
1. 코드 저장소를 clone/pull 한다. Python 3.12 와 git(GitHub 로그인: 비공개 DB 저장소 접근 권한)이 필요하다.
2. `500_local` 폴더를 코드 저장소의 상위 폴더에 둔다(다른 PC 에서 복사). 안에 필요한 것: `103. kakao Api key`, `101. Deepseek API key`, `102. Vworld Api key`, `100. Google_credentials`(구글 키 json + `sheet_id.txt`). 키는 공개 저장소에 올리지 않는다.
3. Tesseract OCR 을 설치하고 한글(kor) 언어 데이터를 포함한다(기본 경로 `C:/Program Files/Tesseract-OCR`).
4. `python gosi/setup_pc.py` — DB 저장소(`wood-land-data-db`)를 **코드 폴더 옆**(`D:\wood-land-data-db`, 코드는 `D:\wood-land-data-Auction`)에 clone 하고 환경변수 `WOOD_LAND_DB_DIR` 로 그 위치를 저장한 뒤, 위 항목이 다 있는지 점검하고, PC 이름(PCyw)을 저장한다. DB 는 이 한 폴더만 쓴다(gosi·news·eiass 공용, 코드 폴더 안에 두지 않는다).
5. `python run_pc_all.py`(또는 최상위 `★PC수집_전체_더블클릭_v….bat`). 처음에는 전용 가상환경 `.venv-pc` 를 만들고 패키지를 설치해 몇 분 걸린다.

PC 가 두 대여도 서로 다른 시간에 돈다. 한 PC 의 push 가 실패해 결과가 남아도 다른 PC 의 실행은 막히지 않고, 같은 sqlite 가 부딪쳐 push 가 안 되면 다음 실행의 시작 전 점검이 그 PC 의 수집 결과만 버리고 원격 최신으로 맞춘다(그 글들은 다시 수집됨). 코드 변경이 섞여 있으면 손대지 않고 멈춘다.
