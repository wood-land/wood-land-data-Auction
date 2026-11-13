"""
diag_fetch.py — 게시판 한 곳을 열어 구조를 진단한다(읽기 전용). GitHub Actions 의 diag-board 워크플로가 쓴다.

왜 필요한가: 일부 지자체 사이트는 한국 밖 IP 에서 열리지 않거나(러너와 같은 조건을 클라우드 개발 환경에서 재현할 수 없다),
JS 화면이라 공보 파서가 목록을 못 읽는다. 실제 수집이 도는 Actions 러너에서 그 주소를 열어 보고 구조를 확인하려고 만들었다(law.md 3절: 구조를 추측하지 않는다).

하는 일(저장소·DB 에는 아무것도 쓰지 않는다. 결과는 --out 폴더와 화면 출력뿐):
  1) 주소를 공보 수집기와 같은 세션(run_gazette.new_session: 전체 UA, 옛 TLS 허용)으로 연다.
  2) 응답 요약(상태·최종 주소·인코딩·크기), 페이지 제목, 링크·iframe·script·form, 날짜/제N호가 들어 있는 줄을 요약한다.
  3) iframe/frame 은 한 단계만 따라가 같은 요약을 만든다(목록이 iframe 안에 있는 사이트).
  4) 현재 공보 파서(cms_adapters.gazette_generic.fetch_list_page)가 이 주소에서 몇 건을 읽는지 재현한다.

안전: 대상은 *.go.kr 만 허용한다(law.md 6절). 시험용으로만 환경변수 DIAG_ALLOW_ANY_HOST=1 이 있으면 그 제한을 푼다.

사용: python diag_fetch.py "https://www.busan.go.kr/news/index" --out diag_out
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

DATE_RE = re.compile(r"20\d{2}\s*[-./년]\s*\d{1,2}\s*[-./월]\s*\d{1,2}")
ISSUE_RE = re.compile(r"제\s?\d{2,5}\s?호|(?:시보|공보|군보|도보|구보)\s?\d{2,5}\s?호")
EBOOK_HINT_RE = re.compile(r"e-?book|ebook|flipbook|viewer|pageflip|dflip|fn_view|goView|javascript:", re.I)
MAX_LINKS = 120
MAX_LINES = 40


def host_allowed(url, environ=None):
    """*.go.kr 만 허용(시험용 DIAG_ALLOW_ANY_HOST=1 이면 모두 허용)."""
    environ = os.environ if environ is None else environ
    if environ.get("DIAG_ALLOW_ANY_HOST") == "1":
        return True
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    return parts.scheme in ("http", "https") and (host == "go.kr" or host.endswith(".go.kr"))


def decode_body(content, declared=None):
    """바이트 -> (글, 쓴 인코딩). 선언된 인코딩 -> utf-8 -> cp949 순으로 시도한다."""
    tried = []
    for enc in [declared, "utf-8", "cp949", "euc-kr"]:
        if not enc or enc in tried:
            continue
        tried.append(enc)
        try:
            return content.decode(enc), enc
        except (UnicodeDecodeError, LookupError):
            continue
    return content.decode("utf-8", errors="replace"), "utf-8(replace)"


def summarize(html, base_url):
    """HTML -> 구조 요약 dict. 네트워크 없이 동작한다(테스트 가능)."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    links = []
    for a in soup.find_all("a"):
        href = (a.get("href") or "").strip()
        onclick = (a.get("onclick") or "").strip()
        text = a.get_text(" ", strip=True)
        if not (href or onclick):
            continue
        links.append({"text": text[:60], "href": urljoin(base_url, href) if href and not href.startswith(("javascript:", "#")) else href[:80],
                      "onclick": onclick[:80]})
    frames = [urljoin(base_url, f.get("src")) for f in soup.find_all(["iframe", "frame"]) if f.get("src")]
    scripts = [urljoin(base_url, s.get("src")) for s in soup.find_all("script") if s.get("src")]
    forms = [{"action": urljoin(base_url, f.get("action") or ""), "method": (f.get("method") or "get").lower(),
              "fields": [i.get("name") for i in f.find_all(["input", "select", "textarea"]) if i.get("name")][:15]}
             for f in soup.find_all("form")]
    refresh = [m.get("content") for m in soup.find_all("meta") if (m.get("http-equiv") or "").lower() == "refresh"]
    text = soup.get_text("\n", strip=True)
    dated = [ln[:140] for ln in text.splitlines() if DATE_RE.search(ln) or ISSUE_RE.search(ln)]
    tables = soup.find_all("table")
    return {
        "title": title,
        "text_chars": len(text),
        "tables": len(tables),
        "table_rows": sum(len(t.find_all("tr")) for t in tables),
        "links": len(links),
        "link_sample": links[:MAX_LINKS],
        "frames": frames,
        "scripts": scripts[:30],
        "forms": forms[:10],
        "meta_refresh": refresh,
        "lines_with_date_or_issue": len(dated),
        "date_line_sample": dated[:MAX_LINES],
        "ebook_or_js_hints": sorted({m.group(0).lower() for m in EBOOK_HINT_RE.finditer(html)})[:12],
    }


def render(label, info, resp_info=None):
    """요약 dict -> 사람이 읽는 글."""
    out = [f"===== {label}"]
    if resp_info:
        out += [f"  응답: HTTP {resp_info['status']} | 최종 주소 {resp_info['final_url']} | {resp_info['content_type']} | {resp_info['bytes']}바이트 | 인코딩 {resp_info['encoding']}"]
        if resp_info.get("redirects"):
            out.append(f"  이동 경로: {' -> '.join(resp_info['redirects'])}")
    out += [f"  제목: {info['title']!r}", f"  본문 글자 {info['text_chars']} | 표 {info['tables']}개(행 {info['table_rows']}) | 링크 {info['links']}개",
            f"  날짜/제N호가 있는 줄 {info['lines_with_date_or_issue']}개 | JS·e-book 단서 {info['ebook_or_js_hints']}"]
    if info["meta_refresh"]:
        out.append(f"  meta refresh: {info['meta_refresh']}")
    if info["frames"]:
        out.append("  iframe/frame: " + " | ".join(info["frames"]))
    if info["forms"]:
        out.append("  form: " + " | ".join(f"{f['method']} {f['action']} {f['fields']}" for f in info["forms"][:5]))
    if info["scripts"]:
        out.append("  script src(앞 10개): " + " | ".join(info["scripts"][:10]))
    if info["date_line_sample"]:
        out.append("  날짜/제N호 줄 예:")
        out += [f"    {ln}" for ln in info["date_line_sample"][:15]]
    if info["link_sample"]:
        out.append("  링크 예(앞 40개):")
        out += [f"    [{l['text']}] href={l['href']} onclick={l['onclick']}" for l in info["link_sample"][:40]]
    return "\n".join(out)


def fetch(session, url, out_dir, tag):
    """주소 하나를 열어 원본·디코딩본을 저장하고 (html, 응답 정보)를 돌려준다."""
    resp = session.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"},
                       timeout=60, allow_redirects=True)
    html, enc = decode_body(resp.content, resp.encoding if "charset" in resp.headers.get("content-type", "").lower() else None)
    (out_dir / f"{tag}.raw").write_bytes(resp.content)
    (out_dir / f"{tag}.html").write_text(html, encoding="utf-8")
    info = {"status": resp.status_code, "final_url": resp.url, "content_type": resp.headers.get("content-type", ""),
            "bytes": len(resp.content), "encoding": enc, "redirects": [r.headers.get("location", "")[:100] for r in resp.history]}
    return html, info


def parser_repro(session, url):
    """현재 공보 파서가 이 주소에서 읽는 행을 재현한다(오류도 그대로 보여 준다)."""
    try:
        from cms_adapters import gazette_generic
        rows = gazette_generic.fetch_list_page(session, url, {"name": "시보"}, 1)
        sample = [{"title": r.get("title", "")[:60], "date": r.get("date_str", ""), "detail_url": r.get("detail_url", "")[:90]} for r in rows[:8]]
        return {"rows": len(rows), "sample": sample}
    except Exception as e:  # 진단 도구라 오류 내용을 그대로 기록하고 계속한다
        return {"error": f"{type(e).__name__}: {str(e)[:300]}"}


def main(argv=None):
    ap = argparse.ArgumentParser(description="게시판 한 곳을 열어 구조를 진단한다(읽기 전용)")
    ap.add_argument("url")
    ap.add_argument("--out", default="diag_out")
    a = ap.parse_args(argv)
    if not host_allowed(a.url):
        print(f"[거부] *.go.kr 주소만 진단합니다: {a.url}")
        return 2
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    from run_gazette import new_session  # 공보 수집기와 같은 세션
    session = new_session()
    report = [f"진단 주소: {a.url}"]
    summary = {"url": a.url}
    try:
        html, info = fetch(session, a.url, out_dir, "page")
    except Exception as e:
        msg = f"[접속 실패] {type(e).__name__}: {str(e)[:300]}"
        print(msg)
        (out_dir / "summary.txt").write_text("\n".join(report + [msg]), encoding="utf-8")
        return 1
    page = summarize(html, info["final_url"])
    summary["page"] = {"response": info, **page}
    report.append(render("페이지", page, info))
    for i, frame_url in enumerate(page["frames"][:4], 1):
        if not host_allowed(frame_url):
            report.append(f"===== iframe {i}: {frame_url} (*.go.kr 가 아니어서 건너뜀)")
            continue
        try:
            fhtml, finfo = fetch(session, frame_url, out_dir, f"frame{i}")
            fpage = summarize(fhtml, finfo["final_url"])
            summary[f"frame{i}"] = {"response": finfo, **fpage}
            report.append(render(f"iframe {i}", fpage, finfo))
        except Exception as e:
            report.append(f"===== iframe {i}: {frame_url} [접속 실패] {type(e).__name__}: {str(e)[:200]}")
    repro = parser_repro(session, a.url)
    summary["parser"] = repro
    if "error" in repro:
        report.append(f"===== 현재 공보 파서 재현: 오류 {repro['error']}")
    else:
        report.append(f"===== 현재 공보 파서 재현: {repro['rows']}건 읽음")
        report += [f"    {r['date']} | {r['title']} | {r['detail_url']}" for r in repro["sample"]]
    text = "\n".join(report)
    (out_dir / "summary.txt").write_text(text, encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
