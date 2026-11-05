# eiass — 환경영향평가 초안공람 사업지구 추출

EIASS(환경영향평가정보지원시스템) **환경영향평가 초안공람**에 올라온 사업의 사업지구 경계를
평가서 초안의 토지이용계획도에서 뽑아 실제 좌표로 맞추고, 편입 필지(PNU)까지 구한다.
(EIASS WFS `BA01_A` 에는 협의가 끝난 사업만 늦게 반영되므로 공람 중인 사업은 이 크롤러로 모은다)

실행: `.github/workflows/eiass.yml` (매일 07:20 KST, 수동 실행 가능)

## 흐름
1. 초안공람 목록(최신순) -> 아직 처리 안 한 사업
2. 상세 -> 사업지위치, 평가서 파일 -> '사업의 개요' PDF
3. 글에서 '토지이용계획(도)/항공사진/중첩/배치도' 그림 쪽을 찾아 고해상도(긴 변 4096px)로 받음
4. 사업경계선 + 용도 채색으로 경계 폴리곤 추출 (`core/extract.py`)
   - 경계선 색을 빨강 -> 자주 -> 파랑 -> 노랑 -> 흰 점선 순서로 찾고, 선이 없으면 용도별 채색 면의 바깥 윤곽을 쓴다
   - 색마다 후보를 만들어 좌표 맞춤·품질검사를 통과하는 첫 후보를 쓴다(엉뚱한 선을 잡으면 축척·면적 검사에서 걸러진다)
5. 좌표 맞춤
   - **1순위(브이월드 필요) `core/anchor.py`**: 도면의 지번 글자(482-11, 산52-26)를 Tesseract(kor)로 읽어 연속지적도의 같은 지번 필지와 짝지어 닮음변환(RANSAC). 등고선 지형도 배경에서도 된다. 지번 6개 이상·잔차 12m 이하·면적 ±6%면 통과(등급 A). Tesseract(kor) 설치 필요(`TESSERACT_CMD` 로 경로 지정 가능), 없으면 건너뜀
   - 나머지(`core/georef.py`, 등급 B):
   - 배경이 항공사진: 브이월드 위성영상과 SIFT 특징점 정합(닮음변환)
   - 배경이 선 도면: 브이월드 연속지적도 경계선과 거리변환 정합(축척은 계획면적으로 고정)
6. 품질검사 통과 -> 결과 저장 + 연속지적도와 겹쳐 PNU 목록 / 실패 -> `review/` (사람이 확인)

품질검사: SIFT 대응점 12개 이상·축척비 0.8~1.25·분포 0.25 이상·계획면적 ±6% /
chamfer 봉우리비 1.15 이상·선 일치율 0.15 이상·4구역 국소 어긋남 5m 이하.

## 검토대기와 알림
품질검사를 통과 못 한 사업은 `review/` 에 남고, 사유에 따라 둘로 나뉜다(`state.json` 의 `need`).
| need | 뜻 | 누가 |
| --- | --- | --- |
| `pc` | 브이월드가 있으면 풀릴 수 있음(선 도면, Actions 에서 위성영상 정합 실패) | 국내 IP PC 가 다음 실행 때 자동으로 다시 시도 |
| `human` | 기계로는 안 됨(경계를 못 찾음, 계획면적을 못 읽음, PC 에서도 정합 실패 등) | **사람** |

`notify.py`(Actions)가 알린다.
- `human` 사업마다 이 저장소에 이슈 `[eiass 확인필요] 사업코드 사업명` 을 연다. 완료되거나 공람이 끝나면 자동으로 닫는다.
- `pc` 사업 중 공람 마감이 5일 이내로 남은 것이 있으면 이슈 `[eiass] 국내 IP PC 실행 필요` 를 연다(없어지면 닫는다).
### 소규모환경영향평가 (`run_perss.py`)
EIASS 평가정보조회(`/biz/base/info/perList.do`, 소규모 = biz_gubn=M)의 최근 접수 사업을 모아 대략 위치를 만든다(`core/perss.py`). 환경영향평가 초안공람(`run_eiass.py`)과는 별개이며, 전략환경영향평가는 하지 않는다.
- 목록: `POST /searchApi/search.do`(collection=business, perssGubn=M, 접수일 최신순). 행 = 사업코드·사업구분·사업명·접수일·완료일·진행현황
- 상세: `perInfo.do?biz_gubn=M&PER_CD=…&REVIRPT_SEQ=…`(GET 으로 열려 영구 링크로 쓴다). '사업위치' 표 = 면형(소재지·면적) / 선형(시점·종점)
- 면형: 대표 지번(도로명) 주소 -> 좌표, 반지름 r = √(면적/π)(최소 30m) 원 + 대표지번 필지. 선형: 시점~종점 직선(10km 초과 제외)
- 결과: `approx/{사업코드}.geojson` -> gpkg 레이어 `EIASS_초안사업지`(구분=대략위치, **평가종류=소규모환경영향평가**), 처리 이력 `state_perss.json`
- 기본: 목록 3쪽·접수 30일 이내·한 번에 60건. `--pages`, `--days`, `--limit`, `--codes 사업코드:순번`, `--force`, `--test`. Actions 는 `eiass.yml` 에서, PC 는 `run_pc.py` 가 환경영향평가 뒤에 돌린다
- 원문(PDF)은 진행현황 '완료' 사업에만 있어(SYSTEM_NAME=PERSS 뷰어) 도면 정합은 아직 하지 않는다

### 대략위치 레이어 (단서가 부족한 도면)
도면에서 지번·지형 단서로 못 맞춘 사업은 **대표지번(사업지위치) 주변 원**을 `approx/{코드}.geojson`, 대표지번 필지를 `approx/{코드}_parcel.geojson` 에 남기고 gpkg 레이어 `대략위치`·`대표지번필지` 로 들어간다. 반지름 = 계획면적과 같은 면적 원 반지름의 1.5배(최소 300m, 면적을 모르면 500m). 반지름이 1km 를 넘는 대규모 사업(계획면적 약 140만㎡ 초과: 당진 석산·새만금 등)은 추출·검토 대상에서 빼고 `skip` 으로 기록한다. QGIS 에서 이 원 안을 위성영상으로 보며 지리참조한다. 확정(자동·수동)되면 지워진다. 이미 검토대기인 사업은 `python run_approx.py` 로 채운다.

### 사람이 지리참조자로 확정 (`run_manual.py`) — 전체 순서
사용자가 하는 일은 **PNG 열기 -> 점 찍기 -> `.points` 올리기** 셋뿐이고, 나머지는 자동이다.
1. **요청(자동)**: 자동 정합에 실패하면 `eiass_check plz/{코드}_{대표지번}_도면.png`(**전체 도면**: 주변 도로·지형이 다 보여 지도와 비교할 수 있음, **파일 이름에 대표 지번**, 문서에 누워 들어간 도면은 글자가 바로 서는 방향으로 돌려 만든다 - `run_request.py 코드 --rot 90` 으로 방향을 바꿀 수 있고, 돌린 각도는 `_review.json` 의 `georef_rot` 에 남아 점을 원래 좌표로 되돌린다. **자동 판별은 글자(한글) 방향만 본다** - 글자는 바로 서 있는데 지도만 누운 도면(예: DG2026O005, 북쪽이 왼쪽)은 못 맞추므로 방위표(N 화살표)를 확인해 `eiass_check plz/★도면_회전하기.bat` 으로 돌린다. 나침반 N 글자 기반 자동 검출은 시험했으나 범례 글자를 잘못 잡아 채택하지 않았다)와 `_review.json`(쪽 px 배율·자동 경계 윤곽·대략 위치)이 만들어지고, 사업마다 GitHub 이슈가 열린다(PNG 링크·요령 포함).
2. **점 찍기(사람)**: 파일 이름의 대표 지번을 지도에서 찾아 위치를 파악한 뒤, QGIS 지리참조자에 **전체 도면 `_도면.png`**(회전하지 말고 그대로)를 올리고 좌표계를 EPSG:5186 으로 한다. 기준점 **2점 이상**(도로 교차점·시설 모서리 등)을 도면 **양끝 쪽으로 멀리** 찍는다. 변환 실행·tif 출력은 필요 없고 **GCP 점만 저장**(.points)한다.
3. **반영(사람, 더블클릭 한 번)**: DB 저장소의 **`eiass_check plz\★지리참조_반영_더블클릭.bat`**(`eiass/run_georef.py`, 검토할 도면과 같은 폴더)을 실행한다. QGIS 가 그림 옆에 저장한 `eiass_check plz/{코드}_…_도면.png.points` 를 자동으로 찾아 가져오므로 **이름을 바꾸거나 옮길 필요가 없다**. DB 받기 -> 4번 반영 -> DB `eiass/` 커밋·푸시까지 한 번에 한다.
4. **반영 내용**(`run_manual.py`, Actions·PC 수집 `run_pc.py` 도 매 실행 처음에 돈다; `manual/{코드}.points` 로 직접 올려도 된다):
   - 검증: 점이 2개 이상이면 가장 먼 두 점 거리가 PNG 폭의 1/3 이상, 잔차 15 m 이하, 경계 면적이 계획면적과 ±10 % 이내.
   - 통과: 닮음변환(2점) / 최소제곱 닮음변환(3점 이상)으로 경계·PNU·미리보기·사업지만 오린 투명 PNG `figures/{코드}_site.png`(+`.pgw`,`.prj`)를 만들고 등급 C, `manual=True`, 상태 ok. `.points` 는 `manual/done/` 으로 옮겨 보관(다시 처리하지 않음), `review/`·대략위치 원은 지워지고 이슈는 다음 알림 단계에서 닫힌다.
   - 실패: 확정하지 않고 사유를 `state.json` 의 `manual_fail` 에 적어 이슈에 댓글로 남긴다. 같은 `.points` 는 다시 처리하지 않으며, 점을 고쳐 다시 올리면(내용이 바뀌면) 다시 처리한다. 경고를 알고도 확정하려면 `--force`.
5. 점이 1개면 계획면적에서 구한 축척·회전 0 으로 맞춘다(정확도는 낮음).
   `eiass_check plz/` 에는 **지금 사람이 해야 할 사업(검토대기)의 도면만** 남는다. 확정·제외된 사업의 파일(도면, QGIS 가 만든 `.points`·`_modified.tif`·`.aux.xml`)은 `run_manual.py` 가 지운다(QGIS 가 열어 둔 파일은 다음 실행에서). 확정한 점은 `manual/done/` 에 보관된다.
6. **검토할 가치가 없는 사업**: `eiass_check plz/` 에서 그 `_도면.png` 를 **지우기만 하면** 된다. 다음 실행(`run_manual.py`)이 '요청 도면이 만들어진 적이 있는데 파일이 없는 검토대기 사업'을 찾아 상태를 skip(검토 제외, `dismissed`)으로 바꾸고, **대략위치 원·요청 파일(review/·figures/)을 모두 지워 gpkg 에서도 빠지며** 이슈를 닫는다. 이미 `.points` 를 올린 사업은 건드리지 않는다. 도면 파일이 없는 사업(경계를 못 찾은 사업)은 `python run_manual.py 사업코드 --dismiss` 로 같은 처리를 한다. 되살리려면 `python run_eiass.py --codes 사업코드:순번 --force`.
도면에서 경계 윤곽을 못 찾은 사업은 이 방법을 못 쓰므로 아래처럼 경계를 직접 그려 넣는다.

사람이 처리할 때는 경계를 손으로 맞춰 DB 저장소 `eiass/projects/{사업코드}.geojson` 을 넣는다(georef 가 '자동'으로 시작하지 않게). 다음 실행에서 완료로 바뀐다.

## 결과 (비공개 `wood-land-data-db/eiass/`)
| 경로 | 내용 |
| --- | --- |
| `EIASS_초안사업지.gpkg` | QGIS 용. 레이어 **하나** `EIASS_초안사업지`(EPSG:5186, 필드 `구분` = 사업지구·대략위치·대표지번필지) + 표 `편입필지` |
| `projects/{사업코드}.geojson` | 사업지구 1건 |
| `parcels/{사업코드}.csv` | 편입 필지 PNU·편입면적·비율 |
| `preview/{사업코드}.jpg` | 위성영상 위 경계(확인용) |
| `figures/{사업코드}_site.png` + `.pgw/.prj` | 사업지구만 남긴(바깥 투명) 도면. QGIS 에 끌어 넣으면 제 위치에 놓임 |
| `figures/{사업코드}_review.png` | 검토대기 사업의 도면 쪽 전체(지리참조자용) |
| `review/{사업코드}.json/.jpg` | 자동 검사를 통과 못 한 사업 |
| `state.json` | 처리 이력 |

필드 `grade`: A=지번 정합, B=SIFT/chamfer, (C=사람 확정). `eiass_url` 은 EIASS 상세 영구 링크, `report_file`·`report_file_seq` 는 평가서 파일. 설계 배경은 `개선안_지리참조.md`.

## PC 설치 (지번 앵커 정합용 Tesseract)
국내 IP PC(PCwj/PCyw)는 `pip install -r requirements.txt` 외에 **Tesseract OCR + 한국어 데이터**가 있어야 지번 앵커 정합이 돈다(없으면 건너뛰고 SIFT·chamfer 로 간다).
1. `winget install UB-Mannheim.TesseractOCR` (기본 경로 `C:\Program Files\Tesseract-OCR`, 다른 곳이면 환경변수 `TESSERACT_CMD`)
2. 한국어 데이터 `kor.traineddata` 를 `C:\Program Files\Tesseract-OCR\tessdata\` 에 넣는다 (https://github.com/tesseract-ocr/tessdata_fast 에서 `kor.traineddata`). 관리자 권한 폴더라 탐색기에서 복사하거나 관리자 PowerShell 사용
3. 확인: `tesseract --list-langs` 에 `kor` 가 보이면 된다. `python run_eiass.py` 첫 줄에도 'Tesseract(kor) 있음' 이 찍힌다

## 국내 IP PC (브이월드)
GitHub Actions 러너(미국 IP)에서는 브이월드가 막힌다(2026-10-25 확인: 주소·위성타일·데이터 API 모두 실패).
그래서 러너에서는 위성영상을 Esri World Imagery, 위치·PNU 를 카카오(격자 근사)로 대신하고,
**선 도면**(지형·지적 배경, 연속지적도 정합이 필요한 것)은 `review/`에 `국내 IP PC 필요`로 남긴다.
PC(PCwj/PCyw)에서 `★PC수집_전체_더블클릭_v20261025.bat`(저장소 최상위, 고시공고도 함께 돈다. 환경영향평가만: `eiass/run_pc.py`) 을 실행하면 새 사업 + 검토대기 사업을 브이월드로 처리하고
DB 저장소 `eiass/` 만 커밋·푸시한다(`run_pc.py`). 키는 환경변수 또는 `500_local` 폴더(`core/keys.py`).

## 로컬 실행
```
pip install -r requirements.txt
set VWORLD_API_KEY=...        (PowerShell: $env:VWORLD_API_KEY="...")
python diag.py                # 접속 점검
python run_eiass.py --pages 2
python run_eiass.py --codes GG2026B008:45831 --force
```
DB 저장소 위치는 `WOOD_LAND_DB_DIR` 환경변수 -> 코드 저장소 옆 폴더 `../wood-land-data-db`(표준: `D:\wood-land-data-db`) -> 예전 방식(코드 폴더 안) -> `eiass/data/` 순서로 찾는다. 결과는 그 폴더의 `eiass/` 에 쌓이고, gosi·news 와 한 저장소를 함께 쓴다.

## Secrets
`DATA_DB_TOKEN`, `VWORLD_API_KEY` (news 와 같음), `VWORLD_DOMAIN`(선택: 브이월드가 도메인을 확인할 때)
