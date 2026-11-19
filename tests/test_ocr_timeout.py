"""OCR 한 쪽이 시간초과여도 문서 전체가 실패하지 않는지 확인한다(2026-11 군보·시보 스캔 PDF 'TimeoutExpired' 16곳)."""
import io
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gosi"))
from core import gazette_extractor as GX  # noqa: E402


def _png():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("L", (200, 100), 255).save(buf, "PNG")
    return buf.getvalue()


class _P:
    def __init__(self, out): self.stdout = out.encode()


def test_timeout_then_retry_with_smaller_image(monkeypatch):
    calls = []

    def fake_run(cmd, input, capture_output, timeout, env):
        calls.append((len(input), timeout, env.get("OMP_THREAD_LIMIT")))
        if len(calls) == 1:
            raise subprocess.TimeoutExpired(cmd, timeout)
        return _P("본문")
    monkeypatch.setattr(GX.subprocess, "run", fake_run)
    assert GX._ocr_png(_png(), "kor") == "본문"
    assert len(calls) == 2 and calls[0][2] == "1"


def test_double_timeout_skips_page_not_document(monkeypatch):
    def fake_run(cmd, input, capture_output, timeout, env):
        raise subprocess.TimeoutExpired(cmd, timeout)
    monkeypatch.setattr(GX.subprocess, "run", fake_run)
    before = GX.OCR_SKIPPED_PAGES
    assert GX._ocr_png(_png(), "kor") == ""
    assert GX.OCR_SKIPPED_PAGES == before + 1
