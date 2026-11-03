"""선택자 호환성 방어 테스트.

2026-11-03 운영(GitHub 러너, soupsieve 3.x)에서 ':not(:has(table td.x))' 같은 복합 선택자가 SelectorSyntaxError 로 거부되어
신문사 4곳이 키워드 11개 전부 실패했다. 개발 PC 의 soupsieve 2.5 는 같은 선택자를 통과시켜 로컬 테스트로는 못 잡았다.
그래서 (1) 어느 버전에서도 문제 되는 구문을 정적으로 금지하고, (2) 현재 설치된 soupsieve 로 모든 선택자를 컴파일해 본다.
"""
import glob, importlib, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import soupsieve
from common.crawler_core import Site
from common.verified_selectors import VERIFIED_SELECTORS as V

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEL_FIELDS = ("list_item_sel", "list_title_sel", "list_title_text_sel", "list_date_sel", "article_date_sel", "article_body_sel", "list_item_parent")


def all_sites():
    out = []
    for f in sorted(glob.glob(os.path.join(HERE, "regions", "12_*.py"))):
        out += importlib.import_module(f"regions.{os.path.basename(f)[:-3]}").SITES
    return out


def selectors():
    for s in all_sites():
        for fld in SEL_FIELDS:
            val = getattr(s, fld, "")
            if val:
                yield s.name, fld, val
    for name, ov in V.items():
        for fld in SEL_FIELDS:
            if ov.get(fld):
                yield name, fld, ov[fld]


def test_no_complex_selectors_inside_not_or_has():
    # ':not(...)' 안에 ':has(...)' 나 공백(자손)·쉼표가 든 복합 선택자, ':has(...)' 안에 쉼표/자손 결합자는 최신 soupsieve 가 거부한다
    bad = []
    for name, fld, sel in selectors():
        if re.search(r":not\([^)]*:has\(", sel) or re.search(r":has\([^)]*[ ,>+~]", sel) or re.search(r":not\([^)]*[ ,>+~]", sel):
            bad.append((name, fld, sel))
    assert not bad, bad


def test_every_selector_compiles_with_the_installed_soupsieve():
    bad = []
    for name, fld, sel in selectors():
        try:
            soupsieve.compile(sel)
        except Exception as e:                                   # noqa: BLE001
            bad.append((name, fld, sel, type(e).__name__))
    assert not bad, bad


def test_list_item_parent_replaces_has_for_table_layouts():
    for name in ("익산신문", "의령신문", "경산신문", "고성신문", "청도신문", "창녕신문", "횡성뉴스", "금산신문"):
        assert V[name]["list_item_parent"] == "table" and ":has(" not in V[name]["list_item_sel"], name
    s = next(x for x in all_sites() if x.name == "음성타임즈")
    assert s.list_item_parent == "table" and ":has(" not in s.list_item_sel
