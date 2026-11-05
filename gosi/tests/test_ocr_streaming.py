# -*- coding: utf-8 -*-
"""스캔 PDF OCR: 쪽 순서 유지, 앞서 만드는 쪽 수 제한, 문서는 한 번에 하나만."""
import threading
import time

from core import gazette_extractor as GX


def _fake(monkeypatch, n_pages, made, ocr_delay=0.01):
    monkeypatch.setattr(GX, "ocr_available", lambda: True)

    def pages(data, scale, max_pages):
        for i in range(n_pages):
            made.append(i)
            yield str(i).encode()

    def ocr(png, lang):
        time.sleep(ocr_delay)
        return f"p{png.decode()}"

    monkeypatch.setattr(GX, "_iter_pages", pages)
    monkeypatch.setattr(GX, "_ocr_png", ocr)


def test_page_order_kept(monkeypatch):
    _fake(monkeypatch, 10, [])
    assert GX.ocr_pdf_text(b"x") == "\n".join(f"p{i}" for i in range(10))


def test_pages_not_all_made_up_front(monkeypatch):
    made, seen = [], []
    _fake(monkeypatch, 30, made, ocr_delay=0.05)
    orig = GX._ocr_png

    def watching(png, lang):
        seen.append(len(made) - len(seen))  # OCR 이 끝나지 않은 채 만들어진 쪽 수
        return orig(png, lang)

    monkeypatch.setattr(GX, "_ocr_png", watching)
    GX.ocr_pdf_text(b"x")
    assert max(seen) <= GX.OCR_AHEAD + 2


def test_one_document_at_a_time(monkeypatch):
    made = []
    _fake(monkeypatch, 5, made)
    active, peak, lock = [0], [0], threading.Lock()
    orig = GX._iter_pages

    def counting(data, scale, max_pages):
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        try:
            yield from orig(data, scale, max_pages)
        finally:
            with lock:
                active[0] -= 1

    monkeypatch.setattr(GX, "_iter_pages", counting)
    ts = [threading.Thread(target=GX.ocr_pdf_text, args=(b"x",)) for _ in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert peak[0] == 1
