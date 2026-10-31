# -*- coding: utf-8 -*-
r"""
health_check.py - 신문사별 '수집이 되고 있는가' 점검 (저장·DB 반영 없음)

신문사마다 검색 → 목록 → 기사 3단계를 실제로 한 번씩 밟아 보고, 아래 증상을 찾는다.
  FETCH_ERROR     검색 페이지를 못 가져옴(접속 시간 초과, 403, 500 ...)
  ZERO            '보상'·'토지' 모두 목록 0건 (검색 URL/목록 선택자 문제, 또는 정말 기사가 없음)
  IGNORES_KEYWORD 엉터리 검색어와 실제 검색어의 결과가 거의 같다 → 검색이 키워드를 무시한다 (예: 인코딩이 틀려 홈 화면 기사만 돌아옴)
  BLANK_TITLES    목록 제목이 비어 있는 항목이 30% 넘음
  NO_BODY         기사 본문을 못 읽음(50자 미만)
  NO_DATE         기사 날짜를 못 읽음
사용: python health_check.py --all --json out.json   /   python health_check.py 경남일보 음성타임즈
"""
import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from common.crawler_core import Crawler, RequestsFetcher, Settings, Site, parse_article, parse_list  # noqa: E402
from diagnose_dates import all_sites  # noqa: E402

NONSENSE = "ㅁㅁㅁ없는말ㅁㅁㅁ"


def check_site(region: str, site: Site) -> dict:
    res = {"region": region, "paper": site.name, "fetch": site.fetch, "flags": [], "note": ""}
    if site.fetch != "requests":
        res["flags"].append("SKIPPED_SELENIUM")
        return res
    f = RequestsFetcher()
    c = Crawler(Settings(save_directory=os.devnull, keywords=["보상"]))
    try:
        def search(kw):
            url, html = c.fetch_search_page(site, kw, 1, f, timeout=15)
            return url, parse_list(html, url, site)
        try:
            url, items = search("보상")
        except Exception as e:
            res["flags"].append("FETCH_ERROR")
            res["note"] = f"{e.__class__.__name__}: {str(e)[:60]}"
            return res
        res["n_real"] = len(items)
        try:
            _, items2 = search("토지")
        except Exception:
            items2 = []
        res["n_real2"] = len(items2)
        if not items and not items2:
            res["flags"].append("ZERO")
            return res
        try:
            _, junk = search(NONSENSE)
        except Exception:
            junk = []
        res["n_nonsense"] = len(junk)
        real_links = {i["link"] for i in items} | {i["link"] for i in items2}
        junk_links = {i["link"] for i in junk}
        if len(junk_links) >= 3 and real_links:
            overlap = len(real_links & junk_links) / len(junk_links)
            res["overlap"] = round(overlap, 2)
            if overlap >= 0.8:
                res["flags"].append("IGNORES_KEYWORD")
        allit = items or items2
        blank = sum(1 for i in allit if not i["title"].strip())
        res["blank_titles"] = f"{blank}/{len(allit)}"
        if allit and blank / len(allit) > 0.3:
            res["flags"].append("BLANK_TITLES")
        # 기사 1건 열기
        try:
            html = f.get(allit[0]["link"], timeout=20, strict=True, encoding=site.encoding)
            art = parse_article(html, site)
            res["body_len"] = len(art["body"]) if art["has_body_el"] else 0
            res["date"] = art["input_date"]
            if not art["has_body_el"] or len(art["body"]) < 50:
                res["flags"].append("NO_BODY")
            if not art["input_date"]:
                res["flags"].append("NO_DATE")
        except Exception as e:
            res["flags"].append("ARTICLE_FETCH_ERROR")
            res["note"] = f"{e.__class__.__name__}: {str(e)[:60]}"
        return res
    finally:
        f.close()


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("papers", nargs="*")
    ap.add_argument("--all", action="store_true", help="활성 신문사 전체")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    sites = [(r, s) for r, s in all_sites() if s.enabled]
    if args.papers:
        sites = [(r, s) for r, s in all_sites() if s.name in args.papers]
    elif not args.all:
        ap.error("신문사 이름 또는 --all")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda rs: check_site(*rs), sites))
    for r in results:
        if r["flags"]:
            print(f"[{','.join(r['flags'])}] {r['region']} {r['paper']} {r.get('note', '')} (실제검색 {r.get('n_real')}/{r.get('n_real2')}건, 엉터리 {r.get('n_nonsense')}건, 겹침 {r.get('overlap')})")
    from collections import Counter
    cnt = Counter(fl for r in results for fl in r["flags"])
    print(f"\n점검 {len(results)}곳 | 정상 {sum(1 for r in results if not r['flags'])}곳 | 증상별:", dict(cnt))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fp:
            json.dump(results, fp, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
