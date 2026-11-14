"""
[GitHub Actions 버전] 로컬 PC 용 공장근린상가 v2 코드를 Actions 에서 돌리도록 옮긴 파일.
사이트 주소/로그인/시트 ID 는 환경변수(Secrets)로 받고, 프롬프트는 환경변수로, 크롬은 headless 로 바꿨다.
수집/저장 로직은 로컬 버전과 동일하다. 환경변수: SITE_DOMAIN, SITE_LOGIN_ID, SITE_LOGIN_PW, TYPE_A_LABEL, TYPE_B_LABEL,
GOOGLE_SA_KEY_JSON, NPL_SHEET_ID(결과 저장 시트 겸 NPL 읽기 시트), MINB_AMT_END, AREA_PYEONG_END.
"""

"""
[2026-11-14 v2 - NPL 사이트 부실채권(NPL) 겹침 열 추가]
'..._공장근린상가 26 1004.py'를 복사해 아래만 바꿨다(수집 조건/저장 구조/기록은 전부 그대로).
  - "{탭}_등기부상세" 탭(공장매각완 양식) 맨 뒤에 'NPL 사이트_NPL' 열을 한 칸 추가했다.
    별도 스프레드시트(NPL_SHEET_ID)의 가장 최근 'NPL_YYYYMMDD' 탭(03_3 NPL 사이트 NPL 크롤링 결과)을
    읽어서, 사이트 물건의 사건번호(연도2자리+번호)가 같고 감정가/매각기일/소재지 중 하나라도 일치하면
    "NPL 겹침" 으로 적는다. 사건번호만 같고 확인이 안 되면 "NPL 후보(확인필요)".
    NPL 탭을 못 읽거나(없음/권한) 너무 오래됐으면(NPL_MAX_AGE_DAYS) 열은 비워 두고 사유만 로그에 남긴다.
  - 메인 'data' 탭(TEMPLATE_HEADERS, 211 가공 코드가 읽는 열)은 건드리지 않았다.

[2026-10-04 추가, 공장/근린상가 전용 파생본]
'01. 사이트  경공매  추출_구글시트 0918 v36.py'(진행물건 전용)를 복사해서 아래와 같이 바꿨다.
사용자 요청: "공장"/"근린상가"만 추출하고 싶다, 과거 기간 말고 현재 진행 중인(앞으로 60일)
물건만, 건물면적 200평 이하만, 최저가격 3억~10억만, 구글시트 '경공매물건'에 탭을
'오늘날짜_공장'/'오늘날짜_근린상가'로 분리 저장.

  1. CTGR_OPTIONS_CA를 [('201210','공장'), ('201130','근린상가')]로 교체했다. 두 값 모두
     사이트 select#ctgr를 실제로 떠서(requests+BeautifulSoup) 확인한 값이다(공장=201210은
     기존과 동일, 근린상가=201130은 이번에 새로 확인).
  2. DAYS_AHEAD=60은 원본 그대로라 수정 없음(이미 "오늘~60일 뒤", 요청과 정확히 일치).
     #stat="11"(진행물건) 필터도 원본 그대로.
  3. 최저가격: DEFAULT_MINB_AMT_END를 5억->10억으로, 새 상수 DEFAULT_MINB_AMT_BGN(3억,
     고정값·프롬프트 없음)을 추가해 apply_filters()의 #minbAmtBgn 하한을 "0"(하한없음)
     대신 이 값으로 설정 -> 결과적으로 "최저가격 3억~10억" 범위 필터가 된다. 상한은 기존
     prompt_minb_amt_end()로 그대로 입력받는다(기본값만 10억으로 바뀜).
  4. 건물면적: 사이트 검색 폼에는 면적 필터가 없어 목록 추출 후 걸러낸다. extract_row()에
     "건물 N㎡" 패턴을 별도로 다시 찾아 평으로 환산한 값(건물면적_평)을 반환 리스트
     "맨 뒤에 추가"했다(기존 19개 필드 순서/인덱스는 전혀 안 건드림 - main()의 data[13]/
     data[14] 같은 위치 참조가 전부 그대로 유효함). TEMPLATE_HEADERS/CURRENCY_COLUMNS도
     맨 뒤에 '건물면적(평)' 한 칸만 추가했다. 새 prompt_area_pyeong_end()로 평 단위 상한을
     입력받고(기본 200평), main()에서 건물면적_평이 없거나 상한을 넘으면 그 행을 건너뛴다.
  5. 저장 구조를 통째로 바꿨다: 원본은 "그 주" 탭 하나에 경매+공매를 몰아 썼지만, 이
     파생본은 CTGR_OPTIONS_CA를 순회하며 물건종류마다 별도의 구글시트 탭
     ("{오늘날짜}_공장", "{오늘날짜}_근린상가")과 별도의 로컬 xlsx
     ("{오늘날짜}_공장.xlsx" 등)에 각각 수집·동기화한다. 그래서 주차(WEEK) 탭 개념/
     지난주 대비 매각완료 추정/오래된 주차 탭 자동정리는 이 파생본에는 해당하지 않아
     main()에서 들어냈다(원본 파일에는 그대로 있음). GOOGLE_SHEET_ID는 원본과 동일한
     '경공매물건' 스프레드시트를 그대로 가리킨다.
  6. 1회성 파생본이 아니라 계속 쓸 수 있도록 로그인/드라이버/상세페이지(지분·등기요약)
     로직은 원본과 100% 동일하게 재사용했다 - main()만 다시 짰고 다른 함수는 안 건드렸다
     (extract_row()의 면적 추출 추가 부분 제외).

[2026-10-04 2차 수정 - 등기부상세/유찰횟수 필터/공매 추가]
사용자가 코드리뷰 중 공장매각완.py의 등기부 근저당권/청구금액 처리 블록을 가리키며
"공장/상가는 이 과정이 필요하다"고 요청, + 유찰횟수 1~2회만, + 공매(PA)도 체크박스로
"근린생활시설"/"산업용및기타특수용건물" 선택해서 수집해달라고 추가 요청했다.
  7. 공장매각완.py의 _td_clean_text/_pair_th_td_texts/_extract_amount/
     extract_base_info_from_detail/extract_bid_history_from_detail/format_bid_history/
     extract_registry_liens_from_detail/dedup_registry_liens/merge_registry_liens_by_owner/
     dedup_registry_claims/sum_yudonghwa_claims/format_registry_liens/format_registry_claims/
     fetch_registry_history_info/save_registry_detail_rows_to_gsheet를 그대로 포팅했다.
     원본의 배당기일 추정/채권원금/연체이자/채권행사권리금액은 "이미 매각 확정된 물건"
     (마지막 입찰회차=낙찰일) 전제라 진행 중인 물건에는 안 맞아 뺐다 - 사용자가 명시적으로
     요청한 근저당권 중복제거·합산(근저당권_합계금액)/청구금액 중복제거·유동화전문합산
     (유동화전문_청구금액)만 가져왔다. 결과는 물건종류마다 "{오늘날짜}_{물건종류}_등기부상세"
     탭에 저장(기존 내용 지우고 새로 씀, REGISTRY_CURRENCY_COLUMNS로 금액 서식 적용 -
     _apply_gsheet_formatting()에 currency_cols 인자를 추가해 메인 시트와 별도로 처리).
     지분/필지 여부와 무관하게 통과한 모든 물건에 대해 수집하며, fetch_detail_info()와는
     별개로 상세페이지를 한 번 더 방문한다(공장매각완.py 원본과 동일한 방식 - 두 함수를
     하나로 합치면 더 효율적이지만, 검증된 원본 로직을 그대로 쓰는 쪽을 택함).
  8. 유찰횟수 1~2회만 수집하도록 main()에 필터를 추가했다. extract_row()/extract_row_pa()가
     유찰횟수를 따로 반환하지 않아서, 이미 반환되는 진행상태 텍스트(data[6])에서 같은
     정규식("유찰\\s*(\\d+)\\s*회")으로 다시 뽑아 비교한다(신건=0회는 자동으로 제외됨).
  9. 공매(PA) 수집을 추가했다. 처음엔 "근린상가에 정확히 대응하는 분류가 없다"는 이유로
     PA를 뺐었는데, 사용자가 라이브 화면에서 체크박스 HTML을 직접 캡처해 알려줬다 -
     근린상가는 리프 체크박스 chkEaCtgr_100010020001(근린생활시설), 공장은 그룹 체크박스
     chkGrpCtgr_10400(산업용및기타특수용건물 - 그룹 클릭 시 하위 15개 항목이 함께
     체크되는 것으로 보임). select#ctgr(단일값, PA_CTGR_MAP의 '10400'/'100010020001')와
     체크박스 중 실제 검색에 반영되는 쪽이 라이브 테스트 전까지 확실치 않아
     apply_filters_pa()에서 둘 다 설정한다. main()의 각 물건종류 루프 안에서 경매 수집이
     끝난 뒤 바로 이어서 공매(PA_PRPTDVSN_VALUES 9개 자산구분 순회)를 수집해 같은
     탭/로컬파일에 합쳐 저장한다(원본 v36.py가 한 주차 탭에 경매+공매를 섞어 저장하던
     방식과 동일). 다만 공매 상세페이지는 구조가 달라 등기부상세(7번) 추출 대상에서는
     제외했다(공장매각완.py 원본의 동일한 제한을 그대로 따름). extract_row_pa()에도
     extract_row()와 동일하게 건물면적_평을 맨 뒤에 추가했다.
"""

"""
사이트((사이트 도메인)) 경매/공매 물건 목록 추출 - 로컬 실행용, '진행물건' 전용 (v37, 2026-09-18)

[이 버전이 만들어진 이유]
사용자가 깃허브 Actions에서 예약 실행 중인 스크립트(환경변수/Secrets로 사이트 주소/로그인/
구글시트 설정을 읽는 "공개 저장소용" 버전)에 v28~v29로 다음 최적화가 추가되었다:
  - (경매) '지분입찰 물건' 필터로 지분 Tid를 먼저 목록만으로 수집(collect_share_tids) ->
    지분 Tid이거나 주소에 "외 N필지"가 있는 물건만 상세페이지를 방문(is_multi_parcel).
    그 외 물건은 상세페이지 방문 없이 목록 정보만으로 바로 기록 -> 속도 대폭 개선.
  - (공매) 상세페이지의 필지별 표(지분/분의 표시)로 지분여부를 먼저 판단해서, 지분 물건일
    때만 상세페이지에서 등기 PDF까지 마저 처리.
  - 구글 시트를 매번 전체 clear+다시쓰기 대신, 중간 저장 때는 새로 늘어난 행만
    append_rows()로 증분 동기화(append_new_rows_to_gsheet) - API 호출/시간 절약. 실행
    종료 시에는 기존처럼 sync_to_google_sheet()로 전체를 한 번 더 맞춰준다.
  - 지난주 탭과 이번 주 스캔된 사건번호를 비교해서, 지난주엔 있었는데 이번 주엔 안 보이는
    (매각완료로 추정되는) 물건 수를 실행이 끝날 때 안내.
  - GOOGLE_SHEET_WEEK_RETENTION(오래된 주차 탭 자동 정리)이 상수로 명확히 분리됨.

이 v30 로컬 버전은 위 최적화 로직을 전부 그대로 가져오되(크롤링 동작은 깃허브 버전과
동일), 설정 부분만 이전 로컬 버전(v27, 2026-08-16~23)을 참조해서 되돌렸다:
  - SITE_DOMAIN/TYPE_A_LABEL/TYPE_B_LABEL/LOGIN_ID/LOGIN_PW/GOOGLE_SHEET_ID/
    GOOGLE_SHEET_SHARE_EMAIL: 환경변수 대신 실제 값을 코드에 직접 기록(로컬 개인 PC에서만
    쓰는 파일이라 공개 저장소처럼 값을 감출 필요가 없음).
  - GOOGLE_CREDENTIALS_PATH_CANDIDATES: 집 PC/노트북 PC/사무실 PC 세 군데 후보 경로 목록
    (v27에서 추가된 멀티 PC 대응 그대로 유지).
  - SAVE_DIR="D:/", 파일명/구글시트 탭 이름 접미사 "_경공매물건"(v27 형식 유지, 깃허브
    버전은 공개 저장소라 "_data"라는 범용 이름을 씀).
  - get_driver()/find_chrome_binary(): headless가 아니라 실제 크롬 창이 보이는 채로 실행
    (깃허브 버전은 화면 없는 리눅스 러너라 반드시 headless였음). 창을 닫아도 바로 안
    죽도록 detach 옵션도 유지.
  - prompt_collect_mode()/prompt_minb_amt_end()(v32에서 최저가격 기준으로 개명): 환경변수
    대신 터미널에서 직접 입력받는 대화형 프롬프트로 되돌림(반환값 자체는
    "type_a"/"type_b"/"both"로 깃허브 버전의 main() 분기와 동일하게 맞춤).
  - AUTOSAVE_EVERY_N_ITEMS=50, GOOGLE_SHEET_WEEK_RETENTION=3 등 값 자체는 깃허브 버전과
    동일하게 맞춰서 두 버전이 항상 같은 방식으로 동작하도록 함.

[v31, 2026-09-07 - 깃허브 Actions 버전에 추가된 안전장치 반영]
사용자가 깃허브 Actions 버전에 2026-09-05~07 사이 다음 안전장치가 추가된 최신 코드를
붙여넣고 "보완된 내용을 로컬 코드에도 접목해서 완전하고 안전한 코드로 만들어달라"고
요청했다. 아래 항목들을 그대로 가져왔다(가져온 이유: 실제로 발생한 사고를 계기로 만든
데이터 보호 장치라 로컬에서도 동일하게 필요함):
  - `ensure_header_row()`: 탭을 열거나 새로 만든 직후 헤더 행이 있는지 확인/보장한다.
    중간 자동저장이 "헤더가 이미 있다"고 가정하고 이어붙이기만 하기 때문에, 새로 만든
    빈 탭에서 실행이 중간에 조용히 실패하면 헤더 없이 데이터부터 시작하는 탭이 굳어버릴
    수 있었던 버그(2026-09-05, 깃허브 버전에서 실제 발견됨)를 막는다. 헤더가 없으면
    자동으로 1행에 삽입해서 복구까지 한다.
  - `sync_to_google_sheet()` 덮어쓰기 안전장치: 실행 마지막의 전체 동기화 직전에 원격
    탭의 실제 행 수를 먼저 확인해서, 원격에 이미 이번 실행이 쓰려는 것보다 "더 많은"
    데이터가 있으면 전체 덮어쓰기 자체를 건너뛴다(2026-08-28~29에 깃허브에서 실제로
    겪은, "나중에 끝난 실행이 시트 전체를 자기 것으로 덮어써서 먼저 쌓인 데이터가
    사라지는" 사고의 재발 방지). 저장 뒤에는 실제 저장된 행 수가 예상과 일치하는지도
    재확인한다(사후 검증). 반환값이 `bool`에서 `(성공여부, 저장전_행수, 저장후_행수)`
    튜플로 바뀌었다.
  - `maybe_autosave()` 사전 확인: 자동저장(증분 append) 직전에, 직전 자동저장이
    마지막으로 기록해둔 행에 지금도 데이터가 그대로 있는지 셀 1개만 가볍게 확인해서,
    혹시 다른 실행(다른 PC 등)이 그 사이 탭을 건드렸는지 한 배치 더 빨리 감지한다.
  - 실행 이력(감사 로그) `_run_log` 탭 신설: 매 실행이 끝날 때마다 실행 시각/수집
    범위/대상 탭/시작 전·후 원격 행수/신규·건너뛴 건수/검증 결과 한 줄을 누적 기록한다
    (`ensure_run_log_tab()`, `log_run_summary()`, `count_total_runs()`). 깃허브 버전은
    이 로그의 "트리거"(예약/수동) 열에 GitHub Actions의 실행 방식을 남기는데, 로컬은
    그 개념이 없으므로 대신 실행한 PC 이름(`_get_local_pc_name()`, 집/노트북/사무실 PC
    구분)을 남기도록 바꿨다 - 여러 PC를 오가며 쓰는 이 프로젝트 특성상 어느 실행이
    어느 PC에서 있었는지가 더 유용한 정보이기 때문이다.

가져오지 않은 것 - 의도적 제외: 깃허브 버전은 이번에 "예약(schedule) 실행"과 "수동
(workflow_dispatch) 실행"을 서로 다른 탭(`_week_tab_name()`을 토요일 기준으로 변경 +
`_manual_tab_name()` 신설)에 쓰도록 나눴다. 이건 같은 GitHub Actions 워크플로우를
크론과 사람이 동시에 건드릴 때 서로 덮어쓰지 않기 위한 조치다. 로컬 버전은 애초에
크론이 없고(항상 사람이 직접 실행) 탭 이름 자체가 이미 깃허브 버전과 다르므로(월요일
기준 + "_경공매물건" 접미사 vs 깃허브의 토요일 기준 + "_data" 접미사) 구조적으로 절대
같은 탭을 가리킬 수 없다 - 즉 이 문제가 로컬에는 애초에 발생하지 않는다. 여기에 "예약/
수동" 구분까지 들여오면 로컬의 기존 핵심 기능("다음날 이어서 하기" - 같은 주 안에서는
언제 실행해도 같은 주차 탭에 계속 누적됨)이 깨진다(깃허브의 수동 탭은 실행일 단위라
매일 새 탭이 생김). 그래서 이 부분만은 가져오지 않고 로컬의 기존 주차별 탭 방식을
그대로 유지했다.

[v32, 2026-09-07 - 감정가격 필터를 최저가격 필터로 교체]
사용자가 목록 검색 화면의 "최저가격" 범위 select 2개(select#minbAmtBgn ~
select#minbAmtEnd, 값/옵션 목록은 기존 AMOUNT_OPTIONS와 동일)의 HTML을 캡처해 제공하고,
기존에 감정가격(select#apslAmtEnd) 상한으로 필터링하던 것을 최저가격 기준으로 바꿔달라고
요청했다(기본값: 최저가격 5억 이하). `apply_filters()`/`apply_filters_pa()`에서
`#apslAmtEnd`를 설정하던 코드를 `#minbAmtBgn`(항상 "0"=하한 없음)과
`#minbAmtEnd`(사용자가 입력한 상한값) 두 필드 설정으로 교체했고, 그에 맞춰
`prompt_apsl_amt_end()` -> `prompt_minb_amt_end()`, `DEFAULT_APSL_AMT_END` ->
`DEFAULT_MINB_AMT_END`, `apsl_amt_end_value` -> `minb_amt_end_value`로 이름도 전부
바꿨다(변수명이 실제 의미와 다르면 나중에 헷갈리므로). 목록 행에서 감평가/최저가를
추출하는 `extract_row()`/`extract_row_pa()`의 `#apslAmt_*`/`#minbAmt_*` 셀렉터는 필터
조건과 무관한 "결과 표시 컬럼"이라 그대로 두었다. 공매(paList.php) 검색 화면에도 같은
`#minbAmtBgn`/`#minbAmtEnd` 필드 ID가 있을 것으로 가정하고 동일하게 적용했는데, 사용자가
공매 화면의 실제 HTML(`id="minbAmtBgn"`/`id="minbAmtEnd"`, 값/옵션 전부 경매 화면과 동일)을
캡처해 그 가정이 맞았음을 바로 확인해줬다(2026-09-07) - 코드 변경 없이 확인만 완료.

[v33, 2026-09-07 - 터미널에 신규 물건 카운터 표시]
사용자가 "터미널 창에서 물건이 추출될때.. 이 물건이 몇개 째인지 카운트 해서 터미널창에서
볼수 있도록 해줘"라고 요청했다. 경매/공매 각 수집 루프에서 신규 물건을 한 건씩 시트에
추가할 때마다 출력하던 `print(data)`/`print(row_data)`를
`print(f"[신규 {total_new_count}번째 물건] {data}")` 형태로 바꿔, 지금까지 이번 실행에서
몇 번째 신규 물건인지 터미널에서 바로 보이게 했다. 지분(필지 분할) 물건처럼 한 물건이 여러
행으로 나뉘는 경우엔 `print(f"[신규 {total_new_count}번째 물건 - 필지 {parcel_idx}/
{len(parcel_addrs)}] {row_data}")`로, 몇 번째 물건의 몇 번째 필지인지까지 함께 표시했다
(물건 번호는 필지마다 늘어나지 않고 같은 물건이면 고정 - 필지는 한 물건을 여러 줄로 쪼갠
것일 뿐 별개 물건이 아니므로). `total_new_count`는 기존에 이미 있던, 경매/공매 두 단계를
합쳐 실행 1회당 하나로 누적되는 카운터를 그대로 재사용한 것으로, 카운트 로직 자체는
새로 추가한 것이 없고 기존 값을 출력문에 노출시키기만 했다(그래서 회귀 위험이 낮음).

[v34, 2026-09-07 - '신규여부' 열에 신건 물건 표시]
사용자가 목록 검색 화면의 "진행상태" select(`select#stat`, `option[value="1110"]`
= 신건)의 HTML을 캡처해 제공하며, 크롤링 완료 후 신건 물건만 걸러 구글시트 M열
('신규여부')에 '신건'이라고 기록해달라고 요청했다. 확인해보니 이 select를 실제로
조작할 필요는 없었다 - `extract_row()`/`extract_row_pa()`가 이미 각 행의
`#statNm_{tid}`(진행상태 텍스트, 예: "신건", "유찰 2회")를 읽어서 "유찰 N회" 패턴이
없으면(=아직 한 번도 유찰되지 않은 신건) `유찰횟수 = 0`으로 계산해왔고, M열 값을
`유찰횟수 == 0`일 때와 아닐 때로 이미 나누고 있었다(예전 라벨은 "신규물건"/"기존물건").
즉 "유찰횟수 0" == 사이트가 말하는 "신건" 상태와 정확히 같은 조건이라, 필터 select를
직접 조작하는 로직을 새로 추가하는 대신 기존 조건은 그대로 두고 라벨 텍스트만
`"신규물건"` -> `"신건"`으로 바꿨다(`extract_row()`/`extract_row_pa()` 양쪽 모두,
2곳). 목록 조회 시 기본으로 선택되어 있는 진행상태 필터가 이미 "진행물건"(신건+유찰만
포함, 매각/종국 등 제외)이라 실제로 추출되는 상태 텍스트는 항상 "신건" 아니면
"유찰 N회"뿐이므로 이 라벨 교체만으로 요청한 동작과 동일하다. "기존물건" 라벨은
그대로 유지했다(사용자가 신건 표시만 요청했고, 이 값이 다른 코드에서 문자열로
비교되는 곳이 없음을 `grep`으로 확인해 안전하게 라벨만 바꿀 수 있었다).

[v35, 2026-09-07 - 구글시트 증분 저장 시 데이터가 AC열부터 밀려 들어가던 실제 사고 수정]
사용자가 "구글시트 탭에 저장된 결과이다"라며 구글시트에서 다운로드한 xlsx를 보내줬는데,
확인해보니 심각한 버그가 있었다: 헤더 행(1행)은 A~S열에 정상적으로 있는데("경매/공매",
"사건번호" 등) 그 아래 실제 물건 데이터는 전부 AC열(29번째 열)부터 시작하고 있었다
(A~AB열은 전부 빈 칸). 반면 사용자가 같은 시점에 올려준 로컬 D드라이브 xlsx 파일은
데이터가 A열부터 정상적으로 들어가 있어서, 문제는 "로컬 엑셀에 데이터를 쓰는 부분"이
아니라 "로컬 데이터를 구글시트로 올리는 부분"에 있다는 게 명확했다. 원인을 추적한 결과
`append_new_rows_to_gsheet()`(중간 자동저장, 50건마다 실행)가 호출하는 gspread의
`ws.append_rows(new_values, value_input_option="RAW")`가 원인이었다 - `table_range`를
지정하지 않으면 구글시트 API가 "새 데이터를 어느 표의 어디부터 이어붙일지"를 시트에
이미 있는 데이터를 보고 스스로 추측하는데, 헤더 행이 A~S열까지는 촘촘히 차 있다가
한참 떨어진 AC열(지분 물건 전용 "토지등기_요약" 칸)에 값이 하나 더 있는 "듬성듬성한"
모양이다 보니, API가 이걸 두 개의 표로 오인해서 새로 추가하는 행을 엉뚱하게 AC열부터
이어붙이는 사고로 이어진 것으로 보인다(반면 실행 맨 마지막의 전체 덮어쓰기
`sync_to_google_sheet()`는 `ws.update(values=..., range_name="A1")`처럼 시작 위치를
명시적으로 지정해서 쓰기 때문에 이 문제가 없다 - 그런데 이번 사고 사례에서는 실행이
중간에 중단되어 이 마지막 전체 덮어쓰기가 아예 실행되지 못했고, 그래서 밀린 채로
저장된 증분 데이터가 그대로 남아있었던 것으로 보인다). 고쳐야 할 부분은 명확했다:
`ws.append_rows(new_values, value_input_option="RAW", table_range="A1")`처럼 "표는
A1부터 시작한다"고 명시적으로 못박아서 구글시트가 표 위치를 추측하지 못하게 했다.
스모크 테스트에도 이 회귀를 바로 잡아낼 수 있도록 `append_rows` 호출에 항상
`table_range="A1"`이 실제로 전달되는지 확인하는 테스트를 새로 추가했다. **참고**: 이미
잘못 밀려서 저장된 기존 구글시트 탭(예: 이번에 문제가 된 `20260907_W37_경공매물건`
탭)은 이 코드 수정만으로 자동으로 고쳐지지 않는다 - 다음 실행 때 그 주차 탭을 삭제하고
새로 만들거나, 시트에서 밀린 데이터를 수동으로 A열로 옮겨야 한다.

[v36, 2026-09-18 - '진행물건' 전용/'매각전부' 전용 코드로 분리]
사용자가 "코드를 분리 하자. '매각 전부'를 추출하는 코드를 별도로 만들어라. 기존의
'진행 물건' 즉 깃에서 스케쥴로 추출하는 코드 = 로컬에서도 '진행물건' 추출 가능한
코드 1개, '매각 전부'만 추출하는 코드 1개로 분리하자"라고 요청했다. 목록 검색 화면의
"진행상태" select(`select#stat`)를 보면 value="11"이 "진행물건"(신건+유찰, 지금까지
이 파일이 계속 수집해온 범위이자 깃허브 Actions 예약 스케줄이 수집하는 범위와 동일),
value="12"가 "매각전부"(매각/매각허가등 + 잔금납부물건 + 배당기일/종결까지 포함하는
상위 분류)다. 지금까지는 이 select를 건드리지 않고 사이트 기본 선택값(진행물건)에만
의존했는데, 이제 두 범위를 서로 다른 파일로 명확히 분리하면서 이 파일(진행물건 전용)은
`apply_filters()`/`apply_filters_pa()`에 `set_field_value(driver, "#stat", "11", ...)`를
명시적으로 추가했다 - 동작 자체는 기존과 동일하지만(사이트 기본값이 이미 "11"이므로),
사이트가 나중에 기본 선택값을 바꾸더라도 이 파일이 계속 "진행물건"만 수집한다고
보장하기 위함이다. 이 파일은 그 외에는 기존 v35와 완전히 동일하다(구글시트 연동,
M열 '신건'/'기존물건' 표시, 최저가격 필터, 안전장치 전부 그대로). '매각전부' 전용
버전은 별도 파일(`사이트_주소추출_0918_v36_매각전부.py`)로 분리했다 - 자세한 차이는
그 파일 docstring 참고. **참고(가정)**: 경매(CA) 목록 화면에서 확인된 `#stat` select
ID를 공매(PA) 페이지에도 동일하게 적용했다 - 이전에 최저가격 필드(#minbAmtBgn/
#minbAmtEnd)가 두 화면에서 실제로 동일한 ID였던 전례를 근거로 한 가정이며, 아직 PA
화면의 실제 "진행상태" select HTML로 직접 확인받지는 않았다. `set_field_value()`는
셀렉터가 없으면 오류 없이 "설정 실패" 로그만 남기고 계속 진행하므로, 가정이 틀려도
크롤링 자체가 멈추지는 않지만 그 경우 공매 쪽 진행상태 필터가 적용되지 않을 수 있다.

[v37, 2026-09-18 - 물건종류(토지/공장) 선택 옵션 추가]
사용자가 "진행물건에서 '토지'만 기본으로 추출하는건가? '공장'도 추출하고 싶다. 옵션으로
넣어라"라고 요청했다. 지금까지 이 파일은 `CTGR_VALUE = '30'`(select#ctgr, "토지" 대분류
전체)로 고정되어 있었다. 사용자가 실제로 캡처해준 경매(caList.php) 화면의 select#ctgr
전체 HTML로 확인한 결과, `value="30"`은 "토지" 대분류(전/답/과수원/임야/대지 등 모든
토지 하위 지목을 묶은 그룹 값)였고, "공장"은 "상업 및 산업용" 대분류(20) 아래 있는
개별 지목 `value="201210"`이었다(참고로 그 화면에는 "지식산업센터"(201216), "창고시설"
(201211) 등 다른 산업용 지목도 있었지만, 이번엔 "공장"만 요청받아 그 값만 추가했다 -
나중에 다른 지목이 필요하면 `CTGR_OPTIONS_CA`에 한 줄만 추가하면 된다).

`CTGR_OPTIONS_CA = [('30', '토지'), ('201210', '공장')]`을 추가하고, 프로그램 시작 시
(수집 범위 선택 바로 다음, 단 경매를 수집하는 경우에만) `prompt_ctgr_mode_ca()`가
"1. 토지만(기본) / 2. 공장만 / 3. 토지+공장 모두" 중 하나를 선택받는다. select#ctgr는
한 번에 하나의 값만 선택 가능한 단일 select라 "모두"를 고르면 공매의 자산구분 9개
카테고리 순회(PA_PRPTDVSN_VALUES)와 정확히 같은 방식으로, 경매 목록을 물건종류마다
처음부터 다시 순회한다(물건종류 하나를 예외 없이 끝까지 순회해야 그 물건종류가
"완료"로 집계되도록 `ca_all_categories_ok` 안전장치도 공매 쪽 `pa_all_categories_ok`와
동일하게 추가했다 - 한 물건종류에서 오류가 나도 나머지 물건종류/공매 수집은 계속
진행되고, 전체가 예외 없이 끝났을 때만 매각완료 비교(`ca_scan_complete`)가 동작한다).
`apply_filters()`/`collect_share_tids()`는 이제 `ctgr_value` 인자를 받아 호출 시점에
어떤 물건종류로 검색할지 결정한다(인자를 생략하면 기존처럼 `CTGR_VALUE`를 써서 이전
버전 호출부와도 호환됨). **참고**: 이 옵션은 경매(CA) 화면에만 적용된다 - 공매
(paList.php)는 코드체계가 완전히 다르고(`PA_CTGR_VALUE = '10100'`은 PA 자체 코드로
"토지" 그룹) 공매 쪽 "공장" 값은 아직 확인받지 못해, 공매는 지금처럼 토지 고정으로
수집된다(필요하면 공매 물건종류 select HTML을 받아 추가할 수 있음). 최종 파일:
`사이트_주소추출_0918_v37_진행물건_공장옵션.py`. mock 기반 스모크 테스트로
`CTGR_OPTIONS_CA` 값, `prompt_ctgr_mode_ca()`의 입력별 반환값(빈 입력/1/2/3/잘못된
입력), `apply_filters`/`collect_share_tids`가 `ctgr_value`를 올바르게 전달하는지,
`main()`이 물건종류를 순회하는 구조로 바뀌었는지까지 전부 확인했다. 실제 사이트에서
"공장"으로 검색했을 때 결과가 올바르게 나오는지는 사용자의 다음 실행이 첫 라이브
확인이 된다.

실행 방법: 이 파일이 있는 폴더에서
`python 사이트_주소추출_0918_v37_진행물건_공장옵션.py`
(사전에 `pip install selenium openpyxl requests beautifulsoup4 pdfplumber gspread
google-auth` 필요, 구글 크롬이 설치되어 있어야 함).
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException, StaleElementReferenceException,
    UnexpectedAlertPresentException
)

from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter
from datetime import datetime, timedelta, date
import sys
import os
import time
import re
import random
import io
import base64
import copy  # (2026-10-04 추가) 등기부현황 표 파싱(_td_clean_text)에서 BeautifulSoup 태그 복제용
from urllib.parse import parse_qs, unquote

import requests
from bs4 import BeautifulSoup

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import gspread
    from google.oauth2.service_account import Credentials as GoogleCredentials
except ImportError:
    gspread = None
    GoogleCredentials = None

# ========================= 로컬용 설정 (여기만 바꾸면 됨) =========================
# 이 파일은 깃허브 Actions에서 돌아가는 버전(환경변수/Secrets로 읽는 버전)과 크롤링 로직은
# 100% 동일하고, 대신 로컬 PC에서 바로 python으로 실행할 수 있도록 사이트 주소/로그인/구글
# 시트 설정을 환경변수가 아니라 이전 버전(v27)처럼 이 파일에 직접 값으로 적어둔 버전이다.
# (2026-08-23: 깃허브 버전에 새로 추가된 최적화 - 지분 물건 사전조회로 상세페이지 방문
#  최소화(경매)/목록의 필지별 표로 지분여부를 먼저 판단(공매), 주차 탭 증분 동기화,
#  지난주 대비 매각완료 추정 안내 - 를 로컬 버전에도 그대로 반영해달라는 요청으로 작성)
SITE_DOMAIN = os.environ.get("SITE_DOMAIN", "")
SITE_BASE = f"https://{SITE_DOMAIN}"
TYPE_A_LABEL = os.environ.get("TYPE_A_LABEL", "경매")
TYPE_B_LABEL = os.environ.get("TYPE_B_LABEL", "공매")
TYPE_HEADER_LABEL = f"{TYPE_A_LABEL}/{TYPE_B_LABEL}"

# 상세페이지(caView.php)는 로그인하지 않으면 "로그인 후 이용하세요" 알림창만 뜨고 내용이
# 안 나온다(라이브 테스트로 확인됨). 아래 계정으로 프로그램 시작 시 자동 로그인한다.
# (다른 계정을 쓰려면 이 두 값만 바꾸면 됨. 로그인 자체를 끄려면 FETCH_DETAIL_DOCS를 False로.)
LOGIN_ID = os.environ.get("SITE_LOGIN_ID", "")
LOGIN_PW = os.environ.get("SITE_LOGIN_PW", "")

GOOGLE_SHEET_ID = os.environ.get("NPL_SHEET_ID", "")   # 결과 탭을 저장하는 시트 = NPL 목록이 있는 시트
GOOGLE_SHEET_SHARE_EMAIL = os.environ.get("SHARE_EMAIL", "")


# ========================= 사용자 설정 =========================
DAYS_AHEAD = 60                 # 매각기일: 오늘부터 며칠 뒤까지 검색할지
CTGR_VALUE = '30'               # 물건종류: select#ctgr 옵션 값. '30'=토지 그룹 전체. (기본값, 아래 CTGR_OPTIONS_CA 참고)

# (2026-09-18 추가) 경매(caList.php) 물건종류 select#ctgr 옵션 중, 프로그램 시작 시
# 선택할 수 있게 만든 항목들. 사용자가 실제로 캡처해준 select#ctgr 전체 HTML로 값을
# 확인함: '30'은 "토지" 대분류(전/답/과수원/임야/대지 등 모든 토지 하위 지목을 포함하는
# 그룹 값), '201210'은 "상업 및 산업용" 대분류(20) 아래 있는 "공장" 개별 지목 값이다.
# prompt_ctgr_mode_ca()가 이 목록에서 1개 이상을 선택받고, main()은 선택된 값마다
# apply_filters()/collect_share_tids()를 다시 호출해 목록을 처음부터 순회한다(공매의
# PA_PRPTDVSN_VALUES 자산구분 순회와 같은 방식). 새 물건종류를 추가하고 싶으면 여기에
# (값, 라벨) 한 줄만 추가하면 된다.
CTGR_OPTIONS_CA = [
    ('201210', '공장'),
    ('201130', '근린상가'),  # (2026-10-04) 사이트 select#ctgr 라이브 확인값
]

# (2026-10-04 추가) 공매(paList.php) 쪽 물건종류 매핑. 경매와 분류 체계가 완전히 달라
# "근린상가"에 정확히 대응하는 값이 없다 - 사용자가 직접 라이브 화면에서 확인해준 값:
#   근린상가 -> "근린생활시설"(리프, value=100010020001, 체크박스 id=chkEaCtgr_100010020001)
#   공장     -> "산업용및기타특수용건물"(그룹, select 값=10400, 체크박스 id=chkGrpCtgr_10400 -
#               그룹 체크박스라 공장시설/창고시설/위험물저장 등 하위 15개 항목이 함께 잡힘)
# select#ctgr(단일값)와 체크박스(chkGrpCtgr_*/chkEaCtgr_*) 중 실제 검색에 반영되는 쪽이
# 라이브 테스트 전까지 확실치 않아 apply_filters_pa()에서 둘 다 설정한다.
PA_CTGR_MAP = {
    '공장': ('10400', '#chkGrpCtgr_10400'),
    '근린상가': ('100010020001', '#chkEaCtgr_100010020001'),
}

SAVE_DIR = "/tmp/"                # 저장 폴더
MAX_PAGES = 500                 # 무한루프 방지용 최대 페이지 수
LIST_PAGE_SIZE = "100"          # 목록 페이지 "N개씩 보기"(select#dataSize) 설정값

TEMPLATE_HEADERS = [
    TYPE_HEADER_LABEL, '사건번호', '주소', '참고사항', '용도', '면적', '진행상태',
    '최저가율', '최저가', '감평가', '입찰일', '상세페이지', '신규여부',
    '지분 여부', '필지별 주소', 'pnu', '토지이용계획', '소유자', '키워드',
    '건물면적(평)',  # (2026-10-04 추가) 맨 뒤에만 추가 - 기존 필드 인덱스 전부 그대로 유지
]

FETCH_DETAIL_DOCS = True        # 상세페이지(필지별 주소/참고사항/등기요약)까지 받아올지 여부
# 테스트용: 이 값(>0)이면 물건종류마다 경매 신규 N건만 수집하고 끝낸다(공매 생략, 이전 탭 정리 안 함).
TEST_MAX_NEW_ITEMS = int((os.environ.get("TEST_MAX_NEW_ITEMS") or "0").strip() or 0)
DETAIL_PAGE_DELAY = (2.0, 4.0)  # 상세페이지 요청 사이 랜덤 대기시간(초) 범위 - 서버 부하 방지
PDF_DOWNLOAD_DELAY = (1.0, 2.5) # 토지등기 PDF 다운로드 사이 랜덤 대기시간(초) 범위 (지분 물건만 해당)
PAGE_CLICK_DELAY = (1.5, 3.0)   # 목록 페이지 넘길 때 랜덤 대기시간(초) 범위
AC_COL = 29                     # 토지등기 요약(지분 물건만)을 기록할 엑셀 열 (AC열)
CURRENCY_COLUMNS = (6, 9, 10, 20)   # 천단위 콤마(#,##0.##) 표시를 적용할 엑셀 열 번호: 면적(6), 최저가(9), 감평가(10), 건물면적_평(20, 2026-10-04 추가)

# (2026-10-04 추가, 공장매각완.py에서 포팅) 물건종류마다 별도 탭에 등기부 근저당권/청구금액
# 상세내역을 저장한다. 공장매각완.py 원본에는 배당기일 추정/채권원금/연체이자/채권행사권리금액도
# 있었지만, 그 계산들은 "이미 매각이 확정된 물건"(마지막 입찰회차=낙찰일) 전제라 아직 진행 중인
# 물건에는 맞지 않아 뺐다 - 근저당권/청구금액 중복제거·합산(사용자가 명시적으로 요청한 부분)만
# 가져왔다.
REGISTRY_DETAIL_HEADERS = [
    '구분', '사건번호', 'tid', '상세페이지',
    '물건번호', '매각일자', '소재지', '개시결정',
    '감정가', '토지면적', '건물면적', '최저가',
    '입찰진행내용',
    '등기부_근저당권설정(말소기준포함)',
    '근저당권_합계금액',
    '채권원금',
    '등기부_청구금액',
    '유동화전문_청구금액',
    '기준일(입찰기일+60일)',
    '이자 연체일수',
    '예상연체이자',
    '채권행사권리금액',
    'NPL_겹침',   # NPL(부실채권) 겹침 표시
]
# REGISTRY_DETAIL_HEADERS 안에서 "금액"을 나타내는 열 번호(1부터 시작): 감정가(9)/최저가(12)/
# 근저당권_합계금액(15)/채권원금(16)/유동화전문_청구금액(18)/예상연체이자(21)/채권행사권리금액(22).
REGISTRY_CURRENCY_COLUMNS = (9, 12, 15, 16, 18, 21, 22)

# (2026-10-04 3차 수정, 공장매각완.py에서 포팅) 근저당권_합계금액 -> 채권원금 추정 배수
# 후보(1.10~1.50, 0.05 단위, x100 정수 연산용). 동률이면 끝자리 0이 더 많이 붙는("깨끗한")
# 쪽, 그마저 같으면 더 작은 배수를 우선한다(원본과 동일 기준).
PRINCIPAL_MULTIPLIERS = (110, 115, 120, 125, 130, 135, 140, 145, 150)

ANNUAL_INTEREST_RATE = 0.10  # 연 이자율 10% (원본 '채권행사권리금액 계산식' 엑셀의 고정값)

# 진행 중인 물건은 아직 낙찰일/배당기일이 없어, 사용자 요청대로 "이번 입찰기일 + 60일"을
# 이자 계산 기준일로 근사한다(원본의 "낙찰일 + 7일(매각결정기일) + 60일(배당기일)" 대신).
REFERENCE_DAYS_AFTER_BID = 60

GOOGLE_SHEETS_ENABLED = True     # 구글 시트 동기화 켜기/끄기 (False면 기존처럼 로컬 xlsx만 저장)
GOOGLE_SHEET_WEEK_RETENTION = 3  # 최근 몇 주치 탭까지 남겨둘지 (이번 주 포함, 그보다 오래된 탭은 자동 삭제)
AUTOSAVE_EVERY_N_ITEMS = 50      # 새 물건을 이 개수만큼 모을 때마다 구글 시트(증분)+로컬 엑셀에 중간 저장

# 서비스 계정 키 파일 경로 - 집 PC/노트북 PC/사무실 PC에서 전부 "같은" 키 파일을 쓰지만
# 저장 위치(폴더 구조)가 PC마다 조금씩 다르다. 매번 PC를 바꿀 때마다 경로를 수동으로 고쳐
# 쓰지 않아도 되도록, 후보 경로 목록을 순서대로 확인해서 실제로 존재하는 첫 번째 경로를
# 자동으로 골라 쓴다. 새 PC에서 키 파일 경로가 다르면 이 목록에 한 줄만 추가하면 된다.
GOOGLE_CREDENTIALS_PATH_CANDIDATES = []
_creds_json_env = os.environ.get("GOOGLE_SA_KEY_JSON", "")
if _creds_json_env:
    _tmp_cred_path = "/tmp/google_credentials.json"
    with open(_tmp_cred_path, "w", encoding="utf-8") as _f:
        _f.write(_creds_json_env)
    GOOGLE_CREDENTIALS_PATH_CANDIDATES = [_tmp_cred_path]


def _resolve_google_credentials_path(candidates):
    """후보 경로 중 실제로 이 PC에 존재하는 첫 번째 경로를 고른다. 아무것도 없으면 첫 번째
    후보를 그대로 반환해서 기존과 동일하게 "파일을 찾을 수 없다"는 명확한 에러 메시지가
    뜨도록 한다(조용히 실패하지 않게)."""
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[0] if candidates else ""


GOOGLE_CREDENTIALS_PATH = _resolve_google_credentials_path(GOOGLE_CREDENTIALS_PATH_CANDIDATES)  # 서비스 계정 키 파일 경로
# ================================================================================

오늘 = datetime.now()
start_date_str = 오늘.strftime('%Y-%m-%d')
end_date_str = (오늘 + timedelta(days=DAYS_AHEAD)).strftime('%Y-%m-%d')
오늘날짜_숫자만 = 오늘.strftime("%Y%m%d")
오늘_ISO주차_번호 = 오늘.isocalendar()[1]

# 저장 파일명: "오늘날짜(YYYYMMDD)_W주차_경공매물건.xlsx" - 주차 번호는 구글 시트 쪽 주차 탭
# 이름(_week_tab_name(), 예: "20260817_W34_경공매물건")과 같은 계산 기준(월요일 시작 ISO
# 주차)을 쓰므로 로컬 파일명과 구글 시트 탭 이름의 주차가 항상 서로 일치한다.
파일명 = f"{오늘날짜_숫자만}_W{오늘_ISO주차_번호:02d}_경공매물건.xlsx"

BASE_URL = f"{SITE_BASE}/ca/caList.php?srchHistory=1"

PA_BASE_URL = f"{SITE_BASE}/pa/paList.php?srchHistory=1"
PA_CTGR_VALUE = '10100'
PA_PRPTDVSN_VALUES = [
    ('seizure', '압류재산'), ('other_general', '기타일반재산'),
    ('finance_collateral', '금융권담보재산'), ('bankruptcy', '파산재산'),
    ('public', '공유재산'), ('public_development', '공공개발재산'),
    ('acquired', '유입재산'), ('entrusted', '수탁재산'), ('disused', '불용품'),
]

AMOUNT_OPTIONS = [
    (1000000, "1백만"), (2000000, "2백만"), (3000000, "3백만"), (4000000, "4백만"),
    (5000000, "5백만"), (6000000, "6백만"), (7000000, "7백만"), (8000000, "8백만"),
    (9000000, "9백만"), (10000000, "1천만"), (20000000, "2천만"), (30000000, "3천만"),
    (40000000, "4천만"), (50000000, "5천만"), (60000000, "6천만"), (70000000, "7천만"),
    (80000000, "8천만"), (90000000, "9천만"), (100000000, "1억"), (150000000, "1억 5천만"),
    (200000000, "2억"), (250000000, "2억 5천만"), (300000000, "3억"), (350000000, "3억 5천만"),
    (400000000, "4억"), (450000000, "4억 5천만"), (500000000, "5억"), (600000000, "6억"),
    (700000000, "7억"), (800000000, "8억"), (900000000, "9억"), (1000000000, "10억"),
    (1100000000, "11억"), (1200000000, "12억"), (1300000000, "13억"), (1400000000, "14억"),
    (1500000000, "15억"), (1600000000, "16억"), (1700000000, "17억"), (1800000000, "18억"),
    (1900000000, "19억"), (2000000000, "20억"), (3000000000, "30억"), (4000000000, "40억"),
    (5000000000, "50억"), (6000000000, "60억"), (7000000000, "70억"), (8000000000, "80억"),
    (9000000000, "90억"), (10000000000, "100억"), (20000000000, "200억"), (30000000000, "300억"),
    (40000000000, "400억"), (50000000000, "500억"), (60000000000, "600억"), (70000000000, "700억"),
    (80000000000, "800억"), (90000000000, "900억"), (100000000000, "1000억"),
]
DEFAULT_MINB_AMT_END = 1000000000  # 최저가격 상한 기본값: 10억 (2026-10-04, 공장/근린상가 전용으로 5억->10억 변경)
DEFAULT_MINB_AMT_BGN = 300000000   # 최저가격 하한 기본값: 3억 (2026-10-04 추가, 고정값 - 프롬프트로 물어보지 않음)
PYEONG_SQM = 3.305785               # 1평 = 3.305785㎡ (건물면적 상한 환산용, 2026-10-04 추가)


# (2026-10-04) 같은 물건이 2번씩 저장되는 문제 방지: 이번 실행에서 이미 시트에 기록한(또는 구글 시트에서
# 불러온 기존) 행의 키를 기억해두고, 같은 키의 행은 다시 쓰지 않는다. 키에 chkNo(페이지 내 순번)는
# 넣지 않는다 - 재수집 때는 같은 물건이라도 순번이 달라질 수 있기 때문이다.
_WRITTEN_ROW_KEYS = set()


def _tid_from_url(url):
    m = re.search(r"(?:tid|cltrNo)=(\d+)", str(url or ""))
    return m.group(1) if m else ""


def _row_dup_key(row_values):
    def _cell(i):
        return re.sub(r"\s+", " ", str(row_values[i] if i < len(row_values) and row_values[i] is not None else "")).strip()
    return (_cell(0), _cell(1), _tid_from_url(_cell(11)), _cell(14))


def append_row_with_format(sheet, row_values, ac_value=None, dedupe=True):
    """행을 추가한다. dedupe=True(기본)이고 같은 키의 행이 이미 있으면 추가하지 않고 None을 반환한다.
    기존 시트 내용을 그대로 옮겨 담을 때는 dedupe=False로 호출한다(키만 등록됨)."""
    key = _row_dup_key(row_values)
    if dedupe and key in _WRITTEN_ROW_KEYS:
        return None
    _WRITTEN_ROW_KEYS.add(key)
    sheet.append(row_values)
    r = sheet.max_row
    for col in CURRENCY_COLUMNS:
        cell = sheet.cell(row=r, column=col)
        if isinstance(cell.value, (int, float)):
            cell.number_format = '#,##0.##'
    if ac_value:
        sheet.cell(row=r, column=AC_COL, value=ac_value)
    return r


def _iso_week_label(dt):
    iso_year, iso_week, _ = dt.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _week_tab_name(dt):
    """dt가 속한 ISO 주차의 구글 시트 탭 이름을 만든다: "YYYYMMDD_W주차_경공매물건"
    형식이며, 로컬 xlsx 저장 파일명(예: "20260823_W34_경공매물건.xlsx")과 시각적으로
    짝이 맞도록 같은 패턴을 쓴다. 실행일이 아니라 그 주가 시작하는 월요일 날짜를 써서,
    같은 주 안에서는 실행 요일과 무관하게 항상 같은 탭 이름이 나온다."""
    iso_year, iso_week, _ = dt.isocalendar()
    monday = date.fromisocalendar(iso_year, iso_week, 1)
    return f"{monday.strftime('%Y%m%d')}_W{iso_week:02d}_경공매물건"


WEEK_TAB_PATTERN = re.compile(r"^\d{8}_W\d{2}_경공매물건$")


def _read_service_account_email(credentials_path):
    try:
        import json as _json
        with open(credentials_path, "r", encoding="utf-8") as f:
            return _json.load(f).get("client_email", "")
    except Exception:
        return ""


def _validate_google_sheet_id(sheet_id):
    sid = (sheet_id or "").strip()
    if sid == "":
        return None, "GOOGLE_SHEET_ID가 비어있습니다."
    if sid.startswith("http"):
        return None, (f"GOOGLE_SHEET_ID에 URL 전체가 들어있습니다: {sid!r}")
    try:
        sid.encode("ascii")
    except UnicodeEncodeError:
        return None, f"GOOGLE_SHEET_ID에 한글/특수문자가 섞여 있습니다: {sid!r}"
    return sid, None


def get_google_spreadsheet():
    if not GOOGLE_SHEETS_ENABLED:
        return None
    if gspread is None or GoogleCredentials is None:
        print("[구글시트] gspread / google-auth 라이브러리가 설치되어 있지 않아 이번에는 건너뜁니다.")
        return None
    if not os.path.exists(GOOGLE_CREDENTIALS_PATH):
        print(f"[구글시트] 서비스 계정 키 파일을 찾을 수 없어 건너뜁니다: {GOOGLE_CREDENTIALS_PATH}")
        return None

    sheet_id, id_err = _validate_google_sheet_id(GOOGLE_SHEET_ID)
    if id_err and not GOOGLE_SHEET_ID:
        pass
    elif id_err:
        print(f"[구글시트] {id_err} 이번에는 건너뜁니다.")
        return None

    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        gc = gspread.service_account(filename=GOOGLE_CREDENTIALS_PATH, scopes=scopes)
        service_account_email = _read_service_account_email(GOOGLE_CREDENTIALS_PATH)

        if sheet_id:
            try:
                sh = gc.open_by_key(sheet_id)
            except gspread.exceptions.APIError as e:
                print(f"[구글시트] 스프레드시트 접근 권한이 없어 이번에는 건너뜁니다 "
                      f"(GOOGLE_SHEET_ID={sheet_id!r}). 서비스 계정 이메일"
                      f"({service_account_email or '키 파일의 client_email 값'})을 '편집자'로 "
                      f"추가했는지 확인하세요. (원본 에러: {e})")
                return None
            except gspread.exceptions.SpreadsheetNotFound:
                print(f"[구글시트] GOOGLE_SHEET_ID로 스프레드시트를 찾을 수 없습니다: {sheet_id!r}")
                return None
        else:
            sh = gc.create("weekly_data_sheet")
            print(f"[구글시트] 새 스프레드시트를 생성했습니다: {sh.url}")
            if GOOGLE_SHEET_SHARE_EMAIL:
                try:
                    sh.share(GOOGLE_SHEET_SHARE_EMAIL, perm_type='user', role='writer')
                    print(f"[구글시트] {GOOGLE_SHEET_SHARE_EMAIL} 계정에 편집 권한을 공유했습니다.")
                except Exception as e:
                    print(f"[구글시트] 공유 실패: {e}")
        return sh
    except Exception as e:
        print(f"[구글시트] 인증/연결에 실패해 이번에는 건너뜁니다: {e}")
        return None


def get_or_create_tab(sh, tab_name):
    if sh is None:
        return None
    try:
        return sh.worksheet(tab_name)
    except gspread.exceptions.WorksheetNotFound:
        try:
            ws = sh.add_worksheet(title=tab_name, rows=100, cols=40)
            print(f"[구글시트] '{tab_name}' 탭이 없어 새로 만들었습니다.")
            return ws
        except Exception as e:
            print(f"[구글시트] '{tab_name}' 탭을 새로 만드는 데 실패했습니다: {e}")
            return None
    except Exception as e:
        print(f"[구글시트] '{tab_name}' 탭을 여는 데 실패했습니다: {e}")
        return None


def get_tab_if_exists(sh, tab_name):
    if sh is None:
        return None
    try:
        return sh.worksheet(tab_name)
    except gspread.exceptions.WorksheetNotFound:
        return None
    except Exception as e:
        print(f"[구글시트] '{tab_name}' 탭을 확인하는 데 실패했습니다: {e}")
        return None


def _build_header_row():
    """TEMPLATE_HEADERS + AC_COL(토지등기 요약) 자리까지 채운 헤더 행 한 줄을 만든다."""
    header_row = list(TEMPLATE_HEADERS)
    while len(header_row) < AC_COL:
        header_row.append("")
    header_row[AC_COL - 1] = "토지등기_요약(지분물건만, 임시)"
    return header_row


def ensure_header_row(ws):
    """탭을 열거나 새로 만든 직후, 반드시 이 함수부터 호출해서 헤더 행이 있는지
    확인/보장한다.

    (2026-09-07, 깃허브 Actions 버전에서 발견된 버그를 로컬 버전에도 반영) 기존에는
    헤더 행이 "실행이 끝까지 완전히 성공했을 때"만 마지막 sync_to_google_sheet()에서
    한 번 쓰였다. 그런데 실행 도중의 중간 저장(append_new_rows_to_gsheet, N건마다)은
    "헤더가 이미 있다"고 가정하고 그 다음 행부터 이어붙이기만 한다 - 새로 만든 빈
    탭은 아직 헤더가 없으므로, 이 중간 저장이 원격 시트의 "데이터가 있는 마지막 행
    다음"(=빈 시트라 1행)에 그대로 물건 데이터를 써버려서, 헤더 자리를 데이터가
    차지해버리는 문제가 있었다. 만약 그 실행이 끝까지 완전히 성공하지 못하면(도중에
    구글 시트 저장만 조용히 실패하는 경우 등) 이 헤더 없는 상태가 그대로 굳어버린다.

    이 함수는 두 가지 상황을 모두 처리한다:
    1) 탭이 완전히 비어있으면 -> 헤더 행을 1행에 즉시 써넣는다(데이터 수집을
       시작하기 전에 미리 해두므로, 이후 중간 저장이 실행 완료 여부와 무관하게
       항상 2행부터 정확하게 쌓인다).
    2) 탭에 이미 내용이 있는데 1행이 정상적인 헤더가 아니라 물건 데이터로
       보이면(위 버그로 이미 망가진 탭) -> 헤더 행을 1행에 삽입해서 기존
       데이터를 전부 한 칸씩 아래로 밀어내고 자동으로 복구한다.
    이미 정상적인 헤더가 있으면(1행에 "사건번호"가 포함되어 있으면) 아무것도
    하지 않는다. 어떤 경우든 예외가 나도 크롤링 자체를 막지 않도록 조용히
    로그만 남긴다."""
    if ws is None:
        return
    try:
        existing = ws.get_all_values()
    except Exception as e:
        print(f"[구글시트] '{ws.title}' 헤더 확인 중 오류: {e}")
        return
    header_row = _build_header_row()
    if not existing:
        try:
            ws.update(values=[header_row], range_name="A1")
            print(f"[구글시트] 새 탭 '{ws.title}'에 헤더 행을 미리 기록했습니다.")
        except Exception as e:
            print(f"[구글시트] '{ws.title}'에 헤더 행을 미리 쓰는 데 실패했습니다: {e}")
        return
    first_row = existing[0]
    if "사건번호" in first_row:
        return  # 이미 정상적인 헤더가 있음
    try:
        ws.insert_row(header_row, index=1)
        print(f"[구글시트] '{ws.title}' 탭에 헤더가 없어 자동으로 복구(1행에 삽입)했습니다.")
    except Exception as e:
        print(f"[구글시트] '{ws.title}' 헤더 자동 복구에 실패했습니다: {e}")


# --- 실행 이력(감사 로그) ---
# 매 실행이 끝날 때마다 요약 정보 한 줄을 이 탭에 누적 기록한다. 주차별 데이터
# 탭(WEEK_TAB_PATTERN)과 이름 패턴이 달라서 cleanup_old_week_tabs()의 정리
# 대상이 되지 않으므로, 지금까지 총 몇 번 실행했는지/데이터가 얼마나 누적
# 됐는지를 한 곳에서 계속 추적할 수 있다. 어느 PC(집/노트북/사무실)에서 실행했는지도
# 함께 남겨서, 나중에 특정 실행의 출처를 바로 알 수 있게 한다.
RUN_LOG_TAB_NAME = "_run_log"
RUN_LOG_HEADERS = [
    "실행시각(KST)", "실행PC", "수집범위", "대상탭",
    "시작전_원격행수", "종료후_원격행수", "이번실행_신규건수", "이번실행_건너뛴기존건수",
    "검증결과", "비고",
]


def _get_local_pc_name():
    """실행 이력에 남길 PC 식별 이름. 호스트명을 얻지 못해도 크롤링에 영향을 주지
    않도록 예외를 조용히 처리한다."""
    try:
        import socket
        return "GitHub Actions"
    except Exception:
        return "알수없는PC"


def ensure_run_log_tab(sh):
    """실행 이력 탭을 열거나(없으면) 새로 만들고, 헤더가 없으면 채워둔다."""
    if sh is None:
        return None
    try:
        ws = sh.worksheet(RUN_LOG_TAB_NAME)
    except gspread.exceptions.WorksheetNotFound:
        try:
            ws = sh.add_worksheet(title=RUN_LOG_TAB_NAME, rows=2000, cols=len(RUN_LOG_HEADERS) + 2)
            ws.update(values=[RUN_LOG_HEADERS], range_name="A1")
            print(f"[실행이력] '{RUN_LOG_TAB_NAME}' 탭을 새로 만들었습니다.")
        except Exception as e:
            print(f"[실행이력] 탭 생성 실패: {e}")
            return None
    except Exception as e:
        print(f"[실행이력] 탭을 여는 데 실패했습니다: {e}")
        return None
    try:
        existing = ws.get_all_values()
        if not existing:
            ws.update(values=[RUN_LOG_HEADERS], range_name="A1")
    except Exception as e:
        print(f"[실행이력] 헤더 확인 중 오류(치명적이지 않음): {e}")
    return ws


def log_run_summary(sh, summary: dict):
    """이번 실행의 요약 정보 한 줄을 실행 이력 탭에 추가한다. 이 로그 자체가
    실패해도(네트워크 오류 등) 크롤링 결과 저장에는 전혀 영향을 주지 않도록
    예외를 조용히 처리한다."""
    ws = ensure_run_log_tab(sh)
    if ws is None:
        return
    row = [summary.get(h, "") for h in RUN_LOG_HEADERS]
    try:
        ws.append_row(row, value_input_option="RAW")
        print(f"[실행이력] 기록 완료 - 대상탭: {summary.get('대상탭')}, "
              f"신규: {summary.get('이번실행_신규건수')}건, 검증결과: {summary.get('검증결과')}")
    except Exception as e:
        print(f"[실행이력] 기록 실패(치명적이지 않음): {e}")


def count_total_runs(sh):
    """지금까지 총 몇 번 실행됐는지(실행 이력 탭의 데이터 행 수)를 센다.
    탭이 없거나 읽기에 실패하면 None을 반환한다."""
    if sh is None:
        return None
    ws = get_tab_if_exists(sh, RUN_LOG_TAB_NAME)
    if ws is None:
        return 0  # 아직 한 번도 로그가 기록된 적 없음(이번이 사실상 첫 실행)
    try:
        values = ws.get_all_values()
        return max(0, len(values) - 1)  # 헤더 제외
    except Exception:
        return None


def load_existing_data_from_gsheet(ws):
    if ws is None:
        return set(), []
    try:
        all_values = ws.get_all_values()
    except Exception as e:
        print(f"[구글시트] '{ws.title}' 탭을 읽는 데 실패했습니다: {e} - 중복 검사 없이 진행합니다.")
        return set(), []
    if not all_values:
        return set(), []

    header_row = all_values[0]
    header_idx = {name: i for i, name in enumerate(header_row) if name}
    if "사건번호" not in header_idx:
        print(f"[구글시트] '{ws.title}' 탭에서 '사건번호' 열을 찾지 못해 중복 검사 없이 진행합니다.")
        return set(), []

    ac_idx = None
    for i, name in enumerate(header_row):
        if name and "토지등기" in str(name):
            ac_idx = i
            break

    currency_positions = {c - 1 for c in CURRENCY_COLUMNS}
    sano_i = header_idx["사건번호"]
    existing_case_numbers = set()
    existing_rows = []
    for row in all_values[1:]:
        if sano_i >= len(row):
            continue
        사건번호 = row[sano_i]
        if not 사건번호:
            continue
        existing_case_numbers.add(str(사건번호).strip())
        row_values = [
            row[header_idx[h]] if (h in header_idx and header_idx[h] < len(row)) else ""
            for h in TEMPLATE_HEADERS
        ]
        for i in currency_positions:
            if i < len(row_values) and row_values[i] not in ("", None):
                try:
                    cleaned = str(row_values[i]).replace(",", "").strip()
                    row_values[i] = float(cleaned) if "." in cleaned else int(cleaned)
                except (ValueError, TypeError):
                    pass
        ac_value = row[ac_idx] if (ac_idx is not None and ac_idx < len(row)) else None
        existing_rows.append((row_values, ac_value))
    return existing_case_numbers, existing_rows


def load_case_numbers_by_type_from_gsheet(ws):
    if ws is None:
        return set(), set()
    try:
        all_values = ws.get_all_values()
    except Exception:
        return set(), set()
    if not all_values:
        return set(), set()
    header_row = all_values[0]
    header_idx = {name: i for i, name in enumerate(header_row) if name}
    if TYPE_HEADER_LABEL not in header_idx or "사건번호" not in header_idx:
        return set(), set()
    jongryu_i = header_idx[TYPE_HEADER_LABEL]
    sano_i = header_idx["사건번호"]
    ca_set, pa_set = set(), set()
    for row in all_values[1:]:
        if sano_i >= len(row) or jongryu_i >= len(row):
            continue
        사건번호 = (row[sano_i] or "").strip()
        if not 사건번호:
            continue
        종류 = row[jongryu_i]
        if 종류 == TYPE_A_LABEL:
            ca_set.add(사건번호)
        elif 종류 == TYPE_B_LABEL:
            pa_set.add(사건번호)
    return ca_set, pa_set


def cleanup_old_week_tabs(sh, retention=GOOGLE_SHEET_WEEK_RETENTION):
    if sh is None:
        return 0
    try:
        titles = [ws.title for ws in sh.worksheets()]
    except Exception as e:
        print(f"[구글시트] 탭 목록을 가져오는 데 실패해 오래된 탭 정리를 건너뜁니다: {e}")
        return 0
    week_titles = sorted({t for t in titles if WEEK_TAB_PATTERN.match(t)}, reverse=True)
    to_delete = [t for t in week_titles if t not in week_titles[:retention]]
    if not to_delete:
        return 0
    removed = 0
    for title in to_delete:
        try:
            ws = sh.worksheet(title)
            sh.del_worksheet(ws)
            removed += 1
            print(f"[구글시트] 보관 기간({retention}주)이 지난 오래된 주차 탭을 삭제했습니다: {title}")
        except Exception as e:
            print(f"[구글시트] '{title}' 탭 삭제에 실패했습니다: {e}")
    return removed


def _gsheet_json_safe(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    return value


def _apply_gsheet_formatting(ws, n_rows, n_cols, currency_cols=None):
    _apply_gsheet_formatting_range(ws, 1, n_rows, n_cols, currency_cols=currency_cols)


def _apply_gsheet_formatting_range(ws, start_row, end_row, n_cols, currency_cols=None):
    """currency_cols를 넘기지 않으면(None) 기존처럼 메인 시트용 CURRENCY_COLUMNS를 쓴다.
    (2026-10-04 포팅) 등기부상세 탭처럼 열 구성이 다른 시트에도 재사용할 수 있도록 콤마
    서식을 적용할 열 번호를 호출자가 지정할 수 있게 했다(원본: 공장매각완.py)."""
    if currency_cols is None:
        currency_cols = CURRENCY_COLUMNS
    try:
        last_col = get_column_letter(n_cols)
        ws.format(f"A{start_row}:{last_col}{end_row}", {"wrapStrategy": "CLIP"})
        currency_start = max(start_row, 2)
        if end_row >= currency_start:
            for col in currency_cols:
                if col > n_cols:
                    continue
                col_letter = get_column_letter(col)
                ws.format(f"{col_letter}{currency_start}:{col_letter}{end_row}",
                          {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.##"}})
    except Exception as e:
        print(f"[구글시트] 서식(줄바꿈/콤마) 적용 중 오류가 발생했지만 데이터 저장에는 영향이 없습니다: {e}")


def _get_remote_row_count(ws):
    """구글 시트 탭에 실제로 몇 행이 들어있는지 '전체를 읽어와서' 확인한다.
    시트의 모든 행/열 데이터를 통째로 내려받는 방식이라(get_all_values), 정확한
    총 행 수가 꼭 필요한 경우(예: 실행 마지막의 전체 덮어쓰기 안전장치)에만 쓴다.
    시트가 커질수록 이 호출 자체의 비용도 커지므로, 실행 도중 반복 호출되는
    가벼운 재확인 용도로는 대신 _remote_row_has_data()를 쓴다.
    읽기 자체가 실패하면(네트워크 오류 등) None을 반환한다."""
    try:
        return len(ws.get_all_values())
    except Exception as e:
        print(f"[검증] '{ws.title}' 탭의 실제 행 수를 확인하지 못했습니다: {e}")
        return None


def _remote_row_has_data(ws, row_number, col=2):
    """시트 전체를 내려받지 않고, 딱 하나의 셀(기본: 사건번호 열)만 가볍게
    확인한다 - "이 행까지 데이터가 실제로 들어갔는지"를 저비용으로 확인하는
    용도. get_all_values()가 전체 데이터를 통째로 가져오는 것과 달리, 이건
    셀 하나에 대한 요청 한 번뿐이라 시트 크기와 무관하게 항상 가볍다. 자동저장
    중간중간의 주기적 재확인(maybe_autosave)은 이 방식을 쓴다."""
    try:
        value = ws.cell(row_number, col).value
        return bool(value)
    except Exception as e:
        print(f"[검증] {row_number}행 확인 중 오류: {e}")
        return None


def sync_to_google_sheet(local_sheet, ws):
    """로컬 엑셀 시트의 전체 내용을 구글 시트 탭에 통째로 덮어써서 미러링한다.

    (2026-09-07, 깃허브 Actions 버전에서 실제로 발생한 사고를 계기로 추가된
    안전장치를 로컬 버전에도 반영) 덮어쓰기 직전에 원격 탭의 "현재" 행 수를
    먼저 확인한다. 만약 원격에 이미 있는 행 수가 지금 이 실행이 쓰려는 내용보다
    "더 많으면" - 이는 이 실행이 시작된 뒤 다른 실행(다른 PC에서 거의 동시에
    실행했거나, 이 실행이 미처 몰랐던 추가 데이터)이 원격에 더 많은 데이터를
    이미 쌓아뒀다는 뜻이므로, 그걸 이 실행이 가진 "더 적은" 내용으로 덮어써서
    지워버리는 사고를 막기 위해 **덮어쓰기 자체를 건너뛴다**. 이런 경우 원격에는
    이미 충분한(또는 더 많은) 데이터가 안전하게 있으므로 손대지 않는 것이 항상
    더 안전하다 - 이 실행이 자기가 새로 모은 데이터는 이미 실행 도중
    append_new_rows_to_gsheet()로 증분 저장됐으므로 유실되지 않는다.

    저장을 실제로 수행한 뒤에는 원격 탭을 다시 읽어 실제 행 수가 방금 쓴
    내용과 정확히 일치하는지 확인한다(사후 검증) - 불일치하면 경고를 남긴다.

    반환값: (성공여부: bool, 저장전_원격행수: int|None, 저장후_원격행수: int|None)"""
    if ws is None:
        return False, None, None
    try:
        remote_before = _get_remote_row_count(ws)
        values = []
        for row in local_sheet.iter_rows(values_only=True):
            values.append([_gsheet_json_safe(v) for v in row])
        n_rows = max(len(values), 1)
        n_cols = max((len(r) for r in values), default=1)
        n_cols = max(n_cols, AC_COL)

        # --- 사전 검증: 덮어쓰면 오히려 행 수가 줄어드는지 확인 ---
        if remote_before is not None and remote_before > n_rows:
            print(f"[구글시트] ⚠️ 덮어쓰기 안전장치 작동: 원격 탭에 이미 {remote_before}행이 "
                  f"있는데 이번 실행이 쓰려는 내용은 {n_rows}행뿐입니다(더 적음). 데이터 손실을 "
                  f"막기 위해 전체 덮어쓰기를 건너뜁니다 - 원격 데이터는 그대로 안전하게 남아있고, "
                  f"이 실행이 새로 모은 데이터는 이미 실행 도중 증분 저장으로 반영되어 있습니다.")
            return True, remote_before, remote_before

        needed_rows = n_rows + 10
        needed_cols = n_cols + 2
        if ws.row_count < needed_rows or ws.col_count < needed_cols:
            ws.resize(rows=max(ws.row_count, needed_rows), cols=max(ws.col_count, needed_cols))
        ws.clear()
        ws.update(values=values, range_name="A1")
        _apply_gsheet_formatting(ws, n_rows, n_cols)

        # --- 사후 검증: 실제로 저장된 행 수가 예상과 일치하는지 재확인 ---
        remote_after = _get_remote_row_count(ws)
        if remote_after is None:
            print(f"[검증] 저장 후 실제 행 수를 다시 확인하지 못했습니다 - 저장 자체는 완료됐습니다.")
        elif remote_after != n_rows:
            print(f"[검증] ⚠️ 불일치 발견: 저장 후 실제 행 수({remote_after})가 "
                  f"예상 행 수({n_rows})와 다릅니다. 탭을 직접 확인해보세요: {ws.title}")
        else:
            print(f"[검증] ✅ 저장 후 실제 행 수가 예상과 정확히 일치합니다 ({remote_after}행).")

        print(f"[구글시트] 동기화 완료: {len(values) - 1 if values else 0}건 "
              f"(스프레드시트 ID: {GOOGLE_SHEET_ID or '(신규 생성)'} / 탭: {ws.title})")
        return True, remote_before, remote_after
    except Exception as e:
        print(f"[구글시트] 업로드 중 오류가 발생해 이번에는 건너뜁니다: {e}")
        return False, None, None


def append_new_rows_to_gsheet(local_sheet, ws, sync_state):
    if ws is None:
        return False
    try:
        last_synced = sync_state.get("synced_rows", 1)
        max_row = local_sheet.max_row
        if max_row <= last_synced:
            return True
        new_values = []
        for row in local_sheet.iter_rows(min_row=last_synced + 1, max_row=max_row, values_only=True):
            new_values.append([_gsheet_json_safe(v) for v in row])
        n_cols = max((len(r) for r in new_values), default=1)
        n_cols = max(n_cols, AC_COL)
        needed_rows = max_row + 10
        needed_cols = n_cols + 2
        if ws.row_count < needed_rows or ws.col_count < needed_cols:
            ws.resize(rows=max(ws.row_count, needed_rows), cols=max(ws.col_count, needed_cols))
        # table_range="A1"을 반드시 명시한다 (2026-09-07, 실제 데이터 밀림 사고로 추가).
        # 지정하지 않으면 구글시트 API가 "어디부터 이어붙일지" 표 범위를 시트 안의
        # 데이터를 보고 자동으로 추측하는데, 헤더 행이 A~S열까지 채우고 한참 떨어진
        # AC열(29번째, 지분 물건 등기요약 칸)에도 값이 하나 있는 "듬성듬성한" 모양이라
        # 이걸 두 개의 표로 오인해서 새로 추가하는 행을 엉뚱하게 AC열부터 이어붙이는
        # 사고가 실제로 발생했다(사용자가 다운로드한 구글시트 사본에서 헤더는 A열부터
        # 정상인데 모든 데이터 행이 AC열부터 시작하는 것으로 확인됨). table_range="A1"로
        # "표는 A1부터 시작한다"고 못박아두면 이 오작동 없이 항상 A열부터 이어붙는다.
        ws.append_rows(new_values, value_input_option="RAW", table_range="A1")
        _apply_gsheet_formatting_range(ws, last_synced + 1, max_row, n_cols)
        sync_state["synced_rows"] = max_row
        print(f"[구글시트] 증분 동기화 완료: {len(new_values)}건 추가 (누적 {max_row - 1}건, 탭: {ws.title})")
        return True
    except Exception as e:
        print(f"[구글시트] 증분 업로드 중 오류가 발생해 이번에는 건너뜁니다: {e}")
        return False


def maybe_autosave(sheet, ws, save_path, total_new_count, sync_state):
    """새 물건이 AUTOSAVE_EVERY_N_ITEMS개 모일 때마다 중간 저장한다.

    (2026-09-07, 깃허브 Actions 버전 반영) 검증 방식: 이번 저장을 하기 **전에**,
    직전 자동저장이 마지막으로 기록해둔 "마지막 행 번호"(sync_state["synced_rows"])에
    지금도 데이터가 그대로 있는지 셀 1개만 가볍게 확인한다(_remote_row_has_data -
    시트 전체를 내려받지 않으므로 시트가 커져도 비용이 항상 일정함). 이렇게 "쓰기
    전에 직전 상태부터 확인"하면, 혹시 그 사이(직전 자동저장 이후 지금까지) 다른
    실행(다른 PC에서의 실행 등)이 이 탭을 건드렸거나 지워버린 경우를 다음 데이터를
    쓰기 전에 미리 감지할 수 있다(문제가 생기고 나서 한참 뒤에야 알아채는 것보다
    한 배치 더 빨리 발견됨). 비용이 셀 1개 조회뿐이라 매 자동저장마다 수행해도
    부담이 없다."""
    if total_new_count <= 0 or total_new_count % AUTOSAVE_EVERY_N_ITEMS != 0:
        return
    print(f"[자동 저장] 지금까지 새로 수집한 물건 {total_new_count}건 - 중간 저장 중...")
    if GOOGLE_SHEETS_ENABLED and ws is not None:
        prev_last_row = sync_state.get("synced_rows", 1)
        if prev_last_row > 1:  # 1행(헤더)뿐이면 아직 비교할 이전 저장분이 없음
            still_there = _remote_row_has_data(ws, prev_last_row)
            if still_there is None:
                print(f"[검증] 직전 저장분({prev_last_row}행) 확인 실패(네트워크) - 이번 저장은 그대로 진행합니다.")
            elif not still_there:
                print(f"[검증] ⚠️ 직전 자동저장까지 있었어야 할 {prev_last_row}행이 지금 비어있습니다! "
                      f"다른 실행(다른 PC 등)이 이 탭을 건드렸을 수 있으니 나중에 결과를 꼭 확인하세요.")
            else:
                print(f"[검증] ✅ 직전 저장분({prev_last_row}행) 그대로 있음 확인.")
        append_new_rows_to_gsheet(sheet, ws, sync_state)
    try:
        sheet.parent.save(save_path)
        print(f"[자동 저장] 로컬 엑셀에도 중간 저장했습니다: {save_path}")
    except Exception as e:
        print(f"[자동 저장] 로컬 엑셀 중간 저장에 실패했습니다: {e}")


def prompt_collect_mode():
    """터미널에서 수집 범위(경매만 / 공매만 / 경매+공매 모두)를 선택받는다. 반환값은
    main()의 분기(if collect_mode in ("type_a", "both") 등)와 맞추기 위해
    "type_a"(경매만) / "type_b"(공매만) / "both"(모두, 기본값) 중 하나를 쓴다."""
    print("\n=== 수집 범위 설정 ===")
    print(f"  1. {TYPE_A_LABEL}만 수집 (caList.php)")
    print(f"  2. {TYPE_B_LABEL}만 수집 (paList.php)")
    print(f"  3. {TYPE_A_LABEL} + {TYPE_B_LABEL} 모두 수집 (기본값)")
    raw = input("\n번호를 입력하세요 (1~3, 그냥 Enter 시 기본값 3): ").strip()
    if raw == "1":
        return "type_a"
    if raw == "2":
        return "type_b"
    if raw == "" or raw == "3":
        return "both"
    print("알 수 없는 입력입니다. 기본값(경매+공매 모두 수집)으로 진행합니다.")
    return "both"


def prompt_ctgr_mode_ca():
    """터미널에서 경매(caList.php) 물건종류를 선택받는다(2026-09-18 추가, 사용자 요청:
    "공장도 추출하고 싶다. 옵션으로 넣어라"). CTGR_OPTIONS_CA 목록 중 1개 이상을 골라
    (값, 라벨) 튜플의 리스트로 반환한다. "모두 수집"을 고르면 main()이 각 물건종류마다
    처음부터 다시 목록을 순회한다(공매 자산구분 9개를 순회하는 것과 동일한 방식) - 사이트
    검색 폼의 select#ctgr가 한 번에 하나의 값만 선택 가능한 단일 select라 여러 물건종류를
    동시에 검색할 수 없기 때문이다.
    ⚠️ 공매(paList.php)는 아직 "공장"에 해당하는 값을 확인하지 못해 이 선택은 경매에만
    적용된다 - 공매는 지금처럼 PA_CTGR_VALUE(토지)로 고정 수집된다."""
    print("\n=== 물건종류 설정 (경매) ===")
    for idx, (_, label) in enumerate(CTGR_OPTIONS_CA, start=1):
        print(f"  {idx}. {label}만 수집" + (" (기본값)" if idx == 1 else ""))
    all_idx = len(CTGR_OPTIONS_CA) + 1
    all_label = " + ".join(label for _, label in CTGR_OPTIONS_CA)
    print(f"  {all_idx}. {all_label} 모두 수집")
    raw = input(f"\n번호를 입력하세요 (1~{all_idx}, 그냥 Enter 시 기본값 1): ").strip()
    if raw == "" or raw == "1":
        return [CTGR_OPTIONS_CA[0]]
    if raw == str(all_idx):
        return list(CTGR_OPTIONS_CA)
    try:
        choice = int(raw)
        if 1 <= choice <= len(CTGR_OPTIONS_CA):
            return [CTGR_OPTIONS_CA[choice - 1]]
    except ValueError:
        pass
    print(f"알 수 없는 입력입니다. 기본값({CTGR_OPTIONS_CA[0][1]}만 수집)으로 진행합니다.")
    return [CTGR_OPTIONS_CA[0]]


def prompt_minb_amt_end():
    """터미널에서 최저가격 상한을 입력받는다. 숫자는 만원 단위로 입력받는다(예: 5억을
    입력하려면 500000000이 아니라 50000을 입력) - 원 단위 그대로 입력하면 0이 여러 개라
    실수하기 쉽다. 라벨("5억" 등)도 그대로 허용한다. 사이트의 select#minbAmtEnd 옵션
    값 자체는 원 단위이므로, 만원 단위 입력값에 10000을 곱해 내부적으로 원 단위로
    변환한 뒤 사이트가 지원하는 값(AMOUNT_OPTIONS)인지 검증한다.

    (2026-09-07 변경) 기존에는 감정가격(select#apslAmtEnd) 단일 상한으로 필터링했는데,
    사용자가 대신 최저가격(select#minbAmtBgn ~ #minbAmtEnd, 시작~끝 범위 select 2개)
    기준으로 필터링하도록 요청 - 하한(minbAmtBgn)은 항상 "선택 안 함"(0)으로 두고
    상한(minbAmtEnd)만 이 함수에서 받은 값으로 설정한다(기본값: 최저가격 5억 이하)."""
    print("\n=== 최저가격 상한 설정 ===")
    print("금액은 '만원' 단위 숫자로 입력합니다 (예: 5억 -> 50000, 1억 -> 10000, 5천만 -> 5000).")
    print("아래는 사이트가 지원하는 값의 예시입니다 (일부, 괄호 안이 입력할 만원 단위 숫자):")
    print("  5,000,000 원 = 5백만(500)   |  100,000,000 원 = 1억(10000)   |  500,000,000 원 = 5억(50000)   |  1,000,000,000 원 = 10억(100000)")
    label_map = {label: val for val, label in AMOUNT_OPTIONS}
    valid_values = {val for val, _ in AMOUNT_OPTIONS}
    while True:
        raw = input(
            f"최저가격 상한을 만원 단위로 입력하세요 (예: 50000 = 5억, 라벨 입력도 가능, "
            f"그냥 Enter 시 기본값 5억): "
        ).strip()
        if raw == "":
            return str(DEFAULT_MINB_AMT_END)
        if raw in label_map:
            return str(label_map[raw])
        cleaned = raw.replace(",", "").replace("만원", "").replace("원", "").replace("만", "").strip()
        if cleaned.isdigit():
            won_value = int(cleaned) * 10000  # 만원 -> 원 변환
            if won_value in valid_values:
                return str(won_value)
        print("사이트에서 지원하지 않는 값입니다. 만원 단위 숫자(예: 50000) 또는 라벨(예: 5억)로 다시 입력해주세요.\n")


DEFAULT_AREA_PYEONG_END = 200  # 건물면적 상한 기본값: 200평 (2026-10-04 추가)


def prompt_area_pyeong_end():
    """터미널에서 건물면적 상한(평 단위)을 입력받는다. 사이트 검색 화면 자체에는 면적
    필터가 없어서, 목록을 다 받아온 뒤 main()에서 이 값으로 걸러낸다(extract_row()가
    각 행의 "건물 N㎡" 텍스트를 평으로 환산해 반환하는 건물면적_평과 비교)."""
    print("\n=== 건물면적 상한 설정 ===")
    print("(사이트 검색 화면에는 건물면적 필터가 없어 목록을 받아온 뒤 이 값으로 걸러냅니다)")
    raw = input(f"건물면적 상한을 '평' 단위로 입력하세요 (그냥 Enter 시 기본값 {DEFAULT_AREA_PYEONG_END}평): ").strip()
    if raw == "":
        return float(DEFAULT_AREA_PYEONG_END)
    cleaned = raw.replace(",", "").replace("평", "").strip()
    try:
        value = float(cleaned)
        if value > 0:
            return value
    except ValueError:
        pass
    print(f"올바르지 않은 입력입니다. 기본값({DEFAULT_AREA_PYEONG_END}평)으로 진행합니다.")
    return float(DEFAULT_AREA_PYEONG_END)


def prompt_minb_amt_end():
    """Actions 버전: 환경변수 MINB_AMT_END(원 단위, 사이트 옵션 값)로 대체. 잘못된 값이면 기본값."""
    raw = (os.environ.get("MINB_AMT_END") or "").strip()
    label_map = {label: val for val, label in AMOUNT_OPTIONS}
    valid_values = {val for val, _ in AMOUNT_OPTIONS}
    if raw in label_map:
        value = str(label_map[raw])
    elif raw.isdigit() and int(raw) in valid_values:
        value = raw
    else:
        if raw:
            print(f"[설정] MINB_AMT_END 값({raw!r})이 올바르지 않아 기본값으로 진행합니다.")
        value = str(DEFAULT_MINB_AMT_END)
    print(f"[설정] 최저가격 상한: {int(value):,}원")
    return value


def prompt_area_pyeong_end():
    """Actions 버전: 환경변수 AREA_PYEONG_END(평)로 대체."""
    raw = (os.environ.get("AREA_PYEONG_END") or "").strip()
    try:
        value = float(raw) if raw else float(DEFAULT_AREA_PYEONG_END)
        if value <= 0:
            raise ValueError
    except ValueError:
        print(f"[설정] AREA_PYEONG_END 값({raw!r})이 올바르지 않아 기본값({DEFAULT_AREA_PYEONG_END}평)으로 진행합니다.")
        value = float(DEFAULT_AREA_PYEONG_END)
    print(f"[설정] 건물면적 상한: {value:g}평")
    return value


def find_chrome_binary():
    """OS별 구글 크롬 기본 설치 경로를 확인해서 존재하는 첫 번째 경로를 반환한다.
    (상세페이지는 반드시 실제 설치된 "구글 크롬"으로 열려야 한다는 요청에 따라, 다른
    크로미움 계열 브라우저가 대신 잡히지 않도록 실행 파일 경로를 명시적으로 지정하기 위함)"""
    candidates = [
        # Windows
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        # macOS
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        # Linux
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def get_driver():
    chrome_options = Options()
    # 브라우저 창을 닫아도 크롬 프로세스가 바로 안 죽고 남아있게(디버깅/눈으로 진행상황
    # 확인할 때 편함). 로컬 실행은 화면이 있으므로 깃허브 버전과 달리 headless를 쓰지 않는다.
    chrome_options.add_argument("--headless=new")   # Actions(화면 없음)
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
    # 창 너비를 데스크톱 크기로 고정 - 사이트가 950px 기준으로 모바일/데스크톱 레이아웃을
    # 나누는데(show-950 / no-950 클래스), 창이 좁으면 데스크톱용 요소가 숨겨져서(.text가
    # 빈 문자열을 반환) 진행상태/최저가율 같은 값이 안 읽히는 문제가 있었음.
    chrome_options.add_argument("--window-size=1920,1080")

    chrome_path = find_chrome_binary()
    if chrome_path:
        chrome_options.binary_location = chrome_path
        print(f"구글 크롬 실행 파일 사용: {chrome_path}")
    else:
        print("구글 크롬 실행 파일을 자동으로 찾지 못해 기본 설정으로 진행합니다 "
              "(Selenium이 알아서 찾은 브라우저를 사용).")

    service = Service()
    return webdriver.Chrome(service=service, options=chrome_options)


def dismiss_alert_if_present(driver, tid=None):
    try:
        alert = driver.switch_to.alert
        text = alert.text
        alert.accept()
        print(f"  [tid={tid}] 알림창 발견, 닫음: {text}")
        return text
    except Exception:
        return None


def login(driver, login_id, password):
    if not login_id or not password:
        print("로그인 정보가 입력되지 않아 로그인을 건너뜁니다 (상세페이지 관련 항목은 비어있게 됩니다).")
        return False
    try:
        driver.execute_script("""
            const btn = document.querySelector('span.topGrid[data-action="loginDivBtn"]');
            if (btn) btn.click();
        """)
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.ID, "client_id"))
        )
        id_el = driver.find_element(By.ID, "client_id")
        pw_el = driver.find_element(By.ID, "passwd")
        id_el.clear()
        id_el.send_keys(login_id)
        pw_el.clear()
        pw_el.send_keys(password)
        driver.find_element(By.ID, "loginBtn").click()
        time.sleep(1.5)
        dismiss_alert_if_present(driver)
        try:
            login_btn_still = driver.find_elements(
                By.CSS_SELECTOR, 'span.topGrid[data-action="loginDivBtn"]'
            )
            if login_btn_still and login_btn_still[0].is_displayed():
                print("경고: 로그인이 안 된 것 같습니다 (아이디/비밀번호를 확인해주세요).")
                return False
        except Exception:
            pass
        print("로그인 완료(또는 시도됨) - 이어서 진행합니다.")
        return True
    except TimeoutException:
        print("경고: 로그인 창(아이디 입력란)을 찾지 못했습니다.")
        return False
    except Exception as e:
        print(f"로그인 시도 중 오류: {e}")
        return False


def set_field_value(driver, selector, value, label):
    try:
        existed = driver.execute_script("""
            const el = document.querySelector(arguments[0]);
            if (!el) return false;
            el.value = arguments[1];
            el.dispatchEvent(new Event('input', {bubbles: true}));
            el.dispatchEvent(new Event('change', {bubbles: true}));
            return true;
        """, selector, value)
        if existed:
            print(f"{label} 설정 완료: {value}")
        else:
            print(f"{label} 설정 실패: {selector} 요소를 페이지에서 찾을 수 없습니다.")
    except Exception as e:
        print(f"{label} 설정 중 오류 발생: {e}")


def set_radio_value(driver, name, value, label):
    try:
        existed = driver.execute_script("""
            const el = document.querySelector(
                'input[name="' + arguments[0] + '"][value="' + arguments[1] + '"]'
            );
            if (!el) return false;
            el.checked = true;
            el.dispatchEvent(new Event('click', {bubbles: true}));
            el.dispatchEvent(new Event('change', {bubbles: true}));
            return true;
        """, name, value)
        if existed:
            print(f"{label} 설정 완료: {value}")
        else:
            print(f"{label} 설정 실패: input[name={name}][value={value}] 요소를 찾을 수 없습니다.")
    except Exception as e:
        print(f"{label} 설정 중 오류 발생: {e}")


def set_checkbox_value(driver, selector, checked, label):
    try:
        existed = driver.execute_script("""
            const el = document.querySelector(arguments[0]);
            if (!el) return false;
            el.checked = arguments[1];
            el.dispatchEvent(new Event('click', {bubbles: true}));
            el.dispatchEvent(new Event('change', {bubbles: true}));
            return true;
        """, selector, checked)
        if existed:
            print(f"{label} 설정 완료: {'체크' if checked else '해제'}")
        else:
            print(f"{label} 설정 실패: {selector} 요소를 페이지에서 찾을 수 없습니다.")
    except Exception as e:
        print(f"{label} 설정 중 오류 발생: {e}")


def set_page_size(driver, size=LIST_PAGE_SIZE):
    set_field_value(driver, "#dataSize", str(size), f"목록 표시 개수({size}개씩 보기)")
    time.sleep(1.5)


def apply_filters(driver, minb_amt_end_value, ctgr_value=None):
    # (2026-09-18 추가) ctgr_value를 명시하지 않으면 기존처럼 CTGR_VALUE(기본 "토지")를
    # 쓴다 - "공장" 옵션 추가로 main()이 여러 물건종류를 순회하며 이 값을 바꿔 넘길 수
    # 있게 되었다(아래 CTGR_OPTIONS_CA/prompt_ctgr_mode_ca() 참고).
    set_field_value(driver, "#ctgr", ctgr_value if ctgr_value is not None else CTGR_VALUE, "물건종류")
    time.sleep(1.2)
    # (2026-09-18 추가) 이 파일은 "진행물건"(신건+유찰, select#stat value="11")만 수집하는
    # 전용 버전이다. 사이트 기본 선택값이 이미 "11"이라 지금까지는 이 필드를 건드리지
    # 않아도 결과가 같았지만, 코드를 '진행물건 전용'/'매각전부 전용' 두 파일로 명확히
    # 분리하면서 사이트의 기본값 변경에 흔들리지 않도록 명시적으로 설정해둔다.
    set_field_value(driver, "#stat", "11", "진행상태(진행물건)")
    time.sleep(1.0)
    set_field_value(driver, "#bgnDt", start_date_str, "매각기일 시작일")
    time.sleep(1.2)
    set_field_value(driver, "#endDt", end_date_str, "매각기일 종료일")
    time.sleep(1.2)
    # (2026-09-07 변경) 감정가격(#apslAmtEnd) 단일 상한 대신, 최저가격 범위
    # (#minbAmtBgn ~ #minbAmtEnd) 기준으로 필터링한다. 하한(minbAmtBgn)은 항상
    # "선택"(0, 하한 없음)으로 두고 상한(minbAmtEnd)만 사용자가 입력한 값으로 설정
    # -> 결과적으로 "최저가격 {minb_amt_end_value}원 이하" 필터가 된다.
    # (2026-10-04) 공장/근린상가 전용: 하한을 "0"(선택안함) 대신 3억 고정값으로 바꿔
    # "최저가격 3억~{상한}원" 범위 필터가 되게 한다. 하한은 프롬프트로 물어보지 않는다.
    set_field_value(driver, "#minbAmtBgn", str(DEFAULT_MINB_AMT_BGN), "최저가격 하한(3억 고정)")
    time.sleep(1.0)
    set_field_value(driver, "#minbAmtEnd", minb_amt_end_value, "최저가격 상한")
    time.sleep(2)


MULTI_PARCEL_PATTERN = re.compile(r'외\s*(\d+)\s*필지')


def is_multi_parcel(address: str) -> bool:
    return bool(MULTI_PARCEL_PATTERN.search(address or ""))


def collect_share_tids(driver, minb_amt_end_value, ctgr_value=None):
    apply_filters(driver, minb_amt_end_value, ctgr_value)
    wait_for_list(driver)
    set_checkbox_value(driver, '#chkSpl_121', True, "[사전조회] 지분입찰 물건 필터")
    time.sleep(1.5)
    wait_for_list(driver)
    set_page_size(driver)
    wait_for_list(driver)

    share_tids = set()
    page_num = 1
    while page_num <= MAX_PAGES:
        wait_for_list(driver)
        time.sleep(0.3)
        rows = get_rows(driver)
        if not rows:
            break
        prev_first_tid = rows[0].get_attribute("data-tid")
        for row in rows:
            tid = row.get_attribute("data-tid")
            if tid:
                share_tids.add(tid)
        next_page = page_num + 1
        if not go_to_page(driver, next_page, prev_first_tid):
            break
        page_num = next_page

    set_checkbox_value(driver, '#chkSpl_121', False, "[사전조회] 지분입찰 물건 필터")
    time.sleep(1.0)
    print(f"[사전조회] 지분 물건 Tid {len(share_tids)}개 확인 (팝업 방문 없이 목록만으로 수집)")
    return share_tids


def apply_filters_pa(driver, minb_amt_end_value, prptdvsn_value,
                      ctgr_select_value=None, ctgr_checkbox_selector=None):
    # (2026-10-04 변경) 공장/근린상가 전용: PA_CTGR_VALUE(토지) 고정 대신, 호출자가
    # 넘긴 물건종류 값/체크박스를 쓴다. select#ctgr와 체크박스(chkGrpCtgr_*/chkEaCtgr_*)
    # 중 실제로 검색에 반영되는 쪽이 라이브 테스트 전까지는 확실치 않아 둘 다 설정한다
    # (사용자가 직접 확인해준 체크박스 HTML 기준 - 공장="산업용및기타특수용건물" 그룹
    # 체크박스(그룹 클릭 시 하위 15개 항목이 함께 체크되는 걸로 보임)/근린상가="근린생활시설"
    # 리프 체크박스).
    set_field_value(driver, "#ctgr", ctgr_select_value if ctgr_select_value is not None else PA_CTGR_VALUE,
                     f"[{TYPE_B_LABEL}] 물건종류(select)")
    time.sleep(1.0)
    if ctgr_checkbox_selector:
        set_checkbox_value(driver, ctgr_checkbox_selector, True, f"[{TYPE_B_LABEL}] 물건종류(체크박스)")
        time.sleep(1.0)
    # (2026-09-18 추가, 가정) 경매(apply_filters)와 동일하게 "진행물건"(#stat value="11")을
    # 명시적으로 설정한다. 공매 화면도 같은 #stat ID를 쓸 것으로 가정했다(최저가격
    # 필드가 두 화면에서 동일 ID였던 전례 근거) - 아직 PA 화면 HTML로 직접 확인되지는
    # 않았다. 셀렉터가 없으면 set_field_value()가 오류 없이 로그만 남기고 넘어간다.
    set_field_value(driver, "#stat", "11", f"[{TYPE_B_LABEL}] 진행상태(진행물건)")
    time.sleep(1.0)
    set_field_value(driver, "#bgnDt", start_date_str, f"[{TYPE_B_LABEL}] 입찰일자 시작일")
    time.sleep(1.0)
    set_field_value(driver, "#clsDt", end_date_str, f"[{TYPE_B_LABEL}] 입찰일자 종료일")
    time.sleep(1.0)
    set_radio_value(driver, "dpslCd", "1", f"[{TYPE_B_LABEL}] 처분방식(매각)")
    time.sleep(1.0)
    set_field_value(driver, "#prptDvsn", prptdvsn_value, f"[{TYPE_B_LABEL}] 자산구분")
    time.sleep(1.0)
    # (2026-10-04 변경) 경매(apply_filters)와 동일하게 하한을 3억 고정값으로.
    set_field_value(driver, "#minbAmtBgn", str(DEFAULT_MINB_AMT_BGN), f"[{TYPE_B_LABEL}] 최저가격 하한(3억 고정)")
    time.sleep(1.0)
    set_field_value(driver, "#minbAmtEnd", str(minb_amt_end_value), f"[{TYPE_B_LABEL}] 최저가격 상한")
    time.sleep(2.0)


def wait_for_list(driver, timeout=15):
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.ID, "lsTbody"))
    )


def get_rows(driver):
    return driver.find_elements(By.CSS_SELECTOR, "#lsTbody > tr[data-tid]")


def get_first_tid(driver):
    rows = get_rows(driver)
    return rows[0].get_attribute("data-tid") if rows else None


def extract_row(row, tid, chk_no=None, tot_no=None):
    try:
        try:
            addr_el = row.find_element(By.CSS_SELECTOR, f"#adrs_{tid}")
            주소 = (addr_el.get_attribute("textContent") or "").strip()
        except NoSuchElementException:
            주소 = ""

        try:
            sano_el = row.find_element(By.CSS_SELECTOR, f"#saNo_{tid}")
            raw = sano_el.get_attribute("textContent") or ""
            사건번호 = re.sub(r"\s+", " ", raw.split("지도")[0]).strip()
        except NoSuchElementException:
            사건번호 = ""

        try:
            ctgr_el = row.find_element(By.CSS_SELECTOR, f"#ctgr_{tid}")
            용도 = (ctgr_el.get_attribute("textContent") or "").strip()
        except NoSuchElementException:
            용도 = ""

        면적 = None
        try:
            area_spans = row.find_elements(By.CSS_SELECTOR, "div.gray.f12 span.gray")
            area_text = " ".join((s.get_attribute("textContent") or "") for s in area_spans)
            m = re.search(r"토지\s*([\d,\.]+)\s*㎡", area_text) or re.search(r"건물\s*([\d,\.]+)\s*㎡", area_text)
            if m:
                면적 = float(m.group(1).replace(",", ""))
        except Exception:
            pass

        # (2026-10-04 추가) 위 '면적'은 토지 텍스트가 있으면 토지를, 없을 때만 건물을
        # 집어서(or 단축평가) 공장/근린상가처럼 토지+건물이 함께 나오는 물건에선 토지
        # 면적이 잡힌다. 건물면적 상한 필터는 반드시 "건물" 텍스트만 따로 다시 찾는다.
        건물면적_평 = None
        try:
            area_spans2 = row.find_elements(By.CSS_SELECTOR, "div.gray.f12 span.gray")
            area_text2 = " ".join((s.get_attribute("textContent") or "") for s in area_spans2)
            m_bld = re.search(r"건물\s*([\d,\.]+)\s*㎡", area_text2)
            if m_bld:
                건물면적_평 = round(float(m_bld.group(1).replace(",", "")) / PYEONG_SQM, 2)
        except Exception:
            pass

        참고사항 = "-"
        try:
            note_els = row.find_elements(By.CSS_SELECTOR, "div.f12 span.orange.f12")
            note_text = (note_els[0].get_attribute("textContent") or "").strip() if note_els else ""
            if note_text:
                참고사항 = note_text
        except Exception:
            pass

        감평가 = None
        최저가 = None
        try:
            apsl_el = row.find_element(By.CSS_SELECTOR, f"#apslAmt_{tid}")
            v = (apsl_el.text or "").replace(",", "").strip()
            감평가 = int(v) if v.isdigit() else None
        except NoSuchElementException:
            pass
        try:
            minb_el = row.find_element(By.CSS_SELECTOR, f"#minbAmt_{tid}")
            v = (minb_el.text or "").replace(",", "").strip()
            최저가 = int(v) if v.isdigit() else None
        except NoSuchElementException:
            pass

        진행상태 = ""
        유찰횟수 = 0
        try:
            stat_el = row.find_element(By.CSS_SELECTOR, f"td.center.no-950 #statNm_{tid}")
            진행상태 = (stat_el.get_attribute("textContent") or stat_el.text or "").strip()
            m2 = re.search(r"유찰\s*(\d+)\s*회", 진행상태)
            유찰횟수 = int(m2.group(1)) if m2 else 0
        except NoSuchElementException:
            pass

        최저가율 = None
        try:
            rate_el = row.find_element(By.CSS_SELECTOR, f"td.center.no-950 #statNm_{tid} + div")
            rate_text = (rate_el.get_attribute("textContent") or rate_el.text or "")
            rate_match = re.search(r"\d+", rate_text)
            최저가율 = int(rate_match.group(0)) if rate_match else None
        except NoSuchElementException:
            pass

        입찰일 = None
        try:
            date_el = row.find_element(By.CSS_SELECTOR, f"td.center.no-950 #bidDt_{tid}")
            raw_date = date_el.text.strip()
            time_el = row.find_element(By.CSS_SELECTOR, f"td.center.no-950 #bidDt_{tid} + div")
            raw_time = time_el.text.strip().strip("()")
            yy, mm, dd = raw_date.split(".")
            hh, mi = raw_time.split(":")
            입찰일 = datetime(2000 + int(yy), int(mm), int(dd), int(hh), int(mi))
        except Exception:
            pass

        신규여부 = "신건" if 유찰횟수 == 0 else "기존물건"
        지분여부 = "지분" if "지분" in 참고사항 else ""

        상세페이지 = ""
        if chk_no is not None and tot_no is not None:
            상세페이지 = f"{SITE_BASE}/ca/caView.php?tid={tid}&chkNo={chk_no}&TotNo={tot_no}"

        필지별주소 = ""
        pnu = ""
        토지이용계획 = ""
        소유자 = ""
        키워드 = ""

        return [
            TYPE_A_LABEL, 사건번호, 주소, 참고사항, 용도, 면적, 진행상태, 최저가율,
            최저가, 감평가, 입찰일, 상세페이지, 신규여부, 지분여부,
            필지별주소, pnu, 토지이용계획, 소유자, 키워드,
            건물면적_평,  # (2026-10-04 추가) 맨 뒤에만 추가 - 기존 인덱스(data[13]/data[14] 등) 불변
        ]
    except Exception as e:
        print(f"[tid={tid}] 데이터 추출 중 오류 발생: {e}")
        return None


def resolve_pa_year(mm, dd, reference_date):
    year = reference_date.year
    try:
        candidate = datetime(year, mm, dd)
    except ValueError:
        return None
    if candidate < reference_date - timedelta(days=30):
        candidate = datetime(year + 1, mm, dd)
    return candidate


def extract_row_pa(row, tid, chk_no=None, tot_no=None):
    try:
        try:
            mgmt_el = row.find_element(By.CSS_SELECTOR, f"#mgmtNo_{tid}")
            raw = mgmt_el.get_attribute("textContent") or ""
            m0 = re.search(r"\d{4}-\d+-\d+", raw)
            사건번호 = m0.group(0) if m0 else re.sub(r"\s+", " ", raw).strip()
        except NoSuchElementException:
            사건번호 = ""

        try:
            addr_el = row.find_element(By.CSS_SELECTOR, f"#cltrNm_{tid}")
            주소 = (addr_el.get_attribute("textContent") or "").strip()
        except NoSuchElementException:
            주소 = ""

        try:
            ctgr_el = row.find_element(By.CSS_SELECTOR, f"#ctgr_{tid}")
            용도 = (ctgr_el.get_attribute("textContent") or "").strip()
        except NoSuchElementException:
            용도 = ""

        면적 = None
        건물면적_평 = None
        try:
            area_el = row.find_element(By.CSS_SELECTOR, f"#area_{tid}")
            area_text = area_el.get_attribute("textContent") or ""
            m1 = re.search(r"토지\s*([\d,\.]+)\s*㎡", area_text)
            if m1:
                면적 = float(m1.group(1).replace(",", ""))
            # (2026-10-04 추가) 건물면적 상한 필터용 - CA와 동일하게 "건물" 텍스트만 따로 추출
            m_bld = re.search(r"건물\s*([\d,\.]+)\s*㎡", area_text)
            if m_bld:
                건물면적_평 = round(float(m_bld.group(1).replace(",", "")) / PYEONG_SQM, 2)
        except NoSuchElementException:
            pass

        참고사항 = "-"
        try:
            note_els = row.find_elements(By.CSS_SELECTOR, "span.orange.f12")
            note_text = (note_els[0].get_attribute("textContent") or "").strip() if note_els else ""
            if note_text:
                참고사항 = note_text
        except Exception:
            pass

        감평가 = None
        try:
            apsl_el = row.find_element(By.CSS_SELECTOR, f"td.right.bold.no-950 #apslAmt_{tid}")
            v = re.sub(r"[^\d]", "", apsl_el.get_attribute("textContent") or "")
            감평가 = int(v) if v else None
        except NoSuchElementException:
            pass

        최저가 = None
        try:
            minb_el = row.find_element(By.CSS_SELECTOR, f"td.right.bold.no-950 #minbAmt_{tid}")
            v = re.sub(r"[^\d]", "", minb_el.get_attribute("textContent") or "")
            최저가 = int(v) if v else None
        except NoSuchElementException:
            pass

        진행상태 = ""
        유찰횟수 = 0
        try:
            stat_el = row.find_element(By.CSS_SELECTOR, f"td.center.no-950 #statNm_{tid}")
            진행상태 = (stat_el.get_attribute("textContent") or "").strip()
            m2 = re.search(r"유찰\s*(\d+)\s*회", 진행상태)
            유찰횟수 = int(m2.group(1)) if m2 else 0
        except NoSuchElementException:
            pass

        최저가율 = None
        try:
            rate_el = row.find_element(By.CSS_SELECTOR, f"td.center.no-950 #statNm_{tid} ~ span.blue")
            rate_text = rate_el.get_attribute("textContent") or ""
            rate_match = re.search(r"\d+", rate_text)
            최저가율 = int(rate_match.group(0)) if rate_match else None
        except NoSuchElementException:
            pass

        입찰일 = None
        try:
            date_el = row.find_element(By.CSS_SELECTOR, f"td.center.no-950 #bgnDtm_{tid}")
            raw_dt = (date_el.get_attribute("textContent") or "").strip()
            m3 = re.match(r"(\d{2})\.(\d{2})\s+(\d{2}):(\d{2})", raw_dt)
            if m3:
                mm, dd, hh, mi = (int(x) for x in m3.groups())
                candidate = resolve_pa_year(mm, dd, 오늘)
                if candidate:
                    입찰일 = candidate.replace(hour=hh, minute=mi)
        except Exception:
            pass

        신규여부 = "신건" if 유찰횟수 == 0 else "기존물건"
        지분여부 = "지분" if "지분" in 참고사항 else ""

        상세페이지 = ""
        if chk_no is not None and tot_no is not None:
            상세페이지 = f"{SITE_BASE}/pa/paView.php?cltrNo={tid}&chkNo={chk_no}&TotNo={tot_no}"

        필지별주소 = ""
        pnu = ""
        토지이용계획 = ""
        소유자 = ""
        키워드 = ""

        return [
            TYPE_B_LABEL, 사건번호, 주소, 참고사항, 용도, 면적, 진행상태, 최저가율,
            최저가, 감평가, 입찰일, 상세페이지, 신규여부, 지분여부,
            필지별주소, pnu, 토지이용계획, 소유자, 키워드,
            건물면적_평,  # (2026-10-04 추가) extract_row()와 동일하게 맨 뒤에만 추가
        ]
    except Exception as e:
        print(f"[{TYPE_B_LABEL}][tid={tid}] 데이터 추출 중 오류 발생: {e}")
        return None


def build_requests_session(driver):
    session = requests.Session()
    try:
        ua = driver.execute_script("return navigator.userAgent;")
    except Exception:
        ua = "Mozilla/5.0"
    session.headers.update({"User-Agent": ua, "Referer": BASE_URL})
    sync_session_cookies(driver, session)
    return session


def sync_session_cookies(driver, session):
    for c in driver.get_cookies():
        try:
            session.cookies.set(c["name"], c["value"], domain=c.get("domain"))
        except Exception:
            pass


def open_detail_tab(driver, detail_url, tid=None):
    original_handle = driver.current_window_handle
    driver.execute_script("window.open(arguments[0], '_blank');", detail_url)
    try:
        WebDriverWait(driver, 10).until(lambda d: len(d.window_handles) > 1)
    except UnexpectedAlertPresentException:
        text = dismiss_alert_if_present(driver, tid)
        print(f"  [tid={tid}] 새 탭이 열리기 전에 알림창 발생({text}) - 로그인 상태를 확인해주세요.")
        return None, ""
    except Exception as e:
        print(f"  [tid={tid}] 상세페이지 탭을 여는 중 오류: {e}")
        return None, ""

    new_handle = [h for h in driver.window_handles if h != original_handle][-1]
    driver.switch_to.window(new_handle)

    html = ""
    try:
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        time.sleep(0.8)
        html = driver.page_source
    except UnexpectedAlertPresentException:
        text = dismiss_alert_if_present(driver, tid)
        print(f"  [tid={tid}] 상세페이지 로딩 중 알림창 발생({text}) - 로그인 상태를 확인해주세요.")
    except Exception as e:
        print(f"  [tid={tid}] 상세페이지 로드 중 오류: {e}")

    return new_handle, html


def close_detail_tab(driver, handle, original_handle, tid=None):
    dismiss_alert_if_present(driver, tid)
    try:
        if handle and handle in driver.window_handles:
            driver.switch_to.window(handle)
            driver.close()
    except Exception:
        pass
    try:
        if original_handle in driver.window_handles:
            driver.switch_to.window(original_handle)
        elif driver.window_handles:
            driver.switch_to.window(driver.window_handles[0])
    except Exception:
        pass


def build_pdf_viewer_url(data_param):
    if not data_param:
        return None
    path = data_param if data_param.startswith("/") else "/" + data_param
    return SITE_BASE + path


def extract_raw_pdf_url(data_param):
    if not data_param:
        return None
    m = re.search(r"[?&]file=([^&]+)", data_param)
    if not m:
        return None
    file_path = m.group(1)
    if not file_path.startswith("/"):
        file_path = "/" + file_path
    return SITE_BASE + file_path


def click_registry_pdf_link(driver, detail_tab_handle, tid=None, timeout=10):
    try:
        link = driver.find_element(By.CSS_SELECTOR, 'a.btn-fileView[data-ctgr="DA"]')
    except NoSuchElementException:
        print(f"  [tid={tid}] 상세페이지에서 토지등기(DA) 링크를 찾지 못했습니다.")
        return None

    before_handles = set(driver.window_handles)
    try:
        driver.execute_script("arguments[0].click();", link)
    except UnexpectedAlertPresentException:
        text = dismiss_alert_if_present(driver, tid)
        print(f"  [tid={tid}] 토지등기 링크 클릭 중 알림창 발생({text})")
        return None
    except Exception as e:
        print(f"  [tid={tid}] 토지등기 링크 클릭 중 오류: {e}")
        return None

    pdf_url = None
    new_handle = None
    try:
        WebDriverWait(driver, timeout).until(lambda d: len(d.window_handles) > len(before_handles))
        new_handle = [h for h in driver.window_handles if h not in before_handles][-1]
        driver.switch_to.window(new_handle)
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        time.sleep(1.0)
        viewer_html = driver.page_source
        soup = BeautifulSoup(viewer_html, "html.parser")
        da_el = soup.select_one('div.file_menu.fileView[data-ctgr="DA"]')
        if da_el and da_el.get("data-param"):
            data_param = da_el["data-param"]
            pdf_url = extract_raw_pdf_url(data_param)
            if pdf_url:
                print(f"  [tid={tid}] 토지등기 팝업에서 실제 PDF 원본 URL 확인: {pdf_url}")
            else:
                pdf_url = build_pdf_viewer_url(data_param)
                print(f"  [tid={tid}] data-param에서 file= 파라미터를 못 찾아 뷰어 URL을 대신 사용: {pdf_url}")
        else:
            pdf_url = driver.current_url
            print(f"  [tid={tid}] 토지등기 팝업에서 data-param을 못 찾아 탭 URL을 그대로 사용: {pdf_url}")
    except UnexpectedAlertPresentException:
        text = dismiss_alert_if_present(driver, tid)
        print(f"  [tid={tid}] 토지등기 PDF 탭 로딩 중 알림창 발생({text})")
    except Exception as e:
        print(f"  [tid={tid}] 토지등기 링크 클릭 후 팝업 확인 중 오류: {e}")
    finally:
        dismiss_alert_if_present(driver, tid)
        try:
            if new_handle and new_handle in driver.window_handles:
                driver.switch_to.window(new_handle)
                driver.close()
        except Exception:
            pass
        try:
            if detail_tab_handle in driver.window_handles:
                driver.switch_to.window(detail_tab_handle)
            elif driver.window_handles:
                driver.switch_to.window(driver.window_handles[0])
        except Exception:
            pass

    return pdf_url


def download_pdf(session, pdf_url):
    try:
        resp = session.get(pdf_url, timeout=20)
        resp.raise_for_status()
        ctype = resp.headers.get("Content-Type", "").lower()
        if "pdf" in ctype or pdf_url.lower().endswith(".pdf"):
            return resp.content
        print(f"  PDF가 아닌 응답입니다: {pdf_url} (Content-Type={ctype})")
        return None
    except Exception as e:
        print(f"  PDF 다운로드 실패 ({pdf_url}): {e}")
        return None


def fetch_pdf_bytes_via_browser(driver, pdf_url, tid=None, timeout=25):
    driver.set_script_timeout(timeout)
    script = """
    var url = arguments[0];
    var callback = arguments[arguments.length - 1];
    fetch(url, {credentials: 'include'})
      .then(function(r) {
        var ctype = (r.headers.get('Content-Type') || '').toLowerCase();
        return r.arrayBuffer().then(function(buf) { return {ctype: ctype, buf: buf}; });
      })
      .then(function(result) {
        var bytes = new Uint8Array(result.buf);
        var binary = '';
        var chunk = 0x8000;
        for (var i = 0; i < bytes.length; i += chunk) {
          binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
        }
        callback({ok: true, ctype: result.ctype, b64: btoa(binary)});
      })
      .catch(function(err) { callback({ok: false, error: String(err)}); });
    """
    try:
        result = driver.execute_async_script(script, pdf_url)
    except Exception as e:
        print(f"  [tid={tid}] 브라우저 fetch()로 PDF 요청 중 오류: {e}")
        return None

    if not result or not result.get("ok"):
        print(f"  [tid={tid}] 브라우저 fetch() 실패: {result.get('error') if result else '응답 없음'}")
        return None

    ctype = result.get("ctype", "")
    try:
        pdf_bytes = base64.b64decode(result["b64"])
    except Exception as e:
        print(f"  [tid={tid}] PDF base64 디코딩 실패: {e}")
        return None

    if not pdf_bytes.startswith(b"%PDF"):
        preview = pdf_bytes[:200].decode("utf-8", errors="replace").strip()
        print(f"  [tid={tid}] PDF가 아닌 응답입니다 (Content-Type={ctype}, %PDF로 시작하지 않음). "
              f"응답 앞부분: {preview!r}")
        return None

    return pdf_bytes


def extract_registry_summary_from_pdf(pdf_bytes):
    if not pdf_bytes or pdfplumber is None:
        return ""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            if not pdf.pages:
                return ""
            page_texts = [(page.extract_text() or "") for page in pdf.pages]
    except Exception as e:
        print(f"  토지등기 PDF 파싱 오류: {e}")
        return ""

    summary_start_idx = None
    for i, t in enumerate(page_texts):
        if "주요 등기사항 요약" in t:
            summary_start_idx = i
            break

    if summary_start_idx is not None:
        full_text = "\n".join(page_texts[summary_start_idx:]).strip()
    else:
        full_text = page_texts[-1].strip()

    m = re.search(
        r"1\.\s*소유지분현황.*?(?=2\.\s*소유지분을\s*제외한|\Z)",
        full_text,
        re.DOTALL,
    )
    if m:
        return m.group(0).strip()
    return full_text


def extract_parcel_texts(soup):
    parcels = []
    rows_tbody = soup.select_one("table.ViewTbl tbody.rowsTbody")
    if not rows_tbody:
        return parcels
    for tr in rows_tbody.find_all("tr"):
        first_td = tr.find("td")
        if not first_td:
            continue
        first_div = first_td.find("div")
        if not first_div:
            continue
        raw = first_div.get_text(separator=" ", strip=True)
        parcel = raw.split("[")[0].strip()
        if parcel:
            parcels.append(parcel)
    return parcels


def build_full_parcel_address(base_address, parcel_text):
    if not base_address or not parcel_text:
        return parcel_text or base_address or ""
    primary = re.sub(r"\s*외\s*\d+\s*필지\s*$", "", base_address).strip()
    prefix = re.sub(r"\S*(동|리|가)\s*(산)?\d+(-\d+)?\s*$", "", primary).strip()
    if prefix:
        return f"{prefix} {parcel_text}".strip()
    return parcel_text


def extract_notes_from_detail(soup):
    parts = []
    for tr in soup.select("table.ViewTbl tr"):
        th = tr.find("th")
        td = tr.find("td")
        if not th or not td:
            continue
        label = th.get_text(separator=" ", strip=True)
        if ("현황" in label and "위치" in label) or label == "참고사항":
            for mobile_span in td.select("span.mobileTitle, span.show-mobile"):
                mobile_span.decompose()
            text = td.get_text(separator="\n", strip=True)
            if text:
                parts.append(f"[{label}]\n{text}")
    return "\n\n".join(parts)


def extract_sale_object_type(soup):
    for th in soup.find_all("th"):
        if th.get_text(strip=True) == "매각물건":
            td = th.find_next_sibling("td")
            if td:
                td_copy = BeautifulSoup(str(td), "html.parser")
                for mobile_span in td_copy.select("span.mobileTitle, span.show-mobile"):
                    mobile_span.decompose()
                return td_copy.get_text(strip=True)
    return ""


def extract_parcel_rows_pa(soup):
    target_table = None
    for table in soup.find_all("table"):
        header_cells = [th.get_text(strip=True) for th in table.find_all("th")]
        if "번호" in header_cells and "종별(지목)" in header_cells and "비고" in header_cells:
            target_table = table
            break
    if target_table is None:
        return []

    rows = []
    for tr in target_table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue
        share_col_text = tds[3].get_text(separator=" ", strip=True)
        remark_text = tds[4].get_text(strip=True)
        if not share_col_text and not remark_text:
            continue
        rows.append((share_col_text, remark_text))
    return rows


def is_pa_share_parcel(share_col_text, remark_text=""):
    combined = f"{share_col_text or ''} {remark_text or ''}"
    return ("지분" in combined) or ("분의" in combined)


def extract_notes_from_detail_pa(soup):
    LABELS_TO_INCLUDE = ("이용현황", "기타")
    parts = []
    for tr in soup.select("table.ViewTbl tr"):
        th = tr.find("th")
        td = tr.find("td")
        if not th or not td:
            continue
        label = th.get_text(strip=True)
        if label in LABELS_TO_INCLUDE:
            text = td.get_text(separator="\n", strip=True)
            if text:
                parts.append(f"[{label}]\n{text}")
    return "\n\n".join(parts)


def extract_pa_pdf_url(soup):
    candidates = soup.select("a.btn-fileView[data-filelink]")
    link = None
    for c in candidates:
        if "토지등기" in c.get_text(strip=True):
            link = c
            break
    if link is None:
        for c in candidates:
            if "tp=I" in (c.get("data-filelink") or ""):
                link = c
                break
    if not link:
        return None
    filelink = (link.get("data-filelink") or "").strip()
    if not filelink:
        return None
    query_str = filelink.split("?", 1)[1] if "?" in filelink else ""
    qs = parse_qs(query_str)
    file_path_vals = qs.get("filePath")
    if file_path_vals and file_path_vals[0]:
        raw_path = unquote(file_path_vals[0])
        if not raw_path.startswith("/"):
            raw_path = "/" + raw_path
        return SITE_BASE + raw_path
    if filelink.startswith("http"):
        return filelink
    path = filelink if filelink.startswith("/") else "/pa/" + filelink
    return SITE_BASE + path


def build_pa_parcel_addresses(base_address, parcel_texts, category=None):
    addr = base_address or ""
    if category and addr.endswith(category):
        addr = addr[: -len(category)].strip()
    addr = re.sub(r"\s*외\s*\d+\s*필지\s*$", "", addr).strip()
    prefix = ""
    for p in parcel_texts:
        if p and addr.endswith(p):
            prefix = addr[: -len(p)].strip()
            break
    return [f"{prefix} {p}".strip() if prefix else p for p in parcel_texts]


def split_multi_parcel_address_pa(base_address, category=None):
    addr = (base_address or "").strip()
    if category and addr.endswith(category):
        addr = addr[: -len(category)].strip()
    if not addr:
        return []
    if "," not in addr:
        return [addr]
    parts = [p.strip() for p in addr.split(",") if p.strip()]
    if len(parts) < 2:
        return [addr]
    m = re.search(r"(산?\d+(?:-\d+)?)\s*$", parts[0])
    if not m:
        return [addr]
    prefix = parts[0][: m.start()].strip()
    first_parcel = m.group(1)
    result = [f"{prefix} {first_parcel}".strip() if prefix else first_parcel]
    for p in parts[1:]:
        if re.fullmatch(r"산?\d+(?:-\d+)?", p):
            result.append(f"{prefix} {p}".strip() if prefix else p)
        else:
            result.append(p)
    return result


def fetch_detail_info_pa(driver, tid, chk_no, tot_no):
    detail_url = f"{SITE_BASE}/pa/paView.php?cltrNo={tid}&chkNo={chk_no}&TotNo={tot_no}"
    parcel_texts = []
    notes_text = ""
    토지등기_요약 = ""
    지분여부 = ""

    original_handle = driver.current_window_handle
    detail_handle = None
    try:
        time.sleep(random.uniform(*DETAIL_PAGE_DELAY))
        detail_handle, html = open_detail_tab(driver, detail_url, tid=tid)
        if not detail_handle:
            return parcel_texts, notes_text, 토지등기_요약, 지분여부

        print(f"  [{TYPE_B_LABEL}][tid={tid}] 상세페이지(브라우저 탭) 로드 완료, 길이 {len(html)}자")
        soup = BeautifulSoup(html, "html.parser")

        parcel_rows = extract_parcel_rows_pa(soup)
        if parcel_rows:
            is_jibun = any(is_pa_share_parcel(share, remark) for share, remark in parcel_rows)
            parcel_texts = [
                remark for share, remark in parcel_rows
                if remark and not is_pa_share_parcel(share, remark)
            ]
        else:
            print(f"  [{TYPE_B_LABEL}][tid={tid}] 필지별 표를 찾지 못했습니다.")
            is_jibun = False

        지분여부 = "지분" if is_jibun else ""
        print(f"  [{TYPE_B_LABEL}][tid={tid}] 필지 {len(parcel_rows)}개, 지분여부={'지분' if is_jibun else '아님'}")

        notes_text = extract_notes_from_detail_pa(soup)

        if is_jibun:
            pdf_url = extract_pa_pdf_url(soup)
            if pdf_url:
                print(f"  [{TYPE_B_LABEL}][tid={tid}] 토지등기 PDF URL 확인: {pdf_url}")
                time.sleep(random.uniform(*PDF_DOWNLOAD_DELAY))
                pdf_bytes = fetch_pdf_bytes_via_browser(driver, pdf_url, tid=tid)
                if pdf_bytes:
                    print(f"  [{TYPE_B_LABEL}][tid={tid}] 토지등기 PDF 다운로드 완료 ({len(pdf_bytes)} bytes)")
                    토지등기_요약 = extract_registry_summary_from_pdf(pdf_bytes)
                    if not 토지등기_요약:
                        print(f"  [{TYPE_B_LABEL}][tid={tid}] 토지등기 PDF에서 텍스트를 추출하지 못했습니다.")
                else:
                    print(f"  [{TYPE_B_LABEL}][tid={tid}] 토지등기 PDF 다운로드 실패 (URL: {pdf_url})")
            else:
                print(f"  [{TYPE_B_LABEL}][tid={tid}] 지분 물건인데 토지등기 PDF 링크(data-filelink)를 찾지 못했습니다.")

    except Exception as e:
        print(f"[{TYPE_B_LABEL}][tid={tid}] 상세페이지 처리 중 오류: {e}")
    finally:
        close_detail_tab(driver, detail_handle, original_handle, tid=tid)

    return parcel_texts, notes_text, 토지등기_요약, 지분여부


# =================== 등기부 근저당권/청구금액 상세 (2026-10-04, 공장매각완.py에서 포팅) ===================
# 사용자 요청: 공장/근린상가는 (1) 등기부_근저당권설정에서 건물/토지 구분 때문에 중복
# 기재되는 항목을 한 번만 남기고, 말소기준 근저당권설정과 같은 권리자의 다른 근저당권설정
# 금액을 합산해 권리자당 한 줄로 표시 + 합계금액을 별도 열에 기록, (2) 등기부_청구금액도
# 같은 이유로 중복 제거 + 권리자명에 "유동화전문"이 포함된 항목만 합산해 별도 열에 기록.
# 아래 함수들은 공장매각완.py 원본 구현을 그대로 가져온 것이다(로직 변경 없음).

def _td_clean_text(td):
    """<td> 안의 모바일 전용 라벨(span.mobileTitle)/버튼(도로명 검색 등)을 뺀 순수 값 텍스트."""
    if td is None:
        return ""
    td_copy = copy.deepcopy(td)
    for sel in ("span.mobileTitle", "span.button", "span.btn_small"):
        for el in td_copy.select(sel):
            el.decompose()
    return td_copy.get_text(" ", strip=True)


def _pair_th_td_texts(table):
    """기본정보 표(ViewTblBase)처럼 <th><td> 쌍이 한 행에 여러 번 나오는 표를
    {th텍스트: td텍스트} 딕셔너리로 만든다."""
    result = {}
    if table is None:
        return result
    for row in table.find_all("tr"):
        cells = row.find_all(["th", "td"])
        i = 0
        while i < len(cells):
            if cells[i].name == "th":
                label = cells[i].get_text(strip=True)
                td = cells[i + 1] if i + 1 < len(cells) and cells[i + 1].name == "td" else None
                if label:
                    result[label] = _td_clean_text(td)
                i += 2
            else:
                i += 1
    return result


def _extract_amount(text):
    """'(49%) 144,219,000' / '294,326,500' 같은 텍스트에서 마지막 숫자만 뽑아 int로."""
    if not text:
        return None
    nums = re.findall(r"[\d,]+", text)
    if not nums:
        return None
    v = nums[-1].replace(",", "")
    return int(v) if v.isdigit() else None


def extract_base_info_from_detail(soup):
    """상세페이지 상단 '기본정보' 표에서 물건번호/매각일자/소재지/개시결정/감정가/
    토지면적/건물면적/최저가/매각가를 추출한다."""
    info = {
        "사건번호": "", "매각일자": "", "소재지": "", "개시결정": "",
        "감정가": None, "토지면적": "", "건물면적": "", "최저가": None, "매각가": None,
    }
    try:
        case_el = soup.select_one("#lyCnt_num .viewtitle span.f20.bold_900")
        if case_el:
            info["사건번호"] = case_el.get_text(strip=True)

        sale_date_el = soup.select_one("#lyCnt_num .viewtitle span.spanBox span.bold")
        if sale_date_el:
            info["매각일자"] = sale_date_el.get_text(strip=True)

        base_table = soup.select_one("#lyCnt_base table.ViewTblBase")
        pairs = _pair_th_td_texts(base_table)
        info["소재지"] = pairs.get("소재지", "")
        info["개시결정"] = pairs.get("개시결정", "")
        info["토지면적"] = pairs.get("토지면적", "")
        info["건물면적"] = pairs.get("건물면적", "")
        info["감정가"] = _extract_amount(pairs.get("감정가"))
        info["최저가"] = _extract_amount(pairs.get("최저가"))
        info["매각가"] = _extract_amount(pairs.get("매각가"))
    except Exception as e:
        print(f"[상세정보] 기본정보 추출 중 오류: {e}")
    return info


def extract_bid_history_from_detail(soup):
    """'입찰 진행 내용' 표(#hist_tb)에서 회차별(1차/2차/... , 변경 포함) 매각기일/
    최저매각가격/결과만 뽑는다(낙찰가·입찰인수 등 요약 행(class="his_Old")은 제외)."""
    rows_out = []
    try:
        hist_tb = soup.select_one("table.ViewTbl tbody#hist_tb")
        if hist_tb is None:
            return rows_out
        for tr in hist_tb.select("tr.hist_tr.no-detail"):
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            회차 = tds[0].get_text(strip=True)
            매각기일 = tds[1].get_text(strip=True)
            최저매각가격 = tds[2].get_text(strip=True)
            결과 = tds[3].get_text(strip=True)
            rows_out.append((회차, 매각기일, 최저매각가격, 결과))
    except Exception as e:
        print(f"[상세정보] 입찰진행내용 추출 중 오류: {e}")
    return rows_out


def format_bid_history(rows):
    parts = []
    for 회차, 매각기일, 최저가, 결과 in rows:
        label = 회차 if 회차 else "(변경)"
        seg = f"{label} {매각기일} {최저가}"
        if 결과:
            seg += f" {결과}"
        parts.append(seg)
    return " | ".join(parts)


def extract_registry_liens_from_detail(soup):
    """등기부 현황(건물/토지) 표에서
      1) 말소기준등기인 근저당권설정 + 같은 권리자의 다른 근저당권설정
      2) 채권금액란에 '청구금액'이 표시된 행(접수일/권리자/청구금액, 등기목적 무관)
    만 뽑는다. 소유권이전/가압류/압류 등 그 외 항목은 버린다."""
    liens = []   # (구분(건물/토지), 말소기준여부, 접수일, 권리자, 금액)
    claims = []  # (구분, 접수일, 권리자, 청구금액, 기타등기사항(관련사건 등))
    try:
        regist_box = soup.select_one("#lyCnt_regist")
        if regist_box is None:
            return liens, claims
        for dt_el in regist_box.select(".sectTitle dt"):
            heading = dt_el.get_text(strip=True)
            m = re.search(r"등기부\s*현황\((.+?)\)", heading)
            if not m:
                continue
            구분 = m.group(1)
            sect_div = dt_el.find_parent("div", class_="sectTitle")
            table = sect_div.find_next("table", class_="ViewTbl") if sect_div else None
            if table is None:
                continue

            data_trs = [tr for tr in table.find_all("tr") if tr.find("td")]

            marker_owners = set()
            for tr in data_trs:
                tds = tr.find_all("td")
                if len(tds) < 6:
                    continue
                등기목적 = tds[1].get_text(strip=True)
                권리자 = tds[2].get_text(strip=True)
                기타등기사항 = tds[4].get_text(" ", strip=True)
                if 등기목적 == "근저당권설정" and "말소기준등기" in 기타등기사항:
                    marker_owners.add(권리자)

            for tr in data_trs:
                tds = tr.find_all("td")
                if len(tds) < 6:
                    continue
                접수일_raw = tds[0].get_text(" ", strip=True)
                접수일_m = re.search(r"\d{4}[.\-]\d{2}[.\-]\d{2}", 접수일_raw)
                접수일 = 접수일_m.group(0) if 접수일_m else 접수일_raw
                등기목적 = tds[1].get_text(strip=True)
                권리자 = tds[2].get_text(strip=True)
                채권금액_td = tds[3]
                기타등기사항 = tds[4].get_text(" ", strip=True)

                청구금액_divs = 채권금액_td.find_all("div")
                is_claim_row = any("청구금액" in d.get_text(strip=True) for d in 청구금액_divs)

                if 등기목적 == "근저당권설정" and 권리자 in marker_owners:
                    금액 = _extract_amount(채권금액_td.get_text(" ", strip=True))
                    말소기준 = "말소기준등기" in 기타등기사항
                    liens.append((구분, "말소기준" if 말소기준 else "", 접수일, 권리자, 금액))
                elif is_claim_row:
                    amt_text = 청구금액_divs[-1].get_text(strip=True) if 청구금액_divs else 채권금액_td.get_text(strip=True)
                    금액 = _extract_amount(amt_text)
                    claims.append((구분, 접수일, 권리자, 금액, 기타등기사항))
    except Exception as e:
        print(f"[상세정보] 등기부현황 추출 중 오류: {e}")
    return liens, claims


def dedup_registry_liens(liens):
    """등기부 현황이 건물/토지 등 여러 구분으로 나뉘어 있어도, 말소기준여부/접수일/권리자/
    금액이 모두 같으면 같은 근저당권을 구분만 다르게 중복 기재한 것이므로 한 번만 남긴다."""
    seen = set()
    deduped = []
    for 구분, 말소기준, 접수일, 권리자, 금액 in liens:
        key = (말소기준, 접수일, 권리자, 금액)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((구분, 말소기준, 접수일, 권리자, 금액))
    return deduped


def merge_registry_liens_by_owner(liens):
    """중복 제거된 근저당권설정 내역을 권리자(은행/유한회사 등) 기준으로 합산한다 - 같은
    권리자가 말소기준 근저당권설정과 그 외 추가 근저당권설정을 함께 가진 경우, 두 금액을
    하나로 더해 권리자당 한 줄로 만든다.
    반환값: (권리자별 합산 목록 [(권리자, 합산금액), ...], 전체 합계금액 또는 None)"""
    deduped = dedup_registry_liens(liens)
    totals = {}
    order = []
    for _, _, _, 권리자, 금액 in deduped:
        if 권리자 not in totals:
            totals[권리자] = 0
            order.append(권리자)
        totals[권리자] += (금액 or 0)
    merged = [(권리자, totals[권리자]) for 권리자 in order]
    grand_total = sum(totals.values()) if merged else None
    return merged, grand_total


def dedup_registry_claims(claims):
    """청구금액 내역도 근저당권설정과 마찬가지로 건물/토지 구분 때문에 같은 내용이 중복
    기재되므로, 접수일/권리자/금액/기타등기사항이 모두 같으면 한 번만 남긴다."""
    seen = set()
    deduped = []
    for 구분, 접수일, 권리자, 금액, 기타등기사항 in claims:
        key = (접수일, 권리자, 금액, 기타등기사항)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((구분, 접수일, 권리자, 금액, 기타등기사항))
    return deduped


def sum_yudonghwa_claims(claims):
    """청구금액 중 권리자명에 '유동화전문'이 포함된 항목(자산유동화전문 유한회사 등)만
    골라 금액을 합산한다. 해당 항목이 없으면 None을 반환한다."""
    total = 0
    found = False
    for _, _, 권리자, 금액, _ in claims:
        if 권리자 and "유동화전문" in 권리자:
            total += (금액 or 0)
            found = True
    return total if found else None


def format_registry_liens(merged_liens):
    """merge_registry_liens_by_owner()가 반환한 권리자별 합산 목록을 문자열로 표시한다."""
    parts = []
    for 권리자, 금액 in merged_liens:
        amt = f"{금액:,}" if 금액 is not None else ""
        parts.append(f"근저당권설정(말소기준) {권리자} {amt}")
    return " | ".join(parts)


def format_registry_claims(claims):
    parts = []
    for 구분, 접수일, 권리자, 금액, 관련사항 in claims:
        amt = f"{금액:,}" if 금액 is not None else ""
        seg = f"[{구분}] {접수일} {권리자} 청구금액 {amt}"
        if 관련사항:
            seg += f" ({관련사항})"
        parts.append(seg)
    return " | ".join(parts)


# =================== 채권원금/연체이자 추정 (2026-10-04 3차 수정, 공장매각완.py에서 포팅) ===================
# 사용자 피드백: "매각 진행되는 물건도 채권원금은 추정하는 금액이다. 근저당권 금액을
# 1.1~1.5로 나눠 정수로 떨어지는 금액" - 이 추정 자체는 날짜와 무관(근저당권_합계금액만
# 있으면 계산 가능)하므로 진행 중인 물건에도 그대로 적용 가능하다(처음엔 "낙찰 전이라
# 안 맞는다"고 전부 뺐었는데, 채권원금 추정 부분은 애초에 날짜 의존이 아니었다).
# 연체이자/채권행사권리금액은 원래 "배당기일"이 있어야 계산되는데, 진행 중인 물건은
# 배당기일이 없으므로 사용자 요청대로 "이번 입찰기일 + 60일"을 기준일로 근사한다.

def _count_trailing_zeros(n):
    n = abs(int(n))
    if n == 0:
        return 0
    count = 0
    while n % 10 == 0:
        n //= 10
        count += 1
    return count


def estimate_registry_principal(total_amount):
    """근저당권_합계금액(등기부상 채권최고액 성격의 금액)을 PRINCIPAL_MULTIPLIERS(1.10~1.50,
    0.05 단위) 후보로 나눠봐서, 나머지 없이 딱 떨어지고 10만원 이상인 결과가 나오는 배수를
    찾아 그 몫을 채권원금으로 추정한다. 딱 떨어지는 후보가 여럿이면 결과 끝자리에 0이
    가장 많이 붙는("깨끗한") 후보를 채택하고, 그마저 동률이면 더 작은 배수를 우선한다.
    딱 떨어지는 후보가 하나도 없으면 None을 반환한다."""
    if not total_amount:
        return None
    scaled = int(total_amount) * 100  # 배수를 정수(x100)로 다뤄 부동소수점 오차를 피한다
    candidates = []
    for m in PRINCIPAL_MULTIPLIERS:
        if scaled % m != 0:
            continue
        quotient = scaled // m
        if quotient >= 100000:
            candidates.append((quotient, m))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-_count_trailing_zeros(item[0]), item[1]))
    return candidates[0][0]


def parse_date_prefix(text):
    """'2023-05-12' 또는 '2023-05-12(수)' 같은 문자열 앞의 YYYY-MM-DD만 뽑아 datetime으로
    (뒤에 다른 텍스트가 붙어 있어도 무시). 형식이 안 맞으면 None."""
    if not text:
        return None
    m = re.match(r"(\d{4}-\d{2}-\d{2})", text.strip())
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d")
    except ValueError:
        return None


def calc_reference_date(sale_date_text):
    """이자 계산 기준일 = 이번 입찰기일(매각일자) + REFERENCE_DAYS_AFTER_BID(60)일.
    아직 낙찰 전이라 실제 배당기일을 알 수 없어, 사용자 요청대로 근사한다."""
    bid_date = parse_date_prefix(sale_date_text)
    if bid_date is None:
        return None
    return bid_date + timedelta(days=REFERENCE_DAYS_AFTER_BID)


def calc_interest_overdue_days(reference_date, gaesi_gyeoljeong_text):
    """이자 연체일수 = 기준일(입찰기일+60일) - 개시결정(경매개시결정등기일).
    둘 중 하나라도 날짜를 못 읽으면 None."""
    if reference_date is None:
        return None
    gaesi = parse_date_prefix(gaesi_gyeoljeong_text)
    if gaesi is None:
        return None
    return (reference_date - gaesi).days


def calc_overdue_interest(principal, overdue_days):
    """예상연체이자 = 채권원금 * 연이자율(10%) / 365 * 이자 연체일수."""
    if principal is None or overdue_days is None:
        return None
    return principal * ANNUAL_INTEREST_RATE / 365 * overdue_days


def calc_claim_exercise_amount(claim_amount, overdue_interest):
    """채권행사권리금액 = 청구금액(유동화전문_청구금액) + 예상연체이자."""
    if claim_amount is None or overdue_interest is None:
        return None
    return claim_amount + overdue_interest


def fetch_registry_history_info(driver, tid, chk_no, tot_no):
    """caView.php 상세페이지를 방문해서 기본정보/입찰진행내용/등기부현황(근저당+청구금액)/
    채권원금 추정/예상연체이자/채권행사권리금액을 한 번에 추출한다. 지분 여부와 무관하게
    수집되는 모든 경매(TYPE_A) 물건에 대해 호출된다.
    (2026-10-04) 채권원금 추정은 날짜와 무관(근저당권_합계금액만 있으면 계산 가능)하므로
    진행 중인 물건에도 원본(공장매각완.py) 그대로 적용한다. 다만 원본의 배당기일(=마지막
    입찰회차=낙찰일 기준)은 아직 낙찰 전이라 쓸 수 없어, 사용자 요청대로 "이번 입찰기일
    (매각일자) + 60일"을 이자 계산 기준일로 근사해 연체이자/채권행사권리금액을 추정한다."""
    detail_url = f"{SITE_BASE}/ca/caView.php?tid={tid}&chkNo={chk_no}&TotNo={tot_no}"
    result = {
        "상세페이지": detail_url, "사건번호": "", "물건번호": "", "매각일자": "",
        "소재지": "", "개시결정": "", "감정가": None, "토지면적": "", "건물면적": "",
        "최저가": None,
        "입찰진행내용": "", "등기부_근저당": "", "근저당권_합계금액": None, "채권원금": None,
        "등기부_청구금액": "", "유동화전문_청구금액": None,
        "기준일(입찰기일+60일)": "", "이자 연체일수": None,
        "예상연체이자": None, "채권행사권리금액": None,
    }
    original_handle = driver.current_window_handle
    detail_handle = None
    try:
        time.sleep(random.uniform(*DETAIL_PAGE_DELAY))
        detail_handle, html = open_detail_tab(driver, detail_url, tid=tid)
        if not detail_handle:
            return result
        soup = BeautifulSoup(html, "html.parser")

        base_info = extract_base_info_from_detail(soup)
        for k in ("사건번호", "매각일자", "소재지", "개시결정", "감정가", "토지면적", "건물면적", "최저가"):
            result[k] = base_info.get(k, result[k])
        result["물건번호"] = base_info.get("사건번호", "")

        history_rows = extract_bid_history_from_detail(soup)
        result["입찰진행내용"] = format_bid_history(history_rows)

        liens, claims = extract_registry_liens_from_detail(soup)
        merged_liens, liens_total = merge_registry_liens_by_owner(liens)
        result["등기부_근저당"] = format_registry_liens(merged_liens)
        result["근저당권_합계금액"] = liens_total
        result["채권원금"] = estimate_registry_principal(liens_total)

        deduped_claims = dedup_registry_claims(claims)
        result["등기부_청구금액"] = format_registry_claims(deduped_claims)
        result["유동화전문_청구금액"] = sum_yudonghwa_claims(deduped_claims)

        reference_date = calc_reference_date(result.get("매각일자"))
        result["기준일(입찰기일+60일)"] = reference_date.strftime("%Y-%m-%d") if reference_date else ""
        overdue_days = calc_interest_overdue_days(reference_date, result.get("개시결정"))
        result["이자 연체일수"] = overdue_days
        overdue_interest = calc_overdue_interest(result.get("채권원금"), overdue_days)
        result["예상연체이자"] = overdue_interest
        result["채권행사권리금액"] = calc_claim_exercise_amount(
            result.get("유동화전문_청구금액"), overdue_interest
        )
    except Exception as e:
        print(f"[tid={tid}] 등기부/입찰이력 상세정보 처리 중 오류: {e}")
    finally:
        close_detail_tab(driver, detail_handle, original_handle, tid=tid)
    return result


# ===================== (v2) NPL 사이트 부실채권(NPL) 겹침 표시 =====================
NPL_SHEET_ID = os.environ.get("NPL_SHEET_ID", "")   # NPL 목록이 저장된 스프레드시트 ID(Secrets). 없으면 NPL 비교를 건너뜀
NPL_TAB_RE = re.compile(r"^NPL_(\d{8})$")
NPL_MAX_AGE_DAYS = 21          # 가장 최근 NPL 탭이 이보다 오래되면 비교하지 않는다(오래된 목록으로 잘못 표시 방지)
NPL_COL_INDEX = len(REGISTRY_DETAIL_HEADERS) - 1


def _npl_case_key(text):
    """'24-639 (2)' / '서울중앙 2024타경639(2)' -> ('24', '639') 또는 None."""
    s = str(text or "")
    m = re.search(r"(\d{2,4})\s*타[경채]?\s*(\d+)", s) or re.search(r"(?<!\d)(\d{2,4})\s*-\s*(\d+)", s)
    if not m:
        return None
    return m.group(1)[-2:], str(int(m.group(2)))


def _npl_int(v):
    d = re.sub(r"[^\d]", "", str(v or ""))
    return int(d) if d else None


def _npl_tokens(addr):
    return {w for w in re.findall(r"[가-힣0-9]+", str(addr or "")) if len(w) >= 2}


def load_npl_index(google_sh):
    """NPL 스프레드시트의 가장 최근 NPL_YYYYMMDD 탭을 읽어 {(yy,번호): [행 dict]} 색인을 만든다. 실패하면 (None, 사유)."""
    if not NPL_SHEET_ID:
        return None, "NPL_SHEET_ID 미설정"
    if gspread is None or not os.path.exists(GOOGLE_CREDENTIALS_PATH):
        return None, "구글 연결 불가"
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        gc = gspread.service_account(filename=GOOGLE_CREDENTIALS_PATH, scopes=scopes)
        nsh = gc.open_by_key(NPL_SHEET_ID)
        tabs = sorted([w for w in nsh.worksheets() if NPL_TAB_RE.match(w.title)], key=lambda w: w.title, reverse=True)
        if not tabs:
            return None, "NPL_YYYYMMDD 탭이 없음(03_3 NPL 사이트 NPL 크롤링을 먼저 실행)"
        ws = tabs[0]
        d = datetime.strptime(NPL_TAB_RE.match(ws.title).group(1), "%Y%m%d").date()
        age = (date.today() - d).days
        if age > NPL_MAX_AGE_DAYS + 6:      # 탭 이름은 그 주 토요일 날짜라 크롤링 시점은 최대 6일 앞
            return None, f"최근 NPL 탭({ws.title})이 너무 오래됨"
        values = ws.get_all_values()
        if not values:
            return None, f"NPL 탭({ws.title})이 비어 있음"
        hdr = values[0]
        need = ["사건번호", "감정가", "매각기일", "소재지"]
        if any(h not in hdr for h in need):
            return None, f"NPL 탭({ws.title}) 헤더가 예상과 다름"
        ix = {h: hdr.index(h) for h in hdr}
        index = {}
        for r in values[1:]:
            if len(r) <= ix["사건번호"]:
                continue
            key = _npl_case_key(r[ix["사건번호"]])
            if not key:
                continue
            row = {h: (r[i] if i < len(r) else "") for h, i in ix.items()}
            index.setdefault(key, []).append(row)
        print(f"[NPL] '{ws.title}' 탭에서 {sum(len(v) for v in index.values())}건 읽음 (사건번호 {len(index)}종)")
        return index, ws.title
    except Exception as e:
        return None, f"NPL 시트 읽기 실패: {e}"


def npl_overlap_text(reg_row, index):
    """등기부상세 행(REGISTRY_DETAIL_HEADERS 순서) 하나를 NPL 색인과 비교해 표시 문구를 돌려준다."""
    if not index:
        return ""
    key = _npl_case_key(reg_row[1])
    if not key or key not in index:
        return ""
    my_price = _npl_int(reg_row[8])
    my_date = re.sub(r"[^\d]", "", str(reg_row[5] or ""))[-6:]
    my_tok = _npl_tokens(reg_row[6])
    best = None
    for c in index[key]:
        proofs = []
        if my_price and _npl_int(c.get("감정가")) == my_price:
            proofs.append("감정가")
        c_date = re.sub(r"[^\d]", "", c.get("매각기일", ""))[-6:]
        if my_date and c_date and my_date == c_date:
            proofs.append("매각기일")
        if len(my_tok & _npl_tokens(c.get("소재지"))) >= 2:
            proofs.append("소재지")
        if best is None or len(proofs) > len(best[1]):
            best = (c, proofs)
    c, proofs = best
    info = " / ".join(x for x in (
        f"NPL 사이트 물번 {c.get('물번')}" if c.get("물번") else "",
        c.get("진행상태", ""), c.get("최저가율", ""),
        f"보유회사 {c['보유회사']}" if c.get("보유회사") else "",
    ) if x)
    if proofs:
        return f"NPL 겹침({'+'.join(proofs)} 일치)" + (f" | {info}" if info else "")
    return "NPL 후보(사건번호만 같음, 확인필요)" + (f" | {info}" if info else "")


def annotate_npl_column(rows, google_sh):
    """registry_detail_rows 각 행의 맨 뒤(NPL 사이트_NPL 열)를 채운다. NPL 을 못 읽으면 빈칸으로 둔다."""
    index, note = load_npl_index(google_sh)
    if index is None:
        print(f"[NPL] 비교 생략: {note}")
    hits = 0
    for r in rows:
        text = npl_overlap_text(r, index) if index else ""
        if len(r) <= NPL_COL_INDEX:
            r.extend([""] * (NPL_COL_INDEX + 1 - len(r)))
        r[NPL_COL_INDEX] = text
        hits += 1 if text else 0
    if index is not None:
        print(f"[NPL] 등기부상세 {len(rows)}건 중 NPL 사이트 부실채권과 겹침/후보 {hits}건 (비교 탭: {note})")
    return hits


def cleanup_old_factory_tabs(google_sh, labels):
    """'YYYYMMDD_<종류>' 와 'YYYYMMDD_<종류>_등기부상세' 탭 중 오늘보다 오래된 것을 지운다(labels 에 든 종류만).
    오늘 날짜 탭이 시트에 없으면(= 이번 실행이 그 종류를 저장하지 못함) 그 종류는 지우지 않는다."""
    try:
        worksheets = google_sh.worksheets()
        titles = {w.title for w in worksheets}
        for label in labels:
            if f"{오늘날짜_숫자만}_{label}" not in titles:
                print(f"[정리] 오늘 탭 '{오늘날짜_숫자만}_{label}' 이 없어 '{label}' 의 이전 탭은 지우지 않습니다.")
                continue
            pat = re.compile(rf"^(\d{{8}})_{re.escape(label)}(?:_등기부상세)?$")
            for ws in worksheets:
                m = pat.match(ws.title)
                if m and m.group(1) < 오늘날짜_숫자만:
                    google_sh.del_worksheet(ws)
                    print(f"[정리] 이전 탭 삭제: {ws.title}")
    except Exception as e:
        print(f"[정리] 이전 탭 정리 중 오류(수집 결과에는 영향 없음): {e}")


def save_registry_detail_rows_to_gsheet(google_sh, rows, tab_name):
    """등기부/입찰이력 상세 추출 결과를 지정한 탭에 저장한다(기존 내용은 지우고 새로 씀 -
    같은 날 재실행해도 중복/열밀림이 생기지 않도록). google_sh는 main()에서 이미 연결한
    핸들을 그대로 받는다(GOOGLE_SHEETS_ENABLED=True가 이 파일의 기본값이라 원본의
    get_google_spreadsheet(force=True) 같은 강제 연결은 필요 없다)."""
    if not rows:
        print(f"[{tab_name}] 저장할 등기부상세 결과가 없어 건너뜁니다.")
        return
    if google_sh is None:
        print(f"[{tab_name}] 구글 스프레드시트 연결이 없어 등기부상세 저장을 건너뜁니다.")
        return
    ws = get_or_create_tab(google_sh, tab_name)
    if ws is None:
        return
    try:
        safe_rows = [[_gsheet_json_safe(v) for v in row] for row in rows]
        all_values = [REGISTRY_DETAIL_HEADERS] + safe_rows
        n_rows = len(all_values)
        n_cols = len(REGISTRY_DETAIL_HEADERS)
        needed_rows = n_rows + 10
        needed_cols = n_cols + 2
        if ws.row_count < needed_rows or ws.col_count < needed_cols:
            ws.resize(rows=max(ws.row_count, needed_rows), cols=max(ws.col_count, needed_cols))
        ws.clear()
        ws.update(values=all_values, range_name="A1", value_input_option="USER_ENTERED")
        _apply_gsheet_formatting(ws, n_rows, n_cols, currency_cols=REGISTRY_CURRENCY_COLUMNS)
        print(f"[{tab_name}] 구글시트에 등기부상세 {len(rows)}건 저장 완료(기존 내용은 지우고 새로 씀).")
    except Exception as e:
        print(f"[{tab_name}] 구글시트 저장 중 오류: {e}")


def fetch_detail_info(driver, session, tid, chk_no, tot_no, base_address):
    detail_url = f"{SITE_BASE}/ca/caView.php?tid={tid}&chkNo={chk_no}&TotNo={tot_no}"
    parcel_addresses = []
    notes_text = ""
    토지등기_요약 = ""
    지분여부 = ""

    original_handle = driver.current_window_handle
    detail_handle = None
    try:
        time.sleep(random.uniform(*DETAIL_PAGE_DELAY))
        detail_handle, html = open_detail_tab(driver, detail_url, tid=tid)
        if not detail_handle:
            return parcel_addresses, notes_text, 토지등기_요약, 지분여부

        print(f"  [tid={tid}] 상세페이지(브라우저 탭) 로드 완료, 길이 {len(html)}자")
        soup = BeautifulSoup(html, "html.parser")

        parcel_texts = extract_parcel_texts(soup)
        if parcel_texts:
            parcel_addresses = [build_full_parcel_address(base_address, p) for p in parcel_texts]
        else:
            print(f"  [tid={tid}] '매각 물건 현황' 표에서 필지 정보를 찾지 못했습니다.")

        notes_text = extract_notes_from_detail(soup)
        if not notes_text:
            print(f"  [tid={tid}] '현황·위치·주변환경'/'참고사항' 텍스트를 찾지 못했습니다.")

        sale_object_type = extract_sale_object_type(soup)
        is_jibun = "지분" in sale_object_type
        지분여부 = "지분" if is_jibun else ""
        if sale_object_type:
            print(f"  [tid={tid}] 매각물건: {sale_object_type} -> 지분여부={'지분' if is_jibun else '아님'}")
        else:
            print(f"  [tid={tid}] 상세페이지에서 '매각물건' 항목을 찾지 못해 지분 여부를 판단하지 못했습니다.")

        if is_jibun:
            pdf_url = click_registry_pdf_link(driver, detail_handle, tid=tid)
            if pdf_url:
                time.sleep(random.uniform(*PDF_DOWNLOAD_DELAY))
                pdf_bytes = fetch_pdf_bytes_via_browser(driver, pdf_url, tid=tid)
                if pdf_bytes:
                    print(f"  [tid={tid}] 토지등기 PDF 다운로드 완료 ({len(pdf_bytes)} bytes)")
                    토지등기_요약 = extract_registry_summary_from_pdf(pdf_bytes)
                    if not 토지등기_요약:
                        print(f"  [tid={tid}] 토지등기 PDF 마지막 페이지에서 텍스트를 추출하지 못했습니다.")
                else:
                    print(f"  [tid={tid}] 토지등기 PDF 다운로드 실패 (URL: {pdf_url})")
            else:
                print(f"  [tid={tid}] 지분 물건인데 토지등기 PDF URL을 얻지 못했습니다.")

    except Exception as e:
        print(f"[tid={tid}] 상세페이지 처리 중 오류: {e}")
    finally:
        close_detail_tab(driver, detail_handle, original_handle, tid=tid)

    return parcel_addresses, notes_text, 토지등기_요약, 지분여부


def click_page_number(driver, target_page):
    buttons = driver.find_elements(By.CSS_SELECTOR, "#paging div.pageBtn")
    for b in buttons:
        if b.text.strip() == str(target_page):
            driver.execute_script("arguments[0].click();", b)
            return True
    return False


def click_next_block(driver):
    buttons = driver.find_elements(By.CSS_SELECTOR, "#paging div.pageBtn")
    for b in buttons:
        if b.text.strip() == "다음":
            driver.execute_script("arguments[0].click();", b)
            return True
    return False


def go_to_page(driver, target_page, prev_first_tid):
    moved = click_page_number(driver, target_page)
    if not moved:
        if not click_next_block(driver):
            return False
        time.sleep(random.uniform(*PAGE_CLICK_DELAY))
        moved = click_page_number(driver, target_page)
        if not moved:
            return False
    try:
        WebDriverWait(driver, 15).until(lambda d: get_first_tid(d) != prev_first_tid)
    except TimeoutException:
        print(f"경고: {target_page} 페이지로 이동 후 목록 변경을 확인하지 못했습니다.")
    return True


def main():
    # (2026-10-04) 이 파생본은 "공장"/"근린상가" 두 물건종류를 항상 둘 다 수집해서
    # 서로 다른 탭/파일에 나눠 저장한다 - 원본의 수집범위/물건종류 선택 프롬프트
    # (prompt_collect_mode/prompt_ctgr_mode_ca)는 쓰지 않는다. 각 물건종류마다 경매(CA)
    # 수집이 끝나면 같은 탭에 이어서 공매(PA)도 PA_CTGR_MAP 매핑으로 수집한다(등기부상세
    # 추출은 경매만 지원 - 파일 상단 docstring 7/9번 참고).
    minb_amt_end_value = prompt_minb_amt_end()
    area_pyeong_end = prompt_area_pyeong_end()

    login_id, login_pw = LOGIN_ID, LOGIN_PW

    print(f"\n검색 조건: 물건종류={'+'.join(l for _, l in CTGR_OPTIONS_CA)}(경매+공매), "
          f"매각기일={start_date_str}~{end_date_str}(진행물건), "
          f"최저가격={DEFAULT_MINB_AMT_BGN:,}~{int(minb_amt_end_value):,}원, "
          f"건물면적 상한={area_pyeong_end:g}평, 유찰횟수=1~2회만")
    if FETCH_DETAIL_DOCS and pdfplumber is None:
        print("경고: pdfplumber 모듈이 설치되어 있지 않아 PDF 텍스트 추출이 동작하지 않습니다.")

    google_sh = None
    if GOOGLE_SHEETS_ENABLED:
        if os.path.exists(GOOGLE_CREDENTIALS_PATH):
            print(f"서비스 계정 키 파일: {GOOGLE_CREDENTIALS_PATH} (이 PC에서 찾음)")
        else:
            print(f"경고: 서비스 계정 키 파일을 이 PC의 등록된 후보 경로 중 어디서도 찾지 "
                  f"못했습니다(후보: {GOOGLE_CREDENTIALS_PATH_CANDIDATES}) - 구글 시트 저장이 "
                  f"건너뛰어지고 로컬 xlsx만 저장됩니다.")
        google_sh = get_google_spreadsheet()

    driver = get_driver()
    category_summaries = []

    try:
        driver.get(BASE_URL)
        wait_for_list(driver)
        time.sleep(1)

        if FETCH_DETAIL_DOCS:
            login(driver, login_id, login_pw)
            time.sleep(1)

        for ctgr_value, ctgr_label in CTGR_OPTIONS_CA:
            tab_name = f"{오늘날짜_숫자만}_{ctgr_label}"
            print(f"\n{'='*70}\n[{ctgr_label}] 구글시트 탭 '{tab_name}' 수집 시작\n{'='*70}")

            category_ws = None
            existing_case_numbers = set()
            existing_rows = []
            run_start_remote_rows = None
            if GOOGLE_SHEETS_ENABLED and google_sh is not None:
                category_ws = get_or_create_tab(google_sh, tab_name)
                if category_ws is not None:
                    ensure_header_row(category_ws)
                    run_start_remote_rows = _get_remote_row_count(category_ws)
                    existing_case_numbers, existing_rows = load_existing_data_from_gsheet(category_ws)

            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "data"
            sheet.append(TEMPLATE_HEADERS)
            if FETCH_DETAIL_DOCS:
                sheet.cell(row=1, column=AC_COL, value="토지등기_요약(지분물건만, 임시)")

            save_path = os.path.join(SAVE_DIR, f"{오늘날짜_숫자만}_{ctgr_label}.xlsx")
            if os.path.exists(save_path):
                base, ext = os.path.splitext(save_path)
                save_path = f"{base}_A{ext}"

            for row_values, ac_value in existing_rows:
                append_row_with_format(sheet, row_values, ac_value, dedupe=False)
            if existing_rows:
                print(f"'{tab_name}' 탭에서 기존 물건 {len(existing_rows)}건을 가져왔습니다 "
                      f"(사건번호 {len(existing_case_numbers)}종). 이미 있는 사건번호는 상세페이지/PDF 요청 없이 건너뜁니다.")

            gsheet_sync_state = {"synced_rows": 1 + len(existing_rows)}

            seen_tids = set()
            doc_session = None
            total_new_count = 0
            test_limit_hit = False
            total_skip_existing = 0
            total_skip_area = 0
            total_skip_fail_count = 0  # (2026-10-04 추가) 유찰횟수 1~2회 조건 불일치로 제외된 건수
            registry_detail_rows = []  # (2026-10-04 추가) 등기부 근저당권/청구금액 상세 - 카테고리별 별도 탭에 저장

            try:
                print(f"\n[{ctgr_label}] 검색 시작...")
                share_tids_ca = set()
                if FETCH_DETAIL_DOCS:
                    print(f"[{ctgr_label}] [사전조회] '지분입찰 물건' 필터로 지분 물건 Tid만 먼저 수집합니다 (팝업 없음)...")
                    share_tids_ca = collect_share_tids(driver, minb_amt_end_value, ctgr_value)

                apply_filters(driver, minb_amt_end_value, ctgr_value)
                wait_for_list(driver)
                set_page_size(driver)
                wait_for_list(driver)

                if FETCH_DETAIL_DOCS:
                    doc_session = build_requests_session(driver)

                page_num = 1
                while page_num <= MAX_PAGES:
                    print(f"[{ctgr_label}] 현재 {page_num} 페이지 데이터 추출 중...")
                    wait_for_list(driver)
                    time.sleep(0.5)

                    rows = get_rows(driver)
                    if not rows:
                        print(f"[{ctgr_label}] 검색 결과가 없습니다.")
                        break

                    prev_first_tid = rows[0].get_attribute("data-tid")
                    tot_no = len(rows)
                    page_extracted_count = 0

                    for chk_no, row in enumerate(rows, start=1):
                        tid = None
                        try:
                            tid = row.get_attribute("data-tid")
                            if tid in seen_tids:
                                continue
                            seen_tids.add(tid)

                            data = extract_row(row, tid, chk_no=chk_no, tot_no=tot_no)
                            if not data:
                                continue
                            page_extracted_count += 1

                            사건번호_key = (data[1] or "").strip()
                            if 사건번호_key and 사건번호_key in existing_case_numbers:
                                total_skip_existing += 1
                                continue

                            # (2026-10-04 추가) 건물면적 상한 필터: extract_row()가 맨 뒤에
                            # 덧붙인 건물면적_평(data[-1])과 비교한다. 건물면적을 못 읽은
                            # 행(None)은 "200평 이하만"이라는 요청 취지상 보수적으로 제외한다.
                            건물면적_평_값 = data[-1]
                            if 건물면적_평_값 is None or 건물면적_평_값 > area_pyeong_end:
                                total_skip_area += 1
                                continue

                            # (2026-10-04 추가) 유찰횟수 1~2회만 수집. 진행상태(data[6])
                            # 텍스트("신건"/"유찰 N회")에서 다시 파싱한다(extract_row()의
                            # 지역 변수 유찰횟수는 반환되지 않으므로 같은 정규식을 재사용).
                            유찰횟수_m = re.search(r"유찰\s*(\d+)\s*회", data[6] or "")
                            유찰횟수_값 = int(유찰횟수_m.group(1)) if 유찰횟수_m else 0
                            if not (1 <= 유찰횟수_값 <= 2):
                                total_skip_fail_count += 1
                                continue

                            base_address = data[2]
                            needs_detail = (tid in share_tids_ca) or is_multi_parcel(base_address)

                            parcel_addrs, 등기요약 = [], ""
                            if FETCH_DETAIL_DOCS and needs_detail and doc_session is not None:
                                parcel_addrs, notes_text, 등기요약, 지분여부_상세 = fetch_detail_info(
                                    driver, doc_session, tid, chk_no, tot_no, base_address
                                )
                                if 지분여부_상세:
                                    data[13] = 지분여부_상세
                                elif tid in share_tids_ca:
                                    data[13] = "지분"
                                if notes_text:
                                    if data[3] and data[3] != "-":
                                        data[3] = f"{data[3]}\n\n{notes_text}"
                                    else:
                                        data[3] = notes_text
                            else:
                                if tid in share_tids_ca:
                                    data[13] = "지분"
                                data[14] = base_address

                            # (2026-10-04 추가) 공장/근린상가는 등기부 근저당권/청구금액
                            # 확인이 필수라서, 지분/필지 여부와 무관하게 모든 통과 물건에
                            # 대해 등기부상세를 추가로 수집한다(공장매각완.py와 동일 방식 -
                            # fetch_detail_info와는 별도로 상세페이지를 한 번 더 방문).
                            if FETCH_DETAIL_DOCS:
                                reg_info = fetch_registry_history_info(driver, tid, chk_no, tot_no)
                                registry_detail_rows.append([
                                    TYPE_A_LABEL, 사건번호_key, tid, reg_info["상세페이지"],
                                    reg_info["물건번호"], reg_info["매각일자"], reg_info["소재지"],
                                    reg_info["개시결정"], reg_info["감정가"], reg_info["토지면적"],
                                    reg_info["건물면적"], reg_info["최저가"],
                                    reg_info["입찰진행내용"], reg_info["등기부_근저당"],
                                    reg_info["근저당권_합계금액"], reg_info["채권원금"],
                                    reg_info["등기부_청구금액"], reg_info["유동화전문_청구금액"],
                                    reg_info["기준일(입찰기일+60일)"], reg_info["이자 연체일수"],
                                    reg_info["예상연체이자"], reg_info["채권행사권리금액"],
                                ])

                            total_new_count += 1

                            if len(parcel_addrs) >= 2:
                                for parcel_idx, addr in enumerate(parcel_addrs, start=1):
                                    row_data = list(data)
                                    row_data[14] = addr
                                    print(f"[{ctgr_label}][신규 {total_new_count}번째 물건 - 필지 {parcel_idx}/{len(parcel_addrs)}] {row_data}")
                                    append_row_with_format(sheet, row_data, 등기요약)
                            else:
                                if parcel_addrs:
                                    data[14] = parcel_addrs[0]
                                print(f"[{ctgr_label}][신규 {total_new_count}번째 물건] {data}")
                                append_row_with_format(sheet, data, 등기요약)

                            maybe_autosave(sheet, category_ws, save_path, total_new_count, gsheet_sync_state)

                            if TEST_MAX_NEW_ITEMS and total_new_count >= TEST_MAX_NEW_ITEMS:
                                print(f"[테스트] 신규 {total_new_count}건 수집해 {ctgr_label} 경매 수집을 여기서 멈춥니다.")
                                test_limit_hit = True
                                break

                        except StaleElementReferenceException:
                            raise
                        except Exception as e:
                            print(f"[{ctgr_label}][tid={tid}] 이 물건 처리 중 오류가 발생해 건너뜁니다: {e}")
                            continue

                    if test_limit_hit:
                        break

                    if page_extracted_count == 0 and page_num > 1:
                        print(f"[{ctgr_label}] 이 페이지에서 추출된 데이터가 없어 이 물건종류 수집을 종료합니다.")
                        break

                    next_page = page_num + 1
                    if not go_to_page(driver, next_page, prev_first_tid):
                        print(f"[{ctgr_label}] 마지막 페이지에 도달했습니다.")
                        break
                    page_num = next_page

            except StaleElementReferenceException:
                print(f"[{ctgr_label}] 페이지 갱신 중 요소 참조가 끊겼습니다. 지금까지 수집된 데이터로 저장합니다.")
            except Exception as e:
                print(f"[{ctgr_label}] 처리 중 오류가 발생해 이 물건종류 수집을 중단합니다: {e}")

            # --- 공매(PA) 수집: 같은 탭에 이어서 저장 (2026-10-04 추가) ---
            # 공매는 상세페이지 구조가 달라(caView.php가 아님) 등기부 근저당권/청구금액
            # 상세 추출은 지원하지 않는다(공장매각완.py 원본과 동일한 제한). 물건종류
            # 매핑은 PA_CTGR_MAP 참고 - 근린상가="근린생활시설", 공장="산업용및기타특수용건물"(그룹).
            pa_ctgr_select_value, pa_ctgr_checkbox_selector = PA_CTGR_MAP.get(ctgr_label, (None, None))
            seen_tids_pa = set()
            try:
                print(f"\n[{TYPE_B_LABEL}/{ctgr_label}] 공매 수집 시작...")
                driver.get(PA_BASE_URL)
                wait_for_list(driver)
                time.sleep(1)

                for prptdvsn_value, prptdvsn_label in ([] if TEST_MAX_NEW_ITEMS else PA_PRPTDVSN_VALUES):   # 테스트 모드는 공매 생략
                    try:
                        print(f"\n[{TYPE_B_LABEL}/{ctgr_label}] 자산구분 '{prptdvsn_label}' 검색 시작...")
                        apply_filters_pa(
                            driver, minb_amt_end_value, prptdvsn_value,
                            ctgr_select_value=pa_ctgr_select_value,
                            ctgr_checkbox_selector=pa_ctgr_checkbox_selector,
                        )
                        wait_for_list(driver)
                        set_page_size(driver)
                        wait_for_list(driver)

                        pa_page_num = 1
                        while pa_page_num <= MAX_PAGES:
                            print(f"[{TYPE_B_LABEL}/{ctgr_label}/{prptdvsn_label}] 현재 {pa_page_num} 페이지 데이터 추출 중...")
                            wait_for_list(driver)
                            time.sleep(0.5)

                            rows = get_rows(driver)
                            if not rows:
                                print(f"[{TYPE_B_LABEL}/{ctgr_label}/{prptdvsn_label}] 검색 결과가 없습니다.")
                                break

                            prev_first_tid_pa = rows[0].get_attribute("data-tid")
                            tot_no = len(rows)
                            page_extracted_count = 0

                            for chk_no, row in enumerate(rows, start=1):
                                tid = None
                                try:
                                    tid = row.get_attribute("data-tid")
                                    if tid in seen_tids_pa:
                                        continue
                                    seen_tids_pa.add(tid)

                                    data = extract_row_pa(row, tid, chk_no=chk_no, tot_no=tot_no)
                                    if not data:
                                        continue
                                    page_extracted_count += 1

                                    사건번호_key = (data[1] or "").strip()
                                    if 사건번호_key and 사건번호_key in existing_case_numbers:
                                        total_skip_existing += 1
                                        continue

                                    건물면적_평_값 = data[-1]
                                    if 건물면적_평_값 is None or 건물면적_평_값 > area_pyeong_end:
                                        total_skip_area += 1
                                        continue

                                    유찰횟수_m = re.search(r"유찰\s*(\d+)\s*회", data[6] or "")
                                    유찰횟수_값 = int(유찰횟수_m.group(1)) if 유찰횟수_m else 0
                                    if not (1 <= 유찰횟수_값 <= 2):
                                        total_skip_fail_count += 1
                                        continue

                                    base_address = data[2]
                                    needs_detail_pa = (data[13] == "지분")

                                    parcel_addrs = split_multi_parcel_address_pa(base_address, category=data[4])
                                    등기요약 = ""
                                    if FETCH_DETAIL_DOCS and needs_detail_pa:
                                        parcel_texts_raw, notes_text, 등기요약, 지분여부_상세 = \
                                            fetch_detail_info_pa(driver, tid, chk_no, tot_no)
                                        table_addrs = build_pa_parcel_addresses(
                                            base_address, parcel_texts_raw, category=data[4]
                                        ) if parcel_texts_raw else []
                                        if table_addrs:
                                            parcel_addrs = table_addrs
                                        if 지분여부_상세:
                                            data[13] = 지분여부_상세
                                        if notes_text:
                                            if data[3] and data[3] != "-":
                                                data[3] = f"{data[3]}\n\n{notes_text}"
                                            else:
                                                data[3] = notes_text

                                    total_new_count += 1

                                    if len(parcel_addrs) >= 2:
                                        for parcel_idx, addr in enumerate(parcel_addrs, start=1):
                                            row_data = list(data)
                                            row_data[14] = addr
                                            print(f"[{TYPE_B_LABEL}/{ctgr_label}][신규 {total_new_count}번째 물건 - 필지 {parcel_idx}/{len(parcel_addrs)}] {row_data}")
                                            append_row_with_format(sheet, row_data, 등기요약)
                                    else:
                                        if parcel_addrs:
                                            data[14] = parcel_addrs[0]
                                        print(f"[{TYPE_B_LABEL}/{ctgr_label}][신규 {total_new_count}번째 물건] {data}")
                                        append_row_with_format(sheet, data, 등기요약)

                                    maybe_autosave(sheet, category_ws, save_path, total_new_count, gsheet_sync_state)

                                except StaleElementReferenceException:
                                    raise
                                except Exception as e:
                                    print(f"[{TYPE_B_LABEL}/{ctgr_label}][tid={tid}] 이 물건 처리 중 오류가 발생해 건너뜁니다: {e}")
                                    continue

                            if page_extracted_count == 0 and pa_page_num > 1:
                                print(f"[{TYPE_B_LABEL}/{ctgr_label}/{prptdvsn_label}] 이 페이지에서 추출된 데이터가 없어 이 카테고리 수집을 종료합니다.")
                                break

                            next_page_pa = pa_page_num + 1
                            if not go_to_page(driver, next_page_pa, prev_first_tid_pa):
                                print(f"[{TYPE_B_LABEL}/{ctgr_label}/{prptdvsn_label}] 마지막 페이지에 도달했습니다.")
                                break
                            pa_page_num = next_page_pa

                    except StaleElementReferenceException:
                        raise
                    except Exception as e:
                        print(f"[{TYPE_B_LABEL}/{ctgr_label}/{prptdvsn_label}] 이 카테고리 처리 중 오류가 발생해 건너뜁니다: {e}")
                        continue

            except StaleElementReferenceException:
                print(f"[{TYPE_B_LABEL}/{ctgr_label}] 페이지 갱신 중 요소 참조가 끊겼습니다. 지금까지 수집된 데이터로 저장합니다.")
            except Exception as e:
                print(f"[{TYPE_B_LABEL}/{ctgr_label}] 공매 수집 중 오류가 발생해 건너뜁니다: {e}")

            # --- 이 물건종류 마무리: 구글시트 동기화 + 등기부상세 탭 + 로컬 저장 ---
            registry_tab_name = f"{tab_name}_등기부상세"
            annotate_npl_column(registry_detail_rows, google_sh)   # (v2) NPL 사이트 부실채권 겹침 표시
            if GOOGLE_SHEETS_ENABLED:
                save_registry_detail_rows_to_gsheet(google_sh, registry_detail_rows, registry_tab_name)

            sync_ok, remote_after_final = True, None
            if GOOGLE_SHEETS_ENABLED and category_ws is not None:
                sync_ok, _remote_before, remote_after_final = sync_to_google_sheet(sheet, category_ws)
                if google_sh is not None:
                    log_run_summary(google_sh, {
                        "실행시각(KST)": (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S"),
                        "실행PC": _get_local_pc_name(),
                        "수집범위": f"경매+공매/{ctgr_label}(진행물건)",
                        "대상탭": tab_name,
                        "시작전_원격행수": run_start_remote_rows if run_start_remote_rows is not None else "",
                        "종료후_원격행수": remote_after_final if remote_after_final is not None else "",
                        "이번실행_신규건수": total_new_count,
                        "이번실행_건너뛴기존건수": total_skip_existing,
                        "검증결과": "OK" if sync_ok else "저장실패(로그 참고)",
                        "비고": f"건물면적({area_pyeong_end:g}평 초과/미확인) 제외 {total_skip_area}건, "
                                f"유찰횟수(1~2회 아님) 제외 {total_skip_fail_count}건, "
                                f"등기부상세 탭 '{registry_tab_name}' {len(registry_detail_rows)}건",
                    })

            workbook.save(save_path)
            print(f"\n[{ctgr_label}] Excel 파일 저장 완료: {save_path} "
                  f"(신규 {total_new_count}건, 기존건너뜀 {total_skip_existing}건, "
                  f"면적초과제외 {total_skip_area}건, 유찰횟수제외 {total_skip_fail_count}건, "
                  f"전체 저장된 행 {sheet.max_row - 1}행, 등기부상세 {len(registry_detail_rows)}건)")
            category_summaries.append(
                (ctgr_label, tab_name, total_new_count, total_skip_existing, total_skip_area, total_skip_fail_count)
            )

    except KeyboardInterrupt:
        print("\n사용자가 실행을 중지했습니다.")
    finally:
        driver.quit()

    # Actions(예약/수동) 실행은 항상 최신 탭만 남긴다 - 과거 데이터는 필요 없다는 요청.
    # 오늘 탭이 실제로 만들어진 물건종류에 한해, 그보다 이전 날짜의 같은 종류 탭(본 탭 + _등기부상세)을 지운다.
    if os.environ.get("GITHUB_ACTIONS") == "true" and GOOGLE_SHEETS_ENABLED and google_sh is not None and not TEST_MAX_NEW_ITEMS:
        cleanup_old_factory_tabs(google_sh, [c[0] for c in category_summaries])

    if category_summaries:
        print(f"\n{'='*70}\n전체 요약\n{'='*70}")
        for label, tab, new_c, skip_c, area_c, fail_c in category_summaries:
            print(f"  [{label}] 탭 '{tab}': 신규 {new_c}건 / 기존건너뜀 {skip_c}건 / "
                  f"면적초과제외 {area_c}건 / 유찰횟수제외 {fail_c}건")


if __name__ == "__main__":
    # (2026-10-04 4차 수정) 라이브 테스트 중 실제로 터진 버그: 코드 곳곳의 print()가
    # ✅/❌ 같은 기호를 쓰는데, 콘솔 기본 인코딩이 cp949(한글 Windows)이면
    # UnicodeEncodeError로 sync_to_google_sheet() 등이 조용히 실패한다(try/except로
    # 감싸져 있어 크롤링 자체는 안 죽지만, 매번 "구글시트 업로드 중 오류" 로그가 남는다).
    # 표준출력/표준에러를 UTF-8로 강제 전환해 원천 차단한다.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()