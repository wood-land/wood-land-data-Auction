# -*- coding: utf-8 -*-
r"""
diagnose_dates.py - 신문사 기사 페이지의 '날짜 위치'를 분석해, 검증된 article_date_sel 을 제안한다.

왜 필요한가
  선택자를 'td, span, div' 처럼 넓게 잡으면 사이트 머리말의 현재 시각이 기사 날짜로 읽혀, 2008년 기사도 '오늘 입력'으로
  수집된다. 신문사마다 HTML 이 달라 사람이 129곳을 일일이 보기 어렵다 -> 기사 몇 개를 실제로 열어 자동으로 분석한다.

동작 (신문사 1곳)
  1. 검색 결과에서 기사 N개(기본 5)를 골라 연다.
  2. 기사마다 '정답 날짜'를 구한다: 메타 태그/JSON-LD 발행일 > '입력/등록/승인/작성일' 라벨 날짜.
  3. 날짜가 들어 있는 요소를 모두 찾아 후보 선택자를 만들고, 모든 기사에서 정답과 대조한다.
     정답이 없는 사이트는 '기사마다 다른 날짜인가 / 머리말·하단이 아닌가 / 제목 근처인가' 로 고른다.
  4. 지금 설정(파이프라인 전체)이 정답과 맞는지 판정하고, 더 나은 선택자를 제안한다.

사용 예
  python diagnose_dates.py 경남일보                  # 신문사 이름
  python diagnose_dates.py --region 경남 --json out.json
  python diagnose_dates.py --all --json out.json     # requests 방식 전체
판정: OK(정답과 일치) / RESCUED(선택자는 틀리지만 메타가 구해 줌) / FIX(틀림) / UNVERIFIED(정답 없음) / FAIL(기사를 못 가져옴)
"""
import argparse
import glob
import importlib
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from bs4 import BeautifulSoup, NavigableString  # noqa: E402

from common.crawler_core import (  # noqa: E402
    Crawler, FetchError, RequestsFetcher, Settings, Site, _ANY_DATE_RE, _fmt, _meta_dates,
    clean_popup_elements, date_from_element, parse_article, parse_article_dates_ex, parse_list)

# 기사 발행일을 뜻하는 라벨 ('게재일'은 지면에 실린 날짜라 제외, '최종편집/수정'은 기사 날짜가 아니다)
_LABEL_RE = re.compile(r"(?:입력|등록일?|승인|작성일?|기사입력|발행일|송고|최초등록|작성)\s*[:：.]?\s*"
                       r"((?:20)?\d{2})\s*[-./년]\s*(\d{1,2})\s*[-./월]\s*(\d{1,2})")
_SKIP_ANCESTOR = re.compile(r"header|nav|footer|gnb|aside|sidebar|banner|popup|ranking|related|weather|clock|today", re.I)
_BAD_CLASS = re.compile(r"^(clearfix|cf|clear|fl|fr|left|right|first|last|on|active|\d)", re.I)
KEYWORDS = ("보상", "사업", "일대", "주민")
META_SELECTORS = ("meta[property='article:published_time']", "meta[property='og:pubdate']", "meta[name='pubdate']",
                  "meta[name='regDate']", "meta[name='article:published_time']")


def _norm_year(y: str) -> str:
    return y if len(y) == 4 else "20" + y


def _text_dates(text: str) -> List[str]:
    return [_fmt(m) for m in _ANY_DATE_RE.finditer(text or "")]


def label_date(soup: BeautifulSoup) -> Optional[str]:
    for t in soup(["script", "style"]):
        t.decompose()
    m = _LABEL_RE.search(re.sub(r"\s+", " ", soup.get_text(" ")))
    if not m:
        return None
    return f"{_norm_year(m.group(1))}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def _selectors_for(el) -> List[str]:
    """요소 1개를 가리키는 후보 선택자들 (짧고 안정적인 것부터)."""
    out: List[str] = []
    tag = el.name
    eid = el.get("id")
    if eid and not re.search(r"\d{3,}", eid):
        out.append(f"#{eid}")
    classes = [c for c in (el.get("class") or []) if not _BAD_CLASS.match(c) and len(c) <= 30]
    cls = "." + ".".join(classes) if classes else ""
    if classes:
        out.append(f"{tag}{cls}")
        par = el.parent
        if par is not None and par.name not in ("[document]", "html", "body"):
            pcls = [c for c in (par.get("class") or []) if not _BAD_CLASS.match(c) and len(c) <= 30]
            pid = par.get("id")
            if pid and not re.search(r"\d{3,}", pid):
                out.append(f"#{pid} {tag}{cls}")
            elif pcls:
                out.append(f"{par.name}.{'.'.join(pcls)} {tag}{cls}")
    for attr in ("bgcolor", "align", "width"):
        v = el.get(attr)
        if v and not classes and tag in ("td", "div", "span", "p", "li", "font", "strong", "em", "b"):
            out.append(f'{tag}[{attr}="{v}"]')
    if not classes and tag not in ("td", "font", "div", "span", "b", "strong", "em", "i", "a"):
        out.append(tag)
    seen, uniq = set(), []
    for s in out:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq


def _in_chrome(el) -> bool:
    """머리말/내비/하단/사이드/배너 안에 있는 요소인가."""
    p = el
    for _ in range(12):
        if p is None or p.name in ("[document]",):
            break
        ident = " ".join([p.get("id") or "", " ".join(p.get("class") or [])])
        if p.name in ("header", "nav", "footer", "aside") or _SKIP_ANCESTOR.search(ident):
            return True
        p = p.parent
    return False


def collect_candidates(soup: BeautifulSoup) -> Dict[str, object]:
    """날짜가 들어 있는 텍스트 노드의 부모(최대 3단계, 텍스트가 짧은 것) -> {선택자: 요소}"""
    cands: Dict[str, object] = {}
    for node in soup.find_all(string=_ANY_DATE_RE):
        if not isinstance(node, NavigableString) or node.parent is None:
            continue
        el = node.parent
        for _ in range(3):
            if el is None or el.name in ("[document]", "html", "body"):
                break
            if len(el.get_text(" ", strip=True)) <= 90:
                for sel in _selectors_for(el):
                    cands.setdefault(sel, el)
            el = el.parent
    return cands


class Page:
    def __init__(self, link: str, title: str, html: str):
        self.link, self.title, self.html = link, title, html
        self.soup = BeautifulSoup(html, "html.parser")
        clean_popup_elements(self.soup)
        m_in, _ = _meta_dates(self.soup, html)
        self.gt_meta = m_in
        self.gt_label = label_date(BeautifulSoup(html, "html.parser"))
        self.gt = self.gt_meta or self.gt_label
        self.gt_kind = "meta" if self.gt_meta else ("label" if self.gt_label else "")
        body = self.soup.body or self.soup
        self.order = {id(e): i for i, e in enumerate(body.find_all(True))}
        self.title_pos = self._find_title_pos(body)

    def _find_title_pos(self, body) -> Optional[int]:
        key = re.sub(r"\s+", "", self.title)[:10]
        if len(key) < 4:
            return None
        for node in body.find_all(string=True):
            if key in re.sub(r"\s+", "", str(node)) and node.parent is not None:
                return self.order.get(id(node.parent))
        return None

    def sel_date(self, sel: str) -> Tuple[Optional[str], bool, Optional[object]]:
        try:
            el = self.soup.select_one(sel)
        except Exception:
            return None, False, None
        if el is None:
            return None, False, None
        ins, _mod, labeled = date_from_element(el)      # 파이프라인과 같은 규칙(큰 요소는 날짜 위치로 안 믿음)
        return ins, labeled, el


def pick_samples(site: Site, fetcher, crawler: Crawler, n: int, with_pages: bool = False):
    """검색 결과에서 기사 n개를 고른다. with_pages=True 면 (샘플, 검색 결과 페이지 [(url, html)]) 를 돌려준다."""
    items: List[dict] = []
    searched: List[Tuple[str, str]] = []
    for kw in KEYWORDS:
        for page in (1, 2):
            try:
                url, html = crawler.fetch_search_page(site, kw, page, fetcher, timeout=12, strict=False)
            except FetchError:
                break
            got = parse_list(html, url, site)
            if not got:
                break
            searched.append((url, html))
            seen = {i["link"] for i in items}
            items += [i for i in got if i["link"] not in seen]
        if len(items) >= 12:
            break
    step = max(1, len(items) // n) if items else 1
    samples = [(i["link"], i["title"]) for i in items[::step][:n]]
    return (samples, searched) if with_pages else samples


def score_candidate(sel: str, pages: List[Page]) -> dict:
    dates, labeled, hits, chrome = [], 0, 0, 0
    gt_pages = [p for p in pages if p.gt]
    ok = 0
    near = []
    for p in pages:
        d, lab, el = p.sel_date(sel)
        dates.append(d)
        if d:
            hits += 1
            labeled += bool(lab)
            if el is not None and _in_chrome(el):
                chrome += 1
            if p.gt and d == p.gt:
                ok += 1
            if el is not None and p.title_pos is not None and id(el) in p.order:
                near.append(p.order[id(el)] - p.title_pos)
    got = [d for d in dates if d]
    return {
        "sel": sel, "dates": dates, "coverage": hits / len(pages),
        "accuracy": (ok / len(gt_pages)) if gt_pages else None,
        "labeled": labeled / max(1, hits), "distinct": len(set(got)),
        "chrome": chrome, "near_title": (sum(abs(x) for x in near) / len(near)) if near else None,
    }


def rank_key(c: dict, n_pages: int, has_gt: bool):
    acc = c["accuracy"] if c["accuracy"] is not None else 0.0
    spread_ok = c["distinct"] >= 2 or n_pages < 3
    near = c["near_title"] if c["near_title"] is not None else 9999
    if has_gt:
        # 정답이 메타 태그에서 나온 사이트는 메타 선택자가 가장 튼튼하다 (HTML 구조가 바뀌어도 유지됨)
        return (-acc, -c["coverage"], c["chrome"] > 0, not spread_ok, not c["sel"].startswith("meta["), -c["labeled"], len(c["sel"]))
    # 정답이 없으면: 머리말 밖 > 기사마다 날짜가 다름 > 라벨 > 제목에 가까움
    return (c["chrome"] > 0, -c["coverage"], not spread_ok, -c["labeled"], near, len(c["sel"]))


def analyze_site(region: str, site: Site, samples: int = 5) -> dict:
    res = {"region": region, "paper": site.name, "sel": site.article_date_sel, "verdict": "FAIL", "pages": 0}
    fetcher = RequestsFetcher()
    crawler = Crawler(Settings(save_directory=os.devnull, keywords=["보상"]))
    try:
        links, searched = pick_samples(site, fetcher, crawler, samples, with_pages=True)
        pages: List[Page] = []
        for link, title in links:
            try:
                html = fetcher.get(link, timeout=20, strict=True, encoding=site.encoding)
            except FetchError:
                continue
            pages.append(Page(link, title, html))
        res["pages"] = len(pages)
        res["links"] = [p.link for p in pages]
        if len(pages) < 2:
            res["note"] = "기사 페이지를 2개 이상 가져오지 못함"
            return res
        gt_pages = [p for p in pages if p.gt]
        has_gt = bool(gt_pages)
        res["gt"] = [p.gt for p in pages]
        res["gt_kind"] = [p.gt_kind for p in pages]

        pipe = [parse_article(p.html, site)["input_date"] for p in pages]
        pipe_ok = (sum(1 for p, d in zip(pages, pipe) if p.gt and d == p.gt) / len(gt_pages)) if has_gt else None
        cur = score_candidate(site.article_date_sel, pages)
        res["current"] = {"pipeline_dates": pipe, "pipeline_acc": pipe_ok, "selector_acc": cur["accuracy"],
                          "selector_dates": cur["dates"], "selector_coverage": cur["coverage"]}

        cand_sels = {}
        for p in pages:
            for s, el in collect_candidates(p.soup).items():
                cand_sels.setdefault(s, 0)
                cand_sels[s] += 1
        # 여러 기사에서 공통으로 나오는 선택자만 (기사마다 구조가 같아야 한다)
        pool = [s for s, k in cand_sels.items() if k >= max(2, len(pages) // 2 + 1)]
        pool += list(META_SELECTORS)
        scored = [score_candidate(s, pages) for s in pool]
        scored = [c for c in scored if c["coverage"] >= 0.6]
        scored.sort(key=lambda c: rank_key(c, len(pages), has_gt))
        best = scored[0] if scored else None
        if best and has_gt and best["accuracy"] != 1.0:
            best = None            # 정답이 있는데 맞지 않는 제안은 내지 않는다
            res["note"] = "정답과 일치하는 선택자를 찾지 못함"
        if best:
            res["proposal"] = {k: best[k] for k in ("sel", "dates", "coverage", "accuracy", "labeled", "distinct", "chrome", "near_title")}
            # 메타 선택자가 1순위여도, 메타가 없는 기사를 위해 '눈에 보이는 라벨 날짜 요소'를 대비책으로 함께 제안한다
            fb = [c for c in scored if not c["sel"].startswith("meta[") and c["coverage"] == 1.0 and c["labeled"] >= 0.8
                  and c["chrome"] == 0 and (c["accuracy"] == 1.0 or not has_gt)]
            if best["sel"].startswith("meta[") and fb:
                res["fallback"] = fb[0]["sel"]
            res["final_sel"] = best["sel"] + (f", {res['fallback']}" if res.get("fallback") else "")
        truth = {p.link: (p.gt or d) for p, d in zip(pages, pipe)}
        res["list"] = analyze_list(site, searched, truth)
        seq = [truth[l] for l in res["links"] if truth.get(l)]          # 목록 위치 순서대로의 표본 기사 날짜
        pairs = list(zip(seq, seq[1:]))
        if pairs:
            res["sample_order_desc"] = round(sum(1 for a, b in pairs if a >= b) / len(pairs), 2)
            res["sample_dates"] = seq
        sel_ok = cur["accuracy"] == 1.0 and cur["coverage"] == 1.0
        if has_gt:
            if pipe_ok == 1.0 and sel_ok:
                res["verdict"] = "OK"
            elif pipe_ok == 1.0:
                res["verdict"] = "RESCUED"
            else:
                res["verdict"] = "FIX"
        else:
            res["verdict"] = "UNVERIFIED"
        return res
    except Exception as e:                      # 한 신문사의 오류가 전체 진단을 멈추지 않게
        res["note"] = f"{e.__class__.__name__}: {e}"
        return res
    finally:
        fetcher.close()


_SHORT_DATE = re.compile(r"^\D{0,12}\d{2,4}\s*[-./년]\s*\d{1,2}\s*[-./월]\s*\d{1,2}일?(?:\s*\(?[월화수목금토일]\)?)?"
                         r"(?:\s*\d{1,2}:\d{2}(?::\d{2})?)?\D{0,6}$")


def analyze_list(site: Site, searched: List[Tuple[str, str]], truth: Dict[str, Optional[str]]) -> dict:
    """검색 결과 목록에서 '기사 날짜' 칸을 찾아 list_date_sel 을 제안하고, 결과가 최신순인지 판정한다.
    칸의 날짜가 (표본 기사의) 정답 날짜와 모두 일치해야 제안한다."""
    from urllib.parse import urljoin
    from common.crawler_core import parse_list_date
    blocks = []
    for url, html in searched:
        soup = BeautifulSoup(html, "html.parser")
        clean_popup_elements(soup)
        for block in soup.select(site.list_item_sel):
            a = block.select_one(site.list_title_sel)
            if a is None or not a.get("href"):
                continue
            link = urljoin(url, a["href"].strip())
            if site.link_contains and site.link_contains not in link:
                continue
            blocks.append((block, link))
    out: dict = {"blocks": len(blocks), "current_sel": site.list_date_sel}
    if len(blocks) < 3:
        return out
    cands: Dict[str, int] = {}
    for block, _ in blocks[:15]:
        for el in block.find_all(True):
            txt = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
            if len(txt) <= 40 and _SHORT_DATE.match(txt):
                kids = [c for c in (el.parent.find_all(True, recursive=False) if el.parent else []) if c.name == el.name]
                sels = _selectors_for(el)
                if not (el.get("class")) and el.parent is not None:
                    idx = [c for c in el.parent.find_all(True, recursive=False)].index(el) + 1
                    sels.append(f"{el.name}:nth-child({idx})")
                for s in sels:
                    cands[s] = cands.get(s, 0) + 1
    best = None
    known = [(i, truth[link]) for i, (_, link) in enumerate(blocks) if truth.get(link)]
    if site.list_date_sel:                      # 지금 설정이 맞는지도 확인한다
        cur_dates = []
        for block, _ in blocks:
            try:
                el = block.select_one(site.list_date_sel)
            except Exception:
                el = None
            cur_dates.append(parse_list_date(el.get_text(" ", strip=True)) if el is not None else None)
        out["current_coverage"] = round(sum(1 for d in cur_dates if d) / len(blocks), 2)
        out["current_ok"] = bool(known) and all(cur_dates[i] == g for i, g in known) and out["current_coverage"] >= 0.8
    for sel in cands:
        dates = []
        for block, _ in blocks:
            try:
                el = block.select_one(sel)
            except Exception:
                el = None
            dates.append(parse_list_date(el.get_text(" ", strip=True)) if el is not None else None)
        cov = sum(1 for d in dates if d) / len(blocks)
        if cov < 0.8:
            continue
        match = sum(1 for i, g in known if dates[i] == g)
        if known and match != len(known):
            continue
        key = (-cov, len(sel))
        if best is None or key < best[0]:
            best = (key, sel, dates, cov, len(known))
    if best:
        _, sel, dates, cov, nk = best
        out.update({"proposal": sel, "coverage": cov, "verified_on": nk, "dates": dates[:12]})
        seq = [d for d in dates if d]
        pairs = list(zip(seq, seq[1:]))
        if pairs:
            desc = sum(1 for a, b in pairs if a >= b) / len(pairs)
            asc = sum(1 for a, b in pairs if a <= b) / len(pairs)
            out["order"] = "desc" if desc >= 0.9 else ("asc" if asc >= 0.9 else "mixed")
            out["order_score"] = round(desc, 2)
    return out


def all_sites() -> List[Tuple[str, Site]]:
    out = []
    for f in sorted(glob.glob(os.path.join(HERE, "regions", "12_*.py"))):
        mod = importlib.import_module(f"regions.{os.path.basename(f)[:-3]}")
        out += [(mod.REGION_NAME, s) for s in mod.SITES]
    return out


def _span_days(dates: List[str]) -> int:
    import datetime
    ds = [datetime.date.fromisoformat(d) for d in dates if d]
    return (max(ds) - min(ds)).days if ds else 0


def _py(v) -> str:
    """파이썬 소스에 쓸 값 표기 (json.dumps 는 False 를 false 로 써서 파이썬 문법이 아니다)."""
    if isinstance(v, str):
        return '"' + v.replace(chr(92), chr(92) * 2).replace('"', chr(92) + '"') + '"'
    return repr(v)


def build_registry(results: List[dict], base: Dict[str, Dict[str, object]]) -> Dict[str, Dict[str, object]]:
    """진단 결과 -> 레지스트리. 기존 항목(base)에 합친다(이번 실행에서는 이미 레지스트리가 적용돼 'OK' 로 나오는 곳을 지우지 않도록).
      article_date_sel : 판정 FIX/RESCUED 이고 정답과 100% 일치하는 제안
      list_date_sel    : 검색 목록에서 정답과 100% 일치하는 날짜 칸을 찾았을 때. 지금 설정이 '날짜는 읽지만 틀린' 경우는 비운다
      newest_first     : 검색 결과가 최신순이 아님이 분명할 때(목록 날짜 또는 표본 기사 순서, 날짜 폭 14일 초과) False
    """
    reg = {k: dict(v) for k, v in base.items()}
    for r in results:
        name, ov = r["paper"], {}
        prop = r.get("proposal")
        if r["verdict"] in ("FIX", "RESCUED") and prop and prop.get("accuracy") == 1.0 and r.get("final_sel"):
            ov["article_date_sel"] = r["final_sel"].replace('"', "'")
        L = r.get("list") or {}
        cov_ok = L.get("coverage") == 1.0 and (L.get("verified_on") or 0) >= 5
        if L.get("proposal") and cov_ok and not L.get("current_ok"):
            ov["list_date_sel"] = L["proposal"].replace('"', "'")
        elif L.get("current_sel") and L.get("current_ok") is False and L.get("current_coverage", 0) >= 0.3 and not L.get("proposal"):
            ov["list_date_sel"] = ""                      # 틀린 날짜를 읽는 설정은 끈다 (최근 기사를 오래된 기사로 오판해 건너뛴다)
        order = L.get("order")
        if order in ("mixed", "asc"):
            ov["newest_first"] = False
        elif not order and r.get("sample_order_desc") is not None and r["sample_order_desc"] <= 0.7 and _span_days(r.get("sample_dates") or []) > 14:
            ov["newest_first"] = False
        if ov:
            reg.setdefault(name, {}).update(ov)
    return reg


def emit_registry(results: List[dict], path: str, base: Optional[Dict[str, Dict[str, object]]] = None):
    import datetime
    if base is None:
        from common.verified_selectors import VERIFIED_SELECTORS as base
    reg = build_registry(results, base)
    region = {r["paper"]: r["region"] for r in results}
    lines = ['# -*- coding: utf-8 -*-',
             '"""검증된 신문사별 설정 레지스트리 (diagnose_dates.py --emit-registry 로 생성, 기존 항목에 합쳐진다. 필요하면 손으로 다듬는다).',
             '',
             'Site(name=...) 가 만들어질 때 이 이름이 있으면 여기 값으로 덮어쓴다 (crawler_core.Site.__post_init__).',
             '  article_date_sel : 기사 페이지의 날짜. 기사 N개를 실제로 열어 메타 태그/라벨 날짜와 100% 일치함을 확인했다.',
             '                     메타 선택자가 앞에 오고, 메타가 없는 기사를 위해 눈에 보이는 날짜 요소가 뒤에 올 수 있다(문서에서 먼저 나오는 것이 선택됨).',
             '  list_date_sel    : 검색 목록의 날짜 칸. 표본 기사의 정답 날짜와 100% 일치할 때만 넣었다. 빈 문자열은 "틀린 날짜를 읽으므로 끔".',
             '  newest_first     : False 면 검색 결과가 최신순이 아니라는 뜻 (오래된 기사 연속 종료 규칙을 쓰지 않는다).',
             '"""',
             'from typing import Dict', '',
             'VERIFIED_SELECTORS: Dict[str, Dict[str, object]] = {']
    today = f"{datetime.date.today():%Y-%m-%d}"
    for name in sorted(reg, key=lambda n: (region.get(n, "~"), n)):
        body = ", ".join(f'"{k}": {_py(v)}' for k, v in reg[name].items())
        lines.append(f'    # {region.get(name, "")} | {today} 진단')
        lines.append(f'    "{name}": {{{body}}},')
    lines += ['}', '']
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    print(f"레지스트리 {len(reg)}곳 -> {path}")


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description="신문사 기사 날짜 위치 분석 / 선택자 제안")
    ap.add_argument("papers", nargs="*", help="신문사 이름")
    ap.add_argument("--region", help="지역 이름 일부 (예: 경남)")
    ap.add_argument("--all", action="store_true", help="활성 + requests 방식 전체")
    ap.add_argument("--samples", type=int, default=5)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--json", default="", help="결과를 JSON 으로 저장")
    ap.add_argument("--emit-registry", default="", metavar="PATH",
                    help="판정이 FIX/RESCUED 이고 정답과 100%% 일치하는 제안만 모아 검증 선택자 레지스트리(.py)로 쓴다")
    args = ap.parse_args()

    sites = [(r, s) for r, s in all_sites() if s.enabled and s.fetch == "requests"]
    if args.papers:
        sites = [(r, s) for r, s in all_sites() if s.name in args.papers]
    elif args.region:
        sites = [(r, s) for r, s in sites if args.region in r]
    elif not args.all:
        ap.error("신문사 이름, --region, --all 중 하나를 지정하세요")

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda rs: analyze_site(rs[0], rs[1], args.samples), sites))
    for r in results:
        prop = r.get("proposal") or {}
        cur = r.get("current") or {}
        print(f"[{r['verdict']:<10}] {r['region']} {r['paper']} | 기사 {r['pages']}개 | 현재 {r['sel']!r}"
              f" (파이프라인 정확도 {cur.get('pipeline_acc')}, 선택자만 {cur.get('selector_acc')})"
              f" -> 제안 {prop.get('sel')!r} (정확도 {prop.get('accuracy')}, 라벨 {prop.get('labeled')}) {r.get('note', '')}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=1)
    from collections import Counter
    print("\n판정 합계:", dict(Counter(r["verdict"] for r in results)))
    if args.emit_registry:
        emit_registry(results, args.emit_registry)


if __name__ == "__main__":
    main()
