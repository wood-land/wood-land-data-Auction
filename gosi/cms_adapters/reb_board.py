"""
reb_board.py — 한국부동산원(reb.or.kr) "보상정보 > 보상계획 공고"(selectNttList.do) 어댑터.

한국부동산원에서 실측 확인했다(2026-09-28). 목록은 평범한 GET이지만, 상세/첨부는 화면
JS가 하는 일을 그대로 재현해야 한다.

목록: GET selectNttList.do?mi=<mi>&bbsId=<bbsId>&currPage=<P> (POST와 결과가 같아 GET 사용).
행은 table tr 안의 <a class="nttInfoBtn" data-id="<nttSn>">, 제목 칸 앞이 번호, 등록일은
"YYYY.MM.DD."(끝에 점이 붙는다) 형식이다.

상세: 화면은 srchForm을 POST하지만 selectNttInfo.do?mi=&bbsId=&nttSn= 로 GET해도 열려
그 URL을 detail_url로 쓴다. 첨부는 상세 HTML에 없고 목록의 클릭 이벤트가 호출하는
GET fileDownChk.do?mi=&bbsId=&nttSn= 의 JSON(nttFileList: fileNm/dwldUrl/extsn)에서 얻고,
실제 다운로드는 GET /reb/common/nttFileDownload.do?fileKey=<dwldUrl> 이다(JS 소스 확인).

이 게시판(보상계획 공고 / 협의 공고)은 모든 글이 보상 대상이라 제목이 사업명뿐이다(예:
"솔안천 개선(재해)복구사업"). 그래서 cities/central_agencies.py에서 City.match_all=True로
키워드 필터 없이 전체를 수집한다(사용자 확인, 2026-09-28).

City.boards 항목 형식: {"name": "보상계획공고", "mi": 9583, "bbs_id": 1143}
"""

import datetime as dt
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


def _origin(url):
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}"


def _parse_date(text):
    try:
        return dt.datetime.strptime(text.strip().rstrip("."), "%Y.%m.%d").date()
    except ValueError:
        return None


def fetch_list_page(session, base_url, board, page_index, page_unit=10):
    """목록 페이지 1개 -> [{"board","notice_no","title","date","date_str","detail_url"}, ...]"""
    mi, bbs_id = board["mi"], board["bbs_id"]
    resp = session.get(
        base_url,
        params={"mi": mi, "bbsId": bbs_id, "currPage": page_index},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    origin = _origin(resp.url)
    rows = []
    for tr in soup.select("table tr"):
        a_tag = tr.select_one("a.nttInfoBtn")
        if a_tag is None:
            continue
        tds = tr.find_all("td")
        if len(tds) < 3:
            continue
        date_str = tds[2].get_text(strip=True)
        rows.append(
            {
                "board": board["name"],
                "notice_no": "",
                "title": a_tag.get_text(" ", strip=True),
                "date": _parse_date(date_str),
                "date_str": date_str,
                "detail_url": f"{origin}/reb/na/ntt/selectNttInfo.do?mi={mi}&bbsId={bbs_id}&nttSn={a_tag['data-id']}",
            }
        )
    return rows


def fetch_attachments(session, detail_url):
    """첨부파일 [{"name","url","ext"}, ...] (다운로드는 하지 않음). fileDownChk.do JSON을 쓴다."""
    q = parse_qs(urlsplit(detail_url).query)
    origin = _origin(detail_url)
    resp = session.get(
        f"{origin}/reb/na/ntt/fileDownChk.do",
        params={"mi": q["mi"][0], "bbsId": q["bbsId"][0], "nttSn": q["nttSn"][0]},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    attachments = []
    for item in resp.json().get("nttFileList") or []:
        name = item.get("fileNm", "")
        if not name:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else (item.get("extsn") or "").lower()
        attachments.append(
            {"name": name, "url": f"{origin}/reb/common/nttFileDownload.do?fileKey={item['dwldUrl']}", "ext": ext}
        )
    return attachments
