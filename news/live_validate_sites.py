from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin
import csv, importlib, sys
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
KEYWORD = chr(0xBCF4) + chr(0xC0C1)
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; NewsSiteStructureCheck/1.0)'}

def check(site):
    url = site.search_url.format(kw=requests.utils.quote(KEYWORD), page=1)
    row = {'site': site.name, 'search_url': url, 'fetch': site.fetch,
           'http_status': '', 'list_matches': '', 'title_matches': '',
           'article_url': '', 'article_status': '', 'date_matches': '',
           'body_matches': '', 'date_fallback': '', 'control_matches': '', 'search_filter': '', 'page_title': '', 'result': '', 'error': ''}
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        row['http_status'] = response.status_code
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        row['page_title'] = soup.title.get_text(' ', strip=True)[:100] if soup.title else ''
        items = soup.select(site.list_item_sel)
        row['list_matches'] = len(items)
        candidates = []
        for item in items:
            anchor = item.select_one(site.list_title_sel)
            if anchor:
                title = anchor.get_text(' ', strip=True)
                href = anchor.get('href', '')
                if href:
                    candidates.append((title, urljoin(response.url, href)))
        row['title_matches'] = len(candidates)
        if candidates:
            row['article_url'] = candidates[0][1]
            article = requests.get(row['article_url'], headers=HEADERS, timeout=15)
            row['article_status'] = article.status_code
            article.raise_for_status()
            art = BeautifulSoup(article.text, 'html.parser')
            row['date_matches'] = len(art.select(site.article_date_sel)) if site.article_date_sel else 0
            row['date_fallback'] = len(art.select('time, [itemprop="datePublished"], [itemprop="dateModified"], meta[property*="date"], .date, .date-info, .byline, p.info, ul.info'))
            row['body_matches'] = len(art.select(site.article_body_sel)) if site.article_body_sel else 0
        control_url = site.search_url.format(kw='zzqvnonexistent987654', page=1)
        control = requests.get(control_url, headers=HEADERS, timeout=15)
        control.raise_for_status()
        control_soup = BeautifulSoup(control.text, 'html.parser')
        row['control_matches'] = len(control_soup.select(site.list_item_sel))
        row['search_filter'] = 'FILTERED' if int(row['list_matches']) > int(row['control_matches']) else 'INCONCLUSIVE'
        row['result'] = 'OK' if candidates and (not site.article_body_sel or row['body_matches']) and row['search_filter'] == 'FILTERED' else 'SELECTOR_REVIEW'
    except Exception as exc:
        row['result'] = 'BLOCKED_OR_ERROR'
        row['error'] = f'{type(exc).__name__}: {exc}'
    return row

def main():
    modules = [importlib.import_module('regions.' + p.stem)
               for p in sorted((ROOT / 'regions').glob('region_*.py'))]
    sites = [site for module in modules for site in module.SITES]
    rows = []
    for site in sites:
        if not site.enabled:
            rows.append({'site': site.name, 'search_url': site.search_url, 'fetch': site.fetch,
                         'http_status': '', 'list_matches': '', 'title_matches': '',
                         'article_url': '', 'article_status': '', 'date_matches': '',
                         'body_matches': '', 'date_fallback': '', 'control_matches': '',
                         'search_filter': 'SKIPPED_DISABLED', 'page_title': '',
                         'result': 'SKIPPED_DISABLED', 'error': site.disabled_reason})
        else:
            rows.append(check(site))
    target = ROOT / 'live_validation_2026-09-25.csv'
    with target.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys() if rows else ['result'])
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        print(f"{row['site']}\t{row['result']}\tsearch={row['http_status']}\titems={row['list_matches']}\tcontrol={row['control_matches']}\tfilter={row['search_filter']}\tdate={row['date_matches']}\tbody={row['body_matches']}\t{row['page_title']}\t{row['error'][:140]}")
    print(f'Wrote {target}')

if __name__ == '__main__':
    main()

