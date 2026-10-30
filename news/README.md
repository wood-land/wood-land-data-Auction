# 지역신문 크롤러 복제본

Notion `72. 지역신문 데이터 추출 코드`의 공통 엔진 + 지역별 Site 설정 구조를 적용한 독립 복제본입니다. 원본 폴더와 원본 스크립트는 수정하지 않았습니다.

- `common/crawler_core.py`: 공통 크롤링·날짜 파싱 엔진
- `common/pnu_resolver.py`: 불완전 주소 완성, Kakao/VWorld 19자리 PNU 발급, SQLite 영구 저장 및 캐시
- `common/admin_names.py`: 시·도·시군구·읍면 이름 사전과 판별 도구 (주소 추출과 주소 완성이 같은 기준을 쓴다)
- `pnu_pipeline.py`: 기사 CSV/엑셀 주소 완성 → PNU 생성 → SQLite(`output/news_articles_pnu.db`) 저장 도구
- `crawler_core.py`: 실행기 호환용 연결 모듈
- `run_crawl.py`: 지역/신문사 실행과 `--check`, `--pnu` 원스톱 연동
- `regions/12_1_...`부터 `regions/12_8_...`: 원본과 같은 지역 구분 번호를 붙인 설정 파일
- `regions/SITE_DIRECTORY.md`: 이식 대기 신문사를 포함한 지역별 홈페이지 주소 색인
- `regions/GYEONGGI_MUNICIPALITY_DIRECTORY.md`: 경기 31개 시·군별 대표 지역신문 홈페이지 조사표
- `legacy_reference/12_1 ...`: 레거시 스크립트와 지역 README 복사본
- `output/`: 결과 저장

실행 예시:
- 점검 모드: `python run_crawl.py 강원 --check`, `python run_crawl.py 전라 --check`, `python run_crawl.py --all --check`
- 수집 및 PNU 자동 발급: `python run_crawl.py 강원 --pnu`
- 단독 PNU 파이프라인: `python pnu_pipeline.py --input output/강원_2026-09-26.csv`
- 단일 주소 테스트: `python pnu_pipeline.py --test "지정면 신평리 400" --hint "원주시"`

현재 강원권 10곳(6곳 활성), 경기·인천권 34곳(26곳 활성), 전라·광주권 29곳(16곳 활성), 충청·대전·세종권 31곳(18곳 활성), 경북·대구·울산권 29곳(13곳 활성)이 설정되어 총 133개 등록 매체 중 **79곳이 실측 활성화**되었습니다. 나머지는 검색 필터·접속·추출 검증이 끝날 때까지 비활성입니다. 검색 폼이 POST인 사이트는 Site 설정의 `search_method`와 `search_form_data`로 제출합니다.

## 정확도 보호장치 (2026-10 정비)
주소와 날짜는 "맞는 것만 저장"을 기준으로 다룬다. 틀린 PNU 한 건이 못 찾은 열 건보다 해롭다.

- **주소 추출**: `따르면`(면), `사업지구`(구), `집중호우시`(시), `충주상가`(가) 같은 일반 낱말을 지명으로 오인하지 않는다.
  시/군/구는 실제 행정구역 이름 사전으로만 인정한다.
- **시군구 결정 우선순위**: 주소에 적힌 시군구 > 신문사 `default_area`·지역힌트 > 읍·면 사전 > 기사 본문에 많이 나온 시·군.
  `Site.default_area` 를 비워 두면 시·도조차 알 수 없어 그 신문사 주소는 조회되지 않으니, 신문사를 추가할 때 반드시 채운다.
- **조회 결과 검증**: API 가 돌려준 필지의 지번(본번·부번·산 여부)과 시군구가 요청과 같을 때만 채택한다.
  (VWorld 는 `용동 63` 을 `용동 산 63` 으로 "보정"해서 돌려준다 — 검증이 없으면 다른 필지의 PNU 가 저장된다.)
  시군구 없이 조회해 서로 다른 지역이 함께 나오면 모호한 것으로 보고 채택하지 않는다.
- **캐시**: 성공은 계속, NOT_FOUND 는 `NEWS_RESOLVER_VERSION` 이 같고 30일 이내일 때만 재사용한다. 일시 오류(ERROR)는 캐시하지 않는다.
- **`basis` 컬럼**(article_addresses): 시군구를 정한 근거. `explicit`(주소에 적힘) / `hint`(신문사·지역힌트) /
  `eupmyeon`(읍·면 사전) / `context`(본문 추정) / `province`(시·도 + 읍·면만으로 조회).
  정확도가 중요한 용도에서는 `eupmyeon`·`context`·`province` 를 거를 수 있다.
- **기사 날짜**: 선택자가 `td, span, div` 처럼 넓으면 사이트 머리말의 현재 시각을 기사 날짜로 읽어 2019년 기사도 "오늘 입력"으로
  수집되던 문제가 있었다. 이제 `입력/등록` 라벨이 있는 날짜 > 메타 태그/JSON-LD 발행일 > 라벨 없는 날짜 순으로 믿고,
  `--check` 가 선택자 날짜와 메타 날짜가 다르면 경고한다.

이미 DB 에 쌓인 실패 주소(NOT_FOUND/ERROR)를 현재 로직으로 다시 조회해 고치기:
```
python pnu_pipeline.py --repair-db <DB경로> --dry-run   # 먼저 결과만 확인
python pnu_pipeline.py --repair-db <DB경로>             # 실제 갱신 (--limit N 으로 일부만)
```
테스트: `python -m pytest tests` (API 호출 없이 가짜 응답으로 돈다)
