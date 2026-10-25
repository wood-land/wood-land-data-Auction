# eiass — 환경영향평가 초안공람 사업지구 추출

EIASS(환경영향평가정보지원시스템) **환경영향평가 초안공람**에 올라온 사업의 사업지구 경계를
평가서 초안의 토지이용계획도에서 뽑아 실제 좌표로 맞추고, 편입 필지(PNU)까지 구한다.
(EIASS WFS `BA01_A` 에는 협의가 끝난 사업만 늦게 반영되므로 공람 중인 사업은 이 크롤러로 모은다)

실행: `.github/workflows/eiass.yml` (매일 07:20 KST, 수동 실행 가능)

## 흐름
1. 초안공람 목록(최신순) -> 아직 처리 안 한 사업
2. 상세 -> 사업지위치, 평가서 파일 -> '사업의 개요' PDF
3. 글에서 '토지이용계획(도)/항공사진/중첩/배치도' 그림 쪽을 찾아 고해상도(긴 변 4096px)로 받음
4. 빨간 사업경계선 + 용도 채색으로 경계 폴리곤 추출 (`core/extract.py`)
5. 좌표 맞춤 (`core/georef.py`)
   - 배경이 항공사진: 브이월드 위성영상과 SIFT 특징점 정합(닮음변환)
   - 배경이 선 도면: 브이월드 연속지적도 경계선과 거리변환 정합(축척은 계획면적으로 고정)
6. 품질검사 통과 -> 결과 저장 + 연속지적도와 겹쳐 PNU 목록 / 실패 -> `review/` (사람이 확인)

품질검사: SIFT 대응점 12개 이상·축척비 0.8~1.25·분포 0.25 이상·계획면적 ±6% /
chamfer 봉우리비 1.15 이상·선 일치율 0.15 이상·4구역 국소 어긋남 5m 이하.

## 결과 (비공개 `wood-land-data-db/eiass/`)
| 경로 | 내용 |
| --- | --- |
| `EIASS_초안사업지.gpkg` | QGIS 용. 레이어 `사업지구`(EPSG:5186) + 표 `편입필지` |
| `projects/{사업코드}.geojson` | 사업지구 1건 |
| `parcels/{사업코드}.csv` | 편입 필지 PNU·편입면적·비율 |
| `preview/{사업코드}.jpg` | 위성영상 위 경계(확인용) |
| `review/{사업코드}.json/.jpg` | 자동 검사를 통과 못 한 사업 |
| `state.json` | 처리 이력 |

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
