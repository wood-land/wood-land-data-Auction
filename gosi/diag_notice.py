"""
diag_notice.py — 공보 글 한 건에서 공고 본문 텍스트와 추출 결과를 보여 준다(읽기 전용). GitHub Actions 의 diag-notice 워크플로가 쓴다.

왜 필요한가: 공보 추출은 첨부 PDF 를 본문 텍스트(미리보기 OCR/PDF 텍스트)로 바꿔 규칙으로 소재지·지번을 읽는다. 소재지가 잘못 읽힌 공고(예: '인천광역시 남동구 기정면 주안동리 599-40')를
고치려면 규칙에 들어간 실제 텍스트를 봐야 하는데, 해당 사이트는 클라우드 개발 환경에서 열리지 않는다. 실제 수집이 도는 Actions 러너에서 같은 파이프라인을 글 한 건에만 돌려 그 텍스트를 확인한다.

하는 일(저장소·DB 에는 아무것도 쓰지 않는다):
  1) run_gazette.process_board 를 그대로 쓰되 게시판 목록을 --post-id 가 든 글 하나로 좁힌다(실제 수집과 같은 첨부 읽기: 미리보기/OCR/다운로드).
  2) 공고 본문이 extract_rows 로 넘어갈 때의 텍스트를 가로채 --grep 정규식이 든 공고만 골라, 일치 줄 주변을 출력하고 전체 본문을 파일로 저장한다.
  3) 지자체 규칙(Regions.rows_from_text)이 본문에서 읽은 원시 소재지와 최종 추출 행을 함께 보여 준다.

사용: python diag_notice.py --board-url https://www.incheon.go.kr/IC010303 --post-id 3092904 --grep 주안동 --out diag_out
"""

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def context_snippets(text, pattern, width=90, limit=12):
    """text 에서 pattern 일치 주변(앞뒤 width 글자)을 줄바꿈 없이 돌려준다(최대 limit 개, 겹치면 건너뜀)."""
    out, last_end = [], -1
    for m in re.finditer(pattern, text or ""):
        if m.start() < last_end:
            continue
        a, b = max(0, m.start() - width), min(len(text), m.end() + width)
        out.append(re.sub(r"\s+", " ", text[a:b]).strip())
        last_end = b
        if len(out) >= limit:
            break
    return out


def run(board_url, post_id, grep, days, module, city, kind, out_dir):
    import run_gazette as G
    from cms_adapters import gazette_generic
    from core import gazette_extractor as GX

    captured = []
    orig_list = gazette_generic.fetch_list_page
    orig_extract = GX.extract_rows

    def only_post(session, base_url, board, page_index, *a, **kw):
        rows = orig_list(session, base_url, board, page_index, *a, **kw)
        return [r for r in rows if str(post_id) in (r.get("detail_url") or "")]

    def recording_extract(notice, regions, *a, **kw):
        rows = orig_extract(notice, regions, *a, **kw)
        captured.append({"notice": notice, "regions": regions, "rows": rows, "title": kw.get("title", "")})
        return rows

    gazette_generic.fetch_list_page = only_post
    GX.extract_rows = recording_extract
    try:
        idx = G.regions_index()
        board = {"module": module, "province": "", "city": city, "kind": kind, "url": board_url, "judged": "", "manual": True}
        res = G.process_board((board, days, idx.get((module, city))))
    finally:
        gazette_generic.fetch_list_page = orig_list
        GX.extract_rows = orig_extract

    lines = [f"게시판 상태: {res['status']} | {res['detail']}",
             f"글 {res['posts']}건, 첨부 {res['attachments']}개, 공고 {res['notices']}건, 보상 공고 {res['comp_notices']}건, 주소 {res['rows']}건"]
    if res["errors"]:
        lines.append("오류: " + " / ".join(res["errors"][:5]))
    out_dir.mkdir(parents=True, exist_ok=True)
    hit = 0
    for i, c in enumerate(captured, 1):
        n = c["notice"]
        if grep and not re.search(grep, n):
            continue
        hit += 1
        (out_dir / f"notice_{i}.txt").write_text(n, encoding="utf-8")
        lines.append(f"===== 공고 {i}: {re.sub(chr(10), ' ', c['title'])[:90]} (본문 {len(n)}자, 추출 {len(c['rows'])}행)")
        lines.append("  [본문에서 일치한 곳]")
        lines += [f"    {s}" for s in context_snippets(n, grep or r"\d+-\d+", limit=10)]
        regions = c["regions"]
        if regions is not None and not callable(regions):
            try:
                raw = regions.rows_from_text(n)
                lines.append(f"  [지자체 규칙이 본문에서 읽은 원시 행 {len(raw)}건, 앞 8건]")
                lines += [f"    소재지={r.get('sojaeji','')!r} 지번={r.get('jibun_incl','')!r}" for r in raw[:8]]
            except Exception as e:  # 진단 도구라 오류를 그대로 보여 주고 계속한다
                lines.append(f"  [원시 행 읽기 오류] {type(e).__name__}: {str(e)[:120]}")
        lines.append("  [최종 추출 행 앞 12건]")
        lines += [f"    {r['sojaeji']} | {r['jimok']} | {r['area_incl']}" for r in c["rows"][:12]]
    if not hit:
        lines.append(f"--grep {grep!r} 에 맞는 보상 공고 본문이 없습니다(읽은 보상 공고 {len(captured)}건).")
    text = "\n".join(lines)
    (out_dir / "summary.txt").write_text(text, encoding="utf-8")
    print(text)
    return 0 if captured else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="공보 글 한 건의 공고 본문과 추출 결과를 보여 준다(읽기 전용)")
    ap.add_argument("--board-url", required=True)
    ap.add_argument("--post-id", required=True, help="글 주소에 들어 있는 번호(예: 3092904)")
    ap.add_argument("--grep", default="", help="이 정규식이 든 공고만 보여 준다")
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--module", default="인천")
    ap.add_argument("--city", default="인천광역시청")
    ap.add_argument("--kind", default="시보")
    ap.add_argument("--out", default="diag_out")
    a = ap.parse_args(argv)
    from diag_fetch import host_allowed
    if not host_allowed(a.board_url):
        print(f"[거부] *.go.kr 주소만 진단합니다: {a.board_url}")
        return 2
    if not re.fullmatch(r"[\w-]{1,40}", a.post_id):
        print("[거부] post-id 는 글자·숫자·-·_ 만 허용합니다")
        return 2
    return run(a.board_url, a.post_id, a.grep, a.days, a.module, a.city, a.kind, Path(a.out))


if __name__ == "__main__":
    sys.exit(main())
