"""
core/site.py - EIASS(www.eiass.go.kr) 접근.

- 초안공람 목록: /searchApi/search.do (사이트 목록 화면이 쓰는 검색 API, HTML 조각을 돌려준다)
- 초안공람 상세: /partcptn/choan/choanEiassView.do (POST BIZ_CD, BIZ_SEQ)
- 평가서 PDF 뷰어(StreamDocs): /common/pdf/view.do -> streamdocsId
    /streamdocs/v4/documents/{id}/document          쪽 수(layout)
    /streamdocs/v4/documents/{id}/texts/{p}         쪽 글자
    /streamdocs/v4/documents/{id}/renderings/{p}    쪽 그림(PNG, 첫 바이트만 바뀌어 있다)
로그인·쿠키 없이 열린다(2026-10-25 확인).
"""
import json
import re
import time

import numpy as np
import requests
from bs4 import BeautifulSoup

BASE = "https://www.eiass.go.kr"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


class Eiass:
    def __init__(self, timeout=40):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Referer": BASE + "/partcptn/choan/choanEiassList.do"})
        self.timeout = timeout

    def _req(self, method, path, **kw):
        last = None
        for i in range(4):
            try:
                r = self.s.request(method, BASE + path, timeout=self.timeout, **kw)
                r.raise_for_status()
                return r
            except requests.RequestException as e:
                last = e
                time.sleep(2 + 3 * i)
        raise last

    # ---------------- 목록 ----------------
    def list_page(self, page=1, alias=2):
        """alias=2 환경영향평가, 1 전략환경영향평가. 공람 시작일 최신순."""
        data = {
            "query": "", "collection": "draft",
            "urlString": f"&alias={alias}&orgnCd=&bizGubunCd=&sido=",
            "viewName": "eiass/user/partcptn/choan/choan" + ("Eiass" if alias == 2 else "Sperss") + "List_searchApi",
            "currentPage": str(page), "sort": "DRFOP_START_DT/DESC,BIZ_SEQ/DESC",
        }
        html = self._req("POST", "/searchApi/search.do", data=data).text
        soup = BeautifulSoup(html, "html.parser")
        rows = []
        for tr in soup.select("tr"):
            a = tr.find("a", href=re.compile(r"view\('"))
            if not a:
                continue
            m = re.search(r"view\('([^']+)',\s*'([^']+)'\)", a["href"])
            tds = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            period = next((t for t in tds if re.search(r"\d{4}\.\d{2}\.\d{2}\s*~", t)), "")
            rows.append({"biz_cd": m.group(1), "biz_seq": m.group(2), "no": tds[0] if tds else "",
                         "biz_type": tds[1] if len(tds) > 1 else "", "biz_nm": a.get_text(" ", strip=True),
                         "choan_period": re.sub(r"\s+", "", period).replace("~", "~")})
        return rows

    # ---------------- 상세 ----------------
    def detail(self, biz_cd, biz_seq):
        html = self._req("POST", "/partcptn/choan/choanEiassView.do", data={"BIZ_CD": biz_cd, "BIZ_SEQ": biz_seq}).text
        soup = BeautifulSoup(html, "html.parser")
        info = {}
        for th in soup.find_all("th"):
            td = th.find_next_sibling("td")
            if td is not None:
                info[th.get_text(" ", strip=True)] = td.get_text(" ", strip=True)
        files = [{"seq": m.group(1), "name": m.group(2)} for m in re.finditer(r"generalView\('(\d+)',\s*'([^']+)'\)", html)]
        return {
            "biz_nm": info.get("사업명", ""), "operator": info.get("사업시행자", ""), "biz_type": info.get("사업구분", ""),
            "location": info.get("사업지위치", ""), "approver": info.get("승인기관", ""),
            "choan_period": info.get("초안 공람 기간", ""), "files": files,
        }

    # ---------------- 평가서 뷰어 ----------------
    def streamdocs_id(self, file_seq, file_nm="a.pdf"):
        t = self._req("POST", "/common/pdf/view.do", data={"FILE_SEQ": file_seq, "FILE_NM": file_nm, "SYSTEM_NAME": "EIASS"}).text
        m = re.search(r"streamdocsId=([A-Za-z0-9_\-]+)", t)
        return m.group(1) if m else None

    def page_count(self, sid):
        t = self._req("GET", f"/streamdocs/v4/documents/{sid}/document").text
        return t.split("}{")[0].count('"bbox"')

    def page_text(self, sid, p):
        t = self._req("GET", f"/streamdocs/v4/documents/{sid}/texts/{p}").text
        return "".join(m.group(1) for m in re.finditer(r'"(?:text|str|t)"\s*:\s*"([^"]*)"', t))

    def render(self, sid, p, zoom=800):
        """쪽 그림을 RGB numpy 배열로. zoom=800 이면 긴 변이 최대 4096px."""
        import cv2
        r = self._req("GET", f"/streamdocs/v4/documents/{sid}/renderings/{p}",
                      params={"zoom": zoom, "jpegQuality": "o", "renderAnnots": "false", "increasePrint": "false"})
        b = bytearray(r.content)
        if b[:1] != b"\x89" and b[1:4] == b"PNG":
            b[0] = 0x89                       # 뷰어가 PNG 첫 바이트를 바꿔 내려준다
        img = cv2.imdecode(np.frombuffer(bytes(b), np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("그림 해석 실패")
        return img[:, :, ::-1].copy()        # BGR -> RGB


def parse_plan_area(texts):
    """평가서 글에서 사업면적(㎡)을 찾는다. '사업면적/사업규모 : 243,774㎡' 또는 토지이용계획 표의 '합 계 243,774'."""
    cands = []
    for t in texts:
        for m in re.finditer(r"(사업\s*면적|사업\s*규모|총\s*면적|계획\s*면적)[^0-9]{0,25}([\d,]{5,})(\.\d+)?\s*(㎡|m2|m²)?", t):
            cands.append((0, int(m.group(2).replace(",", ""))))
        for m in re.finditer(r"합\s*계\s*([\d,]{5,})", t):
            cands.append((1, int(m.group(1).replace(",", ""))))
    if not cands:
        return None
    cands.sort(key=lambda x: x[0])
    best = cands[0][0]
    vals = [v for k, v in cands if k == best and v > 1000]
    if not vals:
        return None
    # 가장 자주 나온 값
    return max(set(vals), key=vals.count)
