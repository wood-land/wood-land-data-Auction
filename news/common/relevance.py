"""보상 관련 기사 판별 (제목+본문 점수제).

검색어로 가져온 기사 중에는 보상과 무관한 기사가 많다. 그래서 '검색어에 걸렸는가'가 아니라
'기사 자체가 토지 보상·편입 사업을 다루는가'를 점수로 판단한다.

판정 기준 (모두 만족해야 저장):
  1. 지번 주소가 추출됨 (호출 측에서 확인)
  2. 점수 >= MIN_SCORE  *그리고*  (보상 직접어 1개 이상  또는  사업어 + 절차어 조합)
점수는 단어 등급 가중치 x (제목이면 3배, 본문이면 1배, 단어별 최대 2회까지만 반영).
"""
import re
from typing import Dict, List, Tuple

# 보상 직접어: 이게 있으면 거의 확실히 보상/수용 관련
DIRECT = {
    "토지보상": 5, "토지 보상": 5, "보상협의": 5, "보상 협의": 5, "손실보상": 5, "보상계획": 5,
    "보상금": 4, "보상가": 4, "협의보상": 5, "수용재결": 5, "토지수용": 5, "수용": 3, "사업인정": 5,
    "편입토지": 5, "편입 토지": 5, "지장물": 4, "이주대책": 4, "이주정착금": 4, "협의양도": 5,
    "감정평가": 3, "토지주": 2, "지주 협의": 3, "재결": 3,
}
# 사업어: 보상이 따라오는 사업/공사
PROJECT = {
    "도로개설": 3, "도로 개설": 3, "도로확장": 3, "도로 확장": 3, "확포장": 3, "우회도로": 3,
    "택지": 0, "산업단지": 3, "지구지정": 3, "도시계획시설": 3, "도시계획도로": 3, "도시개발": 3,
    "정비사업": 3, "재개발": 2, "재건축": 0, "하천정비": 3, "하천 정비": 3, "소하천": 3, "저수지": 2,
    "재해위험": 3, "개선복구": 3, "급경사지": 3, "실시계획": 3, "실시설계": 3, "기본설계": 2,
    "조성사업": 3, "투자심사": 2, "철도": 0, "고속도로": 2, "국도": 0, "지방도": 2, "하수관로": 2,
    "하수처리": 2, "상수도": 0, "공원조성": 3, "주차장": 0, "체육시설": 0, "착공": 0, "준공": 0,
    "공사": 0, "사업": 0, "개발제한": 2, "그린벨트": 2, "군계획": 2, "송전": 3, "송전선로": 3,
}
# 절차어: 주민 대상 공지/설명 절차 (사업어와 같이 나오면 보상 단계)
PROCESS = {
    "주민설명회": 3, "설명회": 2, "공청회": 2, "주민공람": 3, "공람": 2, "열람": 1, "공고": 0,
    "고시": 2, "주민의견": 2, "의견청취": 2, "협의": 0, "토지소유자": 3, "소유자": 0,
    "관계인": 2, "토지조서": 4, "물건조서": 4, "지적": 0, "편입": 2, "지정": 0,
}
# 감점: 보상과 무관하게 지번만 우연히 나오는 글
NEGATIVE = {
    "부고": 6, "인사": 3, "동정": 4, "맛집": 5, "분양": 3, "아파트 분양": 5, "입시": 4, "축제": 3,
    "공연": 3, "전시": 3, "개최": 1, "시상": 3, "수상": 3, "봉사": 3, "기부": 3, "성금": 3,
    "스포츠": 3, "경기결과": 4, "운세": 6, "광고": 3, "사건·사고": 2, "화재": 2, "교통사고": 3,
    "음주운전": 4, "경찰": 1, "구속": 3, "판결": 2, "선거": 2, "후보": 2,
}

TITLE_MULT = 3
MAX_REPEAT = 2
MIN_SCORE = 15


def _score_dict(d: Dict[str, int], title: str, body: str, hits: List[str]) -> int:
    total = 0
    for word, w in d.items():
        if w <= 0:
            continue
        in_title = title.count(word)
        in_body = body.count(word)
        if not (in_title or in_body):
            continue
        total += w * TITLE_MULT * min(in_title, 1) + w * min(in_body, MAX_REPEAT)
        hits.append(word)
    return total


def score_article(title: str, body: str) -> Tuple[int, str]:
    """(점수, 매칭키워드 문자열). 점수가 MIN_SCORE 이상이고 구조 조건을 만족하면 보상 관련으로 본다."""
    title = title or ""
    body = re.sub(r"\s+", " ", body or "")
    d_hits: List[str] = []
    p_hits: List[str] = []
    r_hits: List[str] = []
    n_hits: List[str] = []
    direct = _score_dict(DIRECT, title, body, d_hits)
    project = _score_dict(PROJECT, title, body, p_hits)
    process = _score_dict(PROCESS, title, body, r_hits)
    neg = _score_dict(NEGATIVE, title, body, n_hits)

    structural_ok = bool(d_hits) or (bool(p_hits) and bool(r_hits))
    score = direct + project + process - neg
    if not structural_ok:
        score = min(score, MIN_SCORE - 1)       # 구조 조건 미충족이면 통과 불가
    keywords = ",".join(d_hits + p_hits + r_hits)
    return score, keywords


def is_compensation_related(title: str, body: str) -> Tuple[bool, int, str]:
    score, keywords = score_article(title, body)
    return score >= MIN_SCORE, score, keywords
