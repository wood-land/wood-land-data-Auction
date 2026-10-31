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

## 신문사 설정 진단과 검증 레지스트리 (2026-10)
신문사마다 HTML 이 달라서 "기사 날짜가 어디 있는가"를 사람이 129곳 모두 확인하기는 어렵다. 그래서 기사를 실제로 열어 확인하는 도구를 쓴다.

```
python diagnose_dates.py 경남일보                 # 신문사 이름 (여러 개 가능)
python diagnose_dates.py --region 경남            # 지역 안의 requests 방식 신문사 전체
python diagnose_dates.py --all --samples 8 --json 결과.json
python diagnose_dates.py --all --emit-registry common/verified_selectors.py   # 검증된 제안을 레지스트리에 합침
```
- 기사 5~8개를 열어 **정답 날짜(메타 태그/JSON-LD > `입력/등록/승인` 라벨)** 와 현재 설정을 대조하고, 날짜가 든 요소를 모두 찾아
  후보 선택자를 모든 기사에서 검증해 제안한다. 판정: OK / RESCUED(선택자는 틀리지만 메타가 구해 줌) / FIX / UNVERIFIED(정답 없음).
- 검색 목록의 날짜 칸(`list_date_sel`)과 **검색 결과가 최신순인지**도 판정한다.
- 결과는 `common/verified_selectors.py` 에 모인다. `Site(name=...)` 가 만들어질 때 같은 이름이 있으면 그 값이 신문사 정의를 덮어쓴다
  (`article_date_sel`, `list_date_sel`, `newest_first`). 지역 파일의 정의를 고치지 않아도 되고, 확인한 근거가 한 곳에 남는다.
- **신문사를 추가하거나 사이트가 개편되면 이 도구부터 돌린다.** 선택자를 `td, span, div` 처럼 넓게 잡으면 머리말의 현재 시각이
  기사 날짜로 읽혀 옛 기사가 최근 기사로 수집된다(2026-10 점검에서 저장된 기사의 약 98%가 이 문제였다).

수집 동작
- 날짜 요소의 텍스트가 300자를 넘으면(페이지 전체를 감싼 요소) 날짜 위치로 믿지 않는다.
- `newest_first=False`(검색 결과가 최신순이 아닌 신문사): "오래된 기사 N건 연속이면 키워드 종료" 규칙을 쓰지 않고, 최근 기사가 없는
  페이지가 3쪽 연속이면 종료한다. 페이지 상한은 목록 날짜를 읽을 수 있으면 8쪽, 못 읽으면 5쪽(기사를 열어야 해서 비용이 큼).
- `--time-budget-min N`: N분이 지나면 수집을 멈추고 지금까지의 결과로 정제·PNU 단계를 진행한다(GitHub Actions 는 170분).
  작업 제한시간에 걸려 취소되면 PNU 단계가 못 돌아 그날 결과가 통째로 사라지기 때문이다.
- 같은 기사를 다시 저장해도 `articles.id` 와 `created_at`(최초 수집 시각)은 유지된다. 예전에는 매번 새 행이 되어 신규 건수를 셀 수 없었다.

## 수집 기간 · 기준 날짜 정책 (2026-10-31 확정)
- **실제 실행: 최근 20일** (`run_crawl.py --days` 기본값, `news.yml` 기본값 20). 예약 실행은 지역당 7일에 한 번이라 20일이면 13일이 겹쳐,
  한 번 놓치거나 시간 예산으로 중단된 기사도 다음 회차에 다시 잡힌다. 같은 기사를 다시 저장해도 `created_at` 은 유지된다.
- **시험 테스트: 최근 1년** (`--days 365`). 지방신문은 보상 관련 기사가 자주 나오지 않아 20일로는 0건이 흔하므로, 파이프라인이 실제로
  기사를 찾아 저장하는지는 1년치로 확인한다.
- **신문게시일 표현은 신문사마다 다르다.** 입력 / 기사입력 / 승인(일) / 등록(일) / 작성(일) / 송고 / 발행일은 *입력일*, 수정(일) / 최종수정 /
  최종편집 / 업데이트는 *수정일* 로 읽는다. (`게재일`은 지면에 실린 날짜라 쓰지 않는다)
- **기준 날짜 정책 `Site.date_basis`**: `"modified_first"`(기본) = 수정일이 있으면 수정일, 없으면 입력일 (예: 경남일보) /
  `"input"` = 입력일만, 입력일을 못 읽었을 때만 수정일 (예: 대구신문). 신문사별 설정은 `common/verified_selectors.py`.
- 사이트 인코딩에 주의: 음성타임즈(estimes.co.kr)는 EUC-KR 이라 검색어를 UTF-8 로 보내면 키워드와 무관하게 `전체 0건`이 되고
  홈 화면 기사만 돌아온다. `Site.encoding="euc-kr"` 로 지정한다. 새 신문사를 추가할 때는 엉터리 검색어와 실제 검색어의 결과가 다른지부터 확인한다.

## 신문사별 검색 구조 (2026-10 점검 결과)
`health_check.py` 로 신문사 126곳을 점검한 결과, 같은 목록만 반복해서 읽던 곳이 많았다. 원인은 사이트마다 달랐고, 결과 기사 본문에
검색어가 실제로 들어 있는지까지 확인해 판정했다. 신문사별 확정 설정은 `common/verified_selectors.py` 에 모여 있다.

| 증상 | 원인 | 해결 수단 |
|---|---|---|
| 키워드를 바꿔도 같은 결과 / 홈 화면 기사만 | 검색어 인코딩 불일치 (EUC-KR 사이트에 UTF-8) | `Site.encoding` / `Site.search_encoding` (음성타임즈, 금산신문) |
| 같은 결과 / 2쪽이 1쪽과 같음 | GET 으로 보내야 할 것을 POST, 또는 반대 | `Site.search_method`, `search_form_data` (홍성신문 등 6곳) |
| 2쪽이 1쪽과 같음 | 페이지 이동이 `page=` 가 아니라 base64 `board_data` | `Site.search_builder` -> `common/search_builders.py` (익산신문 계열 7곳, 칠곡신문) |
| 서버 HTML 에 결과가 없음 (자바스크립트가 그림) | 검색 결과를 JSON API 로 받음 | `Site.search_adapter` -> `common/search_adapters.py` (경남신문, 전북일보) |
| 결과 항목에 홈 위젯 기사가 섞임 | 목록 선택자가 너무 넓음 | `list_item_sel` / `list_title_sel` 을 결과 영역으로 좁힘 |
| 제목에 요약·날짜가 섞임 | 카드 전체가 하나의 링크 | `Site.list_title_text_sel` (칠곡신문, 무등일보) |
| 같은 목록만 반복 | 사이트 도메인이 바뀜 | `homepage_url` / `search_url` 교체 (계룡일보 gyeryongilbo.com -> krdaily.co.kr) |

새 신문사를 붙이거나 개편을 점검할 때는 다음 순서로 확인한다.
1. `python health_check.py 신문이름` : 검색 결과가 나오는지, **엉터리 검색어와 결과가 다른지**, 기사 본문·날짜를 읽는지.
2. `python diagnose_dates.py 신문이름` : 기사 날짜 선택자 검증과 제안.
3. 서버 HTML 에 결과가 없으면 브라우저 개발자 도구의 네트워크 탭에서 검색 때 나가는 요청(fetch/XHR)을 찾아 어댑터로 만든다.
   페이지에 심어진 **다른 서비스의 API 접근 토큰**(예: 영남일보가 연합뉴스 Open API 에 쓰는 토큰)을 꺼내 쓰는 방식은 코드에 넣지 않는다.

제외한 신문사: 강릉뉴스, 성남도시신문, 포항시민신문, 거창인터넷뉴스, 음성신문(음성타임즈로 교체), 영남일보(검색이 연합뉴스 API 토큰 방식이라
키워드마다 첫 화면만 읽혀서. 기사 날짜 선택자는 정확하므로 나중에 다시 켤 수 있다).
