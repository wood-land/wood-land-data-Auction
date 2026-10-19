# auction

경공매 물건 데이터를 수집해 구글시트에 저장하는 크롤러입니다.

- 실행: `.github/workflows/auction.yml` (매주 목 16:00 UTC, 금 17:00 UTC 예약 + 수동 실행)
- 코드: `crawler.py`, 의존성: `requirements.txt`
- 결과: 구글시트(탭 `YYYYMMDD_Wxx_data`)에 저장하며 이 저장소에는 올리지 않습니다.
