import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.crawler_core import extract_addresses


def test_keeps_real_addresses_with_city_prefix():
    assert extract_addresses("청주시 흥덕구 봉명동 123번지") == ["청주시 흥덕구 봉명동 123번지"]
    assert extract_addresses("원주시 문막읍 후용리 1153번지 일원") == ["원주시 문막읍 후용리 1153번지"]
    assert extract_addresses("포항시 북구 청하면 신흥리 산 134번지") == ["포항시 북구 청하면 신흥리 산 134번지"]


def test_province_before_city_is_kept():
    # '중구'처럼 이름이 겹치는 구는 시·도 없이는 어느 도시인지 알 수 없다
    assert extract_addresses("서울시 중구 신당동 12번지") == ["서울시 중구 신당동 12번지"]
    assert extract_addresses("경남 창원시 의창구 소답동 550-1번지") == ["경남 창원시 의창구 소답동 550-1번지"]


def test_verb_ending_in_myeon_is_not_an_eupmyeon():
    # '~에 따르면'의 '따르면'이 면 이름으로 붙던 문제 (DB: '충청남도 천안시 따르면 용곡동 295-1')
    assert extract_addresses("시에 따르면 용곡동 295-1번지 일대에") == ["용곡동 295-1번지"]
    assert extract_addresses("이에 따르면 동대동 489-52번지") == ["동대동 489-52번지"]


def test_real_myeon_ending_in_ha_is_kept():
    # 포항시 '청하면' 이 '~하면' 동사형으로 오인되어 사라지면 안 된다
    assert extract_addresses("청하면 신흥리 134번지") == ["청하면 신흥리 134번지"]


def test_non_admin_words_are_not_city_prefix():
    # DB: '경상남도 양산시 호우시 평산동 산40-3', '충북 충주시 사업지구 중앙탑면 창동리 227-1'
    assert extract_addresses("집중호우시 평산동 산40-3번지") == ["평산동 산40-3번지"]
    assert extract_addresses("이번 사업지구 중앙탑면 창동리 227-1번지") == ["중앙탑면 창동리 227-1번지"]


def test_plain_ga_word_is_not_a_place():
    # DB: '충주상가 1' (상가), '시가 100'
    assert extract_addresses("충주상가 1번지") == []
    assert extract_addresses("시가 100번지") == []
    assert extract_addresses("이동 거리 5km 일대") == []          # 숫자 바로 뒤가 일대가 아니면 인정하지 않는다


def test_numbered_ga_address_still_works():
    assert extract_addresses("종로3가 12번지") == ["종로3가 12번지"]


def test_common_nouns_ending_in_dong_ri_are_not_places():
    assert extract_addresses("활동 3건 일대") == []
    assert extract_addresses("관리 5번지") == []


def test_one_char_names_still_work():
    assert extract_addresses("명동 12번지") == ["명동 12번지"]
    assert extract_addresses("화성시 상리 55번지") == ["화성시 상리 55번지"]
    assert extract_addresses("봉명동 12번지") == ["봉명동 12번지"]           # '명동'만 따로 잡히면 안 된다


def test_requires_bunji_or_ildae():
    assert extract_addresses("후용리 1153에서 열렸다") == []
    assert extract_addresses("후용리 1153 일대") == ["후용리 1153"]
