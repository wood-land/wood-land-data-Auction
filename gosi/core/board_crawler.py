"""
board_crawler.py — 지자체 고시공고 게시판 크롤링 공통 루프.

지자체마다 다른 부분(게시판 URL·키워드·블랙리스트·법정동 목록)은 이 모듈에 넣지 않는다.
City(지자체 설정) + cms_adapters의 목록/상세 파서(어댑터)를 받아 동작하며, 새 지자체를
추가할 때(같은 어댑터를 쓰는 경우) 이 파일은 건드리지 않는 것이 원칙이다.
(wonju_crawler.py의 원주시 전용 루프를 지자체 무관하게 일반화한 것 — law.md 참고)

출력 레코드(records)는 지역 데이터 파이프라인 SQLite 설계의 gosigongo_notices 테이블과,
jose_rows는 gosigongo_jose_rows 테이블과 1:1로 대응하도록 필드를 맞춰 두었다. 지금은
CSV/JSONL로만 저장하지만, 이후 SQLite 적재 단계에서는 이 dict 리스트를 그대로
INSERT하면 된다 (records.jsonl / jose_rows.jsonl이 한 줄=한 행이라 그대로 쓰기 좋음).
"""
from __future__ import annotations

import csv
import datetime as dt
import importlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Union

import requests

from . import http_fetch, jose_extractor
from .ai_extract import AI_DOC
from .run_log import LOG
from .sqlite_store import post_key

# hwpx/docx/xlsx/pdf 는 core.jose_extractor 가 직접 읽는다. 옛 이진 .hwp 는 지원하지 않는다.
JOSE_SUPPORTED_EXT = {"hwpx", "xlsx", "xlsm", "docx", "pdf"}
# 안전장치: 어댑터가 날짜를 못 읽는 사이트(형식이 다르거나 구조가 안 맞음)를 만나면
# cutoff 판정이 걸리지 않아 게시판 전체를 끝까지 훑을 수 있다. 그런 사이트는 실제로는
# 코드를 고쳐야 하는 신호이지, 계속 요청을 보내야 할 이유가 아니다 (law.md 서버 부하 배려).
MAX_PAGES_PER_BOARD = 50


@dataclass
class City:
    """지자체 1곳의 설정. 지자체마다 다른 부분은 전부 여기에만 적는다."""

    province: str  # 예: "강원도"
    city: str  # 예: "원주시"
    base_url: str  # 게시판 URL을 만들 때 기준이 되는 사이트 루트
    boards: List[dict]  # [{"name": "공고", "bbsNo": 140, "key": 216}, ...] (어댑터별 형식)
    keywords: List[str]  # 화이트리스트 키워드 (데이터가 쌓이는 대로 계속 확장)
    blacklist: List[str] = field(default_factory=list)  # 화이트리스트에 걸려도 제외할 키워드
    # 토지조서 소재지 검증용. 보통은 Regions 인스턴스 하나(지자체 1곳 = 소재지 1곳 고정).
    # 전자관보처럼 게시글마다 소재지가 전국 각지로 달라지는 곳은 title(str) -> Optional[Regions]
    # 콜러블을 대신 넣을 수 있다(게시글 제목에서 등록된 시군구를 찾아 그 Regions를 재사용하고,
    # 못 찾으면 None을 돌려줘 그 건만 토지조서 추출을 건너뛴다 — cms_adapters/gwanbo_board.py 참고).
    regions: Optional[Union[jose_extractor.Regions, Callable[[str], Optional[jose_extractor.Regions]]]] = None
    adapter: str = "std_ezweb"  # cms_adapters/ 안의 모듈 이름
    # True면 키워드 필터 없이 게시판의 모든 글을 수집한다(블랙리스트는 그대로 적용, matched_keywords는
    # 키워드에 실제로 걸린 것만 담긴다). 게시판 자체가 보상 전용이라 모든 글이 대상인 곳(한국부동산원
    # 보상계획/협의 공고 등)용이다. 일반 공지 게시판에는 쓰지 않는다.
    match_all: bool = False


def _squash(text: str) -> str:
    """제목·키워드의 모든 공백(일반/전각/nbsp/탭)을 없앤다 - 지자체마다 띄어쓰기가 제각각이라 무시하고 비교한다."""
    return "".join((text or "").split())


def matched_keywords(title: str, keywords: List[str]) -> list:
    t = _squash(title)
    return [kw for kw in keywords if _squash(kw) in t]


def matches_blacklist(title: str, blacklist: List[str]) -> bool:
    t = _squash(title)
    return any(_squash(kw) in t for kw in blacklist)


def download_jose_rows(session, adapter, attachments, title, crawled_at, city: City, detail_url: str = "", problems: list = None) -> list:
    """첨부파일을 메모리로만 내려받아 토지조서 행을 뽑는다. 원본은 디스크에 저장하지 않고,
    파싱이 끝나면 즉시 버린다 (지원하지 않는 형식은 건너뛴다).

    city.regions가 콜러블(전자관보 등 전국 단위 출처)이면 이 게시글의 title로 호출해
    그때그때 맞는 Regions를 찾는다 — 매칭되는 시군구가 없으면 None을 돌려주므로 그 건은
    조용히 건너뛴다(전체 실패가 아니라 이 게시글만 해당, run_city의 gate와 별개로 안전).

    problems(리스트)를 주면 다운로드·해석 오류가 난 첨부의 원인코드를 거기에 담는다(처리 끝낸 글 기록에서 '다시 읽어야 할 글'을 가린다).
    첨부 1개마다 수집 로그(core/run_log.py)에 결과와 원인코드를 남긴다. 규칙으로 필지를 못 뽑으면
    DeepSeek(core/ai_extract.py)으로 한 번 더 읽는다."""
    regions = city.regions(title) if callable(city.regions) else city.regions
    if regions is None:
        return []
    rows = []
    for att in attachments:
        if att["ext"] not in JOSE_SUPPORTED_EXT:
            if att["ext"] in ("hwp", "hwpml"):
                LOG.doc(city.city, "고시공고", title, detail_url, att["name"], att["ext"], "건너뜀", 0, "UNSUPPORTED",
                        "구버전 .hwp 는 표 추출 불가")
            continue
        try:
            try:
                data = _download(session, adapter, att, None)
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code in (400, 401, 403) and detail_url:
                    data = _download(session, adapter, att, detail_url)  # Referer 가 없으면 막는 서버(가평군 실측)
                else:
                    raise
            if jose_extractor.not_a_document(data):  # 오류·이동 안내 페이지를 받은 것(통영시·해운대구 실측) - 다시 받도록 다운로드 실패로 기록한다
                raise requests.HTTPError(f"첨부 대신 문서가 아닌 응답 {len(data)}바이트")
            report = {}
            got = jose_extractor.extract_from_attachment(
                data, att["ext"], att["name"], title, regions,
                site_name=city.city, collected_at=crawled_at, ai=AI_DOC, report=report,
            )
            rows += got
            LOG.doc(city.city, "고시공고", title, detail_url, att["name"], att["ext"],
                    "성공" if got and report["code"] in ("OK", "ADDR_CHECK") else
                    ("AI보정" if report["code"] == "AI_USED" else
                     "건너뜀" if report["code"] in ("FORM", "NOT_LAND") else
                     "정상(필지 없음)" if report["code"] in ("NO_PARCELS", "ALL_PUBLIC") else "주의"),
                    len(got), report["code"],
                    f"표 {report['table_rows']}행/본문 {report['text_rows']}행/AI {report['ai_rows']}행"
                    + (f"; {report['detail']}" if report["detail"] else ""))
        except requests.RequestException as e:
            print(f"    [경고] 첨부파일 다운로드 실패: {att['name']} ({e})")
            if problems is not None:
                problems.append("DL_FAIL")
            LOG.doc(city.city, "고시공고", title, detail_url, att["name"], att["ext"], "실패", 0, "DL_FAIL",
                    f"{type(e).__name__}: {str(e)[:200]}")
        except ImportError as e:
            print(f"    [경고] 라이브러리 없음: {att['name']} ({e}) — pip install pdfplumber openpyxl")
            if problems is not None:
                problems.append("PARSE_ERROR")
            LOG.doc(city.city, "고시공고", title, detail_url, att["name"], att["ext"], "실패", 0, "PARSE_ERROR",
                    f"라이브러리 없음: {e}")
        except Exception as e:
            print(f"    [경고] 첨부파일 해석 실패: {att['name']} ({e})")
            if problems is not None:
                problems.append("PARSE_ERROR")
            LOG.doc(city.city, "고시공고", title, detail_url, att["name"], att["ext"], "실패", 0, "PARSE_ERROR",
                    f"{type(e).__name__}: {str(e)[:200]}")
    return rows


def _download(session, adapter, att, referer):
    """첨부 1개를 메모리로 받는다. referer 가 있으면 Referer 헤더를 붙여 GET 한다.
    일시 오류(400/5xx/시간초과)는 http_fetch.retry_call 로 최대 3번까지 다시 받는다(2026-10-25: 영천시·안동시 400, 합천군 ReadTimeout)."""
    def once():
        if referer:
            resp = session.get(att["url"], headers={**adapter.HEADERS, "Referer": referer}, timeout=60)
            resp.raise_for_status()
            return resp.content
        if hasattr(adapter, "download_attachment"):
            # 일부 시스템은 GET으로 바로 못 받고 POST 등 별도 절차가 필요하다
            # (예: ntis_ofr — 첨부파일 다운로드 자체가 POST 폼 제출).
            return adapter.download_attachment(session, att)
        resp = session.get(att["url"], headers=adapter.HEADERS, timeout=60)
        resp.raise_for_status()
        return resp.content  # 메모리에만 보관, 파일로 저장하지 않음

    return http_fetch.retry_call(once)


def write_outputs(city_dir: Path, records: list, jose_rows: list):
    city_dir.mkdir(parents=True, exist_ok=True)

    csv_path = city_dir / "result.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["게시판", "공고번호", "제목", "작성일", "상세링크", "매칭키워드", "첨부파일링크"]
        )
        for rec in records:
            writer.writerow(
                [
                    rec["board_name"],
                    rec["notice_no"],
                    rec["title"],
                    rec["post_date"],
                    rec["detail_url"],
                    "; ".join(rec["matched_keywords"]),
                    "; ".join(rec["attachment_urls"]),
                ]
            )
    print(f"결과 저장: {csv_path}")

    jsonl_path = city_dir / "records.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"BigQuery/SQLite 적재용 레코드 저장: {jsonl_path}")

    jose_csv_path = city_dir / "jose_rows.csv"
    with open(jose_csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=jose_extractor.JOSE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(jose_rows)
    print(f"토지조서(jose_rows) 저장: {jose_csv_path} ({len(jose_rows)}행)")

    jose_jsonl_path = city_dir / "jose_rows.jsonl"
    with open(jose_jsonl_path, "w", encoding="utf-8") as f:
        for r in jose_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def run_city(city: City, days: int, output_dir: Path, dry_run: bool, delay: float, jose_sink: list = None,
             skip_keys: set = None, outcomes: list = None) -> list:
    """지자체 1곳 크롤링. 공고 records(가공된 dict) 리스트를 반환한다.

    skip_keys: 이미 처리를 끝낸 글의 키(core/sqlite_store.post_key) 집합 - 그 글은 첨부를 다시 받지 않고 건너뛴다.
    outcomes: 이번에 처리한 글의 결과 dict 를 여기에 담는다(호출자가 DB 저장 뒤 sqlite_store.record_seen 으로 기록)."""
    adapter = importlib.import_module(f"cms_adapters.{city.adapter}")
    today = dt.date.today()
    cutoff = today - dt.timedelta(days=days - 1)
    crawled_at = dt.datetime.now(dt.timezone.utc).isoformat()
    session = http_fetch.install(requests.Session())  # 중간 인증서를 빠뜨린 사이트(곡성군 등)용 CA 보완
    if hasattr(adapter, "prepare_session"):
        adapter.prepare_session(session, city)

    t_start = time.time()
    matched = []
    scanned, pages_ok, list_errors, detail_errors = 0, 0, 0, 0  # 로그용: 목록에서 훑은 글 수, 읽은 목록 페이지 수, 오류 수
    for board in city.boards:
        print(f"\n=== [{city.city}] 게시판: {board['name']} ===")
        page_index = 1
        while True:
            try:
                rows = adapter.fetch_list_page(session, city.base_url, board, page_index)
            except requests.RequestException as e:
                print(f"  [경고] {page_index}페이지 조회 실패: {e}")
                for retry_wait in (5, 10):  # 일부 사이트는 일시적으로 몇 초씩 응답이 늦다(실측: 안성시)
                    print(f"  {retry_wait}초 후 재시도")
                    time.sleep(retry_wait)
                    try:
                        rows = adapter.fetch_list_page(session, city.base_url, board, page_index)
                        break
                    except requests.RequestException as e2:
                        e = e2
                else:
                    print(f"  [경고] 재시도도 실패, 이 게시판은 여기까지만 수집: {e}")
                    list_errors += 1
                    LOG.board({"city": city.city, "kind": "고시공고", "status": "오류(목록)",
                               "detail": f"{board['name']} {page_index}페이지 목록 요청 실패(재시도 후)", "url": city.base_url,
                               "errors": [f"{type(e).__name__}: {str(e)[:120]}"]}, f"{type(e).__name__}: {str(e)[:120]}")
                    break
            if not rows:
                break
            pages_ok += 1
            scanned += len(rows)

            hit_older = False
            for row in rows:
                if row["date"] is None:
                    continue
                if row["date"] < cutoff:
                    hit_older = True
                    continue
                kws = matched_keywords(row["title"], city.keywords)
                if not kws and not city.match_all and row["title"].endswith(("...", "…")) and hasattr(adapter, "fetch_full_title"):
                    # 목록이 제목을 잘라 보여 주면(…) 키워드가 잘린 뒷부분에 있을 수 있어 상세의 전체 제목으로 다시 판정한다
                    try:
                        full = adapter.fetch_full_title(session, row["detail_url"])
                    except requests.RequestException:
                        full = ""
                    if full and len(full) > len(row["title"].rstrip(".…")):
                        row["title"] = full
                        kws = matched_keywords(full, city.keywords)
                    time.sleep(delay)
                if (kws or city.match_all) and not matches_blacklist(row["title"], city.blacklist):
                    row["matched_keywords"] = kws
                    matched.append(row)

            print(f"  page {page_index}: {len(rows)}건 조회, 누적 매칭 {len(matched)}건")

            if hit_older:
                break
            if page_index >= MAX_PAGES_PER_BOARD:
                print(
                    f"  [경고] {MAX_PAGES_PER_BOARD}페이지까지 갔는데도 cutoff에 못 걸림"
                    # em-dash(—)가 Windows 콘솔 기본 코드페이지(cp949)에서 print 자체를
                    # 죽이는 걸 실측으로 확인해(2026-09-28) 일반 하이픈으로 바꿨다.
                    " - 날짜 인식이 안 되는 사이트이거나(어댑터 점검 필요) 정말로 게시량이"
                    " 많은 사이트일 수 있음. 여기서 중단."
                )
                break
            page_index += 1
            time.sleep(delay)

    print(f"\n[{city.city}] 총 매칭 항목: {len(matched)}건 (최근 {days}일 이내, 키워드 포함)")

    records = []
    jose_rows = []
    skipped = 0
    for row in matched:
        attachments = []
        key = post_key(row["detail_url"], row["title"])
        if skip_keys and key in skip_keys:
            skipped += 1  # 지난 실행에서 끝낸 글: 첨부를 다시 받지 않는다
            continue
        problems, rows_before, detail_failed = [], len(jose_rows), False
        if not dry_run:
            try:
                attachments = adapter.fetch_attachments(session, row["detail_url"])
            except requests.RequestException as e:
                print(f"  [경고] 상세페이지 조회 실패: {row['title']} ({e})")
                detail_errors += 1
                detail_failed = True
                LOG.board({"city": city.city, "kind": "고시공고", "status": "오류(상세)", "detail": f"상세페이지 조회 실패: {row['title'][:60]}",
                           "url": row["detail_url"], "errors": [f"{type(e).__name__}"]}, f"{type(e).__name__}: {str(e)[:120]}")
            time.sleep(delay)
            if not attachments:
                LOG.doc(city.city, "고시공고", row["title"], row["detail_url"], "", "", "건너뜀", 0, "NO_ATTACH",
                        "상세 페이지에서 첨부파일 링크를 찾지 못함")

            if attachments and city.regions is not None:
                got = download_jose_rows(session, adapter, attachments, row["title"], crawled_at, city, row["detail_url"], problems)
                if got:
                    print(f"  [토지조서] {row['title'][:40]} -> {len(got)}필지")
                for g in got:  # 어느 게시글에서 나온 필지인지 남긴다(SQLite 적재용)
                    g["post_url"], g["post_title"], g["post_date"] = row["detail_url"], row["title"], (
                        row["date"].isoformat() if row["date"] else None)
                jose_rows += got
                time.sleep(delay)

        if outcomes is not None and not dry_run and not detail_failed and not problems:  # 오류가 난 글은 기록하지 않아 다음에 다시 읽는다
            outcomes.append({"key": key, "title": row["title"], "post_date": row["date"].isoformat() if row["date"] else None,
                             "status": "ok" if len(jose_rows) > rows_before else "empty", "rows": len(jose_rows) - rows_before})
        records.append(
            {
                "province": city.province,
                "city": city.city,
                "board_name": row["board"],
                "notice_no": row["notice_no"],
                "title": row["title"],
                "post_date": row["date"].isoformat() if row["date"] else None,
                "detail_url": row["detail_url"],
                "attachment_urls": [a["url"] for a in attachments],
                "matched_keywords": row["matched_keywords"],
                "crawled_at": crawled_at,
            }
        )

    # 게시판 1곳당 요약 1행(2026-10-18): 정상으로 읽은 곳도 남겨야 '막힌 곳'과 '조용한 곳'을 로그로 가를 수 있다.
    n_att = sum(len(r["attachment_urls"]) for r in records)
    if list_errors and not pages_ok:
        status = "오류(목록)"  # 목록을 한 쪽도 못 읽음(오류 행은 위에서 이미 남김)
    elif pages_ok == 0:
        status = "목록 0건"  # 요청은 됐는데 글이 하나도 안 보임: 구조 변경이나 차단 응답일 수 있다
    elif not matched:
        status = "최근 게시물 없음"
    elif list_errors or detail_errors:
        status = "정상(일부 오류)"
    else:
        status = "정상"
    if status != "오류(목록)":
        LOG.board({"city": city.city, "kind": "고시공고", "status": status,
                   "detail": f"목록 {pages_ok}쪽 {scanned}건 훑음, 매칭 {len(matched)}건, 목록오류 {list_errors}, 상세오류 {detail_errors}, "
                             f"이미 처리한 글 {skipped}건 건너뜀, {time.time() - t_start:.0f}초",
                   "posts": len(matched), "attachments": n_att, "notices": len(records), "rows": len(jose_rows),
                   "url": city.base_url})

    write_outputs(output_dir / city.city, records, jose_rows)
    if jose_sink is not None:
        jose_sink.extend(jose_rows)
    return records
