# -*- coding: utf-8 -*-
"""
common/pnu_resolver.py - 기사 내 주소 완성, 19자리 PNU 발급(Kakao/VWorld), SQLite 저장 파이프라인

기능:
1. 불완전 주소('지정면 신평리 400' 등)를 지역힌트/신문사/본문 힌트를 조합하여 온전한 한국식 표준 주소로 복원
2. Kakao Local API 및 VWorld Geocoder API를 호출하여 19자리 토지 고유번호(PNU) 및 좌표 획득
3. 중복 API 호출 방지를 위한 SQLite 기반 캐싱 및 영구 저장소(articles, article_addresses) 관리
"""

import hashlib
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import requests

# API 엔드포인트 및 인증 키 (퍼블릭 리포이므로 키는 환경변수 / GitHub Secrets 로만 받는다)
KAKAO_URL = "https://dapi.kakao.com/v2/local/search/address.json"
KAKAO_KEY = os.environ.get("KAKAO_REST_API_KEY", "")
KAKAO_HEADERS = {"Authorization": f"KakaoAK {KAKAO_KEY}"}

VWORLD_URL = "http://api.vworld.kr/req/address"
VWORLD_KEY = os.environ.get("VWORLD_API_KEY", "")

if not KAKAO_KEY or not VWORLD_KEY:
    print("[경고] KAKAO_REST_API_KEY / VWORLD_API_KEY 환경변수가 없습니다. PNU 발급이 실패할 수 있습니다.")

# 광역시·도 표준 명칭 매핑
PROVINCE_STANDARDIZATION = {
    "강원": "강원특별자치도",
    "강원도": "강원특별자치도",
    "경기": "경기도",
    "경기도": "경기도",
    "경남": "경상남도",
    "경상남도": "경상남도",
    "경북": "경상북도",
    "경상북도": "경상북도",
    "전남": "전라남도",
    "전라남도": "전라남도",
    "전북": "전북특별자치도",
    "전라북도": "전북특별자치도",
    "충남": "충청남도",
    "충청남도": "충청남도",
    "충북": "충청북도",
    "충청북도": "충청북도",
    "서울": "서울특별시",
    "서울시": "서울특별시",
    "서울특별시": "서울특별시",
    "인천": "인천광역시",
    "인천시": "인천광역시",
    "인천광역시": "인천광역시",
    "대전": "대전광역시",
    "대전시": "대전광역시",
    "대전광역시": "대전광역시",
    "대구": "대구광역시",
    "대구시": "대구광역시",
    "대구광역시": "대구광역시",
    "광주": "광주광역시",
    "광주시": "광주광역시",
    "광주광역시": "광주광역시",
    "울산": "울산광역시",
    "울산시": "울산광역시",
    "울산광역시": "울산광역시",
    "부산": "부산광역시",
    "부산시": "부산광역시",
    "부산광역시": "부산광역시",
    "세종": "세종특별자치시",
    "세종시": "세종특별자치시",
    "세종특별자치시": "세종특별자치시",
    "제주": "제주특별자치도",
    "제주도": "제주특별자치도",
    "제주특별자치도": "제주특별자치도",
}

# 전국 시·군·구에 대한 광역시·도 역매핑 (전국 자치구/일반구 포함)
SIGUNGU_TO_PROVINCE = {
    # 서울특별시
    "종로구": "서울특별시", "중구": "서울특별시", "용산구": "서울특별시", "성동구": "서울특별시",
    "광진구": "서울특별시", "동대문구": "서울특별시", "중랑구": "서울특별시", "성북구": "서울특별시",
    "강북구": "서울특별시", "도봉구": "서울특별시", "노원구": "서울특별시", "은평구": "서울특별시",
    "서대문구": "서울특별시", "마포구": "서울특별시", "양천구": "서울특별시", "강서구": "서울특별시",
    "구로구": "서울특별시", "금천구": "서울특별시", "영등포구": "서울특별시", "동작구": "서울특별시",
    "관악구": "서울특별시", "서초구": "서울특별시", "강남구": "서울특별시", "송파구": "서울특별시", "강동구": "서울특별시",
    # 부산광역시
    "영도구": "부산광역시", "부산진구": "부산광역시", "동래구": "부산광역시", "해운대구": "부산광역시",
    "사하구": "부산광역시", "금정구": "부산광역시", "연제구": "부산광역시", "수영구": "부산광역시",
    "사상구": "부산광역시", "기장군": "부산광역시",
    # 대구광역시
    "수성구": "대구광역시", "달서구": "대구광역시", "달성군": "대구광역시", "군위군": "대구광역시",
    # 인천광역시
    "미추홀구": "인천광역시", "연수구": "인천광역시", "남동구": "인천광역시", "부평구": "인천광역시",
    "계양구": "인천광역시", "강화군": "인천광역시", "옹진군": "인천광역시",
    # 광주광역시
    "광산구": "광주광역시",
    # 대전광역시
    "유성구": "대전광역시", "대덕구": "대전광역시",
    # 울산광역시
    "울주군": "울산광역시",
    # 세종특별자치시
    "세종시": "세종특별자치시", "세종특별자치시": "세종특별자치시",
    # 경기도
    "수원시": "경기도", "성남시": "경기도", "고양시": "경기도", "용인시": "경기도",
    "부천시": "경기도", "안산시": "경기도", "안양시": "경기도", "남양주시": "경기도",
    "화성시": "경기도", "평택시": "경기도", "의정부시": "경기도", "시흥시": "경기도",
    "파주시": "경기도", "광명시": "경기도", "김포시": "경기도", "군포시": "경기도",
    "이천시": "경기도", "양주시": "경기도", "오산시": "경기도", "구리시": "경기도",
    "안성시": "경기도", "포천시": "경기도", "의왕시": "경기도", "하남시": "경기도",
    "여주시": "경기도", "양평군": "경기도", "동두천시": "경기도", "과천시": "경기도",
    "가평군": "경기도", "연천군": "경기도",
    # 강원특별자치도
    "춘천시": "강원특별자치도", "원주시": "강원특별자치도", "강릉시": "강원특별자치도",
    "동해시": "강원특별자치도", "태백시": "강원특별자치도", "속초시": "강원특별자치도",
    "삼척시": "강원특별자치도", "홍천군": "강원특별자치도", "횡성군": "강원특별자치도",
    "영월군": "강원특별자치도", "평창군": "강원특별자치도", "정선군": "강원특별자치도",
    "철원군": "강원특별자치도", "화천군": "강원특별자치도", "양구군": "강원특별자치도",
    "인제군": "강원특별자치도", "고성군": "강원특별자치도", "양양군": "강원특별자치도",
    # 충청북도
    "청주시": "충청북도", "충주시": "충청북도", "제천시": "충청북도", "보은군": "충청북도",
    "옥천군": "충청북도", "영동군": "충청북도", "증평군": "충청북도", "진천군": "충청북도",
    "괴산군": "충청북도", "음성군": "충청북도", "단양군": "충청북도",
    "상당구": "충청북도", "서원구": "충청북도", "흥덕구": "충청북도", "청원구": "충청북도",
    # 충청남도
    "천안시": "충청남도", "공주시": "충청남도", "보령시": "충청남도", "아산시": "충청남도",
    "서산시": "충청남도", "논산시": "충청남도", "계룡시": "충청남도", "당진시": "충청남도",
    "금산군": "충청남도", "부여군": "충청남도", "서천군": "충청남도", "청양군": "충청남도",
    "홍성군": "충청남도", "예산군": "충청남도", "태안군": "충청남도",
    "동남구": "충청남도", "서북구": "충청남도",
    # 전북특별자치도
    "전주시": "전북특별자치도", "익산시": "전북특별자치도", "군산시": "전북특별자치도",
    "정읍시": "전북특별자치도", "남원시": "전북특별자치도", "김제시": "전북특별자치도",
    "완주군": "전북특별자치도", "진안군": "전북특별자치도", "무주군": "전북특별자치도",
    "장수군": "전북특별자치도", "임실군": "전북특별자치도", "순창군": "전북특별자치도",
    "고창군": "전북특별자치도", "부안군": "전북특별자치도",
    # 전라남도
    "목포시": "전라남도", "여수시": "전라남도", "순천시": "전라남도", "나주시": "전라남도",
    "광양시": "전라남도", "담양군": "전라남도", "곡성군": "전라남도", "구례군": "전라남도",
    "고흥군": "전라남도", "보성군": "전라남도", "화순군": "전라남도", "장흥군": "전라남도",
    "강진군": "전라남도", "해남군": "전라남도", "영암군": "전라남도", "무안군": "전라남도",
    "함평군": "전라남도", "영광군": "전라남도", "장성군": "전라남도", "완도군": "전라남도",
    "진도군": "전라남도", "신안군": "전라남도",
    # 경상북도
    "포항시": "경상북도", "경주시": "경상북도", "김천시": "경상북도", "안동시": "경상북도",
    "구미시": "경상북도", "영주시": "경상북도", "영천시": "경상북도", "상주시": "경상북도",
    "문경시": "경상북도", "경산시": "경상북도", "의성군": "경상북도", "청송군": "경상북도",
    "영양군": "경상북도", "영덕군": "경상북도", "청도군": "경상북도", "고령군": "경상북도",
    "성주군": "경상북도", "칠곡군": "경상북도", "예천군": "경상북도", "봉화군": "경상북도",
    "울진군": "경상북도", "울릉군": "경상북도",
    # 경상남도
    "창원시": "경상남도", "진주시": "경상남도", "통영시": "경상남도", "사천시": "경상남도",
    "김해시": "경상남도", "밀양시": "경상남도", "거제시": "경상남도", "양산시": "경상남도",
    "의령군": "경상남도", "함안군": "경상남도", "창녕군": "경상남도", "고성군": "경상남도",
    "남해군": "경상남도", "하동군": "경상남도", "산청군": "경상남도", "함양군": "경상남도",
    "거창군": "경상남도", "합천군": "경상남도",
    # 제주특별자치도
    "제주시": "제주특별자치도", "서귀포시": "제주특별자치도",
}

# 시/군/구 접미사가 생략된 2~3글자 단어 매핑 (예: "영동" -> ("충청북도", "영동군"))
SHORT_SIGUNGU_MAP = {
    "영동": ("충청북도", "영동군"), "서산": ("충청남도", "서산시"), "제천": ("충청북도", "제천시"),
    "음성": ("충청북도", "음성군"), "괴산": ("충청북도", "괴산군"), "보은": ("충청북도", "보은군"),
    "진천": ("충청북도", "진천군"), "당진": ("충청남도", "당진시"), "공주": ("충청남도", "공주시"),
    "보령": ("충청남도", "보령시"), "논산": ("충청남도", "논산시"), "계룡": ("충청남도", "계룡시"),
    "홍성": ("충청남도", "홍성군"), "예산": ("충청남도", "예산군"), "태안": ("충청남도", "태안군"),
    "부여": ("충청남도", "부여군"), "서천": ("충청남도", "서천군"), "청양": ("충청남도", "청양군"),
    "금산": ("충청남도", "금산군"), "천안": ("충청남도", "천안시"), "아산": ("충청남도", "아산시"),
    "청주": ("충청북도", "청주시"), "충주": ("충청북도", "충주시"), "단양": ("충청북도", "단양군"),
    "옥천": ("충청북도", "옥천군"), "증평": ("충청북도", "증평군"),
    "김해": ("경상남도", "김해시"), "구미": ("경상북도", "구미시"), "포항": ("경상북도", "포항시"),
    "창원": ("경상남도", "창원시"), "진주": ("경상남도", "진주시"), "원주": ("강원특별자치도", "원주시"),
    "강릉": ("강원특별자치도", "강릉시"), "춘천": ("강원특별자치도", "춘천시"), "화순": ("전라남도", "화순군"),
    "목포": ("전라남도", "목포시"), "부천": ("경기도", "부천시"), "수원": ("경기도", "수원시"),
}

# 읍/면 이름 -> (시·도, 시·군·구) 직접 매핑 (시·군·구 생략 주소 자동 복원)
EUP_MYEON_MAP = {
    "영동읍": ("충청북도", "영동군"), "황간면": ("충청북도", "영동군"), "용산면": ("충청북도", "영동군"),
    "추풍령면": ("충청북도", "영동군"), "매곡면": ("충청북도", "영동군"), "상촌면": ("충청북도", "영동군"),
    "양강면": ("충청북도", "영동군"), "용화면": ("충청북도", "영동군"), "학산면": ("충청북도", "영동군"),
    "양산면": ("충청북도", "영동군"), "심천면": ("충청북도", "영동군"),
    "대소읍": ("충청북도", "음성군"), "금왕읍": ("충청북도", "음성군"), "원남면": ("충청북도", "음성군"),
    "음성읍": ("충청북도", "음성군"), "소이면": ("충청북도", "음성군"), "맹동면": ("충청북도", "음성군"),
    "삼성면": ("충청북도", "음성군"), "생극면": ("충청북도", "음성군"), "감곡면": ("충청북도", "음성군"),
    "운산면": ("충청남도", "서산시"), "성연면": ("충청남도", "서산시"), "대산읍": ("충청남도", "서산시"),
    "인지면": ("충청남도", "서산시"), "부석면": ("충청남도", "서산시"), "팔봉면": ("충청남도", "서산시"),
    "지곡면": ("충청남도", "서산시"), "음암면": ("충청남도", "서산시"), "해미면": ("충청남도", "서산시"), "고북면": ("충청남도", "서산시"),
    "두마면": ("충청남도", "계룡시"), "엄사면": ("충청남도", "계룡시"), "신도안면": ("충청남도", "계룡시"),
    "탕정면": ("충청남도", "아산시"), "배방읍": ("충청남도", "아산시"), "음봉면": ("충청남도", "아산시"),
    "신창면": ("충청남도", "아산시"), "둔포면": ("충청남도", "아산시"), "염치읍": ("충청남도", "아산시"),
    "영인면": ("충청남도", "아산시"), "선장면": ("충청남도", "아산시"), "도고면": ("충청남도", "아산시"), "송악면": ("충청남도", "아산시"),
    "오가면": ("충청남도", "예산군"), "삽교읍": ("충청남도", "예산군"), "예산읍": ("충청남도", "예산군"), "덕산면": ("충청남도", "예산군"),
    "태안읍": ("충청남도", "태안군"), "안면읍": ("충청남도", "태안군"), "근흥면": ("충청남도", "태안군"), "소원면": ("충청남도", "태안군"),
    "오송읍": ("충청북도", "청주시 흥덕구"), "오창읍": ("충청북도", "청주시 청원구"), "내수읍": ("충청북도", "청주시 청원구"),
    "옥산면": ("충청북도", "청주시 흥덕구"), "낭성면": ("충청북도", "청주시 상당구"),
    "사리면": ("충청북도", "괴산군"), "괴산읍": ("충청북도", "괴산군"), "칠성면": ("충청북도", "괴산군"),
    "내북면": ("충청북도", "보은군"), "보은읍": ("충청북도", "보은군"),
    "덕산읍": ("충청북도", "진천군"), "진천읍": ("충청북도", "진천군"), "광혜원면": ("충청북도", "진천군"),
    "이양면": ("전라남도", "화순군"), "화순읍": ("전라남도", "화순군"),
    "대동면": ("경상남도", "김해시"), "진영읍": ("경상남도", "김해시"),
    "선산읍": ("경상북도", "구미시"), "고아읍": ("경상북도", "구미시"),
}


@dataclass
class PNUResult:
    raw_address: str
    completed_address: str
    pnu: Optional[str]
    source: str          # 'kakao' | 'vworld' | 'cache' | 'none'
    status: str          # 'SUCCESS' | 'NOT_FOUND' | 'ERROR'
    x: Optional[float] = None
    y: Optional[float] = None
    standard_name: str = ""
    error_message: str = ""


def extract_numbers_and_mountain(addr: str) -> Tuple[str, str, str]:
    """주소 문자열에서 본번(4자리), 부번(4자리), 산구분('1'|'2') 추출"""
    mountain = "1"
    parts = re.split(r"(\d+-\d+|\d+)", addr or "")
    parts = [p.strip() for p in parts if p and p.strip()]
    if parts and re.match(r"\d+-\d+|\d+", parts[-1]):
        main_part = parts[-1]
        if "-" in main_part:
            main_no, sub_no = main_part.split("-", 1)
            sub_no = sub_no.zfill(4)
        else:
            main_no = main_part
            sub_no = "0000"
        main_no = main_no.zfill(4)
        if len(parts) > 1 and parts[-2].endswith("산"):
            mountain = "2"
        return main_no, sub_no, mountain
    return "0000", "0000", mountain


# 특별시/광역시별 구/군 목록 (동명 구 '중구', '동구', '서구', '남구', '북구' 정밀 구분용)
METRO_GU_MAP = {
    "서울특별시": ["종로구", "중구", "용산구", "성동구", "광진구", "동대문구", "중랑구", "성북구", "강북구", "도봉구", "노원구", "은평구", "서대문구", "마포구", "양천구", "강서구", "구로구", "금천구", "영등포구", "동작구", "관악구", "서초구", "강남구", "송파구", "강동구"],
    "부산광역시": ["중구", "서구", "동구", "영도구", "부산진구", "동래구", "남구", "북구", "해운대구", "사하구", "금정구", "강서구", "연제구", "수영구", "사상구", "기장군"],
    "대구광역시": ["중구", "동구", "서구", "남구", "북구", "수성구", "달서구", "달성군", "군위군"],
    "인천광역시": ["중구", "동구", "미추홀구", "연수구", "남동구", "부평구", "계양구", "서구", "강화군", "옹진군"],
    "광주광역시": ["동구", "서구", "남구", "북구", "광산구"],
    "대전광역시": ["동구", "중구", "서구", "유성구", "대덕구"],
    "울산광역시": ["중구", "남구", "동구", "북구", "울주군"],
    "세종특별자치시": ["세종시"],
}


def complete_korean_address(raw_addr: str, area_hint: str = "", paper: str = "",
                            default_area: str = "", context_text: str = "") -> str:
    """
    기사 내 축약/불완전 주소('영동읍 계산리 583-11번지' 등)를 온전한 대한민국 표준 주소로 완성.
    (예: '충청북도 영동군 영동읍 계산리 583-11번지')
    """
    addr = (raw_addr or "").strip()
    if not addr:
        return ""

    full_ctx = f"{area_hint} {default_area} {context_text}"
    prov = None
    sigungu = None

    # 0. 광역시·도 단서 우선 탐색
    for p_short, p_full in PROVINCE_STANDARDIZATION.items():
        if p_short in full_ctx or addr.startswith(p_short):
            prov = p_full
            break

    # 1. 읍/면 사전 매핑: 주소 자체에 읍/면/동이 있으면 주소 내부를 최우선 적용
    has_eup_myeon_dong = any(x in addr for x in ["읍", "면", "동", "가"])
    for em, (p, s) in EUP_MYEON_MAP.items():
        if em in addr:
            prov, sigungu = p, s
            break
        elif not has_eup_myeon_dong and em in context_text[:300]:
            # 주소에 읍/면/동이 전혀 없고 리 지번만 있는 경우 본문에서 읍/면 보충
            prov, sigungu = p, s
            addr = f"{em} {addr}"
            break

    # 2. 광역시/특별시 산하 구 탐색 (대전 중구, 부산 강서구 등)
    if not sigungu and prov and prov in METRO_GU_MAP:
        for gu in METRO_GU_MAP[prov]:
            if gu in addr or gu in full_ctx:
                sigungu = gu
                break

    # 3. 시·군·구 매핑 (주소, 지역힌트, 본문에서 탐색)
    if not sigungu:
        # A. 정식 시·군·구 매핑
        for s_name, p_name in SIGUNGU_TO_PROVINCE.items():
            if s_name in addr or s_name in full_ctx:
                sigungu = s_name
                prov = p_name
                break

    if not sigungu:
        # B. 짧은 지명 매핑 (예: "영동" -> 영동군, "서산" -> 서산시)
        for short_name, (p_name, s_name) in SHORT_SIGUNGU_MAP.items():
            if re.search(rf"(?:^|\s|[^\w]){re.escape(short_name)}(?:$|\s|[^\w])", full_ctx) or short_name in addr:
                sigungu = s_name
                prov = p_name
                break

    # 4. 주소 조립 및 중복 제거
    res = addr

    # 시군구 결합
    if sigungu:
        # addr 시작 부분에 이미 sigungu가 있거나 구 이름이 있는지 체크
        sigungu_last = sigungu.split()[-1]
        if not (res.startswith(sigungu) or res.startswith(sigungu_last)):
            res = f"{sigungu} {res}"
        elif res.startswith(sigungu_last) and not res.startswith(sigungu):
            # 예: "상당구 산성동" -> "청주시 상당구 산성동"
            res = f"{sigungu.replace(sigungu_last, '').strip()} {res}".strip()

    # 광역시·도 결합
    if prov:
        # 이미 prov로 시작하는지 체크
        prov_prefix = prov[:2]  # 예: '충북', '충남', '대전' 등
        starts_with_p = False
        for p in [prov, prov_prefix]:
            if res.startswith(p):
                starts_with_p = True
                # 축약형이면 정식 명칭으로 변경
                if not res.startswith(prov):
                    res = re.sub(rf"^{re.escape(p)}\s*", f"{prov} ", res, 1)
                break
        if not starts_with_p:
            res = f"{prov} {res}"

    return re.sub(r"\s+", " ", res).strip()


def get_pnu_from_kakao(address: str, session: Optional[requests.Session] = None) -> PNUResult:
    """Kakao Local API를 호출하여 19자리 PNU 추출"""
    s = session or requests.Session()
    try:
        r = s.get(KAKAO_URL, headers=KAKAO_HEADERS, params={"query": address}, timeout=10)
        if r.status_code == 429:
            time.sleep(1.5)
            r = s.get(KAKAO_URL, headers=KAKAO_HEADERS, params={"query": address}, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get("documents"):
            doc = data["documents"][0]
            addr_info = doc.get("address")
            if addr_info:
                b_code = addr_info.get("b_code", "")
                address_name = addr_info.get("address_name", "")
                main_no, sub_no, mountain = extract_numbers_and_mountain(address_name or address)
                pnu = f"{b_code[:10]}{mountain}{main_no}{sub_no}"
                x = float(doc.get("x", 0)) if doc.get("x") else None
                y = float(doc.get("y", 0)) if doc.get("y") else None
                return PNUResult(
                    raw_address=address,
                    completed_address=address,
                    pnu=pnu,
                    source="kakao",
                    status="SUCCESS",
                    x=x,
                    y=y,
                    standard_name=address_name,
                )
        return PNUResult(raw_address=address, completed_address=address, pnu=None,
                         source="kakao", status="NOT_FOUND", error_message="검색 결과 없음")
    except Exception as e:
        return PNUResult(raw_address=address, completed_address=address, pnu=None,
                         source="kakao", status="ERROR", error_message=str(e))


def get_pnu_from_vworld(address: str, session: Optional[requests.Session] = None) -> PNUResult:
    """VWorld Geocoder API를 호출하여 19자리 PNU 추출 (폴백)"""
    s = session or requests.Session()
    params = {
        "service": "address",
        "request": "getcoord",
        "version": "2.0",
        "crs": "epsg:4326",
        "address": address,
        "refine": "true",
        "simple": "false",
        "format": "json",
        "type": "PARCEL",
        "key": VWORLD_KEY,
    }
    try:
        r = s.get(VWORLD_URL, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        resp = data.get("response", {})
        if resp.get("status") == "OK":
            refined = resp.get("refined", {})
            structure = refined.get("structure", {})
            pnu = structure.get("level4LC", "")
            std_text = refined.get("text", "")
            pt = resp.get("result", {}).get("point", {})
            x = float(pt.get("x", 0)) if pt.get("x") else None
            y = float(pt.get("y", 0)) if pt.get("y") else None
            if pnu and len(pnu) == 19:
                return PNUResult(
                    raw_address=address,
                    completed_address=address,
                    pnu=pnu,
                    source="vworld",
                    status="SUCCESS",
                    x=x,
                    y=y,
                    standard_name=std_text,
                )
        return PNUResult(raw_address=address, completed_address=address, pnu=None,
                         source="vworld", status="NOT_FOUND", error_message="VWorld 응답에 PNU 없음")
    except Exception as e:
        return PNUResult(raw_address=address, completed_address=address, pnu=None,
                         source="vworld", status="ERROR", error_message=str(e))


class PNUResolver:
    """
    주소 완성 + PNU 발급 + 캐싱 + SQLite 저장을 총괄하는 파이프라인 매니저
    """

    def __init__(self, db_path: str = "output/news_articles_pnu.db"):
        self.db_path = db_path
        self.session = requests.Session()
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            # 1. 기사 정보 테이블
            cur.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    link TEXT UNIQUE,
                    paper TEXT,
                    keyword TEXT,
                    title TEXT,
                    article_date TEXT,
                    area_hint TEXT,
                    raw_address_extracted TEXT,
                    content_hash TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # 컬럼 확인 및 content_hash 추가 (기존 DB 마이그레이션 호환)
            cur.execute("PRAGMA table_info(articles)")
            cols = [row[1] for row in cur.fetchall()]
            if "content_hash" not in cols:
                cur.execute("ALTER TABLE articles ADD COLUMN content_hash TEXT")
            if "relevance_score" not in cols:
                cur.execute("ALTER TABLE articles ADD COLUMN relevance_score INTEGER")
            if "relevance_keywords" not in cols:
                cur.execute("ALTER TABLE articles ADD COLUMN relevance_keywords TEXT")

            # 2. 기사별 추출 주소 및 PNU 발급 내역 테이블
            cur.execute("""
                CREATE TABLE IF NOT EXISTS article_addresses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_link TEXT,
                    raw_address TEXT,
                    completed_address TEXT,
                    pnu TEXT,
                    source TEXT,
                    status TEXT,
                    standard_name TEXT,
                    x REAL,
                    y REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(article_link) REFERENCES articles(link)
                )
            """)
            # 3. 주소 -> PNU 고속 캐시 테이블
            cur.execute("""
                CREATE TABLE IF NOT EXISTS address_pnu_cache (
                    completed_address TEXT PRIMARY KEY,
                    pnu TEXT,
                    source TEXT,
                    standard_name TEXT,
                    x REAL,
                    y REAL,
                    status TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 고속 검색 및 중복 방지용 인덱스
            cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_link ON articles(link)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_title ON articles(title)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_hash ON articles(content_hash)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_art_addr_pnu ON article_addresses(pnu)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_art_addr_link ON article_addresses(article_link)")
            conn.commit()

    def get_cached_pnu(self, completed_address: str) -> Optional[PNUResult]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT pnu, source, standard_name, x, y, status FROM address_pnu_cache WHERE completed_address = ?",
                        (completed_address,))
            row = cur.fetchone()
            if row:
                pnu, source, std_name, x, y, status = row
                return PNUResult(
                    raw_address="",
                    completed_address=completed_address,
                    pnu=pnu,
                    source=f"cache({source})",
                    status=status,
                    x=x,
                    y=y,
                    standard_name=std_name or "",
                )
        return None

    def cache_pnu(self, res: PNUResult):
        if not res.completed_address:
            return
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO address_pnu_cache
                (completed_address, pnu, source, standard_name, x, y, status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (res.completed_address, res.pnu, res.source, res.standard_name, res.x, res.y, res.status))
            conn.commit()

    def resolve(self, raw_addr: str, area_hint: str = "", paper: str = "",
                default_area: str = "", context_text: str = "") -> PNUResult:
        """불완전 주소를 한국식 표준 주소로 완성한 뒤 PNU를 발급(캐시 -> Kakao -> VWorld 폴백)"""
        completed = complete_korean_address(raw_addr, area_hint=area_hint,
                                            paper=paper, default_area=default_area,
                                            context_text=context_text)
        if not completed:
            return PNUResult(raw_address=raw_addr, completed_address="", pnu=None,
                             source="none", status="ERROR", error_message="주소 완성 불가")

        # 캐시 확인
        cached = self.get_cached_pnu(completed)
        if cached:
            cached.raw_address = raw_addr
            return cached

        # 1. Kakao API 호출
        res = get_pnu_from_kakao(completed, session=self.session)
        res.raw_address = raw_addr
        res.completed_address = completed

        # 2. Kakao 실패 시 VWorld 폴백
        if res.status != "SUCCESS" or not res.pnu:
            v_res = get_pnu_from_vworld(completed, session=self.session)
            if v_res.status == "SUCCESS" and v_res.pnu:
                v_res.raw_address = raw_addr
                v_res.completed_address = completed
                res = v_res

        # 캐시 기록
        self.cache_pnu(res)
        return res

    def save_article_and_addresses(self, article: dict, address_results: List[PNUResult]) -> Tuple[int, int]:
        """기사 메타데이터와 발급된 PNU 내역을 SQLite에 트랜잭션으로 안전하게 저장.
        - 동일 지번 PNU에 동일한 내용(링크, 제목, 본문해시)의 신문기사는 중복 저장을 방지하여 1건만 유지.
        - 반환값: (저장된 주소 수, 중복 제외된 주소 수)
        """
        link = article.get("link", "").strip()
        if not link:
            return 0, 0

        title = article.get("title", "").strip()
        body = article.get("body", "").strip()

        # 기사 본문(또는 제목)을 정규화하여 중복 판별용 고유 해시 생성
        content_sample = body if len(body) > 30 else f"{title}\n{body}"
        norm_content = re.sub(r"\s+", "", content_sample)
        content_hash = hashlib.md5(norm_content.encode("utf-8")).hexdigest() if norm_content else ""

        saved_count = 0
        skipped_count = 0

        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            # 기사 본문 저장/갱신
            cur.execute("""
                INSERT OR REPLACE INTO articles
                (link, paper, keyword, title, article_date, area_hint, raw_address_extracted, content_hash,
                 relevance_score, relevance_keywords)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                link,
                article.get("paper", ""),
                article.get("keyword", ""),
                title,
                article.get("date", ""),
                article.get("area", ""),
                article.get("address_extracted", ""),
                content_hash or None,
                article.get("relevance_score"),
                article.get("relevance_keywords", ""),
            ))

            # 동일 기사 호출 내 배치 중복 방지
            seen_in_batch = set()

            # 주소 발급 결과 저장 (동일 PNU + 동일 기사 중복 방지)
            for r in address_results:
                pnu_val = (r.pnu or "").strip()
                completed_val = (r.completed_address or "").strip()
                raw_val = (r.raw_address or "").strip()

                batch_key = (pnu_val if pnu_val else completed_val, raw_val)
                if batch_key in seen_in_batch:
                    skipped_count += 1
                    continue
                seen_in_batch.add(batch_key)

                # A. 유효한 PNU가 발급된 경우:
                #    DB에 동일한 PNU이면서 동일 기사(링크, 제목, 또는 본문 해시)가 이미 있는지 검사
                if pnu_val and r.status == "SUCCESS":
                    cur.execute("""
                        SELECT aa.id, a.paper, a.title
                        FROM article_addresses aa
                        JOIN articles a ON aa.article_link = a.link
                        WHERE aa.pnu = ?
                          AND (
                              a.link = ?
                              OR a.title = ?
                              OR (a.content_hash = ? AND a.content_hash IS NOT NULL AND a.content_hash != '')
                          )
                        LIMIT 1
                    """, (pnu_val, link, title, content_hash))
                    existing = cur.fetchone()
                    if existing:
                        skipped_count += 1
                        print(f"  -> [중복 제외] PNU({pnu_val})에 동일 기사 이미 저장됨: '{title[:30]}' (기존: [{existing[1]}] {existing[2][:25]})")
                        continue

                # B. PNU가 없거나 실패한 주소인 경우:
                #    동일 article_link에 동일 raw_address가 이미 있는지 검사
                else:
                    cur.execute("""
                        SELECT 1 FROM article_addresses
                        WHERE article_link = ? AND raw_address = ?
                        LIMIT 1
                    """, (link, raw_val))
                    if cur.fetchone():
                        skipped_count += 1
                        continue

                # 신규 주소-기사 관계 저장
                cur.execute("""
                    INSERT INTO article_addresses
                    (article_link, raw_address, completed_address, pnu, source, status, standard_name, x, y)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    link,
                    r.raw_address,
                    r.completed_address,
                    r.pnu,
                    r.source,
                    r.status,
                    r.standard_name,
                    r.x,
                    r.y,
                ))
                saved_count += 1

            conn.commit()

        return saved_count, skipped_count

    def close(self):
        self.session.close()
