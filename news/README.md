# 지역신문 크롤러 복제본

Notion `72. 지역신문 데이터 추출 코드`의 공통 엔진 + 지역별 Site 설정 구조를 적용한 독립 복제본입니다. 원본 폴더와 원본 스크립트는 수정하지 않았습니다.

- `common/crawler_core.py`: 공통 크롤링·날짜 파싱 엔진
- `common/pnu_resolver.py`: 불완전 주소 완성, Kakao/VWorld 19자리 PNU 발급, SQLite 영구 저장 및 캐시
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
