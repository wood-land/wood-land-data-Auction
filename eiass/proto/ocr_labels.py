"""지번 글자 OCR (tesseract CLI). 도면 쪽 이미지 -> [(text, cx, cy)] (쪽 px)"""
import csv, io, re, subprocess, tempfile, os
import cv2
import numpy as np

TESS = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
JIBUN = re.compile(r"^(산)?(\d{1,4})(?:-(\d{1,3}))?([가-힣])?$")


def ocr_tiles(img, tile=1000, pad=60, up=2.0, psm=11):
    """큰 도면을 타일로 잘라 확대해 OCR. 반환 [(text, cx, cy, conf)]"""
    H, W = img.shape[:2]
    out = []
    for y in range(0, H, tile):
        for x in range(0, W, tile):
            x0, y0 = max(0, x - pad), max(0, y - pad); x1, y1 = min(W, x + tile + pad), min(H, y + tile + pad)
            sub = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_RGB2GRAY)
            sub = cv2.resize(sub, None, fx=up, fy=up, interpolation=cv2.INTER_CUBIC)
            with tempfile.TemporaryDirectory() as d:
                p = os.path.join(d, "t.png"); cv2.imwrite(p, sub)
                r = subprocess.run([TESS, p, "stdout", "-l", "kor+eng", "--psm", str(psm), "tsv"],
                                   capture_output=True, text=True, encoding="utf-8")
            for row in csv.DictReader(io.StringIO(r.stdout), delimiter="\t", quoting=csv.QUOTE_NONE):
                t = (row.get("text") or "").strip()
                if not t or float(row.get("conf") or -1) < 0:
                    continue
                l, tp, w, h = (float(row[k]) for k in ("left", "top", "width", "height"))
                out.append((t, x0 + (l + w / 2) / up, y0 + (tp + h / 2) / up, float(row["conf"])))
    return out


def jibun_tokens(toks):
    res = []
    for t, cx, cy, c in toks:
        t2 = t.replace(" ", "").replace("—", "-").replace("–", "-").replace("_", "-")
        m = JIBUN.match(t2)
        if m and (m.group(3) or m.group(4) or m.group(1)):
            res.append({"txt": t2, "san": bool(m.group(1)), "bon": int(m.group(2)), "bu": int(m.group(3) or 0),
                        "jimok": m.group(4) or "", "x": cx, "y": cy, "conf": c})
    return res
