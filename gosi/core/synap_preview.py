"""
core/synap_preview.py — 지자체 게시판의 "미리보기"(Synap 문서뷰어)가 만든 변환본을 받아 본문 텍스트로 만든다.

파일 다운로드가 사이트별 특수 방식으로 막혀도 미리보기는 열리는 곳이 많다(사용자 확인). eGovFrame 표준
`/synapsoft/FileViewer.do?atchFileId=..&fileSn=..` 은 Synap 뷰어(`.../doc.html?fn=<파일>&rs=<결과폴더>/`)로
넘어가고, 변환 결과는 일반 HTTP로 받을 수 있다:
  <결과폴더>/<fn>.xml                       페이지 목록(<pdf><path_html>fn.files/N.png</path_html>...)
  <결과폴더>/<fn>.files/N.png               페이지 이미지(793x1121, 글자 레이어 없음)
그래서 페이지 이미지를 받아 OCR(테서랙트 kor+eng, 2배 확대)로 본문을 만든다.
뷰어가 다른 방식(결과 폴더 규칙이 다른 구형 Synap 등)이면 None을 돌려주고 호출하는 쪽이 다른 경로를 쓴다.
"""

import io
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urljoin, urlsplit

from core import gazette_extractor as GX

MAX_PAGES = 3000  # 열어본 문서는 끝까지 읽는다(상한은 폭주 방지용)


def _target(session, viewer_url, referer, headers):
    r = session.get(viewer_url, headers={**headers, "Referer": referer}, timeout=60, allow_redirects=True)
    p = urlsplit(r.url)
    q = parse_qs(p.query)
    fn = (q.get("fn") or [""])[0]
    rs = (q.get("rs") or [""])[0]
    if not fn or not rs:
        return None
    if not rs.endswith("/"):
        rs += "/"
    return f"{p.scheme}://{p.netloc}", fn, rs


def _page_paths(xml_text):
    root = ET.fromstring(xml_text)
    paths = []
    for tag in ("path_html", "path_image"):
        paths = [(el.text or "").strip() for el in root.iter(tag) if (el.text or "").strip()]
        if paths:
            break
    return paths[:MAX_PAGES]


def _prep(png_bytes):
    """페이지 이미지를 OCR에 유리하게: 흑백 + 폭 1600px 미만이면 2배 확대."""
    from PIL import Image

    im = Image.open(io.BytesIO(png_bytes)).convert("L")
    if im.width < 1600:
        im = im.resize((im.width * 2, im.height * 2), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def _synap_pages(session, final_url, headers):
    """Synap 뷰어(doc.html?fn=&rs=) -> 페이지 이미지 URL 목록"""
    p = urlsplit(final_url)
    q = parse_qs(p.query)
    fn = (q.get("fn") or [""])[0]
    rs = (q.get("rs") or [""])[0]
    if not fn or not rs:
        return []
    if not rs.endswith("/"):
        rs += "/"
    base = f"{p.scheme}://{p.netloc}{rs}"
    xr = session.get(base + fn + ".xml", headers=headers, timeout=60)
    if xr.status_code != 200 or "<" not in xr.text[:5]:
        return []
    return [urljoin(base, path) for path in _page_paths(xr.content)]


def _hancom_pages(session, final_url, headers):
    """한컴 뷰어(.../hview.html) -> document.json 의 페이지 수·이미지 이름 규칙으로 페이지 이미지 URL 목록"""
    base = final_url.rsplit("/", 1)[0] + "/"
    jr = session.get(base + "document.json", headers=headers, timeout=60)
    if jr.status_code != 200:
        return []
    j = jr.json()
    total = int(j.get("pageInfo", {}).get("totalPages", 0))
    fi = j.get("fileInfo", {})
    prefix, digit, ext = fi.get("prefix", "document_"), int(fi.get("digit", 4)), fi.get("extension", "jpg")
    start = int(fi.get("startFrom", 1))
    return [f"{base}{prefix}{str(i).zfill(digit)}.{ext}" for i in range(start, start + min(total, MAX_PAGES))]


def preview_text(session, viewer_url, referer, headers, lang="kor+eng"):
    """미리보기 주소 -> OCR 본문 텍스트. 지원하지 않는 뷰어이거나 못 받으면 None."""
    if not GX.ocr_available():
        return None
    r = session.get(viewer_url, headers={**headers, "Referer": referer}, timeout=60, allow_redirects=True)
    if r.status_code != 200:
        return None
    final = r.url
    if "hview.html" in final:
        urls = _hancom_pages(session, final, headers)
    elif "fn=" in final and "rs=" in final:
        urls = _synap_pages(session, final, headers)
    else:
        return None
    if not urls:
        return None

    def one(u):
        img = session.get(u, headers=headers, timeout=60)
        if img.status_code != 200 or not img.content:
            return ""
        return GX._ocr_png(_prep(img.content), lang)

    with ThreadPoolExecutor(3) as ex:
        pages = list(ex.map(one, urls))
    text = "\n".join(pages)
    return text if text.strip() else None
