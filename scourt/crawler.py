# -*- coding: utf-8 -*-
"""
[GitHub Actions 버전] 이 파일은 로컬판 "02_201. 대법원 파산공매 _구글시트 26 0823.py"(v3.6.36)를
Actions(리눅스·헤드리스·비밀키는 환경변수) 에서 돌도록 고친 것이다. 추출 로직은 로컬판과 같다.
  - 키/시트: GOOGLE_CREDENTIALS_EDITER(서비스계정 JSON 전체), GOOGLE_SHEET_ID, KAKAO_REST_API_KEY, VWORLD_API_KEY
  - 시트 탭: 공고목록(원본 누적) / 파산공고_YYMMDD(실행일 날짜 탭, 공고목록에서 매번 재구성) / 로그기록(실행 1회 1줄)
  - 러너(미국 IP)는 브이월드가 막혀 있어 PNU 는 카카오 주소검색을 먼저 쓰고 브이월드는 보조로 쓴다.
  - 환경변수: SCOURT_RUN_MODE(INCREMENTAL|REBUILD_MERGED), SCOURT_MAX_NEW(이번에 새로 읽을 공고 수 상한, 시험용),
              RUN_DEADLINE_MINUTES(이 시간이 지나면 새 공고 읽기를 멈추고 정리, 기본 300)

대법원 '회생파산 재산 매각(부동산) 공고' 크롤러 v3
https://www.scourt.go.kr/portal/notice/realestate/RealNoticeList.work

v2 → v3 에서 고친 것 (실제 인천지방법원 2024하단100623 공고문 PDF로 재현/검증 완료):

  🐛 실제 버그: 구글시트 '파산공매' 시트 주소열이 "전북특별자치도 김제시 7"처럼 잘려서 기록됨
     → 원인을 추적해보니 표 자체는 pdfplumber가 정상적으로 인식하고 있었는데,
       이 법원 PDF의 표 헤더가 "지 번"(주소가 아니라 '지번'이라는 표현), 입찰일정 표는
       "입찰마감일" / "최저입찰금" 이었음. 기존 v2의 키워드 목록에는 "지번", "마감일",
       "최저입찰금"이 빠져 있어서 → 주소 열/입찰일 열/최저가 열을 못 찾음 →
       표 추출이 통째로 실패 → 문장형(plain-text) 정규식 폴백으로 넘어감 →
       PDF의 표 없는 읽기 순서 텍스트에서는 "전북특별자치도 김제시" 바로 다음 줄에
       (실제로는 다른 열인) "7,812,229"이 붙어서 읽혔고, 정규식이 그 금액의 첫 자리 숫자
       "7"에서 주소가 끝난 것으로 잘못 판단해버림.
     → 재현 스크립트로 100% 확인함 (아래 1~4가 실제 수정 내용):

  1) 표 헤더 키워드 대폭 보강
     - 주소 열: "지번"(=지 번, 공백 제거 후 비교) 추가
     - 입찰일 열 / 최저가 열: 고정 키워드 목록이 아니라 '핵심 토큰 조합' 기반으로 판별
       (예: "입찰"+"마감일/기한/기일/기간/개찰일" 중 하나 있으면 입찰일 열,
            "최저"+"입찰" 둘 다 있으면 최저가 열) → 법원마다 표현이 달라도 대응

  2) 표 추출 자체가 실패하는 경우(테두리 없는 표 등)를 줄이기 위해, pdfplumber의
     기본(ruling-line 기반) table 추출이 빈 결과를 주면 텍스트 정렬 기반(vertical/
     horizontal_strategy="text") 전략으로 한 번 더 시도 (_extract_tables_multi_strategy)

  3) (혹시 그래도 문장형 폴백으로 떨어질 경우를 대비한 2차 안전장치) 주소 정규식 재설계:
     - 기존: 시/도 뒤에 "줄바꿈만 아니면 아무 문자나 60자까지 건너뛰고 처음 만나는 숫자"에서
       주소가 끝난다고 판단 → 표의 다른 열(면적/금액 등) 숫자를 지번으로 잘못 채택하기 쉬움
     - 변경: 시/도와 지번 사이에는 한글/공백만 허용(숫자는 "역삼2동", "테헤란로7길"처럼
       바로 뒤에 한글이 붙어 지명의 일부일 때만 허용) + 지번 뒤에 쉼표+숫자(",229"처럼
       천단위 콤마 금액의 일부로 보이면) 오는 경우는 지번으로 인정하지 않음(부정형 전방탐색)
     - 부수 효과: 이 방식은 공백류 문자 클래스에 줄바꿈도 포함되므로, PDF 셀 안에서 줄바꿈으로
       잘린 주소("김제시"↵"백산면 상리 720")도 자연스럽게 이어붙여 인식함

  4) OCR(스캔 이미지 PDF) 읽기 파이프라인 강화
     - 기존: dpi=300, --psm 4 로 1회만 시도
     - 변경: 1차 시도 결과가 부실하면(한글+숫자 글자 수 기준 페이지당 최소치 미달) dpi=450,
       --psm 6 조합으로 재시도하여 더 나은 결과를 채택 (매 문서마다 재시도하는 게 아니라
       "품질이 안 좋을 때만" 추가 비용을 쓰도록 설계해서 평소 처리 속도는 유지)
     - normalize_ocr_text()에 문장부호로 끝나지 않는 단순 줄바꿈(워드랩)을 공백으로
       합치는 soft-join 단계 추가 (표 셀 안 줄바꿈 주소가 잘리는 문제에 대한 추가 방어선)

  나머지(증분 크롤링, 구글시트 동기화, 사람처럼 클릭/대기, 3개 시트 구성 등)는 v2와 동일합니다.

시스템 준비사항은 이전과 동일:
  pip install selenium webdriver-manager openpyxl pdfplumber PyPDF2 pdf2image pytesseract gspread google-auth
  + OCR 쓰려면 poppler, tesseract-ocr(+한국어팩) 별도 설치 필요
"""

import os
import shutil
import re
import json
import time
import random
import glob
import sys
import traceback
import urllib.parse
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException, StaleElementReferenceException
)

from openpyxl import Workbook  # ✅ v3.5: load_workbook은 더 이상 안 씀 (로컬 파일을 되읽지 않음)

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False
try:
    from PyPDF2 import PdfReader
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False
try:
    from pdf2image import convert_from_path
    import pytesseract
    from PIL import ImageOps
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
try:
    import gspread
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# =========================
# 경로/고정값
# =========================
BASE_LIST_URL = "https://www.scourt.go.kr/portal/notice/realestate/RealNoticeList.work"
SEARCH_KEYWORD = "부동산"   # 검색란(searchWord)에 넣을 키워드 - 제목에 이 단어가 들어간 공고만 대상

WORK_DIR  = os.environ.get("SCOURT_WORK_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "work")
PDF_DIR   = os.path.join(WORK_DIR, "pdf")
EXCEL_DIR = WORK_DIR
# ✅ v3.5: "구글시트 단일 기준 + 로컬은 백업용 스냅샷만" 아키텍처로 전환.
#    예전에는 EXCEL_PATH(누적파일)를 매 실행마다 열어서 이어쓰고 다시 읽어들이는 "살아있는
#    작업 사본"으로 취급했는데, 이게 구글시트와 서로 미묘하게 어긋나는(포맷 드리프트,
#    중복 축적, 삭제한 게 되살아남 등) 모든 문제의 근본 원인이었다. 이제 로컬 파일은
#    실행마다 새로 만드는 "그 시점 구글시트 상태의 불변 스냅샷"일 뿐이며, 다음 실행 때
#    다시 읽어서 뭔가 판단하는 데 절대 쓰이지 않는다.
SNAPSHOT_DIR = os.path.join(EXCEL_DIR, "snapshots")

# ✅ v3.6.9: 주소 → PNU(토지 고유번호) 조회로 주소 정확성을 검증한다.
# VWorld(국토교통부) 검색 API를 쓴다 — https://www.vworld.kr 에서 발급받은 개인 키.
# PNU가 정상적으로 반환되면 그 주소가 실제 존재하는 행정구역/지번이라는 뜻이라
# OCR 오탈자로 인한 "그럴듯하지만 실제로는 없는 주소"를 걸러내는 데 쓸 수 있다.
# (완전히 다른 실제 주소로 오인식된 경우는 PNU가 나와도 못 걸러내지만, 최소한
# "존재하지 않는 지번"은 확실히 걸러진다.)
VWORLD_API_KEY = os.environ.get("VWORLD_API_KEY", "").strip()
KAKAO_REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "").strip()
ENABLE_PNU_LOOKUP = bool(VWORLD_API_KEY or KAKAO_REST_API_KEY)   # False로 하면 PNU 조회 자체를 건너뜀 (API 키 없거나 속도 우선시)
PNU_API_DELAY = 0.15       # 호출 사이 최소 대기(초) — API 요청 제한 방지

MAX_PAGES = None       # None = 결과가 더 이상 없을 때까지 끝까지 순회 (안전상한 걸고 싶으면 숫자로 지정)
TEST_MODE = False       # True면 구글시트/로컬 파일 아무것도 안 건드리고 콘솔 출력만 하는 드라이런
TEST_ITEM_LIMIT = 2

# ✅ v3.6.34: 실행 모드를 실제로 쓰는 2개만 남기고 정리했다(사용자 요청 — 안 쓰는 모드가
# 코드만 복잡하게 만든다는 판단). 예전에 있던 GSHEET_FAILED_BACKFILL(사이트 재방문 재추출
# 전용 모드)과 COMPLETENESS_CHECK(21개 법원 전수조사 모드)는 삭제했다.
#
# "INCREMENTAL"    : 평소처럼 목록 페이지를 훑으며 신규 공고 수집. "구글시트가 기준
#                    (source of truth)" — 이미 아는 공고 판단을 구글시트만으로 하고, 맨
#                    위에서 아는 항목 하나 만났다고 멈추지 않고 페이지네이션이 자연스럽게
#                    끝날 때까지 계속 훑으며 모르는 것만 처리한다(그래야 구글시트 중간에서
#                    지워진 공고도 다음 실행 때 재발견됨).
# "REBUILD_MERGED" : 사이트 방문/재크롤링 없이, 지금 있는 '공고목록' 내용만 가지고
#                    '파산공매'를 처음부터 다시 만든다. 주소/입찰일정/지목 파싱 로직을
#                    코드에서 고친 뒤 이미 크롤링해둔 과거 데이터에도 즉시 반영하고 싶을 때
#                    이 모드만 돌리면 된다. ✅ v3.6.34: 지목/물건종류가 통째로 유실된 행은
#                    (예전 GSHEET_FAILED_BACKFILL이 하던 일 중 이 부분만) 로컬에 남아있는
#                    PDF를 사이트 재방문 없이 다시 읽어서 자동으로 보강한다.
# (그 외 값이면 main()이 실행된다 — 즉 RUN_MODE를 "REBUILD_MERGED"가 아닌 아무 값으로
#  두면 INCREMENTAL과 동일하게 동작한다.)
RUN_MODE = os.environ.get("SCOURT_RUN_MODE", "INCREMENTAL").strip() or "INCREMENTAL"
MAX_NEW_ITEMS = int(os.environ.get("SCOURT_MAX_NEW", "0") or 0)   # 0 = 제한 없음 (시험 실행용 상한)
RUN_DEADLINE_MINUTES = float(os.environ.get("RUN_DEADLINE_MINUTES", "300") or 300)
RUN_STARTED = time.time()

MIN_NATIVE_TEXT_LEN = 30   # 이보다 텍스트가 적으면 스캔 이미지 PDF로 간주 → OCR 사용
OCR_MAX_PAGES = 3
OCR_DPI = 300
OCR_LANG = "kor"
OCR_PSM_CONFIG = "--psm 4"
# ✅ v3.6.11: "1차가 부실할 때만 재시도"를 버리고 매번 두 해상도를 다 돌리는 방식으로 바꿨다
# (extract_pdf_text_ocr 참고). --psm은 두 해상도 모두 OCR_PSM_CONFIG(4)를 그대로 쓴다 —
# 실제 문서로 비교해보니 --psm 6(균일 블록)은 이 문서 유형(법원 공고문 표 형식)에서
# --psm 4보다 오히려 훨씬 나쁜 결과를 냈다.
OCR_FALLBACK_DPI = 450

# ✅ v3.6.20: PC 한 대에만 맞는 절대경로 하나를 박아두면 다른 PC(데스크톱 등)에서는
# 그 경로가 아예 없어서 오히려 문제가 된다. 그래서 "① PATH에서 먼저 찾아보고,
# ② 없으면 지금까지 써본 PC들의 알려진 설치 경로를 순서대로 확인"하는 자동 탐색
# 방식으로 바꿨다. 새 PC에서 poppler/tesseract를 설치했는데 PATH가 이 스크립트
# 실행 세션에 반영이 안 되는 경우엔, POPPLER_PATH_CANDIDATES / TESSERACT_CMD_CANDIDATES
# 목록에 그 PC의 실제 설치 경로를 한 줄 추가해두면 된다(기존 줄은 안 지워도 됨 —
# 각 PC는 자기 경로에서만 실제로 존재해서 걸리고, 없는 PC에서는 그냥 건너뛴다).
POPPLER_PATH_CANDIDATES = [
    r"C:\Python\startcoding\Release-26.02.0-0\poppler-26.02.0\Library\bin",  # 노트북
    # 다른 PC(예: 데스크톱)의 poppler bin 경로를 확인되는 대로 여기 추가
]
TESSERACT_CMD_CANDIDATES = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",  # 기본 설치 경로(대부분의 PC에 해당)
    # 다른 PC에 다른 경로로 설치했다면 여기 추가
]


def _find_poppler_path():
    """PATH에 이미 있으면 그걸 쓰고(None 반환 = pdf2image가 알아서 PATH에서 찾음),
    없으면 알려진 후보 경로 중 실제로 pdftoppm.exe가 있는 첫 번째 경로를 쓴다."""
    if shutil.which("pdftoppm"):
        return None
    for c in POPPLER_PATH_CANDIDATES:
        if os.path.isfile(os.path.join(c, "pdftoppm.exe")):
            return c
    return None  # 못 찾아도 일단 None으로 두고, 실제 실행 시 에러 메시지로 알 수 있게 함


def _find_tesseract_cmd():
    """PATH에 이미 있으면 그대로 두고(pytesseract 기본 동작), 없으면 후보 경로에서 찾는다."""
    if shutil.which("tesseract"):
        return None
    for c in TESSERACT_CMD_CANDIDATES:
        if os.path.isfile(c):
            return c
    return None


POPPLER_PATH = _find_poppler_path()
TESSERACT_CMD = _find_tesseract_cmd()
if HAS_OCR and TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

# --- 구글시트 연동 (선택사항) ---
GOOGLE_SHEETS_ENABLED   = True
# ✅ v3.6.35: 사용자가 실제 PDF 6개(부산회생 2021하단1257 / 서울회생 2025하단11907(비상장
# 주식) / 수원회생 2026하단11070 / 창원지방 2025하단10546 / 인천지방 2026하단100231 /
# 인천지방 2025하단101231)를 올려줘서, 이번엔 추측이 아니라 이 파일들에 실제 추출 함수를
# 직접 돌려서 검증했다. 그 과정에서 진짜 버그 하나를 새로 찾아 고쳤다:
#   - extract_property_list_from_tables()가 clean_full_address()로 "완전한 주소를 못
#     찾음"(빈 문자열)이어도 그 항목을 그냥 items에 추가해버리고 있었다. 창원지방법원
#     2025하단10546 문서에서 실제로 재현됨 — 본문 뒤에 첨부된 "응찰서(매수의향서)" 양식
#     페이지의 자유배치 텍스트를 pdfplumber의 텍스트기반 표 추출 전략이 표로 오인했고,
#     "매각대상물 :"이 헤더처럼 잡히면서 "경남 진주시"처럼 지번 없이 잘린 조각이 주소로
#     들어왔다. 이 빈 주소 항목이 있다는 사실 자체가 "표기반 추출 성공"으로 오판되어,
#     실제 주소·지목이 담긴 진짜 매각대상물 텍스트(문장형 폴백)로 아예 못 넘어갔다 —
#     즉 그 공고의 매각대상 전체를 놓치는 사고. addr가 빈 문자열이면 그 행을 건너뛰도록
#     고쳤다(fixed 후 재검증: 정상적으로 "경남 진주시 명석면 가화리 842/843 전"으로 추출됨).
#   - 물건종류 화이트리스트에 "주택"(구체적인 유형 단어 없이 그냥 "주택"만 쓰인 경우,
#     실제 인천지방법원 2025하단101231에서 확인) 추가.
#   - 서울회생 2025하단11907은 "비상장 주식 매각공고"로, 애초에 부동산이 아니어서 매각대상
#     추출이 "실패"로 나오는 게 정상이다(코드 버그 아님 — 대법원 사이트의 제목 필터를
#     통과했지만 내용은 부동산이 아닌 특수 사례).
# ✅ v3.6.34: 사용자 요청 두 가지 반영.
#   1) 실행 모드 정리 — 실제로 안 쓰는 GSHEET_FAILED_BACKFILL / COMPLETENESS_CHECK 모드와
#      그 전용 코드(run_gsheet_failed_backfill/run_completeness_check/collect_court_seq_ids/
#      COURT_CODES/SKIP_VISIT_IF_ALL_CACHED/_update_gsheet_list_row)를 통째로 삭제했다.
#      GSHEET_FAILED_BACKFILL이 하던 일 중 "지목/물건종류가 통째로 유실된 행을 로컬 PDF로
#      다시 읽어서 고치는" 부분만 rebuild_merged_sheet() 안으로 옮겨왔다 — 사이트 재방문
#      없이 로컬에 PDF가 남아있으면 그 파일만 다시 읽고, '검토상태'에 "지목재확인시도"를
#      남겨 같은 PDF를 매번 다시 읽지 않게 했다(성공하면 '공고목록' JSON도 고쳐서 영구 반영).
#   2) PDF 검증 — 사용자가 실제 PDF를 올려주면 extract_property_list_from_tables 등을 그
#      파일에 직접 돌려 검증 가능함을 안내(코드 변경 아님).
# ✅ v3.6.33: '용도' 열엔 토지의 법정 지목(전/답/대/임야/잡종지 등 28종, 불명이면 "토지")을,
# 토지가 아니면(집합건물 등) 물건종류(아파트/빌라/상가 등)를 담기로 확정. 실제 데이터로
# 원인을 세 가지 찾아 각각 고쳤다:
#   1) 지목이 "지목" 필드가 아니라 "기타" 필드에 면적과 뒤섞여 저장된 행("기타":"임야 496㎡")
#      → resolve_yongdo()가 28종 화이트리스트로 '지목'뿐 아니라 '기타' 필드까지 훑어서 찾음
#      (REBUILD_MERGED만 다시 돌려도 즉시 복구됨 — 재크롤링 불필요).
#   2) 표는 정상 인식됐는데(면적/지분은 잡힘) '지목' 열 자체를 못 찾아 지목 정보가 통째로
#      유실된 행(실제 사례: 부산회생법원 2021하단1257) → extract_property_list_from_tables가
#      행 전체 텍스트에서 화이트리스트로 한 번 더 찾도록 안전장치 추가. 이미 이렇게 크롤링돼
#      버린 과거 데이터는 저장된 텍스트 어디에도 지목이 안 남아있어 REBUILD_MERGED로는 복구가
#      안 되므로, GSHEET_FAILED_BACKFILL 재추출 대상 조건에 "지목/물건종류를 하나도 못 찾은
#      행"을 추가해 다음 백필 실행 때 PDF를 다시 읽어 고치도록 했다.
#   3) (사용자 제안: "텍스트 읽으면 줄이 깨질 수 있으니 이미지로 먼저 읽으면 어떤가") 문서
#      전체를 항상 이미지로 먼저 읽게 바꾸진 않았다 — 이미 표/텍스트 추출로 면적·지분·주소는
#      대부분 잘 잡히고 있어(실제 데이터: 233건 중 못 잡은 행은 소수), 매 문서를 이미지+OCR로
#      처리하면 크롤링 전체가 몇 배 느려지는 것에 비해 이득이 적다. 대신 "주소/면적은 잡았는데
#      지목만 하나도 없는" 경우에만 선택적으로 OCR을 한 번 더 돌려서(이미 있으면 재사용) 그
#      주소 주변 텍스트에서 지목/물건종류를 화이트리스트로 찾아 보강한다
#      (_property_items_need_jimok_ocr / enrich_jimok_from_ocr) — 필요한 경우로 비용을
#      한정하면서도 사용자가 걱정한 "표 줄 깨짐" 문제에 대응한다.
# ✅ v3.6.32: 실제 구글시트 데이터로 직접 확인한 결과, '파산공매'의 여러 열이 헤더 이름과
# 전혀 다른 값을 담고 있었다(예: '사건번호' 칸엔 작성일 날짜가, '진행상태' 칸엔 회차 숫자만
# 덩그러니 들어있었음 — 코드가 열 이름과 무관하게 예전 순서 그대로 값을 채워넣던 버그).
# rebuild_merged_sheet()를 다음과 같이 고쳤다:
#   - 사건번호: 첨부파일명(대개 "OO지방법원 2026하단48 ....pdf")에서 실제 사건번호를 추출
#     (extract_case_number). 2자리 연도("26하단3")는 4자리로 보정.
#   - 소유자: 신청인정보("채무자 OOO의 파산관재인 OOO" 등 여러 실제 표현)에서 채무자(=소유자)
#     이름을 추출(extract_owner_from_applicant). 상속재산 매각(망 OOO)이면 "(사망)" 표시.
#   - 진행상태: '파산공매'엔 이미 매각완료 공고를 걸러내고 남은 것만 올라오므로, 여기 남은
#     행은 전부 "N차 진행중"(회차 정보 있으면)/"진행중"(없으면)으로 표시.
#   - 참고사항: 매각대상 항목의 '기타'(건물명/호수/임대보증금/비고 등) 그대로.
#   - 필지별 주소: 같은 공고에 딸린 모든 필지 주소를 " | "로 이어붙여, 한 공고에 여러 필지가
#     있을 때 한눈에 전체를 볼 수 있게 함.
#   - 신규여부: 재구성 직전 '파산공매'에 이미 있던 주소 집합에 없던 주소면 "신규".
# (실제 데이터 302행 기준 검증: 소유자 0건 실패/사건번호 18건 실패 — 후자는 첨부파일명
#  자체에 사건번호가 아예 없는 문서들이라 데이터상 한계.)
# ✅ v3.6.31: _ensure_header_row()가 '파산공매' 헤더를 매번 "기대 구성과 다르다"고 잘못
# 경고하던 문제 수정. MERGED_HEADERS 끝에 넣어둔 예비 빈 칸("", "")은 구글시트
# get_all_values()가 행 끝 빈 셀을 잘라내면서 읽을 때 절대 나타나지 않으므로, 실제로는
# 헤더가 정확해도 완전 일치 비교가 영원히 실패했었다 — 양쪽 다 끝의 빈 문자열을 떼어내고
# 비교하도록 고쳤다(데이터를 망가뜨리는 버그는 아니었고, 로그에 반복되던 거짓 경고 제거용).
# ✅ v3.6.30: 집 PC / 노트북 / 사무실 PC 여러 대에서 같은 스크립트를 돌리는데, 서비스계정
# 키는 "동일한 키 하나를 복사"해서 PC마다 저장 위치(폴더 구조, 대소문자)가 조금씩 다르다.
# (예: 집 PC "C:/startcoding/100. Google_credentials/...", 노트북
# "C:/Python/startcoding/100. google_credentials/..." — startcoding 밑에 Python 폴더가
# 끼어있고, 폴더명 대소문자도 다름). 경로 하나를 고정해두면 다른 PC에서는 아예 못 찾아서
# "파일 없음" 에러가 나므로, POPPLER_PATH_CANDIDATES/TESSERACT_CMD_CANDIDATES와 똑같은
# 방식으로 "PC별 후보 경로 목록 → 실제 존재하는 첫 번째 경로 자동 선택"으로 바꿨다.
# 파일명(google_credentials_편집자.json)은 편집자 권한 키로 모든 PC에서 동일하게 유지 —
# 이 스크립트는 쓰기 작업(공고목록/파산공매 추가·수정)을 하므로 반드시 편집자 권한 키를
# 써야 한다. 읽기전용 키(service_account_읽기전용.json)를 쓰면 쓰기 시도가 전부
# PERMISSION_DENIED로 실패하니, 아래 후보 목록에 "_읽기전용" 파일을 넣지 않도록 주의.
GOOGLE_CREDENTIALS_PATH_CANDIDATES = [
    "C:/startcoding/100. Google_credentials/google_credentials_편집자.json",         # 집 PC
    "C:/Python/startcoding/100. google_credentials/google_credentials_편집자.json",  # 노트북
    # 사무실 PC 경로 확인되는 대로 여기 추가 (기존 줄은 안 지워도 됨 — 각 PC는 자기
    # 경로에서만 실제로 파일이 있어서 걸리고, 없는 PC에서는 그냥 건너뛴다)
]


def _find_google_credentials_path():
    """후보 경로 중 실제로 파일이 있는 첫 번째 경로를 쓴다. 하나도 못 찾으면(예: 이번에
    처음 보는 PC이거나 후보 목록에 아직 안 넣은 경우) 첫 번째 후보를 그대로 반환해서,
    connect_google_sheet()의 기존 "키 파일 없음" 경고 메시지가 그 경로를 보여주게 한다 —
    그래야 사용자가 "어느 경로를 못 찾았는지" 바로 알 수 있다."""
    for c in GOOGLE_CREDENTIALS_PATH_CANDIDATES:
        if os.path.isfile(c):
            return c
    return GOOGLE_CREDENTIALS_PATH_CANDIDATES[0]


GOOGLE_CREDENTIALS_PATH = _find_google_credentials_path()
GOOGLE_SHEET_ID = (os.environ.get("GOOGLE_SHEET_ID") or "1CCk7fK2afaSgNqTADQZlC--mxskNhhDhdWkagQ-Y5kU").strip()
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_EDITER", "").strip()
GOOGLE_SHEET_LIST_TAB     = "공고목록"
# ✅ v3.6: '부동산목록'/'입찰일정' 탭 제거. 그 세부 정보는 이제 '공고목록'의 JSON 상세열에
#    통째로 보관하고, '파산공매'는 크롤링 시점이 아니라 매번 '공고목록'을 다시 읽어서
#    새로 만든다(rebuild_merged_sheet). 이렇게 해야 파싱 로직을 나중에 고쳤을 때 재크롤링
#    없이 과거 행까지 한번에 고쳐진다 — 실제로 파싱 버그가 고쳐진 뒤에도 '파산공매'에
#    옛날 잘못된 값이 그대로 남아있던 문제(공고목록엔 올바른 값이 있는데도)가 실사용 중
#    확인됐는데, 이 구조라면 애초에 생길 수 없는 문제다.

# --- 엑셀 헤더 ---
LIST_HEADERS = [
    "번호", "담당법원", "신청인정보", "제목", "조회수",
    "작성일", "공고만료일", "전화번호",
    "첨부파일명", "상세페이지URL", "추출방식",
    "매각대상부동산요약", "입찰일정요약", "검토상태",
    "매각대상상세JSON", "입찰일정상세JSON",  # ✅ v3.6 추가: 면적/지분/기타/회차 등 전체 정보 보존
]
# ✅ v3.6.29: '파산공매' 헤더 순서/구성을 사용자가 지정한 대로 전면 재배치.
# - "경매/공매" → "경매/공매/파산"으로 이름 변경
# - "참고사항"(주소 다음) / "소유자"(토지이용계획 다음) 신규 열 추가 — 아직 채울 데이터
#   출처가 없어 rebuild_merged_sheet()에서는 빈 칸으로 남겨둔다.
# - "상세페이지URL" → "상세페이지"로 이름을 바꾸고 맨 끝이 아니라 '입찰일' 바로 다음으로 이동.
# 아래 MERGED_COL 인덱스 상수와 함께 써서, rebuild_merged_sheet()가 순서를 하드코딩된
# 숫자가 아니라 이름으로 찾아 채우도록 했다 — 나중에 또 순서가 바뀌어도 여기 리스트만
# 고치면 된다.
MERGED_HEADERS = [
    "경매/공매/파산", "사건번호", "주소", "참고사항", "용도", "면적", "진행상태", "최저가율",
    "최저가", "감평가", "입찰일", "상세페이지", "신규여부", "지분 여부", "필지별 주소", "pnu",
    "토지이용계획", "소유자", "키워드", "", ""
]
MERGED_COL = {name: i for i, name in enumerate(MERGED_HEADERS) if name}  # 헤더 이름 → 열 인덱스(빈 열 이름은 제외)


os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(EXCEL_DIR, exist_ok=True)
IS_ACTIONS = bool(os.environ.get("GITHUB_ACTIONS"))


# =========================
# 대기/사람처럼 클릭 유틸
# =========================
def human_delay(a=1.0, b=3.0):
    time.sleep(random.uniform(a, b))


def clean_text(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def highlight_element(driver, element, color="red", duration=0.5):
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
        original_style = element.get_attribute("style") or ""
        driver.execute_script(
            "arguments[0].style.outline='3px solid %s';"
            "arguments[0].style.backgroundColor='yellow';" % color,
            element
        )
        time.sleep(duration)
        return original_style
    except Exception:
        return ""


def human_click(driver, element, label=""):
    original_style = highlight_element(driver, element)
    if label:
        print(f"   🖱️  클릭: {label}")
    try:
        driver.execute_script("arguments[0].click();", element)
    except Exception as e:
        print(f"   ⚠️ 클릭 실패: {e}")
        return False
    finally:
        try:
            driver.execute_script("arguments[0].style.cssText = arguments[1];", element, original_style)
        except Exception:
            pass
    human_delay(1.0, 3.0)
    return True


# =========================
# 드라이버
# =========================
def build_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1600,1000")
    chrome_options.add_argument("--lang=ko-KR")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
    prefs = {
        "download.default_directory": os.path.abspath(PDF_DIR),
        "download.prompt_for_download": False,
        "plugins.always_open_pdf_externally": True,
        "safebrowsing.enabled": True,
    }
    chrome_options.add_experimental_option("prefs", prefs)
    chrome_bin = os.environ.get("CHROME_BIN", "").strip()
    if chrome_bin:
        chrome_options.binary_location = chrome_bin
    drv_path = os.environ.get("CHROMEDRIVER_PATH", "").strip()
    # 드라이버는 selenium 내장 Selenium Manager 가 chrome 버전에 맞게 받는다
    driver = webdriver.Chrome(service=Service(drv_path) if drv_path else Service(), options=chrome_options)
    driver.set_page_load_timeout(90)
    return driver


# =========================
# 목록 페이지 (searchWord=부동산 필터 적용)
# =========================
def goto_list_page(driver, page_index: int):
    # ⚠️ 이 사이트는 EUC-KR 인코딩을 사용하므로, 검색어도 반드시 euc-kr로 퍼센트 인코딩해야 한다.
    #    (UTF-8로 인코딩하면 서버가 못 알아듣고 검색결과가 깨지거나 0건이 된다)
    # ✅ v3.6.34: bub_cd(법원 코드별 필터링) 매개변수는 COMPLETENESS_CHECK 모드 전용이었는데
    # 그 모드를 삭제하면서 같이 정리했다 — 전체 법원 대상(bub_cd 빈 값)으로 고정.
    q = urllib.parse.quote(SEARCH_KEYWORD, encoding="euc-kr")
    url = f"{BASE_LIST_URL}?pageIndex={page_index}&searchWord={q}&searchOption=&bub_cd="
    print(f"   🌐 이동: {url}")
    driver.get(url)
    human_delay()


# ✅ v3.3: 상세페이지URL 안의 seq_id 파라미터를 뽑는다. 이게 공고의 진짜 영구 고유 ID다.
#    화면에 보이는 '번호'는 법원이 종료 건을 정리하면 재정렬되며 바뀌는 값이라 신뢰할 수 없지만
#    (사용자 확인), seq_id는 URL에 박힌 값이라 재정렬과 무관하게 고정된다.
SEQ_ID_PATTERN = re.compile(r"[?&]seq_id=(\d+)")


def extract_seq_id(url: str) -> str:
    m = SEQ_ID_PATTERN.search(url or "")
    return m.group(1) if m else ""


def parse_list_page(driver):
    rows_out = []
    try:
        WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='RealNoticeView']"))
        )
    except TimeoutException:
        print("   ℹ️ 검색 결과 없음 (또는 상세링크를 찾지 못함)")
        return rows_out

    trs = driver.find_elements(By.CSS_SELECTOR, "tbody tr")
    for tr in trs:
        try:
            link_els = tr.find_elements(By.CSS_SELECTOR, "a[href*='RealNoticeView']")
            if not link_els:
                continue
            title_el = link_els[0]
            detail_url = title_el.get_attribute("href")
            title = clean_text(title_el.text)
            if not title:
                continue
            if SEARCH_KEYWORD not in title:
                continue

            tds = tr.find_elements(By.CSS_SELECTOR, "td")
            no        = clean_text(tds[0].text) if len(tds) > 0 else ""
            court     = clean_text(tds[1].text) if len(tds) > 1 else ""
            applicant = clean_text(tds[2].text) if len(tds) > 2 else ""
            views     = clean_text(tds[-1].text) if tds else ""

            rows_out.append({
                "no": no, "court": court, "applicant": applicant,
                "title": title, "views": views, "detail_url": detail_url,
                "seq_id": extract_seq_id(detail_url),  # ✅ v3.3: 진짜 고유 식별자
            })
        except (NoSuchElementException, StaleElementReferenceException):
            continue
    return rows_out


# =========================
# 상세 페이지
# =========================
def parse_detail_page(driver):
    info = {"작성일": "", "공고만료일": "", "전화번호": "", "attachments": []}
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.tableVer"))
        )
        cells = driver.find_elements(By.CSS_SELECTOR, "table.tableVer th, table.tableVer td")
        texts = [clean_text(c.text) for c in cells]

        def get_value_after(label):
            for i, t in enumerate(texts):
                if t == label and i + 1 < len(texts):
                    return texts[i + 1]
            return ""

        info["작성일"]     = get_value_after("작성일")
        info["공고만료일"] = get_value_after("공고만료일")
        info["전화번호"]   = get_value_after("전화번호")

        links = driver.find_elements(By.CSS_SELECTOR, "table.tableVer a[href*='download(']")
        for a in links:
            name = clean_text(a.text)
            if name:
                info["attachments"].append({"element": a, "name": name})
    except TimeoutException:
        pass
    return info


# =========================
# 첨부파일 다운로드
# =========================
def snapshot_pdf_dir():
    return set(glob.glob(os.path.join(PDF_DIR, "*.pdf")) + glob.glob(os.path.join(PDF_DIR, "*.crdownload")))


def download_attachment_via_click(driver, link_element, timeout=30):
    before = snapshot_pdf_dir()
    if not human_click(driver, link_element, label="첨부파일 다운로드"):
        return None
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(0.5)
        now = snapshot_pdf_dir()
        added = now - before
        pdfs = [p for p in added if p.endswith(".pdf")]
        still_downloading = any(p.endswith(".crdownload") for p in now)
        if pdfs and not still_downloading:
            return pdfs[0]
    print("   ⚠️ 다운로드 완료 확인 실패 (타임아웃)")
    return None


def find_existing_pdf(att_name: str):
    """
    ✅ v3.6.3: 다운로드 폴더(PDF_DIR)에 같은 이름의 파일이 이미 있으면 그걸 그대로 쓴다.
    대법원 사이트의 첨부파일명은 클릭 시 브라우저가 그 이름 그대로 저장하므로
    (동명이인 파일이 있을 때만 브라우저가 "(1)" 등을 붙임), 첨부파일명과 정확히 같은
    파일이 폴더에 있으면 어제/이전 실행에서 이미 받아둔 바로 그 파일일 가능성이 매우 높다.
    이러면 클릭→다운로드 대기 과정을 건너뛰어 그만큼 시간이 줄어든다.
    0바이트(다운로드 중 깨진 파일 등)는 재사용하지 않고 새로 받는다.
    """
    if not att_name:
        return None
    candidate = os.path.join(PDF_DIR, att_name)
    if os.path.exists(candidate) and os.path.getsize(candidate) > 0:
        return candidate
    return None


# =========================
# PDF 텍스트 추출 (native)
# =========================
def extract_pdf_text(pdf_path: str) -> str:
    text = ""
    if HAS_PDFPLUMBER:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text = "\n".join((p.extract_text() or "") for p in pdf.pages)
        except Exception as e:
            print("   ⚠️ pdfplumber 추출 실패:", e)
    if not text and HAS_PYPDF2:
        try:
            reader = PdfReader(pdf_path)
            text = "\n".join((p.extract_text() or "") for p in reader.pages)
        except Exception as e:
            print("   ⚠️ PyPDF2 추출 실패:", e)
    return text


# =========================================================================
# ✅ v3: 표 추출 전략 다중화 (테두리 없는/텍스트정렬 기반 표 대비)
# =========================================================================
def _extract_tables_multi_strategy(page):
    """
    기본(ruling-line 기반) 표 추출이 실패하면(=결과 0개), pdfplumber의 텍스트 정렬 기반
    전략으로 한 번 더 시도한다. 표가 정상 인식되면 표 기반 추출(정확도 높음)을 그대로 쓰게 되어,
    문장형 정규식 폴백으로 떨어지는 빈도 자체를 줄이는 게 목적이다.
    (문장형 폴백은 아무리 정규식을 다듬어도 '표의 다른 열 값과 뒤섞여 읽히는' 근본적인
     위험이 있으므로, 애초에 표로 인식시키는 쪽이 훨씬 안전하다.)
    """
    try:
        tables = page.extract_tables()
    except Exception:
        tables = []
    if tables:
        return tables
    for settings in (
        {"vertical_strategy": "text", "horizontal_strategy": "text"},
        {"vertical_strategy": "text", "horizontal_strategy": "lines"},
        {"vertical_strategy": "lines", "horizontal_strategy": "text"},
    ):
        try:
            tables = page.extract_tables(table_settings=settings)
        except Exception:
            tables = []
        if tables:
            return tables
    return []


# =========================================================================
# ✅ v3: OCR 강화 (다중 시도 + 품질점수 채택 + 워드랩 보정)
# =========================================================================
def _score_ocr_text(text: str) -> int:
    """OCR 결과가 얼마나 '쓸만한지' 대략적으로 점수 매긴다 (완벽한 검증이 아니라
    여러 시도 중 더 나은 결과를 상대 비교로 고르기 위한 용도).
    한글 글자수 + 숫자 글자수를 점수로 삼는다 (텍스트가 심하게 깨지면 둘 다 적게 나온다)."""
    if not text:
        return 0
    hangul = len(re.findall(r"[가-힣]", text))
    digits = len(re.findall(r"\d", text))
    return hangul + digits


def _run_ocr_once(pdf_path: str, max_pages: int, dpi: int, psm_config: str) -> str:
    try:
        images = convert_from_path(
            pdf_path, dpi=dpi, first_page=1, last_page=max_pages,
            poppler_path=(POPPLER_PATH or None),  # ✅ v3.6.19: PATH 미반영 문제 우회용 명시 경로
        )
    except Exception as e:
        print(f"   ⚠️ pdf2image 변환 실패(poppler 미설치 가능성, dpi={dpi}): {e}")
        return ""
    texts = []
    for img in images:
        try:
            # 그레이스케일 + 자동대비(가벼운 보정) — 과도한 이진화/확대는 실측상 오히려 정확도 저하
            proc_img = ImageOps.autocontrast(img.convert("L"))
            texts.append(pytesseract.image_to_string(proc_img, lang=OCR_LANG, config=psm_config))
        except Exception as e:
            print(f"   ⚠️ OCR 실패(tesseract-ocr-kor 미설치 가능성, dpi={dpi}, {psm_config}): {e}")
    return "\n".join(texts)


def soft_join_wrapped_lines(text: str) -> str:
    """
    OCR/네이티브 텍스트에서 '문장/항목 구분'이 아니라 단순 워드랩(단어 중간 줄바꿈)으로 보이는
    줄바꿈을 공백으로 합친다. 표 셀 안에서 줄바꿈된 주소("김제시"↵"백산면 상리 720")가
    문장형 정규식 폴백 단계에서 끊기는 것을 막기 위한 2차 방어선이다
    (1차 방어선은 주소 정규식 자체의 필러가 공백류를 허용하도록 바꾼 것).

    빈 줄(문단 구분으로 추정)이나, 새 항목/문장이 시작하는 것으로 보이는 패턴
    (번호., 글머리기호, 시/도 이름으로 시작 등) 앞의 줄바꿈, 그리고 이전 줄이 마침표/콜론
    등으로 끝나는 경우는 그대로 유지한다.
    """
    lines = text.split("\n")
    out = []
    for i, line in enumerate(lines):
        if i == 0:
            out.append(line)
            continue
        cur = line
        if not cur.strip() or not out[-1].strip():
            out.append(cur)
            continue
        starts_new_item = bool(re.match(
            r"^\s*(?:\d+\s*[.\)]|[가-힣]\s*[.\)]|" + SIDO_PATTERN + r")", cur
        ))
        prev_ends_sentence = bool(re.search(r"[.:;]\s*$", out[-1]))
        if starts_new_item or prev_ends_sentence:
            out.append(cur)
        else:
            out[-1] = out[-1].rstrip() + " " + cur.lstrip()
    return "\n".join(out)


def normalize_ocr_text(text: str) -> str:
    """
    Tesseract가 한글을 한 글자씩 띄어서 인식하는 경우가 많다 (예: "제 주 특 별 자 치 도").
    이러면 주소/지역명 정규식이 전혀 매칭되지 않으므로, 한글-한글 사이의 공백을 제거해서
    붙어있는 정상 텍스트 형태로 되돌린다. 이어서 단순 워드랩(줄바꿈)도 공백으로 합쳐준다.

    ✅ v3.6.7: 지번의 하이픈("-")이 OCR에서 한글 한 글자로 잘못 인식되는 경우가 실제 문서에서
    확인됐다 (예: "산75-1" → "산75ㄱ1"). 숫자와 숫자 사이에 한글이 정확히 한 글자만 끼어있는
    경우는 원래 하이픈이었을 가능성이 매우 높으므로("칠십오점일" 같은 정상 한글 단어가 숫자
    사이에 낄 일은 없음) 하이픈으로 되돌린다.
    """
    if not text:
        return text
    text = re.sub(r"(?<=\d)[가-힣ㄱ-ㅎㅏ-ㅣ](?=\d)", "-", text)
    text = re.sub(r"(?<=[가-힣])\s+(?=[가-힣])", "", text)
    return soft_join_wrapped_lines(text)


def extract_pdf_text_ocr(pdf_path: str, max_pages: int = OCR_MAX_PAGES, dpi: int = OCR_DPI) -> str:
    """
    스캔 이미지 PDF에서 OCR로 텍스트를 뽑는다.

    ✅ v3.6.11: "1차 결과가 부실할 때만 재시도"하던 방식을 버리고, 매번 dpi=300과
    dpi=450(둘 다 --psm 4)을 항상 같이 돌려서 더 나은 쪽을 쓴다. OCR 비용은 대략
    2배가 되지만, 페이지 전체 기준 "부실함" 판정으로는 주소 한 줄만 깨진 경우를
    못 잡아낸다는 게 실제 문서로 확인됐다(페이지 전체엔 글자가 충분히 많아 점수는
    높게 나오는데 정작 핵심인 주소만 오독됨).

    ⚠️ 단순 글자수 점수(_score_ocr_text)로 "어느 쪽이 더 정확한지" 비교하는 것도
    실측해보니 신뢰할 수 없었다(dpi=300이 글자수는 더 많은데 실제 주소 정확도는
    dpi=450이 더 좋았음). 대신 dpi=450 결과를 기본으로 우선한다 — 여러 문서로
    비교해본 결과 일관되게 더 정확했다. 다만 dpi=450 렌더링/OCR 자체가 뭔가
    크게 실패해서 점수가 dpi=300의 절반에도 못 미치면(예: 페이지 변환 오류 등)
    안전하게 dpi=300 쪽으로 대체한다.
    """
    if not HAS_OCR:
        return ""

    text_300 = _run_ocr_once(pdf_path, max_pages, dpi, OCR_PSM_CONFIG)
    text_450 = _run_ocr_once(pdf_path, max_pages, OCR_FALLBACK_DPI, OCR_PSM_CONFIG)
    score_300 = _score_ocr_text(text_300)
    score_450 = _score_ocr_text(text_450)

    if score_450 >= score_300 * 0.5:
        best_text = text_450
    else:
        print(f"   ℹ️ 고해상도(dpi={OCR_FALLBACK_DPI}) 결과가 비정상적으로 부실함"
              f"(score={score_450} vs 기본 {score_300}) → 기본 해상도로 대체")
        best_text = text_300

    return normalize_ocr_text(best_text)


# =========================================================================
# ① '매각 대상' 부분: 주소 / 면적 / 기타  추출
# =========================================================================

SIDO_PATTERN = (
    r"(?:서울특별시|서울시|서울|부산광역시|부산시|부산|대구광역시|대구시|대구|"
    r"인천광역시|인천시|인천|광주광역시|광주시|광주|대전광역시|대전시|대전|"
    r"울산광역시|울산시|울산|세종특별자치시|세종시|세종|"
    r"경기도|경기|강원특별자치도|강원도|강원|충청북도|충북|충청남도|충남|"
    r"전북특별자치도|전라북도|전북|전라남도|전남|경상북도|경북|경상남도|경남|"
    r"제주특별자치도|제주도|제주)"
)
ADMIN_UNIT_HINT = re.compile(r"(시|군|구|읍|면|동|리|로|길)")

# ✅ v3.6.6: 시/군/구/읍/면/동/리 단위 사이 공백이 통째로 사라진 주소를 재구성하기 위한 패턴.
# 이름 부분을 1~3글자로 제한한 것이 핵심이다 — 그래야 "군산시"처럼 이름 안에 접미사와 같은
# 글자('군')가 들어있어도, 그리디 매칭이 "군"에서 섣불리 끊지 않고 "군산"+"시"로 정확히 묶인다.
ADMIN_CHUNK_PATTERN = re.compile(r"[가-힣]{1,3}(?:시|군|구|읍|면|동|리)")


def respace_admin_units(s: str) -> str:
    """
    시/군/구/읍/면/동/리로 끝나는 단위를 그리디하게 하나씩 인식하면서, 그 단위와 다음 글자
    사이에 공백이 없고 다음 글자가 한글이면(=다른 단위가 곧바로 이어붙은 것으로 판단) 공백을
    넣어준다. 이미 공백이 있거나 다음이 숫자/문자열 끝이면 건드리지 않는다.
    """
    if not s:
        return s
    out = []
    last_end = 0
    for m in ADMIN_CHUNK_PATTERN.finditer(s):
        out.append(s[last_end:m.end()])
        last_end = m.end()
        if last_end < len(s) and re.match(r"[가-힣]", s[last_end]):
            out.append(" ")
    out.append(s[last_end:])
    return "".join(out)


def respace_korean_address(addr: str) -> str:
    """
    ✅ v3.6.6: OCR이 한글-한글 사이 공백을 전부 지워버리면서(원래는 "제 주 특 별 자 치 도"처럼
    한 글자씩 쪼개진 걸 붙이려던 것) "군산시개정면통사리"처럼 원래 있어야 할 행정구역 단위
    사이 공백까지 같이 사라지는 문제를 되돌린다.
    시/도 접두어는 SIDO_PATTERN으로 정확히 알 수 있으므로 먼저 떼어내고, 나머지에 대해서만
    시/군/구/읍/면/동/리 그리디 재띄어쓰기를 적용한다 (시/도 이름 자체는 4~7글자로 길어서
    그리디 방식이 오탐할 수 있어 따로 분리 처리).
    이미 정상적으로 띄어쓰기 된 주소는 그대로 유지된다(안전하게 반복 적용 가능).
    """
    if not addr:
        return addr
    m = re.match(SIDO_PATTERN, addr)
    if m:
        sido = m.group(0)
        rest = respace_admin_units(addr[m.end():].lstrip())
        return (sido + " " + rest).strip() if rest else sido
    return respace_admin_units(addr)


def clean_full_address(raw_addr: str):
    """
    '완전한 주소' 패턴을 문자열 안에서 직접 찾아내고, 그 앞뒤에 붙은 건 전부 '부가정보'로 뗀다.
    반환: (정제된 주소, 주소 앞뒤에서 잘려나간 부가정보)
    완전한 주소를 아예 못 찾으면 → ("", "") (엉뚱한 텍스트였다는 뜻이므로 둘 다 비움)
    """
    s = clean_text(raw_addr)
    if not s:
        return "", ""

    m = FINAL_ADDR_PATTERN.search(s)
    if not m:
        m = FINAL_ADDR_BARE_CITY_PATTERN.search(s)
    if not m:
        return "", ""

    addr = m.group(0)
    extra = clean_text((s[:m.start()] + " " + s[m.end():]).strip())
    addr = respace_korean_address(addr)  # ✅ v3.6.6: 사라진 행정구역 단위 사이 공백 복원
    addr = re.sub(r"([가-힣])\s+(읍|면|동|리|가|로|길|구|군|시)(?=\s|\d|$)", r"\1\2", addr)

    return clean_text(addr), extra



# 표 헤더에서 "주소 관련 열"을 찾기 위한 키워드
# ✅ v3: '지번'(=지 번) 추가 — 이 법원처럼 열 이름이 '주소'가 아니라 '지번'인 경우가 있음.
#    짧고 흔한 단어는 '완전히 일치'할 때만 인정하고(송달주소/연락처 등 오탐 방지),
#    구체적인 복합어는 '포함'되면 인정한다.
ADDRESS_COL_EXACT_KEYWORDS    = ["주소", "부동산", "소재지", "지번"]
ADDRESS_COL_CONTAINS_KEYWORDS = [
    "매각대상물", "부동산의표시", "매각대상", "소재지",
    # ✅ v3.6.13: "부동산 소재지"처럼 '소재지'가 포함된 헤더가 실제 문서에서 확인됨.
    # '소재지'는 이미 ADDRESS_COL_EXACT_KEYWORDS에도 있지만 그건 헤더가 정확히
    # "소재지" 하나일 때만 인정하는 것이고, 여기 CONTAINS 목록에도 넣어야
    # "부동산 소재지"처럼 다른 말과 붙어있는 헤더도 잡힌다. 표를 못 찾으면
    # 문장형 폴백으로 떨어지는데, 그 경로에서 표의 다른 열(비고/순번 등) 내용이
    # 뒤섞여 엉뚱한 주소가 만들어지는 사고가 실제로 확인됐다.
]
AREA_COL_KEYWORDS     = ["면적"]
BUILDING_COL_KEYWORDS = ["건물명", "차,동", "동)", "건물내역"]
UNIT_COL_KEYWORDS     = ["호수"]
DEPOSIT_COL_KEYWORDS  = ["임대보증금", "보증금(원)", "보증금"]
REMARK_COL_KEYWORDS   = ["비고"]
SHARE_COL_KEYWORDS    = ["지분"]  # ✅ v3.6.13: "채무자 지분"처럼 지분 전용 열이 있는 문서 대비
# ✅ v3.6.23: '지목' 전용 열이 있는 문서(토지)뿐 아니라, 집합건물 공고문에서 흔히 쓰이는
# "용도" 열(예: "연립주택", "다세대주택", "근린생활시설" 등)도 '파산공매' D열(용도)의
# 출처로 인정한다. 실제 창원지방법원 2024하단66(손지원) 공고문에서 확인됨 — 표 헤더가
# "지목"이 아니라 "용도"였고, 값도 "연립주택"으로 이미 깨끗했는데 기존 키워드 목록에
# "용도"가 없어서 이 열 자체를 못 찾고 D열이 비어 있었다.
JIMOK_COL_KEYWORDS    = ["지목", "용도"]

# ✅ v3.1: '매매목적물'/'매각목적물' 추가 — 서울회생법원 2024하단104794 공고문 실제 검증으로 발견.
#    (이 표현을 못 찾아도 코드 자체는 전체 텍스트를 스캔 범위로 잡아 동작은 하지만,
#     섹션 경계를 정확히 잡아야 무관한 다른 조항의 숫자를 오탐할 위험이 줄어든다)
PROPERTY_SECTION_HEADING = re.compile(
    r"매각\s*대상(?:\s*부동산)?(?:\s*목록)?|매각\s*부동산|부동산\s*의\s*표시|매매\s*목적물|매각\s*목적물"
    r"|공매\s*부동산|공매\s*대상"
    # ✅ v3.6.15: "공매 부동산"이라는 표현이 실제 문서에서 확인됨. 이게 목록에 없으면
    # 섹션 경계를 못 찾아 문서 전체(입찰장소/사무실 주소 등)를 뒤지게 되고, 그 결과
    # 뒤쪽에 있는 무관한 주소(예: 입찰장소)를 매각대상 부동산으로 잘못 집는 사고가 난다.
)
NEXT_SECTION_HEADING = re.compile(
    r"\n\s*(?:\d+\s*[.\)]|[가-힣]\s*[.\)]|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+\s*[.\)])\s*(?!" + SIDO_PATTERN + r")\S"
)

AREA_UNIT_PATTERN = r"(?:㎡|㎥|ｍ|ㅁ|ㅠ)"  # ✅ v3.6.7: 실제 OCR 결과에서 '㎡'가 'ㅠ'로 오독되는 사례 확인, 추가

# ✅ v3.6.22: 주소 셀에 "(임야) 8187㎡"처럼 괄호+공백과 함께 지목이 면적 바로 앞에 붙어있는
# 경우, 지목 글자만 뽑아내기 위한 패턴 ('파산공매' D열은 지목만 깨끗하게 들어가야 하므로
# 면적 숫자까지 같이 들어가면 안 된다).
JIMOK_INLINE_PATTERN = re.compile(r"\(?([가-힣]{1,4})\)?\s*[\d,\.]+\s*" + AREA_UNIT_PATTERN)

# ✅ v3: 지번 뒤에 쉼표+숫자(",229"처럼 천단위 콤마 금액의 일부로 보이는 경우)가 바로 이어지면
#    지번이 아니라 다른 열의 '금액'일 가능성이 매우 높으므로 부정형 전방탐색으로 제외한다.
#    (예: 표 인식 실패로 문장형 폴백이 됐을 때, "김제시 7,812,229"처럼 다른 열 값이 바로
#     뒤에 붙어 읽히는 경우가 있는데, 이 안전장치가 없으면 "7"을 지번으로 잘못 채택함)
ADDR_END_PATTERN = (
    r"(?:산[ \t]*)?\d+(?:-\d+)?(?:[가-힣]{0,2}길[ \t]*\d+(?:-\d+)?)?"
    r"(?!\s*분의)(?!,\d)"
)

# ✅ v3: 시/도와 지번 사이의 '필러'를 한글/공백류로만 제한한다 (숫자는 "역삼2동", "테헤란로7길"
#    처럼 뒤에 한글이 바로 붙어 지명의 일부일 때만 허용). 기존처럼 '줄바꿈만 아니면 아무 문자나
#    60자까지'를 허용하면, 표 인식 실패 시 다른 열의 숫자(면적/금액 등)를 건너뛰어 지번으로
#    오인하는 사고가 난다. \s 안에 개행도 포함되므로, PDF 셀 안에서 줄바꿈으로 잘린 주소
#    ("김제시"↵"백산면 상리 720")도 자연스럽게 하나로 이어붙여 인식된다.
#    non-greedy가 아니라 greedy로 바꾼 것도 중요 포인트: "역삼2동"처럼 주소 중간에 낀 숫자에서
#    섣불리 매칭을 끝내지 않고, 실제 지번(문자열 끝쪽)까지 최대한 밀고 나간 뒤 필요한 만큼만
#    백트래킹하게 된다.
ADDR_FILLER = r"(?:[가-힣]|\s|\d(?=[가-힣]))"

FINAL_ADDR_PATTERN = re.compile(SIDO_PATTERN + ADDR_FILLER + r"{0,40}" + ADDR_END_PATTERN)
FINAL_ADDR_BARE_CITY_PATTERN = re.compile(
    r"[가-힣]{2,6}(?:시|군|구)" + ADDR_FILLER + r"{0,40}" + ADDR_END_PATTERN
)

# ✅ v3.1: 지번 바로 뒤에 마침표가 붙는 표기("...창매리 290. 답 552㎡.")를 위해
#    지목 앞에 마침표 하나는 허용한다(실제 서울회생법원 공고문에서 발견).
PLAIN_PROPERTY_AREA_PATTERN = re.compile(
    r"(" + SIDO_PATTERN + ADDR_FILLER + r"{1,40}" + ADDR_END_PATTERN + r")"
    r"\.?\s*([가-힣]{1,6})?\s*([\d,\.]+)\s*" + AREA_UNIT_PATTERN
)

PLAIN_PROPERTY_NOAREA_PATTERN = re.compile(
    r"(?:\[([^\[\]]{1,12})\]\s*)?(" + SIDO_PATTERN + ADDR_FILLER + r"{1,40}" + ADDR_END_PATTERN + r")"
)

BARE_CITY_ADDR_PATTERN = re.compile(
    r"\[([^\[\]]{1,12})\]\s*([가-힣]{2,6}(?:시|군|구)" + ADDR_FILLER + r"{1,40}" + ADDR_END_PATTERN + r")"
)

AREA_NEARBY_PATTERN = re.compile(r"([\d,\.]+)\s*" + AREA_UNIT_PATTERN)
SHARE_HINT = re.compile(r"지분")


def clean_area_value(s: str) -> str:
    """
    면적 열 값을 정리한다. 보통은 "331", "50.55"처럼 숫자로 시작하지만,
    ✅ v3.6.23: '지목/면적'이 한 열에 같이 들어있는 표(예: "임야 331㎡")에서는 이 열이
    지목 값으로도 재사용되기 때문에, 숫자가 아니라 한글로 시작하는 경우가 생긴다.
    그런 경우엔 문자열 어디에 있든 "숫자+㎡/㎥ 등 단위" 조합을 찾아서 숫자만 뽑아낸다.
    """
    if not s:
        return s
    m = re.match(r"[\d,\.]+", s.strip())
    if m:
        return m.group(0)
    m2 = AREA_NEARBY_PATTERN.search(s)
    if m2:
        return clean_text(m2.group(1))
    return s


def clean_jimok_value(s: str) -> str:
    """
    ✅ v3.6.23: '지목' 전용 열이 따로 없고 "지목 / 면적"처럼 한 열에 같이 들어있는 표
    (예: 셀 값이 "임야 331㎡")에서는 지목 열 원본 값에 면적 숫자가 섞여 있다.
    이 경우 지목 글자만 뽑아낸다("임야 331㎡" → "임야"). "연립주택"처럼 면적이 안 섞인
    이미 깨끗한 값(용도 열 등)은 그대로 둔다.
    """
    if not s:
        return s
    m = JIMOK_INLINE_PATTERN.search(s)
    if m:
        return clean_text(m.group(1))
    return clean_text(s)


# ✅ v3.6.33: '파산공매' D열(용도)에 "토지 종류가 아닌 것"(면적 숫자, 빈 값 등)이 들어가거나
# 아예 빈 칸으로 남는 사고가 실제 데이터로 여럿 확인됐다. 사용자 요청에 따라 이 열의 의미를
# 명확히 정한다: 토지면 '지적법'상 28개 법정 지목(대/전/답/임야/잡종지 등, 분류 불명이면
# "토지") 중 하나, 토지가 아니면(집합건물 등) 물건 종류(아파트/빌라/상가 등)를 담는다.
# 이 화이트리스트를 "지목/기타/건물명" 등 이미 갖고 있는 텍스트에서 값을 재확인/보강하는
# 데 쓴다 — 표의 특정 열(지목/용도) 인식 자체가 실패해도, 같은 행의 다른 텍스트 어딘가에
# 이 단어들이 남아있으면 거기서 건져올 수 있다.
JIMOK_28_TERMS = [
    "전", "답", "과수원", "목장용지", "임야", "광천지", "염전", "대", "공장용지",
    "학교용지", "주차장", "주유소용지", "창고용지", "도로", "철도용지", "제방",
    "하천", "구거", "유지", "양어장", "수도용지", "공원", "체육용지", "유원지",
    "종교용지", "사적지", "묘지", "잡종지",
    "대지",  # 법정 용어는 "대"지만, 실제 문서에 "대지"로 적힌 경우가 흔해 별칭으로 포함
    "토지",  # 28종으로 분류 안 되고 그냥 "토지"라고만 적힌 문서 대비(사용자 확인)
]
# 집합건물 등 '토지가 아닌 물건'의 종류. 지목 화이트리스트에서 아무것도 못 찾았을 때만
# 대신 채워 넣는다(우선순위가 지목보다 낮음).
BUILDING_TYPE_TERMS = [
    "아파트", "연립주택", "다세대주택", "다가구주택", "단독주택", "도시형생활주택",
    "오피스텔", "상가", "근린생활시설", "공장", "창고", "빌라", "다중주택",
    "숙박시설", "업무시설", "지식산업센터",
    # ✅ v3.6.35: 실제 문서(인천지방법원 2025하단101231)에서 "샌드위치조 판넬(조립식)지붕
    # 단층 주택 98.85㎡"처럼 위 구체적인 유형 단어 없이 그냥 "주택"만 쓰인 경우가 확인됨
    # — 위 목록에 없는 형태라 못 잡히고 있었다. 좀 더 구체적인 단어("단독주택" 등)가 이미
    # 앞에서 매칭됐다면 그게 먼저 쓰이고, 그것도 없을 때만 이 범용 단어로 대체된다.
    "주택",
]


def _terms_to_isolated_pattern(terms: list) -> re.Pattern:
    """단어 목록을 '앞뒤가 한글로 이어붙지 않은 경우에만' 매칭하는 패턴으로 만든다.
    "대"/"전"/"답"처럼 한 글자짜리 지목이 "대구", "답십리동", "전주" 같은 무관한 단어
    안에서 잘못 걸리는 걸 막기 위함(Python re의 \\b는 한글-한글 사이를 경계로 안 봐서
    못 씀 — 대신 앞뒤가 한글이 아닌지를 직접 lookaround로 검사한다)."""
    alt = "|".join(sorted(terms, key=len, reverse=True))
    return re.compile(r"(?<![가-힣])(" + alt + r")(?![가-힣])")


JIMOK_TERM_PATTERN = _terms_to_isolated_pattern(JIMOK_28_TERMS)
BUILDING_TYPE_TERM_PATTERN = _terms_to_isolated_pattern(BUILDING_TYPE_TERMS)


def _scan_jimok_whitelist(text: str) -> str:
    if not text:
        return ""
    m = JIMOK_TERM_PATTERN.search(text)
    return m.group(1) if m else ""


def _scan_building_type_whitelist(text: str) -> str:
    if not text:
        return ""
    m = BUILDING_TYPE_TERM_PATTERN.search(text)
    return m.group(1) if m else ""


def resolve_yongdo(item: dict) -> str:
    """매각대상 항목 dict(주소/면적/지분/지목/기타 등)에서 '파산공매' 용도(D)열에 넣을
    최종 값을 결정한다. 우선순위:
      1) '지목' 필드가 이미 28종 화이트리스트(또는 "토지")와 일치 → 그대로 사용
      2) '지목'/'기타' 텍스트 어딘가에서 화이트리스트 지목 단어를 찾을 수 있음 → 그걸 사용
      3) 그래도 없으면 '기타'/'건물명' 텍스트에서 물건종류(아파트/빌라/상가 등) 단어를 찾음
      4) '지목' 필드에 값은 있는데 위 어느 목록에도 없는 낯선 값 → 그래도 버리지 않고 그대로 씀
         (모르는 지목 표현일 수도 있으니, 화이트리스트에 없다고 무조건 빈칸으로 만들진 않는다)
      5) 아무것도 없으면 빈 문자열
    """
    if not item:
        return ""
    jimok_raw = clean_jimok_value(item.get("지목", ""))
    if jimok_raw and (jimok_raw in JIMOK_28_TERMS or JIMOK_TERM_PATTERN.fullmatch(jimok_raw)):
        return jimok_raw

    etc_text = item.get("기타", "") or ""
    combined = " ".join(p for p in [jimok_raw, etc_text] if p)

    found = _scan_jimok_whitelist(combined)
    if found:
        return found

    found_building = _scan_building_type_whitelist(combined)
    if found_building:
        return found_building

    return jimok_raw  # 화이트리스트엔 없지만 뭔가 값은 있었다면 그거라도 보존


# ✅ v3.6.32: '파산공매' D열 이하가 헤더 이름과 안 맞는 값으로 채워지던 문제(사건번호 칸에
# 작성일이, 진행상태 칸에 회차 숫자만 덩그러니 들어가던 것 등)를 고치면서, "공고목록"에
# 이미 갖고 있는 값들에서 사건번호/소유자를 실제로 뽑아내는 헬퍼를 추가한다.
#
# ✅ 사건번호: 실제 '공고목록' 데이터로 확인해보니, 목록 페이지의 '제목'(예: "부동산
# 매각공고")에는 사건번호가 없지만 '첨부파일명'에는 거의 항상 들어있다
# (예: "인천지방법원 2026하단48 부동산 매각 공고등 신청서.pdf" → "2026하단48",
#      "26하단3부동산매각공고.pdf" → 2자리 연도 표기 → "2026하단3"으로 보정).
CASE_NO_PATTERN = re.compile(r"(\d{2,4})(하[가-힣]\d+)")


def extract_case_number(text: str) -> str:
    """첨부파일명(우선) 등에서 법원 사건번호("2026하단48" 등)를 뽑는다. 2자리 연도는
    4자리로 보정한다(26 → 2026). 못 찾으면 빈 문자열."""
    if not text:
        return ""
    m = CASE_NO_PATTERN.search(text)
    if not m:
        return ""
    year, rest = m.group(1), m.group(2)
    if len(year) == 2:
        year = "20" + year
    return year + rest


# ✅ 소유자: '공고목록'의 '신청인정보' 열은 "채무자 OOO의 파산관재인 OOO" 형식이 대부분이라
# (실제 데이터로 확인됨: "채무자 조경숙의 파산관재인 최승철", "채무자 망 김성희의 상속재산
# 파산관재인 서종표" 등), '채무자' 바로 다음에 오는 이름이 곧 매각 대상 부동산의 소유자다.
# "망"(고인)이 붙어있으면 상속재산 매각(소유자 사망) 케이스라는 걸 알 수 있게 표시해둔다.
OWNER_PATTERN = re.compile(r"(?:채무자|피상속인)?\s*(망)?\s*([가-힣]{2,4}?)(?:의|\s|,|\(|$)")


def extract_owner_from_applicant(text: str) -> str:
    """'신청인정보'에서 채무자(=소유자) 이름을 뽑는다. 실제 데이터로 확인된 여러 표현
    ("채무자 OOO의 파산관재인 OOO", "망 OOO의 상속재산의 파산관재인 OOO",
    "피상속인 망 OOO의 상속재산 파산관재인 OOO", "채무자 OOO(개명전:...)의 ...")에 대응한다.
    ⚠️ 휴리스틱이라 100% 정확하진 않을 수 있고, "채무자 김숙진, 김중식의 ..."처럼 채무자가
    여럿이면 첫 번째 이름만 잡는다 — 다른 표현이 더 있으면 알려주면 패턴을 보강할 수 있다."""
    if not text:
        return ""
    m = OWNER_PATTERN.search(text)
    if not m:
        return ""
    dead_mark, name = m.group(1), m.group(2)
    return f"{name}(사망)" if dead_mark else name


def _norm_header(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def _find_col(header_cells, keywords):
    """포함(contains) 매칭 - 구체적이고 긴 키워드용."""
    for i, h in enumerate(header_cells):
        hn = _norm_header(h)
        for kw in keywords:
            if _norm_header(kw) in hn:
                return i
    return None


def _find_col_by_predicate(header_cells, predicate):
    """
    ✅ v3 추가: 고정 키워드 목록 대신, 헤더 텍스트에 대한 판정 함수(predicate)로 열을 찾는다.
    입찰일/최저가 열처럼 법원마다 표현이 제각각인("입찰기한" vs "입찰마감일",
    "최저입찰가" vs "최저입찰금" 등) 경우, 키워드를 계속 추가하는 것보다
    '핵심 토큰 조합'으로 판별하는 쪽이 새로운 표현에도 더 잘 대응한다.
    """
    for i, h in enumerate(header_cells):
        if predicate(h):
            return i
    return None


def _header_matches_bid_date(h: str) -> bool:
    hn = _norm_header(h)
    return "입찰" in hn and any(k in hn for k in ["기한", "기일", "마감일", "기간", "개찰일"])


def _header_matches_min_bid(h: str) -> bool:
    hn = _norm_header(h)
    return "최저" in hn and "입찰" in hn


def _find_address_col(header_cells):
    """
    주소 열 판별 전용: 짧고 흔한 단어("주소","부동산","소재지","지번")는 '완전히 일치'할 때만
    인정하고, 구체적인 복합어("매각대상물" 등)는 '포함'되면 인정한다. (송달주소/연락처 등 오탐 방지)
    """
    for i, h in enumerate(header_cells):
        hn = _norm_header(h)
        if hn in ADDRESS_COL_EXACT_KEYWORDS:
            return i
    return _find_col(header_cells, ADDRESS_COL_CONTAINS_KEYWORDS)


def _strip_bracket_tag(addr: str):
    m = re.match(r"^\[([^\[\]]{1,12})\]\s*(.+)$", addr)
    if m:
        return clean_text(m.group(1)), clean_text(m.group(2))
    return "", addr


def find_share_note(text: str, start: int, end: int, window: int = 250) -> str:
    seg = text[end:end + window]
    for line in seg.split("\n"):
        if SHARE_HINT.search(line):
            return clean_text(line)
    return ""


AREA_DECIMAL_FALLBACK_PATTERN = re.compile(r"(\d+\.\d+)")


def find_area_after(text: str, end: int, window: int = 300) -> str:
    seg = text[end:end + window]
    m = AREA_NEARBY_PATTERN.search(seg)
    if m:
        return clean_text(m.group(1))
    m2 = AREA_DECIMAL_FALLBACK_PATTERN.search(seg)
    return clean_text(m2.group(1)) if m2 else ""


def extract_property_list_from_tables(pdf_path: str):
    """표 기반 1순위 추출: 주소 열이 있는 표에서 주소/면적/기타를 뽑는다."""
    if not HAS_PDFPLUMBER or not pdf_path:
        return []
    items = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = _extract_tables_multi_strategy(page)
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    header = [clean_text(c) for c in table[0]]
                    addr_idx = _find_address_col(header)
                    if addr_idx is None:
                        continue
                    area_idx     = _find_col(header, AREA_COL_KEYWORDS)
                    building_idx = _find_col(header, BUILDING_COL_KEYWORDS)
                    unit_idx     = _find_col(header, UNIT_COL_KEYWORDS)
                    deposit_idx  = _find_col(header, DEPOSIT_COL_KEYWORDS)
                    remark_idx   = _find_col(header, REMARK_COL_KEYWORDS)
                    # ✅ v3.6.13: "채무자 지분"처럼 지분 값을 담은 전용 열이 있는 문서 대비.
                    share_idx    = _find_col(header, SHARE_COL_KEYWORDS)
                    # ✅ v3.6.18/v3.6.23: '지목'(전/답/대지/임야/과수원 등) 또는 '용도'
                    # (연립주택/다세대주택 등, 집합건물 공고문에서 흔함) 전용 열이 있는 문서 대비.
                    jimok_idx    = _find_col(header, JIMOK_COL_KEYWORDS)

                    def cell(row, idx):
                        if idx is None or idx >= len(row):
                            return ""
                        return clean_text(row[idx])

                    for row in table[1:]:
                        if addr_idx >= len(row):
                            continue
                        raw_addr = clean_text(row[addr_idx])
                        if not raw_addr:
                            continue
                        tag, addr_before_clean = _strip_bracket_tag(raw_addr)
                        if not addr_before_clean or not ADMIN_UNIT_HINT.search(addr_before_clean):
                            continue
                        addr, addr_extra = clean_full_address(addr_before_clean)
                        # ✅ v3.6.35: 실제 PDF(창원지방법원 2025하단10546)로 확인된 버그 —
                        # clean_full_address()가 "완전한 주소를 못 찾음"이면 ("", "")을
                        # 돌려주는데, 그동안 이 경우를 걸러내지 않고 그대로 빈 주소 항목을
                        # items에 추가해왔다. 문제는 이게 "표 인식은 됐지만 빈 항목"이라는
                        # 것 — extract_property_list()의 표기반 우선순위 로직이 "items가
                        # 있으니 성공"이라고 판단해버려서, 실제 주소가 담긴 문장형 폴백으로
                        # 아예 못 넘어가고 매각대상 전체를 놓치는 사고로 이어진다(첨부된
                        # 응찰서 양식 페이지의 자유배치 텍스트를 pdfplumber의 텍스트기반
                        # 표 추출 전략이 표로 오인해서, "매각대상물 :"이 헤더처럼 잡히고
                        # "경남 진주시"처럼 잘린 조각이 주소 열 값으로 들어온 경우였다).
                        # 완전한 주소가 아니면 그 행 자체를 건너뛴다.
                        if not addr:
                            continue

                        remark_val = cell(row, remark_idx)

                        # ✅ v3.6.13: 지분 전용 열이 있으면(값이 "22484분의 33"처럼 "지분"이라는
                        # 글자 자체는 안 들어있어도) 그 값을 우선 채택. 없으면 기존처럼 주소/비고
                        # 텍스트 안에서 "지분"이라는 단어가 포함된 부분을 찾는다.
                        share_col_val = cell(row, share_idx)
                        if share_col_val:
                            share_note = share_col_val
                        else:
                            share_note = ""
                            for candidate in [raw_addr, remark_val]:
                                if candidate and SHARE_HINT.search(candidate):
                                    share_note = candidate
                                    break

                        # ✅ v3.6.13: 면적 전용 열이 없고, 주소 셀 안에 "(임야) 8187㎡"처럼
                        # 지목/면적이 같이 들어있는 문서 대비 — 주소 셀 텍스트에서 직접 찾는다.
                        area_val = clean_area_value(cell(row, area_idx))
                        if not area_val:
                            # ✅ v3.6.23: 집합건물 공고문은 "면적" 전용 열 없이 "건물내역"
                            # 열에 "철근콘크리트조 50.55㎡"처럼 면적이 섞여 들어있는 경우가
                            # 흔하다. 그 열에서 먼저 찾아보고, 그래도 없으면 주소 셀에서 찾는다.
                            building_cell = cell(row, building_idx)
                            m_area = AREA_NEARBY_PATTERN.search(building_cell) if building_cell else None
                            if not m_area:
                                m_area = AREA_NEARBY_PATTERN.search(raw_addr)
                            if m_area:
                                area_val = clean_text(m_area.group(1))

                        # ✅ v3.6.22/v3.6.23: '파산공매' D열(용도)에는 지목/용도만 깨끗하게
                        # 들어가야 하는데, 지금까지는 '기타'(유형/건물명/호수/임대보증금/비고/
                        # 주소잔여문자 등이 다 뒤섞인 필드)를 그대로 썼다. '지목' 전용 필드를
                        # 따로 만들어서 D열은 이것만 쓴다. 전용 열(지목/용도)이 있으면 그 값을
                        # 쓰되, clean_jimok_value로 혹시 섞여있는 면적 숫자를 제거한다
                        # ("지목/면적" 병합 열에서 셀 값이 "임야 331㎡"인 경우 대비).
                        # 전용 열이 아예 없으면, 주소 셀에 "(임야) 8187㎡"처럼 붙어있는 지목을
                        # 면적 숫자 없이 지목 글자만 뽑아서 채운다.
                        jimok_val = clean_jimok_value(cell(row, jimok_idx))
                        if not jimok_val:
                            m_jimok = JIMOK_INLINE_PATTERN.search(addr_extra) or JIMOK_INLINE_PATTERN.search(raw_addr)
                            if m_jimok:
                                jimok_val = m_jimok.group(1)

                        # ✅ v3.6.33: 위 두 방식(전용 열 / 주소 셀에 붙은 지목)이 다 실패하면
                        # — 표 헤더 인식이 안 됐거나 지목이 전혀 다른 열에 들어있는 경우 —
                        # 마지막 안전장치로 그 행의 모든 셀 텍스트를 통째로 훑어서 28개
                        # 법정 지목(또는 "토지") 단어가 어딘가에 있는지 찾는다. 실제로 확인된
                        # 사례(부산회생법원 2021하단1257): 표는 정상 인식(면적/지분은 잡힘)
                        # 됐는데 '지목' 열만 못 찾아서 그 행의 지목 정보 자체가 통째로
                        # 유실됐었다 — 이 안전장치가 그런 경우를 막아준다.
                        if not jimok_val:
                            row_text = " ".join(clean_text(c) for c in row if c)
                            jimok_val = _scan_jimok_whitelist(row_text) or _scan_building_type_whitelist(row_text)

                        extra_parts = [
                            p for p in [
                                jimok_val,
                                f"유형:{tag}" if tag else "",
                                f"건물명:{cell(row, building_idx)}" if building_idx is not None and cell(row, building_idx) else "",
                                f"호수:{cell(row, unit_idx)}" if unit_idx is not None and cell(row, unit_idx) else "",
                                f"임대보증금:{cell(row, deposit_idx)}" if deposit_idx is not None and cell(row, deposit_idx) else "",
                                f"비고:{remark_val}" if remark_val else "",
                                addr_extra if addr_extra else "",
                            ] if p
                        ]
                        items.append({
                            "주소": addr,
                            "면적": area_val,
                            "지분": share_note,
                            "지목": jimok_val,  # ✅ v3.6.22: 파산공매 D열(용도) 전용, 지목만 깨끗하게
                            "기타": " / ".join(extra_parts),  # 참고용(공고목록 JSON에는 계속 보존)
                        })
    except Exception as e:
        print(f"   ⚠️ 매각대상 표 추출 실패: {e}")
    return items


def _extract_property_section(text: str):
    """
    반환: (addr_safe_section, raw_section)
    - addr_safe_section: 지분 분수("6148분의 95")를 지번으로 오인하지 않도록 같은 길이의
      공백으로 치환한 버전. 주소/면적 정규식 매칭에 쓴다.
    - raw_section: 치환하지 않은 원본. 지분 텍스트를 놓치지 않고 그대로 캡처하기 위해 쓴다.
    ✅ v3.6.17: 예전에는 분수를 그냥 " "(공백 1글자)로 뭉개서 문자열 길이가 줄어들었는데,
    그러면 이후 정규식 매치의 시작/끝 위치(offset)가 원본 텍스트 위치와 어긋나게 된다.
    같은 길이로(치환된 글자 수만큼) 공백을 채우면 위치가 그대로 유지되어, 같은 s/e 값으로
    두 텍스트(안전판/원본) 모두에서 안전하게 슬라이싱할 수 있다.
    """
    if not text:
        return "", ""
    t = text.replace("\r", "\n")
    m = PROPERTY_SECTION_HEADING.search(t)
    if not m:
        raw_section = t
    else:
        start = m.end()
        next_m = NEXT_SECTION_HEADING.search(t, pos=start + 5)
        end = next_m.start() if next_m else min(len(t), start + 3000)
        raw_section = t[start:end]

    def _blank_same_length(mm):
        return " " * len(mm.group(0))

    addr_safe_section = re.sub(r"\d+\s*분의\s*\d+", _blank_same_length, raw_section)
    return addr_safe_section, raw_section


def extract_property_list_from_plain_text(text: str):
    section, raw_section = _extract_property_section(text)
    if not section:
        return []

    hits = []

    for m in PLAIN_PROPERTY_AREA_PATTERN.finditer(section):
        addr = clean_text(m.group(1))
        jimok = clean_text(m.group(2)) if m.group(2) else ""
        area = clean_text(m.group(3)) if m.group(3) else ""
        hits.append((m.start(), m.end(), addr, area, jimok))

    covered = [(s, e) for s, e, _, _, _ in hits]
    for m in PLAIN_PROPERTY_NOAREA_PATTERN.finditer(section):
        s, e = m.start(2), m.end(2)
        if any(not (e <= cs or s >= ce) for cs, ce in covered):
            continue
        tag = clean_text(m.group(1)) if m.group(1) else ""
        addr = clean_text(m.group(2))
        if not addr or not ADMIN_UNIT_HINT.search(addr):
            continue

        preceding_ctx = section[max(0, s - 20):s]
        if "도로명" in preceding_ctx and hits:
            last = hits[-1]
            merged_extra = (last[4] + " / " if last[4] else "") + f"도로명주소:{addr}"
            hits[-1] = (last[0], last[1], last[2], last[3], merged_extra)
            covered.append((s, e))
            continue

        area = find_area_after(section, e)
        hits.append((s, e, addr, area, tag))
        covered.append((s, e))

    for m in BARE_CITY_ADDR_PATTERN.finditer(section):
        s, e = m.start(2), m.end(2)
        if any(not (e <= cs or s >= ce) for cs, ce in covered):
            continue
        tag = clean_text(m.group(1)) if m.group(1) else ""
        addr = clean_text(m.group(2))
        if not addr or not ADMIN_UNIT_HINT.search(addr):
            continue
        area = find_area_after(section, e)
        hits.append((s, e, addr, area, tag))
        covered.append((s, e))

    hits.sort(key=lambda x: x[0])
    results = []
    seen_span = set()
    seen_content = set()  # ✅ v3.1: (주소, 면적) 내용 기준 중복 제거용
    for s, e, addr, area, extra in hits:
        if (s, e) in seen_span:
            continue
        seen_span.add((s, e))
        share_note = find_share_note(raw_section, s, e)  # ✅ v3.6.17: 분수 안 지워진 원본에서 찾음
        clean_addr, addr_extra = clean_full_address(addr)

        # ✅ v3.1: 공고문 본문 + 첨부된 입찰서 양식에 같은 매각대상 목록이 통째로
        #    한 번 더 나오는 문서가 있다(서울회생법원 2024하단104794 등에서 실제 확인됨).
        #    같은 주소+면적 조합이 이미 나왔으면 중복 등록을 건너뛴다.
        content_key = (clean_addr, area)
        if clean_addr and content_key in seen_content:
            continue
        seen_content.add(content_key)

        combined_extra = " / ".join(p for p in [extra, addr_extra] if p)

        # ✅ v3.6.33: PLAIN_PROPERTY_NOAREA_PATTERN/BARE_CITY_ADDR_PATTERN 경로에서는 "지목"
        # 자리에 실제 지목이 아니라 대괄호 태그("[건물]"/"[토지]" 등)가 들어간다. extra가
        # 28종 화이트리스트(또는 물건종류)와 안 맞으면, 주소 주변 텍스트에서 실제 지목/물건
        # 종류 단어를 한 번 더 찾아서 그게 있으면 그걸 우선한다 — 태그보다 실제 값이 낫다.
        jimok_field = extra
        if not (extra in JIMOK_28_TERMS or JIMOK_TERM_PATTERN.fullmatch(extra or "")
                or extra in BUILDING_TYPE_TERMS):
            nearby = raw_section[max(0, s - 50):min(len(raw_section), e + 150)]
            found = _scan_jimok_whitelist(nearby) or _scan_building_type_whitelist(nearby)
            if found:
                jimok_field = found

        results.append({
            "주소": clean_addr,
            "면적": area,
            "지분": share_note,
            "지목": jimok_field,  # ✅ v3.6.22: PLAIN_PROPERTY_AREA_PATTERN이면 실제 지목("임야" 등),
                            # 그 외 패턴이면 대괄호 태그였지만, v3.6.33부터는 화이트리스트로
                            # 주변에서 실제 값을 찾을 수 있으면 그걸 우선한다.
            "기타": combined_extra,
        })
    return results


# ✅ v3.6.7: 매각공고 요약 표(작은 글씨, 복잡한 표)보다 같이 첨부되는 등기사항증명서
# (등기부등본, 큰 글씨의 표준 정부 양식) 쪽 OCR 정확도가 실제 문서로 확인해보니 훨씬 높다.
# 요약 표에서 통째로 누락되거나 지번/구명이 오독된 항목을, 등기부등본 페이지의
# "[토지] 주소" / "[건물] 주소" 줄로 보충한다.
CIRCLED_NUM_PATTERN = re.compile(r"[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]")
DEUNGI_ADDR_LINE_PATTERN = re.compile(r"\[(?:토지|건물)\]\s*([^\n]+)")
DEUNGI_SHARE_PATTERN = re.compile(r"최종지분\s*[:：]\s*([^\n]+)")


def extract_property_list_from_deungibu_pages(pdf_path: str, max_pages: int = 24):
    """
    ✅ v3.6.12: 이름은 '등기부등본 보조 스캔'이지만, 등기부(`[토지]`/`[건물]` 패턴)뿐 아니라
    첨부된 입찰서 등에 매각대상 주소가 통째로 다시 나오는 "매각대상 목적물"/"매매목적물"
    섹션도 같이 훑는다. 요약 표(1페이지, 작은 글씨 복잡한 표)는 OCR이 자주 깨지는데,
    뒤쪽 첨부 페이지(입찰서, 등기부등본)의 같은 주소는 더 단순한 형식이라 OCR이 더
    안정적으로 되는 경우가 많다 — 둘 다 "같은 주소를 다른 페이지에서 다시 확인할 기회"로
    활용한다. 기본 스캔 범위(OCR_MAX_PAGES=3)를 벗어난 페이지까지 보므로, 첨부 문서가
    많아 요약 표가 앞쪽 몇 페이지 밖에 있는 문서에도 대응된다.
    """
    if not HAS_OCR or not pdf_path:
        return []
    try:
        # ✅ v3.6.12: 여기도 dpi=300 대신 실측상 더 정확했던 OCR_FALLBACK_DPI(450)를 쓴다.
        # 이미 여러 페이지를 도는 보조/최후수단 스캔이라 페이지당 비용 증가보다 정확도가 우선.
        images = convert_from_path(
            pdf_path, dpi=OCR_FALLBACK_DPI, first_page=1, last_page=max_pages,
            poppler_path=(POPPLER_PATH or None),  # ✅ v3.6.19
        )
    except Exception as e:
        print(f"   ⚠️ 보조 스캔: pdf2image 변환 실패: {e}")
        return []

    results = []
    seen_addr = set()
    all_pages_text = []
    for img in images:
        try:
            proc_img = ImageOps.autocontrast(img.convert("L"))
            text = pytesseract.image_to_string(proc_img, lang=OCR_LANG, config=OCR_PSM_CONFIG)
        except Exception:
            continue
        text = normalize_ocr_text(text)
        all_pages_text.append(text)

        # ① 등기부등본 형식: "[토지]"/"[건물]" 줄 + "최종지분"
        m = DEUNGI_ADDR_LINE_PATTERN.search(text)
        if not m:
            continue
        addr, _ = clean_full_address(m.group(1))
        if not addr:
            continue
        m2 = DEUNGI_SHARE_PATTERN.search(text)
        share_note = clean_text(m2.group(0)) if m2 else ""

        # ✅ v3.6.7: 등기부등본 1건은 보통 2페이지(표제부/이하여백)로 구성되어 둘 다
        # "[토지] 주소" 줄을 반복하는데, OCR 오독이 페이지마다 미세하게 달라서
        # ("금이동" vs "금이농") 완전 일치 기준으로는 중복 제거가 안 된다. 대신 지번
        # (끝의 숫자 부분)이 바로 직전 항목과 같으면 "같은 물건의 다음 페이지"로 보고
        # 새 항목을 만들지 않고 지분 정보만 비어있으면 채운다.
        lot_no = re.search(r"(\d+(?:-\d+)?)$", addr)
        prev_lot_no = re.search(r"(\d+(?:-\d+)?)$", results[-1]["주소"]) if results else None
        if results and lot_no and prev_lot_no and lot_no.group(1) == prev_lot_no.group(1):
            if not results[-1]["지분"] and share_note:
                results[-1]["지분"] = share_note
            continue

        if addr in seen_addr:
            continue
        seen_addr.add(addr)
        results.append({"주소": addr, "면적": "", "지분": share_note, "기타": ""})

    # ② "매각대상 목적물"/"매매목적물" 등 반복 섹션 형식: 이미 만들어둔 문장형 추출 로직을
    #    여러 페이지를 합친 전체 텍스트에 그대로 재사용한다 (첨부 입찰서 등에 흔함).
    combined_text = "\n".join(all_pages_text)
    plain_results = extract_property_list_from_plain_text(combined_text)
    for p in plain_results:
        addr = p.get("주소", "")
        if not addr or addr in seen_addr:
            continue
        seen_addr.add(addr)
        results.append(p)

    return results


def _property_items_need_jimok_ocr(items: list) -> bool:
    """주소는 잡았는데(=표/문장형 추출 자체는 됐는데) 지목/물건종류를 단 하나도 못 건진
    경우를 판별한다. ✅ v3.6.33: 사용자 요청 — 텍스트 기반 추출이 표의 줄이 깨져서 지목
    열을 놓치는 경우가 있으니, 이럴 때만 OCR(이미지 기반 읽기)로 한 번 더 보강 시도할
    가치가 있다고 판단한다. (매번 OCR을 돌리면 느려지므로, 필요한 경우로 한정한다)"""
    if not items:
        return False
    if not any((it.get("주소") or "").strip() for it in items):
        return False
    return not any(resolve_yongdo(it) for it in items)


def enrich_jimok_from_ocr(items: list, ocr_text: str) -> int:
    """✅ v3.6.33: 지목/물건종류가 빠진 매각대상 항목을, OCR(이미지 기반) 텍스트에서 그
    주소 근처를 찾아 화이트리스트로 보강한다. 이미 정상 추출된 주소/면적/지분 등은
    건드리지 않고, 지목만 채워 넣는다. 반환값은 실제로 채운 항목 수."""
    if not ocr_text:
        return 0
    filled = 0
    for it in items:
        if resolve_yongdo(it):
            continue
        addr = (it.get("주소") or "").strip()
        if not addr:
            continue
        # 주소 전체가 OCR 오탈자로 정확히 안 나올 수 있어, 끝쪽(지번) 조각으로 위치를 찾는다.
        needle = addr[-6:] if len(addr) >= 6 else addr
        pos = ocr_text.find(needle)
        if pos < 0:
            continue
        window = ocr_text[max(0, pos - 80):pos + 200]
        found = _scan_jimok_whitelist(window) or _scan_building_type_whitelist(window)
        if found:
            it["지목"] = found
            filled += 1
    return filled


def extract_property_list(native_text: str, ocr_text: str, pdf_path: str):
    items = extract_property_list_from_tables(pdf_path)
    if items:
        method = "표기반"
    else:
        items = extract_property_list_from_plain_text(native_text)
        if items:
            method = "문장형(텍스트)"
        else:
            items = extract_property_list_from_plain_text(ocr_text)
            method = "문장형(OCR)" if items else "추출실패"

    # ✅ v3.6.33: 위에서 주소/면적/지분은 잡혔는데 지목/물건종류가 하나도 없으면(표의 지목
    # 열만 못 찾은 경우 등), OCR 텍스트가 있으면 그걸로 지목만 보강 시도한다. (OCR 자체를
    # 새로 돌리진 않는다 — 이미 계산되어 넘어온 ocr_text가 있을 때만 활용)
    if ocr_text and _property_items_need_jimok_ocr(items):
        filled = enrich_jimok_from_ocr(items, ocr_text)
        if filled:
            print(f"   ℹ️ OCR로 지목/물건종류 보강: {filled}건")

    # ✅ v3.6.8: 등기부등본이 첨부된 문서는 흔치 않은 특수 케이스라는 걸 확인했다
    # (사용자 확인: "보통은 등기부가 없다"). 그래서 매번 OCR이 필요할 때마다 최대 24페이지를
    # 훑는 등기부 보조 스캔을 시도하면, 등기부가 없는 절대다수 문서에서는 아무 소득 없이
    # 시간만 낭비하게 된다. 대신 **1차 추출이 완전히 실패(0건)했을 때만** 마지막 수단으로
    # 시도한다 — 등기부가 있으면 이 상황에서 크게 도움이 되고, 없으면 애초에 시도조차
    # 안 하니 낭비가 없다.
    if not items and HAS_OCR and pdf_path and ocr_text:
        supplement = extract_property_list_from_deungibu_pages(pdf_path)
        if supplement:
            items = supplement
            method = "등기부보조"
            print(f"   ℹ️ 1차 추출 실패 → 등기부등본 보조 스캔으로 매각대상 {len(supplement)}건 확보")

    return items, method


# =========================================================================
# ② '입찰기한 및 최저입찰가' 부분: 회차 / 입찰기일 / 최저입찰가 추출 (주소 무시)
# =========================================================================

ROUND_COL_KEYWORDS = ["회차", "차수"]

BID_LINE_PATTERN = re.compile(
    r"(\d+)\s*차\S{0,2}\s+"
    r"(\d{4}\s*[.\-]\s*\d{1,2}\s*[.\-]\s*\d{1,2}\.?(?:\s*\d{1,2}\s*:\s*\d{2})?[^\d\n]{0,10})"
    r"\s*(?:금\s*)?([\d,]{4,})\s*원?"
)

# ✅ v3.6.21: "회차" 열 헤더에만 "차" 글자가 있고, 정작 행 값은 "1","2","3"처럼 숫자만 있는
# 표 형식이 실제 문서(스캔 이미지, OCR로 문장형 폴백된 경우)에서 확인됐다. 이런 문서는
# 위 BID_LINE_PATTERN이 "숫자+차"를 요구해서 전혀 매칭이 안 되고 "추출실패"로 남았었다.
# 회차(1~9로 제한, 표 형식이라 두 자리 이상은 드묾) + 날짜 + 금액이 공백/줄바꿈만 사이에
# 두고 붙어있으면 하나의 회차로 인정한다. 앞에 숫자/마침표가 없어야(=다른 숫자의 일부가
# 아니어야) 매칭하도록 부정형 뒤돌아보기를 걸어 오탐을 줄였다.
BID_LINE_PATTERN_BARE = re.compile(
    r"(?<![\d.])([1-9])\s*\n?\s*"
    r"(\d{4}\s*[.\-]\s*\d{1,2}\s*[.\-]\s*\d{1,2}\.?\s*\n?\s*(?:\d{1,2}\s*:\s*\d{2})?)"
    r"\s*\n?\s*([\d,]{6,})\s*원?"
)


def extract_bid_schedule_from_tables(pdf_path: str):
    """
    표 기반 1순위: 입찰일/최저가 열이 모두 있는 표에서만 추출 (주소 열 유무는 무시).
    ✅ v3: 고정 키워드 대신 _header_matches_bid_date / _header_matches_min_bid 판정함수 사용
    (법원마다 "입찰기한"/"입찰마감일"/"입찰기일", "최저입찰가"/"최저입찰금"/"최저입찰금액" 등
     표현이 제각각이라, 핵심 토큰 조합으로 판별하는 게 더 안정적이다)
    ✅ v3.4: 공고문 본문 + 첨부된 입찰서 양식에 같은 입찰일정 표가 통째로 한 번 더 나오는
    문서가 있다(매각대상 목록에서 먼저 발견된 것과 동일한 문제). (회차, 입찰기일, 최저입찰가)
    내용이 이미 나온 조합이면 다시 추가하지 않는다.
    """
    if not HAS_PDFPLUMBER or not pdf_path:
        return []
    items = []
    seen = set()
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = _extract_tables_multi_strategy(page)
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    header = [clean_text(c) for c in table[0]]
                    biddate_idx = _find_col_by_predicate(header, _header_matches_bid_date)
                    minbid_idx  = _find_col_by_predicate(header, _header_matches_min_bid)
                    if biddate_idx is None or minbid_idx is None:
                        continue  # 입찰일정 표가 아님(예: 매각대상 표) → 스킵
                    round_idx = _find_col(header, ROUND_COL_KEYWORDS)

                    for row in table[1:]:
                        if biddate_idx >= len(row) or minbid_idx >= len(row):
                            continue
                        biddate = clean_text(row[biddate_idx])
                        minbid = clean_text(row[minbid_idx])
                        if not biddate or not minbid:
                            continue
                        round_no = clean_text(row[round_idx]) if round_idx is not None and round_idx < len(row) else ""
                        key = (round_no, biddate, minbid)
                        if key in seen:
                            continue
                        seen.add(key)
                        items.append({"회차": round_no, "입찰기일": biddate, "최저입찰가": minbid})
    except Exception as e:
        print(f"   ⚠️ 입찰일정 표 추출 실패: {e}")
    return items


def extract_bid_schedule_from_plain_text(text: str):
    if not text:
        return []
    items = []
    seen = set()
    for m in BID_LINE_PATTERN.finditer(text):
        round_no = clean_text(m.group(1)) + "차"
        biddate = clean_text(m.group(2))
        minbid = clean_text(m.group(3))
        key = (round_no, biddate, minbid)
        if key in seen:
            continue
        seen.add(key)
        items.append({"회차": round_no, "입찰기일": biddate, "최저입찰가": minbid})

    # ✅ v3.6.21: "차" 붙은 형식으로 하나도 못 찾았으면, 숫자만 있는 회차 표 형식도 시도
    if not items:
        for m in BID_LINE_PATTERN_BARE.finditer(text):
            round_no = clean_text(m.group(1)) + "차"
            biddate = clean_text(m.group(2))
            minbid = clean_text(m.group(3))
            key = (round_no, biddate, minbid)
            if key in seen:
                continue
            seen.add(key)
            items.append({"회차": round_no, "입찰기일": biddate, "최저입찰가": minbid})
    return items


def extract_bid_schedule(native_text: str, ocr_text: str, pdf_path: str):
    items = extract_bid_schedule_from_tables(pdf_path)
    if items:
        return items, "표기반"

    items = extract_bid_schedule_from_plain_text(native_text)
    if items:
        return items, "문장형(텍스트)"

    items = extract_bid_schedule_from_plain_text(ocr_text)
    if items:
        return items, "문장형(OCR)"

    return [], "추출실패"


BID_DATE_PARSE_PATTERN = re.compile(r"(\d{4})\s*[.\-]\s*(\d{1,2})\s*[.\-]\s*(\d{1,2})")


def _parse_bid_date(date_str: str):
    m = BID_DATE_PARSE_PATTERN.search(date_str or "")
    if not m:
        return None
    try:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return datetime(y, mo, d).date()
    except ValueError:
        return None


def parse_amount_to_int(s: str):
    if not s:
        return ""
    digits = re.sub(r"[^\d]", "", str(s))
    if digits:
        try:
            return int(digits)
        except ValueError:
            return s
    return s


def find_nearest_upcoming_bid(bid_items: list) -> dict:
    if not bid_items:
        return {}
    today = datetime.now().date()

    parsed = []
    for b in bid_items:
        d = _parse_bid_date(b.get("입찰기일", ""))
        if d is not None:
            parsed.append((d, b))

    if not parsed:
        return bid_items[0]

    future = [(d, b) for d, b in parsed if d >= today]
    if future:
        future.sort(key=lambda x: x[0])
        return future[0][1]

    parsed.sort(key=lambda x: x[0], reverse=True)
    return parsed[0][1]


# =========================
# 엑셀: 생성/열기 (3개 시트)
# =========================
def connect_google_sheet():
    if not GOOGLE_SHEETS_ENABLED:
        return None
    if not HAS_GSPREAD:
        print("⚠️ gspread 미설치 → 구글시트 연동 스킵 (pip install gspread google-auth)")
        return None
    if not GOOGLE_CREDENTIALS_JSON and not os.path.exists(GOOGLE_CREDENTIALS_PATH):
        print(f"⚠️ 구글 서비스계정 키 없음(환경변수 GOOGLE_CREDENTIALS_EDITER·파일 {GOOGLE_CREDENTIALS_PATH}) → 구글시트 연동 스킵")
        return None
    try:
        if GOOGLE_CREDENTIALS_JSON:
            gc = gspread.service_account_from_dict(json.loads(GOOGLE_CREDENTIALS_JSON))
        else:
            gc = gspread.service_account(filename=GOOGLE_CREDENTIALS_PATH)
        sh = gc.open_by_key(GOOGLE_SHEET_ID)
        print(f"🔗 구글시트 연결 성공: {sh.title}")
        return sh
    except Exception as e:
        print(f"⚠️ 구글시트 연결 실패({e}) → 로컬 엑셀만 사용")
        return None


def _ensure_header_row(ws, expected_headers: list, sheet_label: str = "") -> bool:
    """
    ✅ v3.6.29: 탭 하나의 1행이 기대하는 헤더 구성과 정확히 일치하는지 확인하고, 다르면
    맞춰준다. 실제로 겪은 상황(‘파산공매’ 헤더까지 통째로 삭제 후 REBUILD_MERGED 실행)처럼
    헤더 자체가 없는 경우는 물론, 헤더는 있는데 열 이름/순서가 기대값과 다른 경우까지 잡는다.

    - 데이터 행이 없으면(헤더도 없거나, 헤더만 있고 아래 데이터가 없으면) 그냥 기대하는
      헤더로 덮어써도 안전하다 — 밑에 맞춰야 할 기존 값이 없기 때문. 즉시 덮어쓴다.
    - 데이터 행이 이미 있는데 헤더가 기대값과 다르면, 여기서 함부로 헤더만 바꾸면 실제
      값과 열 이름이 어긋난다('공고목록'처럼 계속 누적되는 탭이 이 경우). 자동으로 고치지
      않고 경고만 남긴다 — 이런 탭은 열 구성을 바꾸려면 데이터까지 같이 마이그레이션해야
      하므로, 그 판단은 사람이 해야 한다. ('파산공매'처럼 호출부가 매번 전체를 다시 쓰는
      탭은 이 함수가 경고만 남기고 넘어가도, 뒤이어 호출부가 데이터까지 통째로 다시 쓰면서
      헤더도 강제로 맞추기 때문에 안전하다.)

    반환값: 헤더를 실제로 새로 썼으면 True, 그대로 뒀으면 False.
    """
    values = ws.get_all_values()
    current_header = values[0] if values else []
    # ✅ v3.6.31: 구글시트 get_all_values()는 행 끝의 빈 셀("")을 잘라내고 돌려준다.
    # expected_headers 끝에 의도적으로 넣어둔 빈 문자열 칸("", "" 등, 예비 열)이 있으면
    # current_header에는 절대 나타나지 않으므로, 실제로는 헤더가 정확히 일치해도
    # current_header == expected_headers가 영원히 False가 되어 매번 "헤더가 다르다"는
    # 거짓 경고가 반복되는 문제가 있었다. 양쪽 다 끝의 빈 문자열을 떼어내고 비교한다.
    def _rstrip_blanks(lst: list) -> list:
        out = list(lst)
        while out and out[-1] == "":
            out.pop()
        return out
    if _rstrip_blanks(current_header) == _rstrip_blanks(expected_headers):
        return False
    has_data_rows = len(values) > 1
    if has_data_rows:
        print(f"   ⚠️ '{sheet_label}' 탭의 헤더가 기대 구성과 다른데 데이터 행이 이미 있어 "
              f"자동으로 고치지 않았습니다. 열 구성을 바꾸려면 기존 데이터도 같이 정리해야 합니다.")
        print(f"      현재: {current_header}")
        print(f"      기대: {expected_headers}")
        return False
    try:
        # ⚠️ gspread 6.0부터 update()의 위치 인자 순서가 (range, values) → (values, range)로
        # 바뀌었다. 설치된 gspread 버전이 6.0 이전/이후 어느 쪽이든 안전하게 동작하도록
        # range_name=/values= 키워드 인자로 명시해서 호출한다(위치 인자로 넘기지 않음).
        ws.update(range_name="A1", values=[expected_headers], value_input_option="RAW")
        print(f"   🛠️ '{sheet_label}' 탭 헤더를 표준 구성으로 (재)작성했습니다.")
        return True
    except Exception as e:
        print(f"   ❌ '{sheet_label}' 헤더 작성 실패: {type(e).__name__}: {e}")
        return False


def get_or_create_gsheet_tab(sh, title: str, headers: list):
    """
    ✅ v3.6.29: 탭이 없으면 새로 만들고, 있으면 _ensure_header_row로 헤더 구성을 확인/보정한다.
    main() 뿐 아니라 REBUILD_MERGED 등 이 함수를 거치는 모든 RUN_MODE에 헤더 확인이
    자동으로 적용된다.
    """
    if sh is None:
        return None
    try:
        ws = sh.worksheet(title)
    except Exception:
        ws = sh.add_worksheet(title=title, rows=2000, cols=max(len(headers) + 2, 10))
        ws.append_row(headers, value_input_option="RAW", table_range="A1")
        return ws
    _ensure_header_row(ws, headers, sheet_label=title)
    return ws


def get_known_seq_ids(gws_list) -> set:
    """
    ✅ v3.5: "구글시트가 유일한 기준"으로 단순화. 로컬 엑셀 폴백을 완전히 제거했다.
    구글시트가 유일한 데이터 저장소이므로, 구글시트 조회에 실패하면 "이미 아는 것"을
    안전하게 판단할 방법이 없다 — 이 상태에서 무리하게 진행하면 이미 있는 공고를 다시
    처리해서 중복을 만들 위험이 있으므로, 실패 시 빈 집합이 아니라 예외를 그대로 올려서
    호출부(main 등)가 실행을 중단하도록 한다.
    """
    headers = gws_list.row_values(1)
    known = set()
    if "상세페이지URL" in headers:
        col = headers.index("상세페이지URL") + 1
        for v in gws_list.col_values(col)[1:]:
            sid = extract_seq_id(v)
            if sid:
                known.add(sid)
    return known


# ── 파산공매 결과 탭: 파산공고_YYMMDD (실행일 KST). 같은 날 다시 돌리면 같은 탭을 다시 만든다 ──
MERGED_TAB_PREFIX = "파산공고_"
LEGACY_MERGED_TAB = "파산공매"   # 예전 고정 이름 탭 (이전 결과 탭이 없을 때 PNU 캐시용으로만 읽음)


def merged_tab_name(dt=None) -> str:
    from datetime import timezone, timedelta
    return MERGED_TAB_PREFIX + (dt or datetime.now(timezone(timedelta(hours=9)))).strftime("%y%m%d")


def previous_merged_ws(sh, today_name: str):
    """오늘 탭을 뺀 가장 최근 '파산공고_YYMMDD' 탭. 없으면 옛 '파산공매' 탭. 둘 다 없으면 None."""
    try:
        tabs = [w for w in sh.worksheets()
                if re.fullmatch(MERGED_TAB_PREFIX + r"\d{6}", w.title.strip()) and w.title.strip() != today_name]
        if tabs:
            return max(tabs, key=lambda w: w.title.strip())
        return sh.worksheet(LEGACY_MERGED_TAB)
    except Exception:
        return None



def export_gsheet_snapshot(gsheet) -> str:
    """
    ✅ v3.5: 로컬 파일의 새로운 역할 — "그 시점 구글시트 상태를 그대로 복사한 불변 백업".
    실행할 때마다 타임스탬프가 붙은 새 파일을 만든다(기존 파일을 열어서 이어쓰지 않음).
    이 파일은 사람이 나중에 열어보거나 재해 복구용으로 참고하는 용도일 뿐,
    코드가 다음 실행 때 다시 읽어들여서 뭔가 판단하는 데는 절대 쓰이지 않는다.
    """
    if IS_ACTIONS:
        return ""   # 러너 디스크는 일회용이라 로컬 백업 의미가 없다(구글시트가 유일한 원본)
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SNAPSHOT_DIR, f"대법원파산공매_snapshot_{ts}.xlsx")
    try:
        wb = Workbook()
        wb.remove(wb.active)
        # ✅ v3.6: '부동산목록'/'입찰일정' 탭 제거 → 스냅샷 대상도 2개로 축소
        for tab_name in ["공고목록", merged_tab_name()]:
            try:
                gws = gsheet.worksheet(tab_name)
                values = gws.get_all_values()
            except Exception as e:
                print(f"   ⚠️ 스냅샷: '{tab_name}' 탭 조회 실패({e}) → 이 탭은 스냅샷에서 빠짐")
                continue
            ws = wb.create_sheet(tab_name)
            for row in values:
                ws.append(row)
        wb.save(path)
        print(f"📸 구글시트 스냅샷 백업: {path}")
    except Exception as e:
        print(f"⚠️ 스냅샷 백업 실패(구글시트 데이터 자체에는 영향 없음): {type(e).__name__}: {e}")
    return path


def _parse_property_items_from_row(row: dict) -> list:
    """
    '공고목록' 한 행에서 매각대상 부동산 목록(list of dict)을 복원한다.
    ✅ 우선순위: JSON 상세열(면적/지분/기타까지 완전 보존) → 없으면 요약열(주소만, 레거시 행 대비)
    """
    raw_json = row.get("매각대상상세JSON")
    if raw_json:
        try:
            items = json.loads(raw_json)
            if isinstance(items, list):
                return items
        except Exception:
            pass
    # 레거시 폴백: 요약열은 주소만 파이프(|)로 이어붙인 문자열이라 주소만 복원 가능
    summary = row.get("매각대상부동산요약") or ""
    return [{"주소": a.strip(), "면적": "", "지분": "", "기타": ""}
            for a in summary.split("|") if a.strip()]


def _parse_bid_items_from_row(row: dict) -> list:
    """
    '공고목록' 한 행에서 입찰일정 목록(list of dict)을 복원한다.
    ✅ 우선순위: JSON 상세열 → 없으면 요약열("회차:날짜:최저가 | ...")을 파싱.
    요약열 파싱 시, 날짜 안에 콜론(시:분)이 섞여 있어도 안전하도록 오른쪽에서
    최저가를 먼저 떼어내고(rsplit), 왼쪽에서 회차를 떼어내는(split) 순서로 처리한다.
    """
    raw_json = row.get("입찰일정상세JSON")
    if raw_json:
        try:
            items = json.loads(raw_json)
            if isinstance(items, list):
                return items
        except Exception:
            pass
    summary = row.get("입찰일정요약") or ""
    items = []
    for chunk in summary.split("|"):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            left, minbid = chunk.rsplit(":", 1)
            round_no, biddate = left.split(":", 1)
        except ValueError:
            continue
        items.append({"회차": round_no.strip(), "입찰기일": biddate.strip(), "최저입찰가": minbid.strip()})
    return items


def _pnu_from_kakao(address: str) -> str:
    """카카오 주소검색으로 19자리 PNU 를 만든다(법정동코드 10 + 산여부 1 + 본번 4 + 부번 4).
    러너(미국 IP)에서는 브이월드가 막혀 있어 이쪽을 먼저 쓴다."""
    if not KAKAO_REST_API_KEY:
        return ""
    for attempt in range(3):
        try:
            r = requests.get("https://dapi.kakao.com/v2/local/search/address.json",
                             headers={"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"},
                             params={"query": address, "analyze_type": "similar"}, timeout=10)
            if r.status_code == 429:
                time.sleep(1.5 * (attempt + 1))
                continue
            r.raise_for_status()
            for doc in r.json().get("documents", []):
                a = doc.get("address") or {}
                b_code = a.get("b_code") or ""
                main_no = a.get("main_address_no") or ""
                if len(b_code) != 10 or not main_no.isdigit():
                    continue
                sub_no = a.get("sub_address_no") or "0"
                mountain = "2" if a.get("mountain_yn") == "Y" else "1"
                return f"{b_code}{mountain}{int(main_no):04d}{int(sub_no or 0):04d}"
            return ""
        except Exception:
            time.sleep(1.0 * (attempt + 1))
    return ""


def get_pnu_from_address(address: str) -> str:
    """
    ✅ v3.6.9: 주소를 VWorld(국토교통부) 검색 API에 넣어 PNU(19자리 토지 고유번호)를
    받아온다. PNU가 정상적으로 반환되면 그 주소가 실제 존재하는 지번이라는 뜻이라,
    OCR 오탈자로 생긴 "존재하지 않는 지번" 주소를 걸러내는 신호로 쓸 수 있다.
    지번(PARCEL) 방식으로 먼저 시도하고, 안 되면 도로명(ROAD) 방식으로도 시도한다.
    실패해도(네트워크 오류, 키 미설정 등) 예외를 올리지 않고 빈 문자열만 반환한다 —
    PNU 조회는 부가 검증 기능일 뿐, 이것 때문에 전체 작업이 멈추면 안 되기 때문.
    """
    if not ENABLE_PNU_LOOKUP or not HAS_REQUESTS or not address:
        return ""
    pnu = _pnu_from_kakao(address)
    if pnu:
        return pnu
    if not VWORLD_API_KEY:
        return ""
    base_url = "https://api.vworld.kr/req/search"
    for category_type in ("PARCEL", "ROAD"):
        params = {
            "service": "search", "request": "search", "version": "2.0",
            "size": "10", "page": "1", "query": address, "type": "address",
            "category": category_type, "format": "json", "errorformat": "json",
            "key": VWORLD_API_KEY,
        }
        try:
            resp = requests.get(base_url, params=params, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("response", {}).get("result", {}).get("items", [])
            if items and len(items[0].get("id", "")) == 19:
                return items[0]["id"]
        except Exception:
            continue
    return ""


def _reverify_address_via_deungibu(att_name: str, prop_index: int, deungibu_cache: dict):
    """
    ✅ v3.6.10: PNU 조회가 실패한(=아마 오독된) 주소를, 등기부등본 보조 스캔으로 재검증한다.
    같은 문서 안에서 항목 순번(prop_index)이 같은 등기부 쪽 주소를 후보로 삼는다 —
    "시홍시"→"시흥시"처럼 지번은 맞고 지역명만 틀린 경우든, "릉시강동 면임곡리"처럼
    아예 뭉개진 경우든 지번 문자열 매칭 없이도 순번으로 대응시킬 수 있다.
    ⚠️ 이 함수는 후보만 반환한다 — 실제 채택 여부는 호출부가 PNU 재조회로 검증한 뒤 결정한다
    (순번 매칭은 추측일 뿐이므로, 진짜 맞는지는 PNU가 나오는지로만 확인한다).
    같은 PDF는 이번 재구성 실행 안에서 한 번만 스캔하도록 deungibu_cache에 결과를 재사용한다.
    """
    if not att_name or not HAS_OCR:
        return ""
    pdf_path = find_existing_pdf(att_name)
    if not pdf_path:
        return ""  # 로컬에 PDF가 없으면(이미 지워졌으면) 재검증 자체가 불가능
    if pdf_path not in deungibu_cache:
        try:
            deungibu_cache[pdf_path] = extract_property_list_from_deungibu_pages(pdf_path)
        except Exception:
            deungibu_cache[pdf_path] = []
    candidates = deungibu_cache[pdf_path]
    if 0 <= prop_index < len(candidates):
        return candidates[prop_index].get("주소", "")
    return ""


# ✅ v3.6.36: '매각완료' 판정을 mark_closed_announcements()의 "사이트 목록에서 사라짐" 감지
# 하나에만 의존하지 않는다. 그 방식은 (1) INCREMENTAL이 페이지네이션을 끝까지 다 훑은
# 실행에서만 동작하고, (2) 법원이 매각이 끝난 공고를 목록에서 아예 안 내리고 그냥 두는
# 경우엔 영원히 감지가 안 된다. '공고만료일'은 법원이 상세페이지에 직접 명시하는 날짜이므로,
# 그 날짜가 이미 지났으면 사이트가 내렸든 안 내렸든 이 공고는 더 이상 "현재 진행 중"이 아니다
# — REBUILD_MERGED처럼 사이트를 아예 안 훑는 실행에서도 항상 정확하게 걸러지도록, 저장된
# 날짜 자체를 오늘과 비교하는 것을 1차 판정 기준으로 삼고, "매각완료" 문자열 표시는 그 보조
# 신호로만 쓴다.
def _is_announcement_expired(exp_str: str) -> bool:
    exp_str = (exp_str or "").strip()
    if not exp_str:
        return False
    if exp_str == "매각완료":
        return True
    d = _parse_bid_date(exp_str)  # 이름은 '입찰일'용이지만 실제론 범용 YYYY.MM.DD 파서
    if d is None:
        return False
    return d < datetime.now().date()


def rebuild_merged_sheet(gsheet):
    """
    ✅ v3.6: '파산공매'를 크롤링 시점에 조금씩 append하는 게 아니라, 매번 '공고목록' 전체를
    다시 읽어서 처음부터 새로 만든다. 이렇게 하면:
      - 주소/입찰일정 파싱 로직을 나중에 고쳐도, 재크롤링 없이 이 함수만 다시 실행하면
        과거 행까지 전부 최신 로직으로 다시 계산되어 자동으로 고쳐진다
        (실제로 겪은 문제: 파싱 버그 수정 후에도 '파산공매'에 옛날 잘못된 값이 남아있었음 — 이제
        '파산공매'는 '공고목록'에서 파생된 결과물일 뿐이라 원본(공고목록)이 맞으면 항상 맞다)
      - 주소 기준 중복 제거, 빈 주소 행 제외도 이 함수가 매번 새로 판단하므로 누적 오염이 없다

    ✅ v3.6.9: 각 주소의 PNU(토지 고유번호)를 VWorld API로 조회해서 'pnu' 열에 채운다.
    PNU가 채워졌다는 건 그 주소가 실제 존재하는 지번이라는 뜻이라 신뢰도의 신호가 된다.
    '파산공매'는 매번 통째로 다시 만들기 때문에, 매번 모든 주소를 새로 API 조회하면
    느리고 낭비다 — 그래서 재작성 전에 기존 '파산공매'에 이미 있던 (주소→PNU) 값을
    먼저 읽어서 캐시로 재사용하고, 새로 나타난 주소만 실제로 API를 호출한다.

    ✅ v3.6.10: PNU 조회가 실패하면(=주소가 의심스러우면), 로컬에 원본 PDF가 아직 남아있는
    경우에 한해 등기부등본 보조 스캔으로 자동 재검증을 시도한다. 후보 주소로 다시 PNU를
    조회해서 실제로 성공할 때만 교체한다 — 추측이 틀리면 원래 값을 그대로 둔다.

    ✅ v3.6.14: 그래도 끝까지 PNU가 안 나오면(등기부 재검증도 실패), '공고목록'의 원본 행이
    애초에 잘못 추출됐을 가능성이 높다고 보고(예: 표 헤더 인식 실패로 뒤죽박죽 문장형 폴백이
    쓰인 경우) '검토상태'에 "PNU확인필요"라고 표시해둔다 — 사람이 그 행을 눈여겨보라는
    표시다(주소가 의심스럽다는 신호). ⚠️ v3.6.34: 예전엔 이 표시를 GSHEET_FAILED_BACKFILL
    모드가 보고 사이트를 재방문해 그 공고를 통째로 재추출했는데, 그 모드를 삭제하면서
    "지목/물건종류가 통째로 유실된 행"에 대한 로컬 PDF 재확인은 이 함수 안으로 옮겨왔지만
    (아래 '지목재확인시도' 로직), 주소 자체가 의심스러운 이 경우까지 자동으로 다시 손대진
    않는다 — 잘못 건드리면 신뢰도가 오히려 낮아질 수 있어서, 사람이 확인 후 필요하면 해당
    '공고목록' 행을 지우고 INCREMENTAL을 다시 돌려 재수집하는 편이 안전하다.
    """
    gws_list = gsheet.worksheet(GOOGLE_SHEET_LIST_TAB)
    today_tab = merged_tab_name()
    gws_merged = get_or_create_gsheet_tab(gsheet, today_tab, MERGED_HEADERS)
    # 오늘 탭이 새로 만들어져 비어 있으면, PNU 캐시·신규여부는 이전 결과 탭에서 가져온다
    cache_values = []
    try:
        cache_values = gws_merged.get_all_values()
        if len(cache_values) < 2:
            gws_prev = previous_merged_ws(gsheet, today_tab)
            if gws_prev is not None:
                cache_values = gws_prev.get_all_values()
                print(f"   ℹ️ 캐시/신규여부 기준: 이전 탭 '{gws_prev.title}' ({len(cache_values) - 1}행)")
    except Exception as e:
        cache_values = []
        print(f"   ⚠️ 이전 결과 탭 조회 실패(캐시 없이 진행): {e}")
    deungibu_cache = {}  # pdf_path -> 등기부 스캔 결과 (같은 실행 안에서 중복 OCR 방지)

    # ✅ 기존 '파산공매'에서 (주소 → PNU) 캐시를 먼저 확보 (지우기 전에!)
    pnu_cache = {}
    if ENABLE_PNU_LOOKUP:
        try:
            old_values = cache_values
            if len(old_values) >= 2:
                old_headers = old_values[0]
                if "주소" in old_headers and "pnu" in old_headers:
                    a_idx = old_headers.index("주소")
                    p_idx = old_headers.index("pnu")
                    for r in old_values[1:]:
                        if a_idx < len(r) and p_idx < len(r) and r[a_idx] and r[p_idx]:
                            pnu_cache[r[a_idx]] = r[p_idx]
        except Exception as e:
            print(f"   ⚠️ 기존 PNU 캐시 조회 실패(새로 다 조회함): {e}")

    # ✅ v3.6.32: '신규여부' 열용 — 이번에 새로 쓰기 전에, 지우기 직전의 '파산공매'에 이미
    # 있던 주소 집합을 먼저 확보해둔다. 재구성 후 이 집합에 없는 주소만 "신규"로 표시한다.
    old_addr_set = set()
    try:
        old_merged_values = cache_values
        if len(old_merged_values) >= 2 and "주소" in old_merged_values[0]:
            a_idx2 = old_merged_values[0].index("주소")
            for r in old_merged_values[1:]:
                if a_idx2 < len(r) and r[a_idx2]:
                    old_addr_set.add(r[a_idx2])
    except Exception as e:
        print(f"   ⚠️ 기존 주소 목록 조회 실패(신규여부 판정 생략): {e}")

    values = gws_list.get_all_values()
    if len(values) < 2:
        print("   ℹ️ '공고목록'에 데이터가 없어 '파산공매'를 비웁니다.")
        rows_out = []
    else:
        headers = values[0]
        rows_out = []
        seen_addr = set()
        pnu_new_calls = 0
        reverified = 0
        flagged_for_reextract = 0
        # ✅ v3.6.24: "PNU확인필요" 표시도 예전엔 행마다 _update_gsheet_list_row()로
        # 즉시 API 호출(update_cell)을 날렸다. PNU 조회 실패가 몰리는 실행(예: 신규
        # 법원 대량 수집 직후)에서는 이 표시 대상 행이 수십 건에 달해, 이것만으로도
        # 분당 쓰기 할당량을 넘길 수 있었다. 루프 중엔 (행 번호, 표시할 값)만 모아두고,
        # 루프가 다 끝난 뒤 한 번의 batch_update로 몰아서 보낸다.
        status_batch = []  # ✅ v3.6.34: '검토상태' 열에 쓸 내용을 행별로 한 번만 모아서 보낸다
                            # (PNU확인필요/지목재확인시도 표시가 서로 덮어쓰지 않도록 통합).
        jimok_json_batch = []  # ✅ v3.6.34: 로컬 PDF 재추출로 지목을 보강했으면, '공고목록'의
                                # 매각대상상세JSON도 고쳐서 다음 실행부터는 다시 안 해도 되게 한다.
        jimok_local_fixed = 0
        review_status_col_letter = _col_letter(headers, "검토상태") if "검토상태" in headers else None
        prop_json_col_letter = _col_letter(headers, "매각대상상세JSON") if "매각대상상세JSON" in headers else None
        for row_idx, raw_row in enumerate(values[1:], start=2):
            row = {h: (raw_row[i] if i < len(raw_row) else "") for i, h in enumerate(headers)}

            # ✅ v3.6.26: mark_closed_announcements()가 사이트 목록에서 더 이상 보이지 않는
            # 공고의 '공고만료일' 칸을 (원래 날짜 대신) "매각완료"로 덮어쓴다. 이렇게 표시된
            # 공고는 이미 끝난 물건이므로 '파산공매'(매수 후보 목록)에는 올릴 필요가 없다.
            # ✅ v3.6.36: 그 표시만 보고 걸러내면, 법원이 목록에서 안 내린(계속 게시된) 만료
            # 공고나, REBUILD_MERGED처럼 사이트를 안 훑는 실행에서는 놓친다. '공고만료일'에
            # 저장된 실제 날짜가 오늘보다 과거면 그 자체로 "더 이상 진행 중이 아님"이므로,
            # 표시 여부와 무관하게 항상 걸러낸다(현재 진행 중인 공고만 '파산공매'에 남긴다).
            if _is_announcement_expired(row.get("공고만료일")):
                continue

            property_items = _parse_property_items_from_row(row)
            bid_items = _parse_bid_items_from_row(row)
            nearest_bid = find_nearest_upcoming_bid(bid_items)
            row_has_unresolved_pnu_failure = False
            row_status_additions = []

            # ✅ v3.6.34: GSHEET_FAILED_BACKFILL 모드를 없애면서, "저장된 JSON 어디에도
            # 지목/물건종류가 안 남아있는" 행(예: 부산회생법원 2021하단1257 — 표는 정상
            # 인식됐는데 지목 열만 통째로 유실)을 고칠 방법이 없어지면 안 되므로, 그 역할을
            # REBUILD_MERGED 안으로 옮겼다. 사이트 재방문(다운로드) 없이, 로컬에 이미 받아둔
            # PDF가 남아있으면(find_existing_pdf) 그 파일만 다시 읽어서 지목을 보강한다.
            #
            # ⚠️ v3.6.36 버그 수정: 예전엔 "PDF를 못 찾아서 시도조차 못 한 경우"에도
            # '검토상태'에 "지목재확인시도"를 똑같이 남겼다. 이 사용자는 크롤링용 PC가
            # 여러 대라 PDF 다운로드 폴더가 PC마다 따로 있는데, 하필 해당 PDF가 없는 PC에서
            # REBUILD_MERGED가 먼저 실행되면 "이미 시도함" 표시만 영구히 남고 실제로는 한
            # 번도 재확인이 안 된 채 그대로 굳어버렸다(나중에 PDF가 있는 PC에서 다시 실행해도
            # already_tried_jimok에 걸려 재시도가 아예 안 됨) — 이게 "코드는 고쳤다는데
            # 시트엔 여전히 안 채워진다"의 실제 원인 중 하나였다.
            # 이제 "지목재확인시도"는 로컬에 PDF를 실제로 찾아서 다시 읽어본 경우에만 남기고,
            # PDF를 못 찾은 경우엔 "PDF없음(재수집필요)"만 남긴다 — 이 표시는 already_tried_jimok
            # 판정에 안 걸리므로, PDF가 있는 다른 PC에서 실행하면 자동으로 다시 시도된다.
            items_with_addr = [it for it in property_items if (it.get("주소") or "").strip()]
            existing_status_text = row.get("검토상태") or ""
            already_tried_jimok = "지목재확인시도" in existing_status_text
            if items_with_addr and not already_tried_jimok and not any(resolve_yongdo(it) for it in items_with_addr):
                att_name_for_reparse = row.get("첨부파일명", "")
                pdf_path_local = find_existing_pdf(att_name_for_reparse) if att_name_for_reparse else None
                if pdf_path_local:
                    jimok_changed = False
                    if HAS_PDFPLUMBER:
                        fresh_items = extract_property_list_from_tables(pdf_path_local)
                        for it in items_with_addr:
                            if resolve_yongdo(it):
                                continue
                            match = next((f for f in fresh_items if f.get("주소") == it.get("주소")), None)
                            if match and resolve_yongdo(match):
                                it["지목"] = match.get("지목", "")
                                jimok_changed = True
                    if HAS_OCR and not any(resolve_yongdo(it) for it in items_with_addr):
                        ocr_text_local = extract_pdf_text_ocr(pdf_path_local)
                        if ocr_text_local and enrich_jimok_from_ocr(items_with_addr, ocr_text_local):
                            jimok_changed = True
                    if jimok_changed:
                        jimok_local_fixed += 1
                        if prop_json_col_letter is not None:
                            jimok_json_batch.append({
                                "range": f"{prop_json_col_letter}{row_idx}",
                                "values": [[json.dumps(property_items, ensure_ascii=False)]],
                            })
                    # 실제로 PDF를 열어서 시도했으니(성공/실패와 무관하게) 한 번만 시도하도록 표시.
                    row_status_additions.append("지목재확인시도")
                elif "PDF없음(재수집필요)" not in existing_status_text:
                    # 이 PC엔 원본 PDF가 없어 시도 자체를 못 했다 — "시도함"으로 치지 않는다.
                    row_status_additions.append("PDF없음(재수집필요)")

            # ✅ v3.6.32: 공고(=사건) 단위로 한 번만 계산하면 되는 값들 — 첨부파일명에서
            # 뽑는 사건번호, 신청인정보에서 뽑는 소유자, 그리고 이 공고에 딸린 필지가
            # 여러 개일 때 "필지별 주소" 열에서 한눈에 보여줄 전체 주소 목록.
            case_no = extract_case_number(row.get("첨부파일명", "")) or extract_case_number(row.get("제목", ""))
            owner = extract_owner_from_applicant(row.get("신청인정보", ""))
            all_parcel_addrs = " | ".join(
                dict.fromkeys(  # 순서를 유지하면서 중복 제거
                    respace_korean_address((pp.get("주소") or "").strip())
                    for pp in property_items if (pp.get("주소") or "").strip()
                )
            )

            for idx, p in enumerate(property_items):
                addr = (p.get("주소") or "").strip()
                addr = respace_korean_address(addr)  # ✅ v3.6.6: 재크롤링 없이도 저장된 주소의
                                                       # 사라진 행정구역 공백을 재구성 시점에 복원

                pnu = ""
                if ENABLE_PNU_LOOKUP and addr:
                    if addr in pnu_cache:
                        pnu = pnu_cache[addr]
                    else:
                        pnu = get_pnu_from_address(addr)
                        pnu_new_calls += 1
                        time.sleep(PNU_API_DELAY)
                        if pnu:
                            pnu_cache[addr] = pnu

                        # ✅ v3.6.10: PNU 실패 → 등기부등본 보조 스캔으로 재검증 시도
                        if not pnu:
                            candidate = _reverify_address_via_deungibu(
                                row.get("첨부파일명", ""), idx, deungibu_cache
                            )
                            candidate = respace_korean_address(candidate) if candidate else ""
                            if candidate and candidate != addr:
                                cand_pnu = pnu_cache.get(candidate) or get_pnu_from_address(candidate)
                                pnu_new_calls += 1
                                time.sleep(PNU_API_DELAY)
                                if cand_pnu:
                                    print(f"   🔧 PNU 재검증으로 주소 보정: {addr!r} → {candidate!r}")
                                    addr, pnu = candidate, cand_pnu
                                    pnu_cache[addr] = pnu
                                    reverified += 1

                        if not pnu:
                            row_has_unresolved_pnu_failure = True

                if not addr or addr in seen_addr:
                    continue
                seen_addr.add(addr)

                # ✅ v3.6.24: rebuild_merged_sheet는 '공고목록'에 이미 저장된 JSON을 그대로
                # 읽어서 '파산공매'를 다시 쓸 뿐, PDF를 다시 읽지 않는다. 그런데 v3.6.23 이전
                # (지목/면적 정제 로직이 생기기 전) 코드로 크롤링된 행은 JSON의 "지목" 필드
                # 자체에 이미 "임야 331㎡"처럼 면적이 섞인 오염된 값이 저장되어 있다.
                # extract_property_list_from_tables()를 아무리 고쳐도 이 저장된 값 자체는
                # 재크롤링 전까지 바뀌지 않으므로, REBUILD_MERGED만 돌려서는 "여전히
                # 임야331"처럼 보이는 게 당연했다 — 저장된 값을 읽는 시점에도 같은 정제
                # 함수(clean_jimok_value/clean_area_value)를 한 번 더 통과시켜야, 이미
                # 크롤링된 과거 데이터까지 재크롤링 없이 즉시 고쳐진다.
                #
                # ✅ v3.6.33: 그런데 실제 데이터를 보니 "지목" 필드 자체가 비어있고, 지목
                # 글자("임야" 등)가 "기타" 필드에 면적과 뒤섞여 저장된 행("기타": "임야 496㎡")
                # 도 있었다 — 이런 행은 clean_jimok_value(p.get("지목",""))만으로는 못 구한다.
                # resolve_yongdo()가 '지목' 필드뿐 아니라 '기타' 필드까지 화이트리스트로
                # 훑어서 찾아준다 — 이 역시 재크롤링 없이 REBUILD_MERGED만으로 즉시 고쳐진다.
                jimok_clean = resolve_yongdo(p)
                area_clean = clean_area_value(p.get("면적", ""))

                # ✅ v3.6.29: 열 위치를 하드코딩된 순서가 아니라 MERGED_COL(헤더 이름 → 인덱스)로
                # 채운다. 이렇게 해야 MERGED_HEADERS 순서가 또 바뀌어도 이 블록을 다시 손볼
                # 필요 없이 자동으로 맞는 칸에 값이 들어간다.
                #
                # ✅ v3.6.32: 지금까지 "사건번호" 칸엔 사건번호가 아니라 작성일이, "진행상태"
                # 칸엔 상태가 아니라 회차 숫자만 들어가 있었다(둘 다 실제 데이터로 확인된 버그
                # — 헤더 이름과 담긴 내용이 서로 다른 뜻이었음). 실제로 뽑을 수 있는 값으로
                # 교체한다:
                #   - 사건번호: 첨부파일명(대개 "OO지방법원 2026하단48 ....pdf" 형식)에서 추출
                #   - 진행상태: '파산공매'엔 이미 "공고만료일=매각완료" 행을 걸러내고 남은
                #     것만 올라오므로(위 continue), 여기 남은 행은 전부 "진행 중"이라는 뜻이다.
                #     회차 정보가 있으면 "N차 진행중", 없으면 그냥 "진행중"으로 표시한다.
                #   - 참고사항: 매각대상 항목의 '기타'(건물명/호수/임대보증금/비고 등)를 그대로.
                #   - 소유자 / 필지별 주소: 위에서 공고 단위로 미리 계산해둔 값 사용.
                #   - 신규여부: 재구성 전 '파산공매'에 이미 있던 주소 집합에 없으면 "신규".
                # ⚠️ '회차' 값은 추출 경로에 따라 이미 "차"가 붙어있는 경우("6차", 문장형
                # 추출)와 숫자만 있는 경우("2", 표기반 추출)가 섞여 있다. 둘 다 그대로
                # "{round_no}차"를 붙이면 "6차차"처럼 겹치므로, 이미 붙어있으면 그대로 쓴다.
                round_no = nearest_bid.get("회차", "")
                round_label = round_no if (not round_no or round_no.endswith("차")) else f"{round_no}차"
                out_row = [""] * len(MERGED_HEADERS)
                out_row[MERGED_COL["경매/공매/파산"]] = "파산"
                out_row[MERGED_COL["사건번호"]] = case_no
                out_row[MERGED_COL["주소"]] = addr
                out_row[MERGED_COL["참고사항"]] = p.get("기타", "")
                # ✅ v3.6.22: '용도' 열엔 지목만 깨끗하게 — '기타'(비고/임대보증금/유형 등이
                # 섞인 필드)를 쓰지 않는다. 지목이 없으면 그냥 공란(억지로 안 채움).
                out_row[MERGED_COL["용도"]] = jimok_clean
                out_row[MERGED_COL["면적"]] = area_clean
                out_row[MERGED_COL["진행상태"]] = f"{round_label} 진행중" if round_no else "진행중"
                out_row[MERGED_COL["최저가"]] = parse_amount_to_int(nearest_bid.get("최저입찰가", ""))
                out_row[MERGED_COL["입찰일"]] = nearest_bid.get("입찰기일", "")
                out_row[MERGED_COL["상세페이지"]] = row.get("상세페이지URL", "")
                out_row[MERGED_COL["신규여부"]] = "신규" if addr not in old_addr_set else ""
                # ✅ v3.6.16: 지분 비율까지 상세히 적을 필요 없음(사용자 요청) — 지분 언급이
                # 있으면 "지분"이라고만 표시하고, 정확한 비율이 궁금하면 '공고목록'의
                # 매각대상상세JSON(원문 그대로 보존됨)을 찾아보면 되므로 여기엔 플래그만 남긴다.
                out_row[MERGED_COL["지분 여부"]] = "지분" if p.get("지분") else ""
                out_row[MERGED_COL["필지별 주소"]] = all_parcel_addrs
                out_row[MERGED_COL["pnu"]] = pnu
                out_row[MERGED_COL["소유자"]] = owner
                rows_out.append(out_row)

            # ✅ v3.6.14: 이 행의 주소 중 하나라도 끝까지 PNU가 안 나왔고, 아직 한 번도
            # 이 표시를 단 적 없으면 재추출 대상으로 표시한다.
            # ✅ v3.6.24: 즉시 쓰지 않고 배치 목록에만 쌓아둔다 (아래에서 한 번에 전송).
            # ✅ v3.6.34: 위 지목 재확인 표시와 같은 셀(검토상태)에 같이 쓸 수 있으므로,
            # 둘 다 row_status_additions에 모아서 한 번에 합쳐 쓴다(따로 쓰면 나중에 실행되는
            # batch_update가 먼저 것을 덮어써버리는 사고가 날 수 있다).
            if (row_has_unresolved_pnu_failure and ENABLE_PNU_LOOKUP
                    and review_status_col_letter is not None
                    and "PNU확인필요" not in (row.get("검토상태") or "")
                    and "PNU재시도완료" not in (row.get("검토상태") or "")):
                row_status_additions.append("PNU확인필요")
                flagged_for_reextract += 1

            if row_status_additions and review_status_col_letter is not None:
                existing_status = (row.get("검토상태") or "").strip()
                new_status = " ".join([existing_status] + row_status_additions).strip() if existing_status \
                    else " ".join(row_status_additions)
                status_batch.append({
                    "range": f"{review_status_col_letter}{row_idx}",
                    "values": [[new_status]],
                })

        if status_batch:
            try:
                gws_list.batch_update(status_batch, value_input_option="RAW")
            except Exception as e:
                print(f"   ⚠️ '검토상태' 일괄 표시 실패({len(status_batch)}건 대상): {type(e).__name__}: {e}")

        if jimok_json_batch:
            try:
                gws_list.batch_update(jimok_json_batch, value_input_option="RAW")
            except Exception as e:
                print(f"   ⚠️ 지목 보강 결과 저장 실패({len(jimok_json_batch)}건 대상): {type(e).__name__}: {e}")

        if jimok_local_fixed:
            print(f"   🔧 로컬 PDF 재확인으로 지목/물건종류 보강: {jimok_local_fixed}건")

        if ENABLE_PNU_LOOKUP:
            print(f"   🔎 PNU 조회: 캐시 재사용 {len(seen_addr) - pnu_new_calls}건 / 신규 API 호출 {pnu_new_calls}건"
                  + (f" / 등기부 재검증으로 보정 {reverified}건" if reverified else "")
                  + (f" / 재추출 대상으로 표시 {flagged_for_reextract}건" if flagged_for_reextract else ""))

    # 헤더만 남기고 기존 데이터 전부 지운 뒤 새로 씀
    try:
        gws_merged.resize(rows=1)
    except Exception:
        pass
    # ✅ v3.6.29: '파산공매'는 이 함수가 실행될 때마다 데이터를 통째로 다시 쓰므로(바로 아래
    # append_rows), 헤더도 항상 표준 구성(MERGED_HEADERS)으로 강제로 맞춘다. get_or_create_
    # gsheet_tab의 _ensure_header_row는 "이미 데이터가 있으면 자동으로 안 고침" 원칙이라
    # (예: 실행 시작 시점엔 옛 헤더 + 옛 데이터가 남아있었을 수 있음) 여기서 놓칠 수 있는데,
    # 여기는 어차피 데이터까지 같이 재작성하니 헤더가 어긋날 위험이 없다.
    try:
        # ⚠️ 위 _ensure_header_row와 동일한 이유로 range_name=/values= 키워드로 명시 호출.
        gws_merged.update(range_name="A1", values=[MERGED_HEADERS], value_input_option="RAW")
    except Exception as e:
        print(f"   ⚠️ '{today_tab}' 헤더 갱신 실패: {type(e).__name__}: {e}")
    if rows_out:
        try:
            gws_merged.append_rows(rows_out, value_input_option="RAW", table_range="A1")
        except Exception as e:
            print(f"   ❌ '{today_tab}' 재작성 실패: {type(e).__name__}: {e}")
            return None
    pnu_idx = MERGED_COL["pnu"]
    no_pnu = sum(1 for r in rows_out if not r[pnu_idx]) if ENABLE_PNU_LOOKUP else 0
    print(f"🔁 '{today_tab}' 재구성 완료: {len(rows_out)}행 (공고목록 {len(values) - 1}건 기준)"
          + (f" — ⚠️ PNU 조회 실패(주소 의심) {no_pnu}건" if ENABLE_PNU_LOOKUP and no_pnu else ""))
    return {"rows": len(rows_out), "no_pnu": no_pnu, "announcements": max(len(values) - 1, 0)}


def _col_letter(headers: list, header_name: str) -> str:
    """헤더 이름 → A1 표기용 열 문자(A, B, ... Z, AA, ...)."""
    idx = headers.index(header_name) + 1  # 1-based
    a1 = gspread.utils.rowcol_to_a1(1, idx)  # 예: "F1"
    return re.match(r"[A-Z]+", a1).group()


def mark_closed_announcements(gws_list, closed_seq_ids: set) -> int:
    """
    ✅ v3.6.2: main()이 사이트 목록을 끝까지 다 훑었는데도 더 이상 보이지 않는 seq_id는
    법원이 매각을 완료했거나 목록에서 내린 것으로 보고, '공고목록'의 '공고만료일' 칸을
    "매각완료"로 덮어쓴다 (요청에 따라 원래 있던 만료일 값은 대체됨).

    ✅ v3.6.24: 예전에는 대상 행마다 update_cell()을 한 번씩(=API 호출 한 번씩) 날렸는데,
    한 실행에서 매각완료로 표시할 행이 수십~수백 개가 되면 구글시트 쓰기 할당량
    (분당 쓰기 요청 수)을 순식간에 넘겨서 APIError 429가 무더기로 발생했다(실제 로그로
    확인됨 — 70건을 표시하려다 다수가 429로 조용히 실패). 개별 update_cell 대신
    batch_update()로 모든 대상 행을 한 번의 API 호출에 담아 보내도록 바꿔서, 이 시나리오
    에서의 API 호출 횟수를 (표시할 행 수)회에서 1회로 줄인다.
    """
    if not closed_seq_ids or gws_list is None:
        return 0
    values = gws_list.get_all_values()
    if not values:
        return 0
    headers = values[0]
    if "상세페이지URL" not in headers or "공고만료일" not in headers:
        print("   ⚠️ '공고목록'에 '상세페이지URL' 또는 '공고만료일' 열이 없어 매각완료 표시를 건너뜁니다.")
        return 0
    url_col = headers.index("상세페이지URL")
    exp_col_letter = _col_letter(headers, "공고만료일")

    batch_data = []
    for i, row in enumerate(values[1:], start=2):
        url = row[url_col] if url_col < len(row) else ""
        sid = extract_seq_id(url)
        if sid and sid in closed_seq_ids:
            batch_data.append({"range": f"{exp_col_letter}{i}", "values": [["매각완료"]]})

    updated = 0
    if batch_data:
        try:
            gws_list.batch_update(batch_data, value_input_option="RAW")
            updated = len(batch_data)
        except Exception as e:
            print(f"   ❌ '매각완료' 일괄 표시 실패: {type(e).__name__}: {e}")
    print(f"   ✅ '매각완료' 표시 {updated}행 (대상 seq_id {len(closed_seq_ids)}건)")
    return updated


def remove_default_sheet1_if_empty(sh):
    for name in ["시트1", "Sheet1"]:
        try:
            ws = sh.worksheet(name)
        except Exception:
            continue
        try:
            values = ws.get_all_values()
            is_empty = not values or all(not any(row) for row in values)
            if is_empty:
                sh.del_worksheet(ws)
                print(f"🧹 빈 기본 탭 '{name}' 삭제함")
            else:
                print(f"ℹ️ '{name}' 탭에 데이터가 있어 그대로 둠 (수동으로 확인해주세요)")
        except Exception as e:
            print(f"⚠️ '{name}' 탭 정리 중 오류: {e}")


# =========================
# 로그기록 탭 (실행 1회 = 1줄)
# =========================
LOG_TAB = "로그기록"
LOG_HEADERS = ["실행시각(KST)", "모드", "상태", "훑은 목록쪽수", "사이트 확인 공고", "신규 공고 처리", "첨부없음", "OCR 사용",
               "매각완료 표시", "파산공매 행수", "PNU 실패", "소요(분)", "메모", "실행링크"]


def write_run_log(gsheet, stats: dict):
    """'로그기록' 탭에 실행 결과 1줄을 이어 붙인다. 실패해도 예외를 올리지 않는다."""
    if gsheet is None:
        return
    try:
        from datetime import timezone, timedelta
        kst = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")
        rid, repo = os.environ.get("GITHUB_RUN_ID"), os.environ.get("GITHUB_REPOSITORY")
        link = f"https://github.com/{repo}/actions/runs/{rid}" if rid and repo else "(로컬 실행)"
        ws = get_or_create_gsheet_tab(gsheet, LOG_TAB, LOG_HEADERS)
        row = [kst, stats.get("mode", ""), stats.get("status", ""), stats.get("pages", ""), stats.get("seen", ""),
               stats.get("new", ""), stats.get("no_attach", ""), stats.get("ocr", ""), stats.get("closed", ""),
               stats.get("merged_rows", ""), stats.get("no_pnu", ""),
               round((time.time() - RUN_STARTED) / 60, 1), str(stats.get("memo", ""))[:300], link]
        ws.append_row(row, value_input_option="RAW", table_range="A1")
        print(f"📝 '{LOG_TAB}' 탭에 실행 기록 저장")
    except Exception as e:
        print(f"⚠️ 로그기록 저장 실패(수집 결과에는 영향 없음): {type(e).__name__}: {e}")


def _deadline_passed() -> bool:
    return (time.time() - RUN_STARTED) / 60 >= RUN_DEADLINE_MINUTES


# =========================
# 메인
# =========================
def main():
    """
    ✅ v3.6: '공고목록'에만 직접 쓴다('부동산목록'/'입찰일정' 탭 자체가 없어짐).
    매각대상/입찰일정 상세 정보는 JSON으로 직렬화해서 '매각대상상세JSON'/'입찰일정상세JSON'
    열에 통째로 저장하고, '파산공매'는 이 함수가 끝날 때 rebuild_merged_sheet()가
    '공고목록' 전체를 다시 읽어서 처음부터 새로 만든다.
    """
    if TEST_MODE:
        print(f"🧪 TEST_MODE 활성화 — 구글시트/로컬 파일 아무것도 안 건드리는 드라이런, 최신 {TEST_ITEM_LIMIT}건만 콘솔에 출력")
        gsheet = gws_list = None
        known_seq_ids = set()
    else:
        gsheet = connect_google_sheet()
        if gsheet is None:
            print("⚠️ 구글시트 연결 실패 → 중단합니다 (구글시트가 유일한 데이터 기준이라 연결이 필수입니다).")
            return 1
        remove_default_sheet1_if_empty(gsheet)
        gws_list = get_or_create_gsheet_tab(gsheet, GOOGLE_SHEET_LIST_TAB, LIST_HEADERS)
        try:
            known_seq_ids = get_known_seq_ids(gws_list)
        except Exception as e:
            print(f"⚠️ 구글시트에서 seq_id 확인 실패({e}) → 중단합니다 (안전하게 '이미 아는 것'을 판단할 수 없어서 진행하지 않습니다).")
            return 1

    print(f"📌 기존 수집 공고(구글시트 기준): {len(known_seq_ids)}건" if known_seq_ids else "📌 기존 이력 없음 → 전체 수집")
    print(f"🔎 검색 필터: 제목에 '{SEARCH_KEYWORD}' 포함된 공고만 수집")

    # ✅ v3.6.2: 매각완료 판정용. initial_known_seq_ids는 이번 실행 시작 시점에 구글시트에
    # '이미 있던' 공고 집합(스냅샷)이고, all_seen_seq_ids는 이번에 사이트 목록을 훑으며
    # '실제로 화면에서 본' 공고 집합이다. 목록을 끝까지 다 훑었는데(scan_completed_fully=True)
    # initial에는 있지만 all_seen에는 없는 것 = 사이트에서 내려간(매각완료 등) 공고로 간주한다.
    initial_known_seq_ids = set(known_seq_ids)
    all_seen_seq_ids = set()
    scan_completed_fully = True

    pending_list = []
    run_stats = {"mode": "INCREMENTAL", "status": "성공", "pages": 0, "seen": 0, "new": 0, "no_attach": 0,
                 "ocr": 0, "closed": 0, "merged_rows": "", "no_pnu": "", "memo": ""}

    def flush_to_gsheet():
        if TEST_MODE or gws_list is None or not pending_list:
            return
        try:
            gws_list.append_rows(pending_list, value_input_option="RAW", table_range="A1")
            pending_list.clear()
        except Exception as e:
            print(f"   ❌ 구글시트 '공고목록' 업로드 실패: {type(e).__name__}: {e}")

    try:
        driver = build_driver()
    except Exception as e:
        traceback.print_exc()
        run_stats["status"] = "오류"
        run_stats["memo"] = f"브라우저 시작 실패 {type(e).__name__}: {str(e)[:150]}"
        write_run_log(gsheet, run_stats)
        return 1
    total_list = 0
    stop_all = False  # TEST_MODE 건수 한도 등, "정말 전체를 멈춰야 하는" 경우에만 True
    processed_items = 0

    try:
        page = 1
        while True:
            if stop_all:
                break
            if MAX_PAGES is not None and page > MAX_PAGES:
                print(f"🛑 최대 페이지({MAX_PAGES}) 도달. 종료")
                scan_completed_fully = False
                break

            if _deadline_passed():
                print(f"⏰ 실행 시간 한도({RUN_DEADLINE_MINUTES:.0f}분) 도달 → 새 공고 읽기를 멈추고 정리합니다")
                scan_completed_fully = False
                run_stats["memo"] = "시간한도로 중단(다음 실행이 이어서 수집)"
                break

            print(f"\n📄 목록 페이지 {page} 처리 중...")
            run_stats["pages"] = page
            goto_list_page(driver, page)
            list_rows = parse_list_page(driver)
            print(f"🔍 {len(list_rows)}건 감지 (제목에 '{SEARCH_KEYWORD}' 포함된 것만)")
            if not list_rows:
                print("🛑 더 이상 항목 없음(페이지네이션 끝). 종료")
                break

            for row in list_rows:
                if MAX_NEW_ITEMS and processed_items >= MAX_NEW_ITEMS:
                    print(f"🧪 SCOURT_MAX_NEW={MAX_NEW_ITEMS}건 도달 → 새 공고 읽기를 멈춥니다(시험 실행)")
                    scan_completed_fully = False
                    run_stats["memo"] = f"시험실행: 신규 {MAX_NEW_ITEMS}건까지만"
                    stop_all = True
                    break
                if _deadline_passed():
                    scan_completed_fully = False
                    run_stats["memo"] = "시간한도로 중단(다음 실행이 이어서 수집)"
                    stop_all = True
                    break
                if TEST_MODE and processed_items >= TEST_ITEM_LIMIT:
                    print(f"  🧪 테스트 처리 건수({TEST_ITEM_LIMIT}) 도달 → 종료")
                    stop_all = True
                    break

                run_stats["seen"] += 1
                if row["seq_id"]:
                    all_seen_seq_ids.add(row["seq_id"])  # 건너뛰든 새로 처리하든, '봤다'는 사실은 기록

                if row["seq_id"] and row["seq_id"] in known_seq_ids:
                    print(f"  ⏭️  [번호 {row['no']} / seq_id {row['seq_id']}] 이미 수집됨 → 건너뜀")
                    continue
                if not row["seq_id"]:
                    print(f"  ⚠️ [{row['no']}] {row['title']} → URL에서 seq_id를 못 찾음(형식 변경 가능성). "
                          f"멈추지 않고 계속 진행하되 이 행은 그대로 처리합니다.")

                processed_items += 1
                if row["seq_id"]:
                    known_seq_ids.add(row["seq_id"])
                print(f"  ▶ [{row['no']}] {row['title']} ({row['court']})")

                if TEST_MODE:
                    print("     🧪 (드라이런이라 상세페이지 방문/다운로드는 생략)")
                    continue

                driver.get(row["detail_url"])
                human_delay(1.0, 3.0)
                detail = parse_detail_page(driver)

                if not detail["attachments"]:
                    list_row = [
                        row["no"], row["court"], row["applicant"], row["title"], row["views"],
                        detail["작성일"], detail["공고만료일"], detail["전화번호"],
                        "", row["detail_url"], "첨부없음", "", "", "", "[]", "[]"
                    ]
                    pending_list.append(list_row); total_list += 1
                    run_stats["no_attach"] += 1
                    continue

                for att in detail["attachments"]:
                    pdf_path = find_existing_pdf(att['name'])
                    if not att["name"].lower().endswith(".pdf"):
                        # hwp 등 PDF가 아닌 첨부는 읽을 수 없고, 다운로드 확인(.pdf 감시)만 30초 헛돈다
                        print(f"     ⏭️  PDF가 아닌 첨부({att['name']}) → 다운로드 생략")
                        pdf_path = None
                    elif pdf_path:
                        print(f"     💾 로컬에 이미 있는 PDF 재사용(다운로드 생략): {att['name']}")
                    else:
                        pdf_path = download_attachment_via_click(driver, att["element"])
                    native_text = extract_pdf_text(pdf_path) if pdf_path else ""

                    property_items, prop_method = extract_property_list(native_text, "", pdf_path)
                    bid_items, bid_method = extract_bid_schedule(native_text, "", pdf_path)

                    ocr_text = ""
                    # ✅ v3.6.33: 지목/물건종류가 하나도 없이 빠진 경우("표는 읽었는데 지목 열만
                    # 놓침")도 OCR 트리거 조건에 추가 — 텍스트 기반 추출이 표의 줄바꿈 등으로
                    # 깨져서 지목을 놓쳐도, 이미지 기반(OCR)으로 다시 보면 잡힐 때가 있다.
                    needs_ocr = (
                        not property_items or not bid_items
                        or _property_items_need_jimok_ocr(property_items)
                    )
                    if pdf_path and needs_ocr and HAS_OCR:
                        ocr_text = extract_pdf_text_ocr(pdf_path)
                        if ocr_text:
                            if not property_items:
                                property_items, prop_method = extract_property_list(native_text, ocr_text, pdf_path)
                            elif _property_items_need_jimok_ocr(property_items):
                                filled = enrich_jimok_from_ocr(property_items, ocr_text)
                                if filled:
                                    print(f"   ℹ️ OCR로 지목/물건종류 보강: {filled}건")
                            if not bid_items:
                                bid_items, bid_method = extract_bid_schedule(native_text, ocr_text, pdf_path)

                    review_flag = "OCR 필요 - 수동확인" if ocr_text else ""
                    if ocr_text:
                        run_stats["ocr"] += 1

                    property_summary = " | ".join(p["주소"] for p in property_items if p.get("주소"))
                    bid_summary = " | ".join(
                        f"{b['회차']}:{b['입찰기일']}:{b['최저입찰가']}" for b in bid_items
                    )
                    method_summary = f"매각대상={prop_method}, 입찰일정={bid_method}"

                    list_row = [
                        row["no"], row["court"], row["applicant"], row["title"], row["views"],
                        detail["작성일"], detail["공고만료일"], detail["전화번호"],
                        att["name"], row["detail_url"], method_summary,
                        property_summary, bid_summary, review_flag,
                        json.dumps(property_items, ensure_ascii=False),
                        json.dumps(bid_items, ensure_ascii=False),
                    ]
                    pending_list.append(list_row); total_list += 1

                    if review_flag:
                        print(f"     ⚠️ {review_flag} (스캔 이미지 PDF로 판단되어 OCR 사용)")
                    print(f"     📎 {att['name']} → 매각대상[{prop_method}]: {property_summary or '(없음)'}")
                    print(f"                    입찰일정[{bid_method}]: {bid_summary or '(없음)'}")

            flush_to_gsheet()
            if stop_all:
                break
            page += 1

    except KeyboardInterrupt:
        print("\n🛑 사용자 중단. 지금까지 처리한 만큼 저장 후 종료합니다...")
        scan_completed_fully = False
    except Exception as e:
        print(f"\n❌ 처리 중 예외 발생: {type(e).__name__}: {e}")
        traceback.print_exc()
        scan_completed_fully = False
        run_stats["status"] = "오류"
        run_stats["memo"] = f"{type(e).__name__}: {str(e)[:200]}"
    finally:
        flush_to_gsheet()
        print(f"\n📁 이번 실행 처리 결과: 공고목록 신규 {total_list}행")
        if not TEST_MODE and gsheet is not None:
            print(f"   - 구글시트: {gsheet.url}")
            if scan_completed_fully:
                closed = initial_known_seq_ids - all_seen_seq_ids
                if closed:
                    print(f"🔒 사이트 목록을 끝까지 확인했고, 더 이상 보이지 않는 공고 {len(closed)}건을 "
                          f"'매각완료'로 표시합니다.")
                    mark_closed_announcements(gws_list, closed)
                    run_stats["closed"] = len(closed)
                else:
                    print("🔒 매각완료로 새로 표시할 공고 없음.")
            else:
                print("   ℹ️ 이번 실행은 목록을 끝까지 다 훑지 못해(중단/최대페이지 도달) 매각완료 판정은 건너뜁니다.")
            try:
                merged = rebuild_merged_sheet(gsheet) or {}
            except Exception as e:
                traceback.print_exc()
                merged = {}
                run_stats["status"] = "오류"
                run_stats["memo"] = (run_stats["memo"] + " / " if run_stats["memo"] else "") + \
                    f"파산공매 재구성 실패 {type(e).__name__}: {str(e)[:150]}"
            run_stats["merged_rows"] = merged.get("rows", "")
            run_stats["no_pnu"] = merged.get("no_pnu", "")
            run_stats["new"] = total_list
            if run_stats["status"] == "성공" and not run_stats["seen"]:
                run_stats["status"] = "경고"
                run_stats["memo"] = (run_stats["memo"] + " / " if run_stats["memo"] else "") + \
                    "목록에서 공고를 한 건도 못 봄(사이트 접속 차단/구조 변경 의심)"
            export_gsheet_snapshot(gsheet)
            write_run_log(gsheet, run_stats)
        try:
            driver.quit()
        except Exception:
            pass
    return 1 if run_stats["status"] in ("오류", "경고") else 0


def run_rebuild_merged_only():
    """
    RUN_MODE = "REBUILD_MERGED"
    사이트 방문/크롤링 없이, 지금 구글시트 '공고목록'에 있는 내용만으로 '파산공매'를
    처음부터 다시 만든다. 파싱/포맷 로직을 고친 뒤 과거 데이터에도 바로 반영하고 싶을 때 사용.
    ✅ v3.6.34: 로컬에 PDF가 남아있는데 지목/물건종류가 통째로 유실된 행은, 이 함수 안에서
    rebuild_merged_sheet()가 사이트 방문 없이 그 PDF만 다시 읽어 자동으로 보강한다
    (예전 GSHEET_FAILED_BACKFILL 모드가 하던 일 중 이 부분은 이제 여기로 흡수됨).
    """
    gsheet = connect_google_sheet()
    if gsheet is None:
        print("⚠️ 구글시트 연결 실패 → 중단")
        return 1
    stats = {"mode": "REBUILD_MERGED", "status": "성공"}
    try:
        merged = rebuild_merged_sheet(gsheet) or {}
        stats["merged_rows"] = merged.get("rows", "")
        stats["no_pnu"] = merged.get("no_pnu", "")
    except Exception as e:
        traceback.print_exc()
        stats["status"] = "오류"
        stats["memo"] = f"{type(e).__name__}: {str(e)[:200]}"
    export_gsheet_snapshot(gsheet)
    write_run_log(gsheet, stats)
    return 1 if stats["status"] == "오류" else 0


# ✅ v3.6.34: 실제로 계속 쓰는 두 모드(INCREMENTAL/REBUILD_MERGED)만 남기고 나머지는
# 코드에서 통째로 삭제했다(사용자 요청) — GSHEET_FAILED_BACKFILL(사이트 재방문 재추출)과
# COMPLETENESS_CHECK(21개 법원 전수조사)는 이제 없다. GSHEET_FAILED_BACKFILL이 하던 일 중
# "지목이 통째로 유실된 행 복구"는 REBUILD_MERGED(rebuild_merged_sheet의 로컬 PDF 재확인
# 로직)로 옮겨졌고, 그 외의 경우(첨부파일 자체를 못 읽었거나 PDF가 로컬에서 지워진 경우)는
# '공고목록'에서 해당 행을 지우고 INCREMENTAL을 다시 돌리면 그 공고가 "모르는 것"으로
# 다시 인식되어 자연스럽게 재수집된다.
if __name__ == "__main__":
    if RUN_MODE == "REBUILD_MERGED":
        code = run_rebuild_merged_only()
    else:
        code = main()
    sys.exit(code or 0)