# wood-land-data-gosi

전국 지자체 고시·공고 게시판과 공보(시보·군보·도보)에서 **토지보상 공고의 필지(소재지·지번 -> PNU)** 를 모으는 크롤러입니다. 코드만 공개하고, **수집 결과 DB 는 비공개 저장소**(`wood-land-data-db`, 다른 수집기와 공용)에 둡니다.

| 저장소 | 공개 | 내용 |
|---|---|---|
| `wood-land-data-gosi` (이 저장소) | 공개 | 크롤러 코드, GitHub Actions 워크플로 |
| `wood-land-data-db` | **비공개** | 여러 크롤러 공용 DB 저장소. 이 크롤러 몫은 `gosi/`: `{지역}.sqlite`(Actions 수집), `국내IP_{지역}.sqlite`(PC 수집). 뉴스·환경영향평가는 `news/`, `eiass/` |

## 동작
- GitHub Actions(`.github/workflows/collect-gosigongo.yml`)가 매일 06:30 KST 에 돌아 지역마다 3일에 한 번 수집하고, 결과를 비공개 DB 저장소에 커밋한다(Secret `GOSI_DB_TOKEN`).
- 필요한 Secret: `KAKAO_REST_API_KEY`, `DEEPSEEK_API_KEY`(선택), `GOOGLE_CREDENTIALS_EDITER` + `GOOGLE_SHEET_ID`(선택, 수집 로그 시트), `GOSI_DB_TOKEN`.
- 미국 IP(Actions)에서 막히는 게시판은 국내 IP PC 에서 `★PC수집_전체_더블클릭_v….bat`(저장소 최상위; 고시공고만: gosi/run_blocked_local.py) 로 수집한다(`core/blocked_sites.py`).
- 자세한 내용은 `README_스케줄.md` 참고.

## 폴더 구성 (PC)
저장소마다 폴더를 따로 두고 `D:\` 바로 아래에 나란히 clone 한다. DB 저장소는 한 곳만 clone 해서 모든 수집기가 같이 쓴다(`core/paths.py` 가 옆 폴더 `../wood-land-data-db` 를 찾는다).
```
D:\wood-land-data-gosi\    (공개 코드: 고시공고)
D:\wood-land-data-news\    (공개 코드: 지역신문, 예정)
D:\wood-land-data-eiass\   (공개 코드: 환경영향평가, 예정)
D:\wood-land-data-db\      (비공개 DB 저장소, 한 번만 clone: gosi/ news/ eiass/)
```

## PC 에서 쓰기 (한 번만 준비)
```
git clone https://github.com/wood-land/wood-land-data-gosi.git
cd wood-land-data-gosi
git clone https://github.com/wood-land/wood-land-data-db.git ../wood-land-data-db     # 비공개 DB 저장소(옆 폴더에 한 번만)
pip install -r requirements.txt
```
키·시트 ID 는 저장소에 두지 않는다. `500_local` 폴더(환경변수 `GOSI_LOCAL_DIR`, 또는 이 폴더의 `.local_dir` 파일에 경로 한 줄, 또는 상위 폴더에 있으면 자동) 아래에 둔다:
카카오 키 파일(폴더 이름에 `kakao`), 구글 서비스 계정 키 `google_credentials_편집자.json` 과 `sheet_id.txt`(폴더 이름에 `google_credentials`), DeepSeek 키(폴더 이름에 `deepseek`).
