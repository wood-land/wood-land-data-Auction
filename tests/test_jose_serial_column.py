"""세목조서 첫 열 '지번 순번'(연번)을 지번으로 읽지 않는지 확인한다.
의성군 안평천 하천재해예방사업 세목조서(2026-11-15 실측): 연번 1,2,3… 이 지번으로 저장돼 경매 물건(하령리 391)과 겹친 것으로 잘못 나왔다."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gosi"))
from core import jose_extractor as j  # noqa: E402


def _grid():
    head1 = ["지번\n순번", "소재지", "당초지번", "편입지번", "공부\n지목", "실제\n이용", "당초면적\n(㎡)", "편입면적\n(㎡)", "소유자 및 공유자", "", "", "", ""]
    head2 = ["", "", "", "", "", "", "", "", "성명", "소유형태", "소유지분", "", "송달주소"]
    rows = [[290, "의성군 안평면 하령리", "202", "202-1", "답", "", 1564, 67, "경상북도", "", "", "", ""],
            [291, "의성군 안평면 하령리", "203", "203-3", "답", "", 900, 478, "경상북도", "", "", "", ""],
            [292, "의성군 안평면 하령리", "204", "204", "답", "", 800, 300, "경상북도", "", "", "", ""]]
    return [head1, head2] + [[str(c) for c in r] for r in rows]


def test_serial_column_is_not_jibun():
    rows, _ = j.rows_from_document_grids([(1, 0, _grid())], "x.xlsx", "")
    got = [r["jibun_incl"] for r in rows]
    assert "290" not in got and "291" not in got
    assert got == ["202-1", "203-3", "204"]
