# -*- coding: utf-8 -*-
"""검색 주소 생성기 - search_url 템플릿({kw}, {page})로는 표현할 수 없는 사이트용.

Site.search_builder 에 이름을 적으면 crawler_core.fetch_search_page 가 이 모듈의 함수로 (검색어, 페이지) -> URL 을 만든다.
각 생성기는 사이트에서 실제로 확인한 규칙을 그대로 따른다 (docstring 에 근거를 적는다).
"""
import base64
from typing import Callable, Dict
from urllib.parse import quote


def _b64(s: str) -> str:
    return base64.b64encode(s.encode("ascii")).decode()


def iksan_package(site, keyword: str, page: int) -> str:
    """익산신문 패키지 솔루션 (default/search_list.php): 익산·의령·경산·고성·청도·영덕·창녕·횡성 ...
    - 검색어는 그 사이트의 검색 인코딩(Site.search_encoding, 없으면 encoding, 그것도 없으면 EUC-KR)으로 퍼센트 인코딩해야 한다 (틀리면 키워드를 무시하고 홈 화면 위젯만 돌려준다).
    - 1쪽: ?s_mode=1&area_part=&time=1&start_day=&end_day=&part_idx=&search_order=<EUC-KR 검색어>
    - 2쪽부터: ?board_data=<base64('startPage%3D' + 시작위치)>||&search_items=<base64(검색 조건)>|| (한 페이지 20건, 시작위치 0,20,40 ...)
      (사이트가 만든 '[2]' 링크를 해독해서 확인한 규칙. page= 같은 파라미터는 무시된다.)
    """
    base = site.search_url.split("?")[0]
    enc = (site.search_encoding or site.encoding or "euc-kr").lower()     # 사이트마다 다르다: 익산신문은 EUC-KR, 의령신문 등은 UTF-8
    k = quote(keyword.encode(enc, errors="ignore"))
    if page <= 1:
        return f"{base}?s_mode=1&area_part=&time=1&start_day=&end_day=&part_idx=&search_order={k}"
    items = (f"part_idx%3D%26mult%3D%26group_id%3D%26s_mode%3D1%26reporter%3D%26start_day%3D%26end_day%3D"
             f"%26search_order%3D{k}%26area_part%3D")
    return f"{base}?board_data={_b64('startPage%3D' + str((page - 1) * 20))}||&search_items={_b64(items)}||"


def ismart_package(site, keyword: str, page: int) -> str:
    """칠곡신문(ismartnews.com/news/search.php): 익산신문 패키지와 같은 board_data/search_items 방식이지만 검색어는 UTF-8 이고
    search_items 끝에 필드가 더 붙는다(search_old, writer, writer_name, day_auto). 사이트가 만든 '[2]' 링크를 해독해 확인했다.
    1쪽: ?search_order=<검색어>   /   2쪽부터: ?board_data=<base64('startPage%3D' + 시작위치)>||&search_items=<base64(조건)>|| (20건씩)
    """
    base = site.search_url.split("?")[0]
    enc = (site.search_encoding or site.encoding or "utf-8").lower()
    k = quote(keyword.encode(enc, errors="ignore"))
    if page <= 1:
        return f"{base}?search_order={k}"
    items = (f"part_idx%3D%26mult%3D%26group_id%3D%26s_mode%3D%26reporter%3D%26start_day%3D%26end_day%3D"
             f"%26search_order%3D{k}%26area_part%3D%26search_old%3D%26writer%3D%26writer_name%3D%26day_auto%3D")
    return f"{base}?board_data={_b64('startPage%3D' + str((page - 1) * 20))}||&search_items={_b64(items)}||"


BUILDERS: Dict[str, Callable] = {"iksan_package": iksan_package, "ismart_package": ismart_package}
