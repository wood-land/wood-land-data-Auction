"""
crawler_core.py - 지방 신문사 키워드 기사 수집기 (공통 코어)

강원일보 수집기(72_101_강원일보_0919_v2.py)를 여러 신문사에서 쓸 수 있도록 일반화한 것.
- 신문사마다 다른 부분(검색 URL, 선택자)은 Site 설정(region_*.py)에만 적는다.
- 지번 추출, 기간 필터, 연속 종료, CSV 이어하기, 대기 시간은 모두 이 파일 한 곳에서 처리한다.
- 지역(도) 단위로 실행하고, 결과는 지역별 CSV 1개(신문사 컬럼으로 구분)에 모은다.

수집 규칙 (v2와 동일)
- 기사 기준일: '수정' 일자가 있으면 수정일, 없으면 '입력'일
- 기준일이 (오늘 - 기간)보다 오래된 기사가 N건 연속이면 다음 키워드로 (검색 결과가 최신순이므로)
- 본문에서 '동/리/가 + 번지수(+번지)' 지번이 특정된 기사만 저장

v3에서 달라진 점
- 페이지를 가져오는 방식(Selenium / requests)과 해석(BeautifulSoup)을 분리했다.
  Site.fetch = "requests" 로 두면 브라우저 없이 훨씬 빠르게 수집한다(서버가 완성된 HTML을 주는 신문사만).
- 목록의 날짜가 기간보다 한참 오래된 기사는 본문을 열지 않고 건너뛴다(요청 수 절감).
- 이미 확인한 기사(주소가 없어 저장하지 않은 기사 포함)를 .seen.tsv에 기억해 재실행 시 다시 열지 않는다.
- 이름이 한 글자인 동/리(명동 12번지, 상리 산 12번지, 중동 100번지 일대 등)도 찾는다. (v2는 놓쳤음)
- 주소 앞에 붙은 시/군/구 이름(예: '원주시 문막읍 후용리 1153')과 기사 지역 정보(지역힌트)를 함께 저장한다.
  → 이후 PNU 변환 단계에서 시군구를 정하는 단서로 쓴다. (검증은 PNU 변환 단계에서 법정동 코드표로 할 것)
"""
from __future__ import annotations

import html as html_lib
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import quote, urljoin

import pandas as pd
from bs4 import BeautifulSoup

from common.admin_names import NON_PLACE_DONGRI, is_place_eupmyeon, peel_sigungu_suffix
from common.search_adapters import ADAPTERS as SEARCH_ADAPTERS
from common.search_builders import BUILDERS as SEARCH_BUILDERS
from common.verified_selectors import VERIFIED_SELECTORS

# ============================ 지번 주소 추출 ============================
# 패턴: (읍/면 이름)? + (동/리 지명 | 'N가' 지명) + (산)?번지수(-번지수)? + (번지)?
# 예: '문막읍 후용리 1153', '황지동 산 143-1번지', '온의동 산43-3번지', '종로3가 12번지'
# - 읍/면은 앞이 한글이 아닐 때만 시작으로 본다 ('~에 따르면'의 '따르면'처럼 지명이 아닌 것은 아래에서 따로 걸러냄)
# - '가'는 숫자가 붙은 'N가'만 인정한다 ('상가 1', '시가 100'처럼 일반 낱말을 지명으로 오인하던 문제)
ADDRESS_RE = re.compile(
    r"(?P<eup>(?<![가-힣])[가-힣]{2,6}(?:읍|면)\s*)?"
    r"(?P<dr>[가-힣]{2,8}(?:동|리)|[가-힣]{1,6}\d가)\s*(?:산\s*)?\d{1,4}(?:-\d{1,4})?(?:\s*번지)?"
)
ADDRESS_CONTEXT_WORDS = ("일대", "일원")

# 이름이 한 글자인 동/리 (예: '명동 12번지', '중동 100번지 일대', '상리 산 12번지', '화성시 상리 55번지').
# v2 정규식은 '이름 2글자 이상 + 동/리'만 잡아서 이런 지명을 놓쳤다.
# - '동/리'만 대상으로 한다
# - 바로 앞 글자가 한글이면 제외한다 → '봉명동'의 '명동', '사무관리 3'의 '관리'처럼 긴 낱말의 끝부분을 지명으로 오인하지 않음
# - 인정 기준: '번지'가 붙어 있거나, 숫자 바로 뒤에 '일대/일원'이 이어져야 함 ('거리 5km 일대' 같은 문장 제외)
ADDRESS_SHORT_RE = re.compile(
    r"(?P<eup>(?<![가-힣])[가-힣]{2,6}(?:읍|면)\s*)?"
    r"(?P<dr>(?<![가-힣])[가-힣](?:동|리))\s*(?:산\s*)?\d{1,4}(?:-\d{1,4})?(?:\s*번지)?"
)


def _sigungu_before(text: str, pos: int) -> str:
    """주소 바로 앞에 붙은 시/군/구 (예: '청주시 흥덕구 ' + '봉명동 123').
    실제 행정구역 이름 사전으로 확인하므로 '사업지구', '집중호우시' 같은 낱말은 붙지 않는다."""
    _, prefix = peel_sigungu_suffix(text[max(0, pos - 30):pos], with_province=True)
    return prefix


def _clean_match(m: "re.Match") -> Tuple[str, int]:
    """매칭된 주소를 정리하고 (주소, 시작 위치) 를 돌려준다. 지명이 아닌 읍/면 접두어는 떼어낸다.
    지명이 아닌 동/리 낱말('활동 3건', '관리 5곳')이면 ('', 0)."""
    dr = m.group("dr")
    if dr in NON_PLACE_DONGRI:
        return "", 0
    eup = m.group("eup")
    start = m.start()
    text = m.group(0)
    if eup is not None and not is_place_eupmyeon(eup.strip()):
        text = text[len(eup):]               # '따르면 동대동 489-52' -> '동대동 489-52'
        start += len(eup)
    return re.sub(r"\s+", " ", text).strip(), start


def extract_addresses(text: Optional[str]) -> List[str]:
    """본문에서 지번 주소를 뽑는다.
    '번지'가 붙어 있거나, 매칭 직후 몇 글자 안에 '일대'/'일원'이 있어야 '지번이 특정된' 것으로 본다.
    (동/리 지명 뒤에 숫자가 바로 안 나오면 애초에 매칭되지 않으므로,
     '~일대에서 열렸다'처럼 지번 없이 '일대'만 쓰인 문장은 자동으로 걸러진다.)
    주소 바로 앞에 실제 시/군/구 이름이 있으면 함께 붙여서 돌려준다."""
    text = text or ""
    matches = [(m, False) for m in ADDRESS_RE.finditer(text)]
    long_spans = [(m.start(), m.end()) for m, _ in matches]
    for m in ADDRESS_SHORT_RE.finditer(text):      # 한 글자 동/리 (긴 지명과 겹치는 것은 제외)
        if not any(m.start() < e and m.end() > s for s, e in long_spans):
            matches.append((m, True))
    matches.sort(key=lambda x: x[0].start())

    found: List[str] = []
    for m, is_short in matches:
        addr, start = _clean_match(m)
        if not addr:
            continue
        has_bunji = "번지" in addr
        if is_short:
            # 한 글자 지명은 '거리 5km 일대', '이동 3km 일원'처럼 일반 문장과 섞이기 쉬우므로
            # '일대/일원'이 숫자 바로 뒤에 붙어 있을 때만 인정한다 (번지가 있으면 그대로 인정)
            near = text[m.end():].lstrip().startswith(ADDRESS_CONTEXT_WORDS)
        else:
            near = any(w in text[m.end(): m.end() + 6] for w in ADDRESS_CONTEXT_WORDS)
        if has_bunji or near:
            prefix = _sigungu_before(text, start)
            full = f"{prefix} {addr}" if prefix else addr
            if full not in found:
                found.append(full)
    return found


# ============================ 날짜 처리 ============================
_D = r"(\d{2,4})[-./년]\s*(\d{1,2})[-./월]\s*(\d{1,2})일?"
# 신문사마다 '신문게시일' 표현이 다르다: 입력, 기사입력, 승인(일), 등록(일), 작성(일), 송고, 발행일 -> 입력일 / 수정(일), 최종수정, 최종편집 -> 수정일
_INPUT_RES = [re.compile(r"(?:입력|발행일)\s*:?\s*" + _D), re.compile(r"(?:승인|등록|작성|송고)일?\s*:?\s*" + _D)]
_MODIFIED_RE = re.compile(r"(?:최종수정|최종편집|수정|업데이트)일?\s*:?\s*" + _D)
_ANY_DATE_RE = re.compile(_D)


def _fmt(m: "re.Match") -> str:
    year = int(m.group(1))
    if year < 100:
        year += 2000 if year <= 69 else 1900
    return f"{year:04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def parse_article_dates_ex(date_info_text: Optional[str]) -> Tuple[Optional[str], Optional[str], bool]:
    """'입력 : 2026-09-17 00:05:00 수정 : 2026-09-17 00:06:17' 또는 '입력 2026.09.18 16:45'
    → (입력일, 수정일, 입력일에 '입력/등록/승인…' 라벨이 붙어 있었는가)  ('YYYY-MM-DD' 형식으로 통일)
    라벨 없이 문서에서 처음 나온 날짜는 기사 날짜가 아닐 수 있다(사이트 머리말의 현재 시각 등)."""
    text = re.sub(r"\s+", " ", date_info_text or "")
    ins = None
    labeled = False
    for rx in _INPUT_RES:
        m = rx.search(text)
        if m:
            ins = _fmt(m)
            labeled = True
            break
    mod = _MODIFIED_RE.search(text)
    if not ins:
        prefix = text[:mod.start()] if mod else text
        any_date = _ANY_DATE_RE.search(prefix)
        if any_date:
            ins = _fmt(any_date)
    return ins, (_fmt(mod) if mod else None), labeled


# 날짜 요소의 텍스트가 이보다 길면 '페이지 전체를 감싼 요소'를 잡은 것이다. 그 안에서 처음 나온 날짜는 사이드바의
# 다른 기사나 머리말의 시각일 뿐 기사 날짜가 아니다 (선택자를 'td, span, div'로 넓게 잡은 신문사에서 발생).
MAX_DATE_ELEMENT_TEXT = 300


def date_from_element(el) -> Tuple[Optional[str], Optional[str], bool]:
    """선택자로 잡은 요소 -> (입력일, 수정일, 라벨 여부). 요소가 너무 크면 (None, None, False)."""
    if el is None:
        return None, None, False
    text = el.get("content") or el.get("datetime") or el.get_text(" ")
    if len(text) > MAX_DATE_ELEMENT_TEXT:
        return None, None, False
    return parse_article_dates_ex(text)


def parse_article_dates(date_info_text: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """(입력일, 수정일). 라벨 여부가 필요하면 parse_article_dates_ex 를 쓴다."""
    ins, mod, _ = parse_article_dates_ex(date_info_text)
    return ins, mod


def pick_reference_date(input_date, modified_date, basis: str = "modified_first"):
    """기사의 기준 날짜 -> (날짜문자열, '수정'|'입력') / 둘 다 없으면 (None, None)
    basis  "modified_first"(기본): 수정일이 있으면 수정일, 없으면 입력일 (예: 경남일보)
           "input"             : 입력일(입력/기사입력/승인/등록)만 쓴다. 입력일을 못 읽었을 때만 수정일 (예: 대구신문)"""
    if basis == "input":
        if input_date:
            return input_date, "입력"
        return (modified_date, "수정") if modified_date else (None, None)
    if modified_date:
        return modified_date, "수정"
    if input_date:
        return input_date, "입력"
    return None, None


def parse_list_date(text: Optional[str]) -> Optional[str]:
    """목록의 '2026-09-17 [12:05:00]' 등에서 첫 날짜 → 'YYYY-MM-DD'"""
    m = _ANY_DATE_RE.search(text or "")
    return _fmt(m) if m else None


def is_recent(date_str: str, start_date: datetime) -> bool:
    return datetime.strptime(date_str, "%Y-%m-%d") >= start_date


# ============================ 신문사 설정 ============================
@dataclass
class Site:
    """신문사 1곳의 설정. 신문사마다 다른 부분은 전부 여기에만 적는다."""
    name: str                    # 신문사 이름 (CSV '신문사' 컬럼)
    search_url: str              # 검색 URL. {kw}=검색어(URL 인코딩됨), {page}=페이지 번호. 최신순 정렬 상태여야 함
    list_item_sel: str           # 검색 결과 기사 1건을 감싸는 요소
    list_title_sel: str          # (기사 1건 안에서) 제목 + 링크 <a>
    list_date_sel: str           # (기사 1건 안에서) 날짜가 들어 있는 요소. 안에서 첫 YYYY-MM-DD 를 읽음
    article_date_sel: str        # 기사 페이지에서 '입력/수정' 날짜가 있는 요소
    article_body_sel: str        # 기사 페이지의 본문
    link_contains: str = ""      # 이 문자열을 포함한 링크만 기사로 인정 (광고/기타 링크 제외)
    fetch: str = "selenium"      # "selenium" | "requests"
    search_method: str = "GET"   # 검색 폼이 POST를 사용하는 사이트용
    search_form_data: Tuple[Tuple[str, str], ...] = ()  # POST payload 템플릿: {kw}, {page}, {page_index}
    encoding: str = ""           # requests 사용 시 강제할 인코딩 (예: "euc-kr"). 비우면 자동
    meta_hints: Tuple[str, ...] = ()   # 기사 <meta property=...> 중 지역힌트로 쓸 것 (예: "article:section")
    default_area: str = ""       # 지역 신문사면 기본 지역 (예: "원주시"). 지역힌트 앞에 붙는다
    delay_article: Tuple[float, float] = (1.5, 3.5)   # 기사 1건 열고 난 뒤 대기(초)
    delay_page: Tuple[float, float] = (1.0, 2.0)      # 검색 결과 1페이지 처리 뒤 대기(초)
    list_skip_margin_days: Optional[int] = 30   # 목록 날짜가 (시작일 - N일)보다 이전이면 본문을 안 열고 '오래된 기사'로 처리. None이면 항상 연다
    max_pages: Optional[int] = None             # 키워드당 최대 페이지. None이면 Settings 값
    note: str = ""               # 메모 (검색 방식 차이 등)
    homepage_url: str = ""       # Newspaper homepage, separate from its search endpoint.
    enabled: bool = True
    disabled_reason: str = ""
    search_adapter: str = ""     # 검색 결과를 JSON API 로 받는 사이트 (common/search_adapters.py 의 이름). JSON -> 목록 HTML 로 바꿔 준다
    list_title_text_sel: str = ""    # 목록의 링크가 카드 전체를 감싸 링크 텍스트에 요약·날짜까지 섞일 때, 항목 안에서 제목만 담은 요소 (예: 칠곡신문 div.news_tit)
    search_encoding: str = ""    # 검색어를 퍼센트 인코딩할 때의 문자셋 (search_builder 가 쓴다). 기사 페이지 디코딩용 encoding 과 별개다
    search_builder: str = ""     # 검색 주소를 코드로 만들어야 하는 사이트 (common/search_builders.py 의 이름). 비우면 search_url 템플릿을 쓴다
    date_basis: str = "modified_first"   # 기준 날짜: "modified_first"(수정일 우선) | "input"(입력일만). pick_reference_date 참고
    newest_first: bool = True    # 검색 결과가 최신순인가. False 면 '오래된 기사 N건 연속이면 종료' 규칙을 쓰지 않는다
                                 # (최신순이 아니면 오래된 기사 뒤에 최근 기사가 있어도 놓치게 된다)

    def __post_init__(self):
        # diagnose_dates.py 로 기사를 실제로 열어 정답 날짜와 대조해 확인한 선택자가 있으면 그것을 쓴다
        # (common/verified_selectors.py). 신문사 정의마다 흩어져 있던 넓은 선택자('td, span, div' 등)를 한 곳에서 바로잡는다.
        for key, value in VERIFIED_SELECTORS.get(self.name, {}).items():
            setattr(self, key, value)


def site_from(template: dict, **overrides) -> Site:
    """공통 템플릿(같은 뉴스 솔루션을 쓰는 신문사들의 기본값)에 신문사별 값을 덮어써서 Site를 만든다."""
    return Site(**{**template, **overrides})


# ※ 아래 템플릿은 충청일보에서만 확인됨. 다른 신문사에 쓸 때는 --check 로 먼저 점검할 것.
TEMPLATE_ARTICLEVIEW = dict(
    article_date_sel="ul.infomation",                 # '기자명 ... 입력 2026.09.18 16:45 댓글 0'
    article_body_sel="#article-view-content-div",
    link_contains="articleView",
    meta_hints=("article:section", "article:section1"),   # 예: 충남 / 서산
)


# ============================ 공통 설정 ============================
@dataclass
class Settings:
    save_directory: str
    keywords: List[str]
    blacklist_keywords: Tuple[str, ...] = ("행사", "사설")
    exclude_title_keywords: Tuple[str, ...] = ("[포토뉴스]", "[동정]", "[의정소식]")
    search_period_days: int = 20       # 최근 N일 이내 기사만 수집
    max_old_in_a_row: int = 3          # 기간보다 오래된 기사가 연속 N건이면 다음 키워드로
    max_pages_per_keyword: int = 30    # 안전장치
    headless: bool = False             # True면 브라우저 창 없이 실행 (Selenium 사용 시)
    workers: int = 8                   # requests 방식 신문사를 동시에 수집할 개수 (1이면 순차)
    min_score: int = 0                 # 0이면 relevance.MIN_SCORE 사용
    today: Optional[datetime] = None   # 테스트용 (None이면 현재 시각)
    max_stale_pages: int = 3           # 최신순이 아닌 신문사: 최근 기사가 한 건도 없는 페이지가 연속 N쪽이면 키워드 종료
    max_pages_unsorted_no_list: int = 5   # 위와 같되 목록에서 날짜를 못 읽는 신문사(기사를 열어 봐야 날짜를 앎)
    max_pages_unsorted: int = 8        # 최신순이 아닌 신문사의 키워드당 최대 페이지 (기사를 열어 봐야 날짜를 아는 곳이 많아 비용이 크다)
    time_budget_min: float = 0.0       # 0이 아니면 이 시간(분)이 지나면 수집을 멈추고 지금까지의 결과로 마무리한다.
                                       # (GitHub Actions 작업 제한시간에 걸려 취소되면 PNU 단계가 못 돌아 결과가 통째로 사라진다)


CSV_COLUMNS = ["신문사", "검색어", "제목", "링크", "날짜", "날짜기준", "지번포함여부", "지역힌트", "주소추출", "보상점수", "보상키워드", "본문"]


# ============================ HTML 해석 (순수 함수) ============================
def clean_popup_elements(soup: BeautifulSoup):
    """Remove popup / layer ad overlays so they do not contaminate search results or dates."""
    for p in soup.select('div[id*="popup"], div[class*="popup"], div[id*="pop"], div[id*="layer"], div[class*="modal"], div.banner-zone__popup, #hd_pop, .layer-popups'):
        # Keep forms (some sites nest the search input inside a header layer)
        if not p.select_one('form') and not p.select_one('input[name*="search"], input[name="q"], input[name="stx"]'):
            p.decompose()


def parse_list(html: str, page_url: str, site: Site) -> List[dict]:
    """검색 결과 HTML → [{'title','link','list_date'}]"""
    soup = BeautifulSoup(html or "", "html.parser")
    clean_popup_elements(soup)
    items = []
    for block in soup.select(site.list_item_sel):
        # 같은 기사로 가는 링크가 여러 개일 수 있다(썸네일 이미지 링크 + 제목 링크). 이미지만 있는 링크가 먼저 잡히면 제목이
        # 통째로 비므로(남도일보·전남일보는 목록 20건 전부), 글자가 있는 링크를 우선하고 없으면 이미지 alt 를 쓴다.
        anchors = [x for x in block.select(site.list_title_sel) if x.get("href")]
        if not anchors:
            continue
        a = next((x for x in anchors if x.get_text(strip=True)), anchors[0])
        link = urljoin(page_url, a["href"].strip())
        if site.link_contains and site.link_contains not in link:
            continue
        title_text = a.get_text()
        if site.list_title_text_sel:
            te = block.select_one(site.list_title_text_sel)
            if te is not None and te.get_text(strip=True):
                title_text = te.get_text()
        if not title_text.strip():
            img = a.find("img")
            title_text = (img.get("alt") or "") if img is not None else ""
        date_el = block.select_one(site.list_date_sel) if site.list_date_sel else None
        items.append({
            "title": " ".join(html_lib.unescape(title_text).split()),      # 사이트가 &amp;apos; 처럼 두 번 이스케이프한 제목 대응
            "link": link,
            "list_date": date_el.get_text(" ", strip=True) if date_el is not None else "",
        })
    return items


def element_text(el) -> str:
    """요소의 텍스트. <br>/문단 경계는 줄바꿈으로, 인라인 태그는 그대로 이어 붙인다."""
    for t in el.find_all(["script", "style"]):
        t.decompose()
    for br in el.find_all("br"):
        br.replace_with("\n")
    for blk in el.find_all(["p", "div", "li", "tr", "h1", "h2", "h3", "h4"]):
        blk.append("\n")
    text = el.get_text()
    text = re.sub(r"[ \t 　]+", " ", text)
    text = re.sub(r"[ ]*\n[ \n]*", "\n", text)
    return text.strip()


def _meta_content(soup: BeautifulSoup, name: str) -> str:
    tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
    return (tag.get("content") or "").strip() if tag else ""


_META_PUBLISHED = ("article:published_time", "og:pubdate", "pubdate", "regDate", "author:pubdate")
_META_MODIFIED = ("article:modified_time", "og:updated_time", "lastmod")


def _meta_dates(soup: BeautifulSoup, html: str) -> Tuple[Optional[str], Optional[str]]:
    """메타 태그 / JSON-LD 에 들어 있는 (발행일, 수정일). 사람이 읽는 화면 요소보다 믿을 만하다."""
    ins = mod = None
    for name in _META_PUBLISHED:
        v = _meta_content(soup, name)
        if v:
            ins = parse_article_dates(v)[0]
            if ins:
                break
    for name in _META_MODIFIED:
        v = _meta_content(soup, name)
        if v:
            mod = parse_article_dates(v)[0]
            if mod:
                break
    if not ins:
        m = re.search(r'"datePublished"\s*:\s*"(\d{4})-(\d{2})-(\d{2})', html or "")
        if m:
            ins = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    if not mod:
        m = re.search(r'"dateModified"\s*:\s*"(\d{4})-(\d{2})-(\d{2})', html or "")
        if m:
            mod = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return ins, mod


def parse_article(html: str, site: Site) -> dict:
    """기사 HTML → {'input_date','modified_date','body','area','date_source','date_conflict'}

    기사 날짜를 믿는 순서
      1. 선택자가 잡은 요소에 '입력/등록/승인…' 라벨이 붙은 날짜가 있으면 그것 (사람이 읽는 화면의 명시적 표기)
      2. 메타 태그(article:published_time 등)·JSON-LD 의 발행일
      3. 라벨 없이 선택자가 잡은 첫 날짜 (최후 수단)
    선택자를 'td, span, div'처럼 넓게 잡은 신문사는 문서에서 처음 나온 요소(사이트 머리말의 '오늘 날짜' 시계 등)를
    잡기 쉽다. 이때 라벨 없는 날짜를 그대로 쓰면 2019년 기사도 '오늘 입력'으로 읽혀 최근 기사로 수집되므로,
    라벨이 없으면 메타 태그를 우선한다."""
    soup = BeautifulSoup(html or "", "html.parser")
    clean_popup_elements(soup)
    date_el = soup.select_one(site.article_date_sel)
    input_date, modified_date, labeled = date_from_element(date_el)
    meta_in, meta_mod = _meta_dates(soup, html)

    date_source = "선택자(라벨)" if (input_date and labeled) else ""
    date_conflict = ""
    if not (input_date and labeled) and meta_in:
        if input_date and input_date != meta_in:
            date_conflict = f"선택자 날짜 {input_date} ≠ 메타 날짜 {meta_in}"
        input_date, modified_date = meta_in, (meta_mod or modified_date)
        date_source = "메타"
    elif input_date and not labeled:
        date_source = "선택자(라벨 없음)"
    if input_date and not modified_date and meta_mod and meta_mod != input_date and date_source != "메타":
        modified_date = meta_mod

    body_el = soup.select_one(site.article_body_sel)
    body = element_text(body_el) if body_el is not None else ""

    # 폴백: 본문이 비어있거나 너무 짧으면 meta og:description / twitter:description 사용
    if len(body.strip()) < 30:
        meta_desc = (_meta_content(soup, "og:description") or
                     _meta_content(soup, "twitter:description") or
                     _meta_content(soup, "description"))
        if meta_desc and len(meta_desc.strip()) > len(body.strip()):
            body = meta_desc.strip()

    if not body.strip():
        body = "(본문 추출 실패)"

    parts: List[str] = [site.default_area] if site.default_area else []
    for name in site.meta_hints:
        v = _meta_content(soup, name)
        if v and v not in parts:
            parts.append(v)
    title = _meta_content(soup, "og:title") or _meta_content(soup, "twitter:title")
    if not title:
        h = soup.find(["h1", "h2"])
        title = h.get_text(" ", strip=True) if h is not None else (soup.title.get_text(" ", strip=True) if soup.title else "")
    return {"input_date": input_date, "modified_date": modified_date, "title": " ".join(html_lib.unescape(title).split()),
            "body": body, "area": " ".join(parts), "has_date_el": date_el is not None,
            "has_body_el": (body != "(본문 추출 실패)"),
            "date_source": date_source, "date_conflict": date_conflict}


# ============================ 페이지 가져오기 ============================
from common.relevance import is_compensation_related  # noqa: E402


class FetchError(Exception):
    pass


class SeleniumFetcher:
    def __init__(self, headless: bool):
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        options = webdriver.ChromeOptions()
        # Block browser-level pop-up windows and permission prompts. This does not
        # hide in-page dialogs or remove legitimate content from the article DOM.
        options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.popups": 2,
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_setting_values.geolocation": 2,
        })
        options.add_argument("--disable-notifications")
        options.set_capability("unhandledPromptBehavior", "dismiss")
        on_linux = sys.platform.startswith("linux")
        # 리눅스에서 화면(DISPLAY)이 없으면(서버, 깃 자동 실행 등) 자동으로 headless
        if headless or (on_linux and not os.environ.get("DISPLAY")):
            options.add_argument("--headless=new")
        if on_linux:   # 컨테이너/CI 환경에서 크롬이 뜨도록
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
        except ImportError:   # webdriver-manager 가 없으면 selenium 4.6+ 내장 Selenium Manager 사용
            service = None
        self.driver = (webdriver.Chrome(service=service, options=options) if service
                       else webdriver.Chrome(options=options))
        self.driver.set_page_load_timeout(40)
        self._primary_handle = self.driver.current_window_handle

    def _close_unexpected_windows(self):
        """Close auxiliary tabs/windows opened by site ads, preserving the crawl tab."""
        handles = list(self.driver.window_handles)
        if self._primary_handle not in handles and handles:
            # A site may replace the initial tab. Keep the first remaining tab as
            # the working tab instead of closing every live window.
            self._primary_handle = handles[0]
        for handle in handles:
            if handle == self._primary_handle:
                continue
            try:
                self.driver.switch_to.window(handle)
                self.driver.close()
            except Exception:
                # A popup can close itself while handles are being enumerated.
                continue
        if self._primary_handle in self.driver.window_handles:
            self.driver.switch_to.window(self._primary_handle)

    def _dismiss_layer_popups(self):
        """Dismiss JavaScript alerts and remove in-page layer popups / modals that block crawling."""
        # 1. Dismiss any JavaScript alert/confirm/prompt
        try:
            from selenium.common.exceptions import NoAlertPresentException
            self.driver.switch_to.alert.dismiss()
        except Exception:
            pass

        # 2. Click close buttons and hide layer popups via injected script
        js_dismiss = """
        (function() {
            // Click common popup close buttons
            const closeSelectors = [
                '.popup-close', '.layer-popup-close', '.pop_close', '.btn_close',
                '.close', 'button.close', 'a.close', 'a[onclick*="close"]',
                'a[onclick*="hide"]', 'button[onclick*="close"]', 'button[onclick*="hide"]',
                'input[value*="닫기"]', 'input[value*="하루"]', 'input[value*="오늘"]',
                'a[href*="close"]', 'a[href*="javascript:close"]', '.btn-layer-close',
                '#close_layer', '.modal-close'
            ];
            for (const sel of closeSelectors) {
                try {
                    document.querySelectorAll(sel).forEach(el => {
                        if (el && el.offsetParent !== null) { el.click(); }
                    });
                } catch (e) {}
            }

            // Hide lingering popup layers
            const popupLayerSelectors = [
                'div[id*="popup"]', 'div[class*="popup"]', 'div[id*="pop"]',
                'div[id*="layer"]', 'div[class*="layer"]', 'div[class*="modal"]',
                'div.banner-zone__popup', '#hd_pop', '.layer-popups'
            ];
            for (const psel of popupLayerSelectors) {
                try {
                    document.querySelectorAll(psel).forEach(pel => {
                        if (pel.id === 'search' || pel.classList.contains('search_wrap') || pel.querySelector('form')) return;
                        if (pel.offsetWidth > 0 && pel.offsetHeight > 0 && pel.offsetHeight < window.innerHeight * 0.95) {
                            pel.style.display = 'none';
                            pel.style.visibility = 'hidden';
                        }
                    });
                } catch (e) {}
            }
        })();
        """
        try:
            self.driver.execute_script(js_dismiss)
        except Exception:
            pass

    def get(self, url: str, wait_selector: Optional[str] = None, timeout: int = 10,
            strict: bool = False, encoding: str = "") -> str:
        from selenium.common.exceptions import TimeoutException, WebDriverException
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait
        try:
            self._close_unexpected_windows()
            self.driver.get(url)
            self._close_unexpected_windows()
            self._dismiss_layer_popups()
            if wait_selector:
                try:
                    WebDriverWait(self.driver, timeout).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector)))
                except TimeoutException:
                    if strict:
                        raise FetchError(f"요소 대기 시간 초과: {wait_selector}")
                self._close_unexpected_windows()
                self._dismiss_layer_popups()
            return self.driver.page_source
        except WebDriverException as e:
            try:
                from selenium.common.exceptions import NoAlertPresentException
                self.driver.switch_to.alert.dismiss()
            except NoAlertPresentException:
                pass
            except Exception:
                pass
            raise FetchError(e.__class__.__name__) from e

    def close(self):
        try:
            self.driver.quit()
        except Exception:
            pass


class RequestsFetcher:
    UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

    def __init__(self):
        import requests
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.UA, "Accept-Language": "ko-KR,ko;q=0.9"})

    def get(self, url: str, wait_selector: Optional[str] = None, timeout: int = 15,
            strict: bool = False, encoding: str = "") -> str:
        import requests
        try:
            r = self.session.get(url, timeout=max(timeout, 15))
        except requests.RequestException as e:
            raise FetchError(e.__class__.__name__) from e
        if r.status_code >= 400:
            raise FetchError(f"HTTP {r.status_code}")
        if encoding:
            r.encoding = encoding
        elif not r.encoding or r.encoding.lower() == "iso-8859-1":
            r.encoding = r.apparent_encoding
        return r.text

    def get_raw(self, url: str, headers: Optional[dict] = None, timeout: int = 15) -> bytes:
        """GET 후 응답 본문을 바이트 그대로 돌려준다 (JSON API 용)."""
        import requests
        try:
            r = self.session.get(url, headers=headers or {}, timeout=max(timeout, 15))
        except requests.RequestException as e:
            raise FetchError(e.__class__.__name__) from e
        if r.status_code >= 400:
            raise FetchError(f"HTTP {r.status_code}")
        return r.content

    def post_raw(self, url: str, data: dict, headers: Optional[dict] = None, timeout: int = 15) -> bytes:
        """POST 후 응답 본문을 바이트 그대로 돌려준다 (JSON API 처럼 응답 헤더의 문자셋이 틀린 경우 직접 해독하려고)."""
        import requests
        try:
            r = self.session.post(url, data=data, headers=headers or {}, timeout=max(timeout, 15))
        except requests.RequestException as e:
            raise FetchError(e.__class__.__name__) from e
        if r.status_code >= 400:
            raise FetchError(f"HTTP {r.status_code}")
        return r.content

    def post(self, url: str, data: dict, timeout: int = 15, encoding: str = "") -> str:
        import requests
        try:
            r = self.session.post(url, data=data, timeout=max(timeout, 15))
        except requests.RequestException as e:
            raise FetchError(e.__class__.__name__) from e
        if r.status_code >= 400:
            raise FetchError(f"HTTP {r.status_code}")
        if encoding:
            r.encoding = encoding
        elif not r.encoding or r.encoding.lower() == "iso-8859-1":
            r.encoding = r.apparent_encoding
        return r.text

    def close(self):
        self.session.close()


# ============================ 수집 ============================
@dataclass
class SiteStats:
    name: str
    keywords_total: int = 0
    keywords_with_results: int = 0
    pages: int = 0
    opened: int = 0
    saved: int = 0
    blacklist_skipped: int = 0
    irrelevant_skipped: int = 0
    errors: int = 0
    failed: str = ""
    seconds: float = 0.0          # 이 신문사에 쓴 시간(초). 구글시트 수집로그용
    timed_out: bool = False       # 시간 예산을 다 써서 일부 키워드/페이지를 못 돌았다


class Crawler:
    def __init__(self, settings: Settings,
                 fetcher_factory: Optional[Callable[[str], object]] = None,
                 sleep: Callable[[float], None] = time.sleep):
        self.st = settings
        self._factory = fetcher_factory or self._default_factory
        self._sleep = sleep
        self._fetchers: Dict[str, object] = {}
        self._tls = threading.local()          # 병렬 수집 시 스레드마다 별도 fetcher
        self._all_fetchers: List[object] = []
        self._lock = threading.Lock()
        self._now = time.time                  # 테스트에서 가짜 시계를 넣을 수 있다
        self.deadline: Optional[float] = (self._now() + settings.time_budget_min * 60) if settings.time_budget_min else None

    def expired(self) -> bool:
        """시간 예산을 다 썼는가."""
        return self.deadline is not None and self._now() >= self.deadline

    def _default_factory(self, kind: str):
        if kind == "selenium":
            return SeleniumFetcher(self.st.headless)
        if kind == "requests":
            return RequestsFetcher()
        raise ValueError(f"알 수 없는 fetch 방식: {kind}")

    def fetcher(self, kind: str):
        """fetcher 는 스레드별로 하나씩 만든다(requests.Session 을 스레드 간에 공유하지 않기 위해)."""
        cache = getattr(self._tls, "cache", None)
        if cache is None:
            cache = self._tls.cache = {}
        if kind not in cache:
            cache[kind] = self._factory(kind)
            with self._lock:
                self._all_fetchers.append(cache[kind])
        return cache[kind]

    def fetch_search_page(self, site: Site, keyword: str, page: int, fetcher=None,
                          timeout: int = 10, strict: bool = False):
        """Fetch a configured GET search URL or submit a site's verified POST form."""
        f = fetcher or self.fetcher(site.fetch)
        if site.search_adapter:
            return SEARCH_ADAPTERS[site.search_adapter](site, keyword, page, f)
        if site.search_builder:
            url = SEARCH_BUILDERS[site.search_builder](site, keyword, page)
            return url, f.get(url, wait_selector=site.list_item_sel, timeout=timeout, strict=strict, encoding=site.encoding)
        kw_enc = quote(keyword.encode(site.encoding)) if site.encoding else quote(keyword)
        url = site.search_url.format(kw=kw_enc, page=page)
        method = site.search_method.upper()
        if method == "GET":
            html = f.get(url, wait_selector=site.list_item_sel, timeout=timeout,
                         strict=strict, encoding=site.encoding)
            return url, html
        if method != "POST" or not hasattr(f, "post"):
            raise FetchError(f"지원하지 않는 검색 방식: {method}/{site.fetch}")
        values = {"kw": keyword, "page": page, "page_index": max(0, page - 1)}
        if site.encoding:
            payload = {key: value.format(**values).encode(site.encoding)
                       for key, value in site.search_form_data}
        else:
            payload = {key: value.format(**values) for key, value in site.search_form_data}
        return url, f.post(url, data=payload, timeout=timeout, encoding=site.encoding)

    def close(self):
        with self._lock:
            fetchers, self._all_fetchers = self._all_fetchers, []
        for f in fetchers:
            try:
                f.close()
            except Exception:
                pass

    def pause(self, rng: Tuple[float, float], site: Optional["Site"] = None):
        # requests 방식은 신문사별로 병렬이라 한 서버에는 여전히 순차 요청이다. 대기를 1/4로 줄여 속도를 올린다.
        scale = 0.25 if (site is not None and site.fetch == "requests") else 1.0
        self._sleep(random.uniform(*rng) * scale)

    # ------------------------------ 지역 단위 실행 ------------------------------
    def run_region(self, region_name: str, sites: List[Site], only: Optional[List[str]] = None) -> str:
        """지역(도) 1곳의 신문사들을 차례로 수집해 지역 CSV 1개에 저장. CSV 경로 반환."""
        if only:
            sites = [s for s in sites if s.name in only]
        run = RegionRun(self, region_name)
        print(f"[{region_name}] 수집 기간: {run.start_date:%Y-%m-%d} 이후 | 신문사 {len(sites)}곳 | "
              f"키워드 {len(self.st.keywords)}개 | 저장: {run.csv_path}")
        disabled = [site for site in sites if not site.enabled]
        for site in disabled:
            print(f"  [DISABLED] {site.name}: {site.disabled_reason or 'Live validation required'}")
        sites = [site for site in sites if site.enabled]
        # requests 방식 신문사는 서로 다른 서버이므로 병렬로, 브라우저(Selenium)는 한 대뿐이라 순차로.
        fast = [s for s in sites if s.fetch == "requests"]
        slow = [s for s in sites if s.fetch != "requests"]
        workers = max(1, self.st.workers)
        if workers > 1 and len(fast) > 1:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(run.collect_site, s) for s in fast]
                for fu in futures:
                    try:
                        fu.result()
                    except Exception as e:      # 한 신문사 실패가 전체를 멈추지 않게
                        print(f"  [병렬 오류] {e.__class__.__name__}: {e}")
        else:
            slow = fast + slow
        for site in slow:
            run.collect_site(site)
        run.print_summary()
        self.last_run = run          # 호출한 쪽이 신문사별 통계(run.stats)를 읽을 수 있게
        return run.csv_path

    # ------------------------------ 점검 ------------------------------
    def check_site(self, site: Site, keyword: str) -> bool:
        """저장 없이 검색 1페이지 + 첫 기사 1건을 읽어 선택자가 맞는지 확인."""
        print(f"\n=== 점검: {site.name} (fetch={site.fetch}, 검색어 '{keyword}') ===")
        if not site.enabled:
            print(f"  [DISABLED] {site.disabled_reason or 'Live validation required'}")
            return False
        f = self.fetcher(site.fetch)
        try:
            url, html = self.fetch_search_page(site, keyword, 1, f, timeout=10, strict=False)
        except FetchError as e:
            print(f"  ✘ 검색 페이지를 못 가져옴: {e}")
            return False
        items = parse_list(html, url, site)
        if not items:
            print(f"  ✘ 목록 0건: list_item_sel/list_title_sel/link_contains/검색 URL을 확인하세요 (HTML {len(html)}자)")
            return False
        print(f"  ✔ 목록 {len(items)}건")
        for it in items[:3]:
            print(f"     - {it['title'][:35]} | 목록날짜 {parse_list_date(it['list_date'])} | {it['link'][:70]}")
        if not any(parse_list_date(it["list_date"]) for it in items):
            # Some sites expose dates only on article pages. The crawler already
            # falls back to article dates when a list has no date field.
            print("  · 목록 날짜 없음: 기사 페이지 날짜를 확인합니다")

        try:
            ahtml = f.get(items[0]["link"], wait_selector=site.article_date_sel, timeout=15,
                          strict=True, encoding=site.encoding)
        except FetchError as e:
            print(f"  ✘ 기사 페이지를 못 가져옴: {e}")
            return False
        art = parse_article(ahtml, site)
        ok = True
        ref, kind = pick_reference_date(art["input_date"], art["modified_date"], site.date_basis)
        print(f"  {'✔' if ref else '✘'} 기사 날짜: 입력 {art['input_date']} / 수정 {art['modified_date']} → 기준 {ref}({kind}) [출처: {art['date_source'] or '없음'}]")
        if art["date_conflict"]:
            print(f"  ⚠ {art['date_conflict']} → article_date_sel 이 기사 날짜가 아닌 요소(머리말 시계 등)를 잡고 있다. 메타 날짜를 대신 사용했지만 선택자를 좁히는 것이 좋다.")
        elif art["date_source"] == "선택자(라벨 없음)":
            print("  ⚠ 날짜에 '입력/등록' 라벨이 없고 메타 태그도 없어 올바른 날짜인지 확인할 수 없다 → 기사 화면과 직접 대조해 볼 것.")
        ok &= bool(ref)
        body_ok = art["has_body_el"] and len(art["body"]) > 50
        print(f"  {'✔' if body_ok else '✘'} 본문 {len(art['body'])}자: {art['body'][:50]!r}")
        ok &= body_ok
        print(f"  · 지역힌트: {art['area'] or '(없음)'}")
        print(f"  · 첫 기사 주소 추출: {extract_addresses(art['body']) or '(없음 - 정상일 수 있음)'}")
        return ok


class RegionRun:
    """지역 1곳의 실행 상태(CSV 경로, 이미 확인한 기사 목록, 신문사별 통계)."""

    def __init__(self, crawler: Crawler, region_name: str):
        self.c = crawler
        st = crawler.st
        now = st.today or datetime.now()
        self.start_date = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=st.search_period_days)
        os.makedirs(st.save_directory, exist_ok=True)
        self.csv_path = os.path.join(st.save_directory, f"{region_name}_{now:%Y-%m-%d}.csv")
        self.seen_path = os.path.splitext(self.csv_path)[0] + ".seen.tsv"
        self.lock = threading.Lock()
        self.seen: Dict[str, Tuple[str, str]] = self._load_seen()
        self.stats: Dict[str, SiteStats] = {}

    def _load_seen(self) -> Dict[str, Tuple[str, str]]:
        """CSV가 없으면 헤더 생성. 있으면 이미 확인한 기사 목록을 읽어 이어하기를 지원.
        (주소가 없어 CSV에 저장하지 않은 기사도 .seen.tsv에 기억해 재실행 시 다시 열지 않는다)"""
        seen: Dict[str, Tuple[str, str]] = {}
        if not os.path.exists(self.csv_path):
            pd.DataFrame(columns=CSV_COLUMNS).to_csv(self.csv_path, index=False, encoding="utf-8-sig")
        else:
            df = pd.read_csv(self.csv_path, encoding="utf-8-sig", dtype=str).fillna("")
            if list(df.columns) != CSV_COLUMNS:      # 예전 형식(점수 컬럼 없음) 파일은 새 형식으로 맞춘다
                df = df.reindex(columns=CSV_COLUMNS, fill_value="")
                df.to_csv(self.csv_path, index=False, encoding="utf-8-sig")
            for _, row in df.iterrows():
                if row.get("링크"):
                    seen[row["링크"]] = (row["날짜"], row["날짜기준"])
        if os.path.exists(self.seen_path):
            with open(self.seen_path, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.rstrip("\n").split("\t")
                    if len(parts) == 3:
                        seen[parts[0]] = (parts[1], parts[2])
        return seen

    def _remember(self, link: str, ref_date: str, kind: str):
        with self.lock:
            self.seen[link] = (ref_date, kind)
            with open(self.seen_path, "a", encoding="utf-8") as f:
                f.write(f"{link}\t{ref_date}\t{kind}\n")

    def _append_row(self, row):
        with self.lock:
            row.to_csv(self.csv_path, mode="a", header=False, index=False, encoding="utf-8-sig")

    # ------------------------------ 신문사 / 키워드 ------------------------------
    def collect_site(self, site: Site):
        st = self.c.st
        stats = self.stats.setdefault(site.name, SiteStats(site.name))
        print(f"\n########## {site.name} ##########")
        t0 = time.time()
        try:
            self._collect_site_keywords(site, stats)
        finally:
            stats.seconds += time.time() - t0

    def _collect_site_keywords(self, site: Site, stats: SiteStats):
        st = self.c.st
        for idx, keyword in enumerate(st.keywords, start=1):
            if self.c.expired():
                stats.timed_out = True
                print(f"\n[{site.name}] 시간 예산({st.time_budget_min:g}분)을 다 써서 남은 키워드는 건너뜁니다")
                return
            print(f"\n[{site.name}] ({idx}/{len(st.keywords)}) 검색어 '{keyword}' 검색 중...")
            try:
                self.collect_keyword(site, keyword, stats)
            except Exception as e:   # 한 키워드/신문사의 실패가 전체를 멈추지 않게
                stats.errors += 1
                stats.failed = f"{e.__class__.__name__}: {e}"
                print(f"  → 검색 실패: {stats.failed}")

    def collect_keyword(self, site: Site, keyword: str, stats: SiteStats):
        """키워드 1개 수집. 기간 밖 기사가 max_old_in_a_row건 연속이면 종료."""
        st = self.c.st
        fetcher = self.c.fetcher(site.fetch)
        # 최신순이 아니면 끝까지 훑을 수밖에 없다. 목록 날짜를 읽을 수 있으면 오래된 기사를 열지 않고 건너뛰어 싸므로 상한을 넉넉히,
        # 못 읽으면 기사를 열어 봐야 날짜를 알아 비용이 크므로 상한을 줄인다.
        unsorted_cap = st.max_pages_unsorted if site.list_date_sel else min(st.max_pages_unsorted, st.max_pages_unsorted_no_list)
        max_pages = site.max_pages or (st.max_pages_per_keyword if site.newest_first
                                       else min(st.max_pages_per_keyword, unsorted_cap))
        stop_on_old = site.newest_first
        stale_pages = 0
        old_in_a_row = 0
        prev_links = None
        stats.keywords_total += 1

        for page in range(1, max_pages + 1):
            if self.c.expired():
                stats.timed_out = True
                return
            url, html = self.c.fetch_search_page(site, keyword, page, fetcher,
                                                 timeout=10, strict=False)
            items = parse_list(html, url, site)
            if not items:
                print(f"  → {page}페이지: 결과 없음, 종료")
                return
            if page == 1:
                stats.keywords_with_results += 1
            stats.pages += 1

            links = [it["link"] for it in items]
            if links == prev_links:   # 마지막 페이지 이후 같은 페이지가 반복되는 경우 방지
                return
            prev_links = links

            recent_on_page = False
            for item in items:
                if self.c.expired():
                    stats.timed_out = True
                    return
                link, title = item["link"], item["title"]
                list_date = parse_list_date(item["list_date"])

                # 제목만 보고도 지번이 나올 가능성이 없는 기사는 본문을 열지 않고 건너뛴다
                if any(kw in title for kw in st.exclude_title_keywords):
                    continue

                # 블랙리스트 키워드 제목 검사 (행사, 사설 등 - 본문을 열지 않고 즉시 제외)
                matched_bl_title = [bkw for bkw in st.blacklist_keywords if bkw in title]
                if matched_bl_title:
                    self._remember(link, list_date or datetime.now().strftime("%Y-%m-%d"), "블랙리스트(제목)")
                    stats.blacklist_skipped += 1
                    print(f"  → 블랙리스트 제외(제목 '{matched_bl_title[0]}'): {title[:35]}")
                    continue

                # 이미 확인한 기사 (다른 키워드/이전 실행에서 처리됨)
                if link in self.seen:
                    ref_date, _ = self.seen[link]
                    if is_recent(ref_date, self.start_date):
                        old_in_a_row = 0
                        recent_on_page = True
                    else:
                        old_in_a_row += 1
                        if stop_on_old and old_in_a_row >= st.max_old_in_a_row:
                            print(f"  → 오래된 기사 {st.max_old_in_a_row}건 연속, 다음 키워드로")
                            return
                    continue

                # 목록 날짜가 기간보다 한참 오래되면 본문을 열지 않고 '오래된 기사'로 처리
                list_date = parse_list_date(item["list_date"])
                if (site.list_skip_margin_days is not None and list_date and
                        not is_recent(list_date, self.start_date - timedelta(days=site.list_skip_margin_days))):
                    self._remember(link, list_date, "목록")
                    old_in_a_row += 1
                    print(f"  → 기간 밖(목록 {list_date}) {title[:30]} ({old_in_a_row}/{st.max_old_in_a_row})")
                    if stop_on_old and old_in_a_row >= st.max_old_in_a_row:
                        print(f"  → 오래된 기사 {st.max_old_in_a_row}건 연속, 다음 키워드로")
                        return
                    continue

                try:
                    ahtml = fetcher.get(link, wait_selector=site.article_date_sel, timeout=15,
                                        strict=True, encoding=site.encoding)
                except FetchError as e:
                    stats.errors += 1
                    print(f"  → 기사 열기 오류({title[:20]}...): {e}")
                    self.c.pause(site.delay_article, site)
                    continue
                self.c.pause(site.delay_article, site)
                stats.opened += 1

                art = parse_article(ahtml, site)
                if not title.strip() and art.get("title"):
                    title = art["title"]                        # 목록에서 제목을 못 읽은 기사: 기사 페이지의 제목을 쓴다
                    if any(kw in title for kw in st.exclude_title_keywords):
                        self._remember(link, list_date or datetime.now().strftime("%Y-%m-%d"), "제외(제목)")
                        continue
                    bl = [b for b in st.blacklist_keywords if b in title]
                    if bl:
                        self._remember(link, list_date or datetime.now().strftime("%Y-%m-%d"), "블랙리스트(제목)")
                        stats.blacklist_skipped += 1
                        print(f"  → 블랙리스트 제외(제목 '{bl[0]}'): {title[:35]}")
                        continue
                ref_date, ref_kind = pick_reference_date(art["input_date"], art["modified_date"], site.date_basis)
                if not ref_date:   # 기사 페이지에서 못 읽으면 목록 날짜로 대체
                    ref_date, ref_kind = list_date, "목록"
                if not ref_date:
                    print(f"  → 날짜 확인 불가, 건너뜀: {title[:30]}")
                    continue

                self._remember(link, ref_date, ref_kind)

                # 블랙리스트 키워드 본문 검사 (행사, 사설 등 - 지번 추출 전 필터링)
                full_text = f"{title}\n{art['body']}"
                matched_bl_body = [bkw for bkw in st.blacklist_keywords if bkw in full_text]
                if matched_bl_body:
                    stats.blacklist_skipped += 1
                    print(f"  → 블랙리스트 제외(본문 '{matched_bl_body[0]}') [{ref_kind} {ref_date}] {title[:35]}")
                    continue

                if is_recent(ref_date, self.start_date):
                    old_in_a_row = 0
                    recent_on_page = True
                    addresses = extract_addresses(full_text)
                    if addresses:
                        related, score, hit_words = is_compensation_related(title, art["body"])
                        if st.min_score:
                            related = score >= st.min_score and bool(hit_words)
                        if not related:
                            stats.irrelevant_skipped += 1
                            print(f"  → 보상 무관({score}점), 건너뜀 [{ref_kind} {ref_date}] {title[:40]}")
                            continue
                        row = pd.DataFrame([{
                            "신문사": site.name, "검색어": keyword, "제목": title, "링크": link,
                            "날짜": ref_date, "날짜기준": ref_kind, "지번포함여부": "Y",
                            "지역힌트": art["area"], "주소추출": "; ".join(addresses),
                            "보상점수": score, "보상키워드": hit_words, "본문": art["body"],
                        }], columns=CSV_COLUMNS)
                        self._append_row(row)
                        stats.saved += 1
                        print(f"  → 저장 [{ref_kind} {ref_date}] {score}점 주소:{'; '.join(addresses)} {title}")
                    else:
                        print(f"  → 지번 없음, 건너뜀 [{ref_kind} {ref_date}] {title[:40]}")
                else:
                    old_in_a_row += 1
                    print(f"  → 기간 밖 [{ref_kind} {ref_date}] {title[:30]} ({old_in_a_row}/{st.max_old_in_a_row})")
                    if stop_on_old and old_in_a_row >= st.max_old_in_a_row:
                        print(f"  → 오래된 기사 {st.max_old_in_a_row}건 연속, 다음 키워드로")
                        return

            if not site.newest_first:
                stale_pages = 0 if recent_on_page else stale_pages + 1
                if stale_pages >= st.max_stale_pages:
                    print(f"  → 최근 기사가 없는 페이지 {stale_pages}쪽 연속, 다음 키워드로")
                    return

            self.c.pause(site.delay_page, site)

    # ------------------------------ 요약 ------------------------------
    def print_summary(self):
        print("\n" + "=" * 60)
        print("수집 요약")
        for s in self.stats.values():
            line = (f"  {s.name}: 저장 {s.saved}건 | 블랙리스트 제외 {s.blacklist_skipped}건 | 보상 무관 {s.irrelevant_skipped}건 | 기사 열람 {s.opened}건 | 검색 {s.pages}페이지 | "
                    f"결과 있는 키워드 {s.keywords_with_results}/{s.keywords_total} | 오류 {s.errors}")
            print(line)
            if s.keywords_total and s.keywords_with_results == 0:
                print(f"    ⚠ {s.name}: 모든 키워드에서 검색 결과가 0건 → 검색 URL/선택자 점검 필요 (--check)")
            if s.failed:
                print(f"    ⚠ 마지막 오류: {s.failed}")
            if s.timed_out:
                print(f"    ⚠ {s.name}: 시간 예산을 다 써서 일부만 수집했습니다 (이미 확인한 기사는 .seen.tsv 에 남아, 같은 폴더에서 다시 실행하면 이어서 수집)")
        print(f"\n✅ 저장 완료: {self.csv_path}")
