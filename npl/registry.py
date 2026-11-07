# -*- coding: utf-8 -*-
"""두인 상세페이지의 기본정보 / 입찰이력 / 등기부(근저당·청구금액) / 채권 추정 추출.

로컬 '공장근린상가' 추출기(공장매각완.py 포팅본)의 해당 블록을 그대로 가져왔다(로직 변경 없음).
브라우저 탭 열기/닫기·사이트 주소·지연시간은 auction/crawler.py 의 것을 쓴다.
"""
import copy
import random
import time
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

import dooin_base as _b

open_detail_tab = _b.open_detail_tab
close_detail_tab = _b.close_detail_tab
DETAIL_PAGE_DELAY = _b.DETAIL_PAGE_DELAY
SITE_BASE = _b.SITE_BASE


# (2026-10-04 3차 수정, 공장매각완.py에서 포팅) 근저당권_합계금액 -> 채권원금 추정 배수
# 후보(1.10~1.50, 0.05 단위, x100 정수 연산용). 동률이면 끝자리 0이 더 많이 붙는("깨끗한")
# 쪽, 그마저 같으면 더 작은 배수를 우선한다(원본과 동일 기준).
PRINCIPAL_MULTIPLIERS = (110, 115, 120, 125, 130, 135, 140, 145, 150)

ANNUAL_INTEREST_RATE = 0.10  # 연 이자율 10% (원본 '채권행사권리금액 계산식' 엑셀의 고정값)

# 진행 중인 물건은 아직 낙찰일/배당기일이 없어, 사용자 요청대로 "이번 입찰기일 + 60일"을
# 이자 계산 기준일로 근사한다(원본의 "낙찰일 + 7일(매각결정기일) + 60일(배당기일)" 대신).
REFERENCE_DAYS_AFTER_BID = 60

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

