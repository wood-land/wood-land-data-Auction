# -*- coding: utf-8 -*-
"""검색 어댑터 - 검색 결과를 HTML 이 아니라 JSON API 로 주는(자바스크립트가 그려 주는) 사이트용.

어댑터는 (사이트, 검색어, 쪽, fetcher) -> (요청 URL, 목록 HTML) 을 돌려준다. JSON 을 기존 목록 파서(parse_list)가 읽을 수 있는
단순한 HTML 로 바꿔 주므로 나머지 수집 로직(날짜 판정, 연속 종료, 저장)은 그대로 쓴다.
각 어댑터의 docstring 에 확인한 근거(브라우저에서 본 실제 요청)를 적는다.
"""
import html
import json
import re
from typing import Callable, Dict, Iterable, Tuple


def _plain(text: str) -> str:
    """검색 API 는 검색어를 <b>보상</b> 처럼 강조해서 보낸다. 강조 태그를 걷고 HTML 엔티티를 풀어 순수한 제목으로 만든다."""
    # 강조에 쓰는 태그(b, em, strong, mark, span, font)만 걷는다. 제목에 원래 있는 <사업> 같은 꺾쇠 낱말은 지우면 안 된다.
    return html.unescape(re.sub(r"</?(?:b|em|strong|mark|span|font)(?:\s[^>]*)?>", "", text or "", flags=re.I)).strip()


def _li(link: str, title: str, date: str) -> str:
    title = _plain(title)
    return f'<li class="it"><a href="{html.escape(link, quote=True)}">{html.escape(title)}</a><span class="d">{html.escape(date)}</span></li>'


def _decode(raw: bytes) -> str:
    for enc in ("utf-8", "cp949"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def knnews_json(site, keyword: str, page: int, fetcher) -> Tuple[str, str]:
    """경남신문(knnews.co.kr): 검색 페이지(search_new/search2.php)가 자바스크립트로 JSON API 를 호출해 목록을 그린다.
    - POST https://search.knnews.co.kr/openSearch/totalSearch  (폼: startCount, listCount, page, total, sort=DATE/DESC, sfield, query)
    - 응답 JSON: {total, CONTENTS_LIST:[{ARTICLE_ID, ART_TITLE, PRESSDATE, ART_UPD_TIME, ...}]}  (헤더는 ISO-8859-1 이라 UTF-8 로 직접 해독)
    - 최신순(sort=DATE/DESC) 정렬을 지원한다. 한 번에 10건, startCount = (쪽-1)*10.
    브라우저로 검색 페이지를 열어 네트워크 요청과 사이트 스크립트를 읽어 확인했다(2026-10-31).
    """
    per = 10
    url = "https://search.knnews.co.kr/openSearch/totalSearch"
    data = {"startCount": str((page - 1) * per), "listCount": str(per), "page": str(page), "total": "1",
            "sort": "DATE/DESC", "sfield": "TITLE,CONTENTS", "query": keyword}
    raw = fetcher.post_raw(url, data=data, headers={"Referer": "https://www.knnews.co.kr/search_new/search2.php",
                                                    "Origin": "https://www.knnews.co.kr"}, timeout=25)
    j = json.loads(_decode(raw))
    items = j.get("CONTENTS_LIST") or []
    rows = [_li(f"https://www.knnews.co.kr/news/articleView.php?idxno={it.get('ARTICLE_ID') or it.get('DOCID')}",
                it.get("ART_TITLE") or "", it.get("PRESSDATE") or it.get("ART_CRE_TIME") or "") for it in items]
    return url, "<html><body><ul>" + "".join(rows) + "</ul></body></html>"


def jjan_rest(site, keyword: str, page: int, fetcher) -> Tuple[str, str]:
    """전북일보(jjan.kr): 검색 페이지(/search?searchText=)가 자바스크립트로 REST API 를 호출해 목록을 그린다. 서버가 주는 HTML 에는
    '오늘의 순위' 같은 고정 목록만 있어서 키워드와 무관한 같은 10건이 돌아온다.
    - GET https://www.jjan.kr/rest/search?searchText=<검색어>&searchType=all&from=&to=&page=<쪽>   (쪽은 1부터, 20건씩, 최신순)
    - 응답 JSON: {list:[{id, title, viewTitle, createDate, updateDate, releaseDate ...}], pages:{totalElements, totalPages}}
    - 기사 주소는 https://www.jjan.kr/article/<id>. 목록 날짜는 수정일(updateDate)을 쓴다(수정일 기준 사이트이므로 최근 수정된 기사를 건너뛰지 않기 위해).
    브라우저로 검색 페이지를 열어 실제 네트워크 요청을 읽어 확인했다(2026-10-31).
    """
    from urllib.parse import quote
    url = f"https://www.jjan.kr/rest/search?searchText={quote(keyword)}&searchType=all&from=&to=&page={page}"
    raw = fetcher.get_raw(url, headers={"Referer": "https://www.jjan.kr/search"}, timeout=25)
    j = json.loads(_decode(raw))
    rows = []
    for it in j.get("list") or []:
        date = (it.get("updateDate") or it.get("releaseDate") or it.get("createDate") or "")[:10] or f"{it['id'][:4]}-{it['id'][4:6]}-{it['id'][6:8]}"
        rows.append(_li(f"https://www.jjan.kr/article/{it['id']}", it.get("viewTitle") or it.get("title") or "", date))
    return url, "<html><body><ul>" + "".join(rows) + "</ul></body></html>"


ADAPTERS: Dict[str, Callable] = {"knnews_json": knnews_json, "jjan_rest": jjan_rest}
