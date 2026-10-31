"""
core/perss.py - 소규모환경영향평가(EIASS 평가정보조회, biz_gubn=M) 목록·상세.

- 목록: POST /searchApi/search.do (collection=business, perssGubn=M, 접수일 최신순). HTML 조각을 돌려준다.
        행 = 사업코드 · 사업구분 · 사업명 · 접수일 · 완료일 · 진행현황, 사업명 링크 view('per', 사업코드, 순번)
- 상세: POST/GET /biz/base/info/perInfo.do (PER_CD, REVIRPT_SEQ). 탭은 화면만 바꾸므로 한 페이지에 다 있다.
        '사업위치' 행의 표 detail_tbl 에 소재지·면적(면형) 또는 '시점 : … 종점 : …'(선형)이 들어 있다.
원문(PDF)은 진행현황이 완료인 사업에만 있고(SYSTEM_NAME=PERSS 뷰어), 이 모듈은 위치·면적까지만 다룬다.
"""
import re
import urllib.parse

from bs4 import BeautifulSoup

from .site import BASE, Eiass

URL_STRING = ("&alias=2&completeFl={done}&openFl=Y&businessExquery={cx}&whrChFl=&aSYear=&aEYear=&rSYear=&rEYear="
              "&orgnCd=&nrvFl=&bizGubunCd=&perssGubn=M")
CHOAN = "<CHOAN:contains:Y>"   # 값을 한 번 더 인코딩하면 검색엔진이 못 읽어 빈 목록이 온다(실측)


def detail_url(per_cd, seq):
    return f"{BASE}/biz/base/info/perInfo.do?biz_gubn=M&PER_CD={per_cd}&REVIRPT_SEQ={seq}"


def _num(t):
    m = re.search(r"[\d,]+(?:\.\d+)?", t or "")
    return float(m.group(0).replace(",", "")) if m else None


class Perss(Eiass):
    def list_page(self, page=1, done=""):
        """done: ''(전체) | '완료' | '진행'. 반환 [{per_cd, seq, biz_type, biz_nm, recv_date, done_date, status}]"""
        params = {"query": "", "collection": "business",
                  "urlString": URL_STRING.format(done=done, cx=CHOAN),
                  "viewName": "/eiass/user/biz/base/info/searchListPer_searchApi",
                  "currentPage": str(page), "sort": "DATE/DESC", "listCount": "10"}
        soup = BeautifulSoup(self._req("POST", "/searchApi/search.do", data=params).text, "html.parser")
        rows, seen = [], set()
        for tr in soup.select("tr"):
            a = tr.find("a", href=re.compile(r"view\('per'"))
            if not a:
                continue
            m = re.search(r"view\('per',\s*'([^']+)',\s*'([^']+)'\)", a["href"])
            if m.group(1) in seen:      # 화면용·모바일용 표가 같은 사업을 두 번 담는다
                continue
            seen.add(m.group(1))
            tds = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            rows.append({"per_cd": m.group(1), "seq": m.group(2), "biz_type": tds[1] if len(tds) > 1 else "",
                         "biz_nm": a.get_text(" ", strip=True), "recv_date": tds[3] if len(tds) > 3 else "",
                         "done_date": tds[4] if len(tds) > 4 else "", "status": tds[5] if len(tds) > 5 else ""})
        return rows

    def detail(self, per_cd, seq):
        """상세 -> dict(biz_nm, biz_type, kind(면형|선형|…), location(소재지 글), start, end, plan_m2, agency, applicant)"""
        html = self._req("POST", "/biz/base/info/perInfo.do", data={"biz_gubn": "M", "PER_CD": per_cd, "REVIRPT_SEQ": seq}).text
        soup = BeautifulSoup(html, "html.parser")
        info = {}
        for th in soup.select("td.head, th"):
            nxt = th.find_next_sibling("td")
            if nxt is not None:
                info.setdefault(re.sub(r"\s+", "", th.get_text()), nxt)
        out = {"biz_nm": "", "biz_type": "", "kind": "", "location": "", "start": "", "end": "", "plan_m2": None,
               "agency": "", "applicant": ""}
        g = lambda k: re.sub(r"\s+", " ", info[k].get_text(" ", strip=True)) if k in info else ""
        out["biz_nm"], out["biz_type"], out["agency"] = g("사업명"), g("사업구분"), g("협의기관")
        out["applicant"] = re.sub(r"^사업시행자 표 ", "", g("사업시행자"))
        loc = info.get("사업위치")
        if loc is not None:
            head = re.sub(r"\s+", " ", loc.get_text(" ", strip=True))
            out["kind"] = head.split(" ")[0] if head else ""      # 면형/선형/점형
            tbl = loc.select_one("table.detail_tbl")
            if tbl:
                cells = [c.get_text(" ", strip=True) for c in tbl.select("tr")[-1].find_all("td")]
                heads = [c.get_text(strip=True) for c in tbl.select("tr")[0].find_all("th")]
                text = re.sub(r"\s+", " ", cells[0]) if cells else ""
                out["location"] = text
                if "면적" in heads and len(cells) > heads.index("면적"):
                    out["plan_m2"] = _num(cells[heads.index("면적")])
                m = re.search(r"시\s*점\s*:\s*(.*?)\s*\*\s*종\s*점\s*:\s*(.*)$", text)
                if m:
                    out["start"], out["end"] = m.group(1).strip(), m.group(2).strip()
        return out
