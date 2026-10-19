"""
goheung_eminwon_api.py — 고흥군 고시/공고 JSON API 전용 어댑터.

고흥군 페이지(contentsView.do?pageId=www99)는 순수 JS 렌더링이라(초기 HTML에
목록 데이터가 없고, 로드 후 별도 POST 요청으로 채워짐) 페이지 안의 inline
<script>를 직접 읽어 실제 호출을 확인했다(2026-09-28):
  - 목록: POST /getEminwon.do (application/x-www-form-urlencoded)
          action=L&seq=&notAncmtSeCode=01,04,05&listGubun=A&recordCnt=<n>&
          movePage=<page>&prevAction=L&prevMovePage=<page>
          -> JSON {"dataArr":{"list":[{"idx","seq","sj","gosiNo","regDe","termDe",
             "deptNm","rdcnt"}, ...],"pageCnt","totalCnt","page"},"errChk":"N"}
  - 상세: 같은 엔드포인트에 action=V&seq=<seq> -> JSON
          {"dataArr":{"sj","cn","fileList":[{"fileNm","fileHref"}, ...], ...}}
    fileHref가 이미 완성된 GET URL(eminwon.goheung.go.kr/emwp/jsp/ofr/
    FileDownNew.jsp?user_file_nm=...&sys_file_nm=...&file_path=...)이라 담양군과
    달리 JS(goDownLoad) 파싱이 전혀 필요 없다 — download_attachment도 따로 안
    두고 core.board_crawler의 기본 GET 경로를 그대로 쓴다.
"""

import datetime as dt
import html

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

_API_URL = "https://www.goheung.go.kr/getEminwon.do"
_DETAIL_MARKER = "#goheung-seq="
_DATE_FORMATS = ["%Y-%m-%d", "%Y.%m.%d"]


def _parse_post_date(date_str):
    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    data = {
        "action": "L",
        "seq": "",
        "notAncmtSeCode": "01,04,05",
        "listGubun": "A",
        "recordCnt": page_unit,
        "movePage": page_index,
        "prevAction": "L",
        "prevMovePage": page_index,
    }
    resp = session.post(_API_URL, data=data, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    payload = resp.json()
    items = payload.get("dataArr", {}).get("list", []) or []

    rows = []
    for item in items:
        seq = item.get("seq", "")
        if not seq:
            continue
        date_str = item.get("regDe", "")
        rows.append(
            {
                "board": board["name"],
                "notice_no": item.get("gosiNo", ""),
                "title": item.get("sj", "").strip(),
                "date": _parse_post_date(date_str),
                "date_str": date_str,
                "detail_url": base_url + _DETAIL_MARKER + str(seq),
            }
        )
    return rows


def fetch_attachments(session, detail_url):
    """상세 페이지의 첨부파일 [{"name", "url", "ext"}, ...] (다운로드는 하지 않음)."""
    base_url, marker, seq = detail_url.partition(_DETAIL_MARKER)
    if not marker:
        return []
    data = {"action": "V", "seq": seq}
    resp = session.post(_API_URL, data=data, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    payload = resp.json()
    files = payload.get("dataArr", {}).get("fileList", []) or []

    attachments = []
    for f in files:
        name = (f.get("fileNm") or "").strip()
        # fileHref 값 자체에 "&"가 "&amp;"로 HTML 엔티티 인코딩된 채 들어있다
        # (실측 확인, 2026-09-28) — 그대로 쓰면 두 번째 쿼리파라미터부터 다
        # 잘려나가 400/500 에러가 난다.
        url = html.unescape(f.get("fileHref") or "")
        if not name or not url:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        attachments.append({"name": name, "url": url, "ext": ext})
    return attachments
