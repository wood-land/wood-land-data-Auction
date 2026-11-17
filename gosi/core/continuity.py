"""한 고시문 안에서 '인근 필지가 이어서 적힌다'는 성질로 엉뚱한 지역 필지(변환 오류)를 가려낸다.

사용자 지시 2026-11-17: 한국부동산원처럼 전국 단위 출처도 지번을 인근 필지로 이어서 적는다(도로처럼 길어도 앞뒤 지번이 순서대로 근처에서 이어진다).
같은 고시문 안에 인근이 아닌 다른 지역 필지가 있으면 그건 오류다.
PNU 앞 4자리(시군; 창원시 의창구·성산구처럼 한 시의 구는 같은 것으로 본다)·2자리(시도)만 쓴다(좌표 없이 판단). 서울+경기 철도처럼 진짜 걸친 사업은 걸친 쪽이 한 덩어리로 이어지므로 걸리지 않는다.

규칙(해결된 PNU 가 6개 이상인 고시문에만 적용):
 R1 외딴 필지: 문서 순서로 앞뒤 3개씩(최대 6개) 이웃 중 같은 시군이 하나도 없고, 이웃의 2/3 이상이 한 시군으로 모여 있으면 외딴 필지.
 R2 소수 시도: 해결된 PNU 가 8개 이상이고 한 시도가 70% 이상인데, 다른 시도 필지가 합쳐서 max(2, 10%) 이하이면 그 필지들은 외딴 필지.
"""
from collections import Counter

MIN_RESOLVED = 6
WINDOW = 3


def region_outliers(pnus):
    """pnus: 문서 순서의 PNU(없으면 None) 리스트 -> 외딴 필지의 위치(index) 집합."""
    idx = [i for i, p in enumerate(pnus) if p and len(p) >= 5]
    n = len(idx)
    if n < MIN_RESOLVED:
        return set()
    code4 = [pnus[i][:4] for i in idx]  # 시군(구는 같은 시로 묶임). 아래 변수명은 code4 지만 4자리다
    out = set()
    # R2: 소수 시도
    sido = Counter(c[:2] for c in code4)
    top, topn = sido.most_common(1)[0]
    if n >= 8 and topn >= 0.7 * n:
        minor = [k for k in range(n) if code4[k][:2] != top]
        if minor and len(minor) <= max(2, int(0.1 * n)):
            out.update(idx[k] for k in minor)
    # R1: 외딴 필지
    for k in range(n):
        near = code4[max(0, k - WINDOW):k] + code4[k + 1:k + 1 + WINDOW]
        if not near or code4[k] in near:
            continue
        common, cnt = Counter(near).most_common(1)[0]
        if cnt >= 2 / 3 * len(near) and common != code4[k]:
            out.add(idx[k])
    return out
