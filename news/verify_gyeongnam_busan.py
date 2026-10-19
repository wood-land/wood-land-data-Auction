"""
verify_gyeongnam_busan.py - 경남·부산 신문사 23개 전 매체 실측 검증 스크립트

실행:
    python verify_gyeongnam_busan.py
"""
import importlib
import requests
from bs4 import BeautifulSoup
import urllib.parse
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from crawler_core import parse_list

mod = importlib.import_module("regions.12_6_gyeongnam_busan")
SITES = mod.SITES

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def verify_all():
    print(f"=== 경남·부산 권역 {len(SITES)}개 언론사 정밀 실측 검증 시작 ===")
    results = []

    for site in SITES:
        name = site.name
        area = site.default_area
        keyword = "보상"
        page = 1
        
        try:
            if site.search_method == "POST":
                data = {}
                for k, v in site.search_form_data:
                    val = v.format(kw=keyword, page=page, page_index=page-1)
                    if site.encoding:
                        val = val.encode(site.encoding)
                    data[k] = val
                r = requests.post(site.search_url, data=data, headers=HEADERS, timeout=10, verify=False)
            else:
                url = site.search_url.format(kw=urllib.parse.quote(keyword), page=page)
                r = requests.get(url, headers=HEADERS, timeout=10, verify=False)

            if site.encoding:
                r.encoding = site.encoding
            elif r.encoding == 'ISO-8859-1' or not r.encoding:
                r.encoding = r.apparent_encoding or 'utf-8'

            items = parse_list(r.text, r.url, site)
            if not items:
                print(f"[-] {name} ({area}): FAIL - 검색 결과 기사 링크 0건")
                results.append((name, area, "FAIL", "0 links", 0, 0))
                continue

            sample = items[0]
            ar = requests.get(sample["link"], headers=HEADERS, timeout=10, verify=False)
            if site.encoding:
                ar.encoding = site.encoding
            elif ar.encoding == 'ISO-8859-1' or not ar.encoding:
                ar.encoding = ar.apparent_encoding or 'utf-8'

            asoup = BeautifulSoup(ar.text, 'html.parser')
            body_el = asoup.select_one(site.article_body_sel)
            body_len = len(body_el.get_text(strip=True)) if body_el else 0

            date_el = asoup.select_one(site.article_date_sel)
            date_txt = date_el.get_text(strip=True) if date_el else ""

            if body_len > 100:
                print(f"[+] {name} ({area}): PASS - 기사 {len(items)}건, 본문 {body_len}자, 날짜: {date_txt[:25]}")
                results.append((name, area, "PASS", f"{len(items)} links, {body_len} chars", len(items), body_len))
            else:
                print(f"[!] {name} ({area}): WARN - 기사 {len(items)}건, 본문 부족({body_len}자)")
                results.append((name, area, "WARN", f"{len(items)} links, {body_len} chars", len(items), body_len))

        except Exception as e:
            print(f"[!] {name} ({area}): ERROR - {e}")
            results.append((name, area, "ERROR", str(e), 0, 0))

    passed = sum(1 for r in results if r[2] == "PASS")
    print(f"\n==================================================")
    print(f"검증 완료: {passed} / {len(SITES)} 성공 (성공률: {passed/len(SITES)*100:.1f}%)")
    print(f"==================================================")

if __name__ == "__main__":
    verify_all()

