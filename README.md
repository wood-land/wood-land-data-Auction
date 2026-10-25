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
