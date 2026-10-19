"""
cities/gwanbo.py — 대한민국 전자관보(gwanbo.go.kr) 고시·공고 게시판 목록.

2026-09-27 실측 확인:
  - 대한민국 전자관보는 정부 및 지자체의 고시·공고·령·법률 등을 포괄하여 발행한다.
  - 토지보상 및 도시계획/개발사업과 직접 연관된 카테고리:
      1) 고시 (category_order: 10) - 국토교통부, 환경청, 산림청 등 도로/하천/산업단지 지정 및 지형도면 고시
      2) 공고 (category_order: 11) - 보상계획 공고, 사업인정 의견청취 공고 등
      3) 지방자치단체 (category_order: 18) - 각 시/도 및 시/군/구의 관보 게재 고시·공고
  - 어댑터: cms_adapters.gwanbo_board

토지조서(regions) 연동:
  - 전자관보는 게시글마다 소재지가 전국 각지로 달라져 지자체 1곳짜리 Regions를 고정으로
    못 쓴다 — 대신 core.region_registry.resolve_regions_for_title을 넣어 둔다(콜러블).
    core.board_crawler.download_jose_rows가 게시글 title로 이 함수를 호출해, 제목에서
    cities/*.py에 이미 등록된 시군구 이름을 찾으면 그 Regions를 재사용하고(읍면리 데이터가
    이미 검증돼 있어 정확도가 높다), 못 찾으면 None을 돌려줘 그 건만 조용히 건너뛴다
    (law.md 3-2 — 등록 안 된 지역까지 임의로 추측해서 맞추지 않는다).
"""
from core.board_crawler import City
from core.region_registry import resolve_regions_for_title

from cities._shared import DEFAULT_BLACKLIST, DEFAULT_KEYWORDS

PROVINCE_NAME = "관보"

GWANBO = City(
    province="대한민국",
    city="전자관보",
    base_url="https://gwanbo.go.kr",
    boards=[
        {"name": "고시", "category_order": 10},
        {"name": "공고", "category_order": 11},
        {"name": "지방자치단체", "category_order": 18},
    ],
    keywords=DEFAULT_KEYWORDS,
    blacklist=DEFAULT_BLACKLIST,
    regions=resolve_regions_for_title,
    adapter="gwanbo_board",
)

CITIES = [GWANBO]
