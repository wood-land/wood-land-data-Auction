"""
gwanbo_board.py — 대한민국 전자관보(gwanbo.go.kr) 검색 API 및 PDF 다운로드 어댑터.

2026-09-27 실측 확인:
  - 전자관보는 목록 페이지를 일반 HTML 테이블이 아닌 비동기 AJAX(/SearchRestApi.jsp)로 제공한다.
  - 검색 API 파라미터:
      mode: "keyword"
      index: "gwanbo"
      query: "keyword_category_order:({category_order})" (고시: 10, 공고: 11, 지방자치단체: 18)
      pageNo: 1, 2, ...
      listSize: 50
      sort: "date" (최신순 정렬)
  - 응답 형식: JSON
      data[].list[].stored_field_subject : 공고 제목 (HTML 태그 포함, 정규식으로 제거)
      data[].list[].keyword_field_regdate : 발행일자 (YYYYMMDD)
      data[].list[].stored_field_url      : ezPDF WebViewer 링크 (/ezpdf/customLayout.jsp?contentId=...&tocId=...)
      data[].list[].stored_toc_seq        : 목차 시퀀스 ID (tocId)
      data[].list[].stored_organ_nm       : 소관기관/부서명
  - 첨부파일/원문 PDF:
      POST /user/common/ofcttCntntDownload.do
      Body: {"cntnt_seq_no": toc_id}
      응답 바이너리가 유효한 %PDF-1.4 포맷으로 내려받아지며, core/jose_extractor 를 통해 토지조서 추출 연계 가능.
"""
from __future__ import annotations

import datetime as dt
import re
from typing import List, Optional
from urllib.parse import parse_qs, urljoin, urlsplit

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
}

_TAG_RE = re.compile(r"<[^>]+>")
_NOTICE_NO_RE = re.compile(r"([가-힣A-Za-z0-9]+(?:고시|공고)?\s*제?\s*\d{4}[-~]\d+\s*호?)")


def clean_html(text: str) -> str:
    """HTML 태그 제거 및 공백 정리."""
    if not text:
        return ""
    clean = _TAG_RE.sub("", text)
    return " ".join(clean.split())


def extract_notice_no(title: str, default_val: str = "") -> str:
    """제목에서 공고/고시 번호 패턴(예: 국토교통부고시제2026-495호) 추출."""
    m = _NOTICE_NO_RE.search(title)
    if m:
        return m.group(1).strip()
    return default_val


def prepare_session(session: requests.Session, city) -> None:
    """세션 공통 헤더 설정."""
    session.headers.update(HEADERS)
    session.headers.update({
        "Referer": "https://gwanbo.go.kr/user/search/searchKeyword.do"
    })


def fetch_list_page(
    session: requests.Session, base_url: str, board: dict, page_index: int
) -> List[dict]:
    """전자관보 SearchRestApi.jsp 비동기 API를 호출하여 해당 카테고리의 공고 목록 반환."""
    api_url = urljoin(base_url, "/SearchRestApi.jsp")
    category_order = board.get("category_order", 10)  # 기본값 10 (고시)

    query = f"keyword_category_order:({category_order})"
    data = {
        "mode": "keyword",
        "index": "gwanbo",
        "query": query,
        "pQuery_tmp": "",
        "pageNo": str(page_index),
        "listSize": "50",
        "sort": "date",
    }

    resp = session.post(api_url, data=data, timeout=15)
    resp.raise_for_status()

    try:
        json_data = resp.json()
    except Exception:
        return []

    data_cats = json_data.get("data", [])
    if not data_cats:
        return []

    # 해당 카테고리 또는 첫 번째 카테고리의 list 추출
    target_items = []
    for cat in data_cats:
        if str(cat.get("category_order")) == str(category_order):
            target_items = cat.get("list") or []
            break
    if not target_items and data_cats:
        target_items = data_cats[0].get("list") or []

    rows = []
    for item in target_items:
        raw_title = item.get("stored_field_subject", "")
        title = clean_html(raw_title)
        if not title:
            continue

        regdate = item.get("keyword_field_regdate", "")
        date_val: Optional[dt.date] = None
        if len(regdate) == 8 and regdate.isdigit():
            try:
                date_val = dt.date(int(regdate[:4]), int(regdate[4:6]), int(regdate[6:8]))
            except ValueError:
                date_val = None

        notice_no = extract_notice_no(title, item.get("stored_laword_seq_no", ""))
        stored_url = item.get("stored_field_url", "")
        detail_url = urljoin(base_url, stored_url) if stored_url else ""

        rows.append(
            {
                "board": board.get("name", "관보"),
                "notice_no": notice_no,
                "title": title,
                "date": date_val,
                "detail_url": detail_url,
                "toc_id": item.get("stored_toc_seq", ""),
                "organ_nm": item.get("stored_organ_nm", ""),
            }
        )

    return rows


def fetch_attachments(session: requests.Session, detail_url: str) -> List[dict]:
    """상세 뷰어 URL(customLayout.jsp)에서 tocId를 추출하여 PDF 다운로드 항목 구성."""
    if not detail_url:
        return []

    parsed = urlsplit(detail_url)
    qs = parse_qs(parsed.query)
    toc_id = qs.get("tocId", [""])[0]
    content_id = qs.get("contentId", [""])[0]

    # tocId가 쿼리스트링에 없으면 페이지 HTML에서 파싱 시도
    if not toc_id:
        try:
            resp = session.get(detail_url, timeout=10)
            if resp.ok:
                m = re.search(r"tocId=([A-Za-z0-9]+)", resp.text)
                if m:
                    toc_id = m.group(1)
        except Exception:
            pass

    if not toc_id:
        return []

    download_url = f"https://gwanbo.go.kr/user/common/ofcttCntntDownload.do?cntnt_seq_no={toc_id}"
    return [
        {
            "name": f"전자관보_{toc_id}.pdf",
            "url": download_url,
            "ext": "pdf",
            "toc_id": toc_id,
            "content_id": content_id,
        }
    ]


def download_attachment(session: requests.Session, att: dict) -> bytes:
    """전자관보 원문 PDF 다운로드 (POST /user/common/ofcttCntntDownload.do)."""
    toc_id = att.get("toc_id")
    if not toc_id and "cntnt_seq_no=" in att.get("url", ""):
        toc_id = att["url"].split("cntnt_seq_no=")[1].split("&")[0]

    if not toc_id:
        raise ValueError(f"첨부파일 식별자(toc_id)가 누락되었습니다: {att}")

    download_url = "https://gwanbo.go.kr/user/common/ofcttCntntDownload.do"
    headers = {
        **HEADERS,
        "Referer": "https://gwanbo.go.kr/main.do",
    }
    resp = session.post(download_url, data={"cntnt_seq_no": toc_id}, headers=headers, timeout=30)
    resp.raise_for_status()

    return resp.content
