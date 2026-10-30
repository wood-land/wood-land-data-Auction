import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.pnu_resolver import complete_korean_address, complete_korean_address_candidates as cands


def first(raw, hint="", ctx=""):
    c = cands(raw, area_hint=hint, context_text=ctx)
    return c[0] if c else None


# ---- DB 에서 실제로 틀렸던 사례 ----
def test_substring_match_daesowon_is_not_sowon():
    # '대소원면' 안의 '소원면'(태안군) 부분 일치로 충남 태안군이 붙던 문제
    assert first("대소원면 완오리 607", "충주시") == ("충청북도 충주시 대소원면 완오리 607", "hint")


def test_paper_hint_beats_eupmyeon_dictionary():
    # 영주시 부석면 / 함양군 지곡면 인데 사전의 서산시로 고정되던 문제
    assert first("부석면 북지리 548", "영주시")[0].startswith("경상북도 영주시 부석면")
    assert first("지곡면 마산리 668-13", "함양군")[0].startswith("경상남도 함양군 지곡면")


def test_explicit_city_beats_province_hint():
    # '포항시 북구 ...' 가 대구 힌트 때문에 '대구광역시 북구 포항시 북구'로 조립되던 문제
    assert first("포항시 북구 청하면 신흥리 산 134", "대구광역시") == ("경상북도 포항시 북구 청하면 신흥리 산 134", "explicit")


def test_leading_province_token_is_not_duplicated():
    # '대구광역시 달서구 대구시 달서구 대곡동' 중복
    assert first("대구시 달서구 대곡동 159", "대구광역시")[0] == "대구광역시 달서구 대곡동 159"


def test_junk_prefix_is_dropped():
    assert first("따르면 동대동 489-52", "충청 충남 천안")[0] == "충청남도 천안시 동대동 489-52"
    assert first("호우시 평산동 산40-3", "경상남도", "양산시는 평산동 일대")[0] == "경상남도 양산시 평산동 산 40-3"


def test_not_an_address_returns_nothing():
    assert cands("충주상가 1", area_hint="충주시") == []
    assert complete_korean_address("충주상가 1", area_hint="충주시") == ""
    assert cands("활동 3", area_hint="충주시") == []


# ---- 시군구 단서 우선순위 ----
def test_gosung_is_resolved_by_province():
    assert first("거진읍 거진리 100", "강원특별자치도 고성군")[0].startswith("강원특별자치도 고성군")
    assert first("거류면 당동리 100", "경상남도 고성군")[0].startswith("경상남도 고성군")
    # 시·도 단서가 없으면 기본값(강원)
    assert first("죽왕면 오봉리 10", "고성군")[0].startswith("강원특별자치도 고성군")


def test_gwangju_si_is_gyeonggi_but_gwangju_gu_is_metropolitan():
    assert first("오포읍 문형리 10", "광주시")[0].startswith("경기도 광주시")
    assert first("광주시 북구 일곡동 100")[0] == "광주광역시 북구 일곡동 100"
    assert first("북구 일곡동 100", "광주")[0] == "광주광역시 북구 일곡동 100"


def test_general_gu_gets_parent_city():
    assert first("의창구 소답동 550-1", "경상남도")[0] == "경상남도 창원시 의창구 소답동 550-1"
    assert first("상당구 산성동 10", "충청북도")[0] == "충청북도 청주시 상당구 산성동 10"


def test_metro_gu_uses_hint_province():
    assert first("서구 진천동 826", "대구광역시")[0] == "대구광역시 서구 진천동 826"


def test_context_city_used_only_without_hint_and_ranked_by_frequency():
    ctx = "김해시는 김해시 주촌면 일대 사업 창원시와 협의"
    c = cands("주촌면 천곡리 산112", area_hint="경상남도", context_text=ctx)
    assert c[0] == ("경상남도 김해시 주촌면 천곡리 산 112", "context")
    assert any("창원시" in a for a, _ in c)               # 덜 나온 도시는 대안 후보로 뒤에 남는다


def test_context_ignores_non_city_words_ending_in_si():
    # '집중호우시' 를 도시로 보면 안 된다
    c = cands("평산동 산40-3", area_hint="경상남도", context_text="집중호우시 피해 우려, 양산시는")
    assert c[0][0] == "경상남도 양산시 평산동 산 40-3"


def test_context_city_must_match_known_province():
    # 경남 기사에서 충북 도시 이름이 나왔다고 그쪽으로 가면 안 된다
    c = cands("가좌동 409-2", area_hint="경상남도", context_text="청주시 사례를 참고, 진주시는")
    assert all("청주시" not in a for a, _ in c)
    assert c[0][0].startswith("경상남도 진주시")


def test_eupmyeon_dictionary_only_when_no_hint_and_province_agrees():
    assert first("배방읍 장재리 483-3", "")[0] == "충청남도 아산시 배방읍 장재리 483-3"
    assert first("배방읍 장재리 483-3", "")[1] == "eupmyeon"
    # 경남 기사에서 충남 사전을 쓰면 안 된다
    c = cands("배방읍 장재리 483-3", area_hint="경상남도")
    assert all("아산시" not in a for a, _ in c)


def test_address_province_conflicts_with_hint_city():
    # 주소에 '경상북도' 가 명시돼 있으면 함양군(경남) 힌트는 버린다
    c = cands("경상북도 가흥동 676-2", area_hint="함양군")
    assert all("함양군" not in a for a, _ in c)


def test_province_plus_eupmyeon_is_the_last_fallback_and_never_drops_the_eupmyeon():
    # 진주신문에 실린 '궁류면 평촌리 9' 는 의령군이다. 힌트(진주시)가 틀렸을 때 읍/면을 버리고
    # '진주시 평촌리 9' 로 조회하면 다른 면의 같은 이름 리가 우연히 맞아 엉뚱한 필지가 채택된다.
    c = [a for a, _ in cands("궁류면 평촌리 9", area_hint="진주시")]
    assert c == ["경상남도 진주시 궁류면 평촌리 9", "경상남도 궁류면 평촌리 9"]
    assert all("궁류면" in a for a in c)


def test_province_only_hint_queries_by_province():
    assert cands("풍류동 179", area_hint="경상남도") == [("경상남도 풍류동 179", "province")]


def test_no_province_and_no_city_means_no_query():
    # 횡성뉴스(지역힌트 없음)의 '마산리 46-1' 을 시·도 없이 조회하면 다른 도의 마산리(파주 등)가 채택된다
    assert cands("마산리 46-1", area_hint="", context_text="") == []
    assert cands("마산리 46-1", area_hint="", context_text="횡성군은")[0][0] == "강원특별자치도 횡성군 마산리 46-1"


def test_lot_formatting_is_normalized():
    assert first("내서읍 원계리388", "창원시")[0] == "경상남도 창원시 내서읍 원계리 388"
    assert first("명동 산104번지", "창원시 진해구")[0].endswith("명동 산 104")
    assert first("후용리 1153 - 2번지", "원주시")[0].endswith("후용리 1153-2")


def test_candidates_are_deduplicated_and_capped():
    c = cands("주촌면 천곡리 산112", area_hint="경상남도",
              context_text="김해시 창원시 진주시 양산시 거제시 통영시", max_candidates=3)
    assert len(c) == 3 and len({a for a, _ in c}) == 3


def test_every_province_full_name_is_recognized_as_a_province():
    # 정식 명칭이 사전 키에 없어서 default_area='강원특별자치도' 가 무시되던 문제
    from common.pnu_resolver import parse_hint
    for full in ("강원특별자치도", "전북특별자치도", "제주특별자치도", "세종특별자치시", "경상남도", "서울특별시"):
        assert parse_hint(full) == (full, [])
    assert cands("후용리 1153", area_hint="강원특별자치도") == [("강원특별자치도 후용리 1153", "province")]
