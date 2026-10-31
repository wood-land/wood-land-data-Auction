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

### 사람이 지리참조자로 확정 (`run_manual.py`)
1. 검토대기가 되면 `figures/{코드}_review.png`(도면 쪽 전체)와 `_review.json`(쪽 px 배율·자동 경계·대략 위치)이 만들어진다.
2. QGIS 지리참조자에 `_review.png` 를 올려 기준점 **2점 이상**(도로 교차점·시설 모서리 등, 서로 멀리)을 찍고 GCP 점을 `eiass/manual/{코드}.points` 로 저장한다.
3. `python run_manual.py 사업코드` -> 닮음변환(2점) / 최소제곱 닮음변환(3점 이상, 잔차 표시)으로 경계·PNU·미리보기·`figures/{코드}_site.png` 를 만든다. 등급 C, `manual=True`. 점이 1개면 계획면적에서 구한 축척·회전 0.
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
DB 저장소 위치는 `WOOD_LAND_DB_DIR` 환경변수 -> 형제 폴더 `../wood-land-data-db` -> `eiass/data/` 순서로 찾는다.

## Secrets
`DATA_DB_TOKEN`, `VWORLD_API_KEY` (news 와 같음), `VWORLD_DOMAIN`(선택: 브이월드가 도메인을 확인할 때)
