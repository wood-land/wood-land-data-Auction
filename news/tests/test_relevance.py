import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.relevance import is_compensation_related


def test_compensation_article_passes():
    ok, score, kw = is_compensation_related(
        "OO면 도로개설 토지 보상 협의 착수", "OO리 123-4번지 일원 편입토지 소유자 대상 보상협의 주민설명회")
    assert ok and "보상협의" in kw


def test_project_plus_process_passes():
    ok, _, _ = is_compensation_related("하천정비사업 주민설명회 개최", "소하천 정비사업 실시계획 주민공람 토지소유자")
    assert ok


def test_unrelated_with_address_rejected():
    assert not is_compensation_related("OO읍 아파트 분양 시작", "OO리 100번지 분양")[0]
    assert not is_compensation_related("지역 축제 개최 안내", "축제 OO리 33번지 공연 개최")[0]
    assert not is_compensation_related("마을 경로당 준공식", "사업비 2억 공사 완료 OO리 11-1")[0]
