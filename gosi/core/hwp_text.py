"""
core/hwp_text.py — 구버전 한글(.hwp, HWP 5.x 이진 형식)에서 본문 텍스트만 뽑는다. 외부 패키지 없이 표준 라이브러리만 사용.

.hwp 는 MS 복합 문서(OLE CFB) 컨테이너다. 구조:
  FileHeader                  — 서명 "HWP Document File", 속성(bit0 압축, bit1 암호, bit2 배포용)
  BodyText/Section0, Section1 — 레코드 열(압축 시 raw deflate). PARA_TEXT(태그 67)가 문단 본문(UTF-16LE)
1) CFB 읽기(read_streams)  2) 레코드에서 PARA_TEXT만 이어 붙이기(hwp_to_text)
암호/배포용 문서(본문이 암호화됨)는 지원하지 않고 HwpUnsupported 를 던진다.
"""

import struct
import zlib

CFB_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
ENDOFCHAIN = 0xFFFFFFFE
FREESECT = 0xFFFFFFFF
HWPTAG_PARA_TEXT = 67


class HwpUnsupported(Exception):
    pass


class _CFB:
    def __init__(self, data):
        if data[:8] != CFB_SIGNATURE:
            raise HwpUnsupported("OLE 복합 문서가 아님")
        self.data = data
        self.sec = 1 << struct.unpack_from("<H", data, 0x1E)[0]
        self.mini_sec = 1 << struct.unpack_from("<H", data, 0x20)[0]
        n_fat, first_dir, _, cutoff, first_minifat, n_minifat, first_difat, n_difat = struct.unpack_from(
            "<IIIIIIII", data, 0x2C
        )
        self.cutoff = cutoff
        difat = list(struct.unpack_from("<109I", data, 0x4C))
        sec = first_difat
        for _ in range(n_difat):
            if sec in (ENDOFCHAIN, FREESECT):
                break
            raw = self._sector(sec)
            vals = struct.unpack("<%dI" % (self.sec // 4), raw)
            difat += list(vals[:-1])
            sec = vals[-1]
        fat = []
        for s in difat[:n_fat] if n_fat else difat:
            if s in (ENDOFCHAIN, FREESECT):
                continue
            fat += struct.unpack("<%dI" % (self.sec // 4), self._sector(s))
        self.fat = fat
        self.dir_entries = self._read_dir(self._chain(first_dir))
        root = self.dir_entries[0]
        self.mini_stream = self._read_chain_bytes(root["start"], root["size"]) if root["size"] else b""
        self.minifat = []
        if n_minifat and first_minifat not in (ENDOFCHAIN, FREESECT):
            raw = self._read_chain_bytes(first_minifat, None)
            self.minifat = list(struct.unpack("<%dI" % (len(raw) // 4), raw[: len(raw) // 4 * 4]))

    def _sector(self, n):
        off = (n + 1) * self.sec
        return self.data[off: off + self.sec]

    def _chain(self, start):
        out, seen = [], set()
        s = start
        while s not in (ENDOFCHAIN, FREESECT) and s < len(self.fat) and s not in seen:
            seen.add(s)
            out.append(s)
            s = self.fat[s]
        return out

    def _read_chain_bytes(self, start, size):
        raw = b"".join(self._sector(s) for s in self._chain(start))
        return raw if size is None else raw[:size]

    def _read_dir(self, sectors):
        raw = b"".join(self._sector(s) for s in sectors)
        entries = []
        for i in range(0, len(raw), 128):
            e = raw[i: i + 128]
            if len(e) < 128:
                break
            nlen = struct.unpack_from("<H", e, 0x40)[0]
            name = e[: max(0, nlen - 2)].decode("utf-16-le", "replace")
            typ = e[0x42]
            left, right, child = struct.unpack_from("<III", e, 0x44)
            start = struct.unpack_from("<I", e, 0x74)[0]
            size = struct.unpack_from("<Q", e, 0x78)[0] & 0xFFFFFFFF
            entries.append({"name": name, "type": typ, "left": left, "right": right, "child": child, "start": start, "size": size})
        return entries

    def paths(self):
        """{'BodyText/Section0': 항목, ...}"""
        out = {}

        def walk(idx, prefix):
            stack, seen = [idx], set()
            while stack:
                i = stack.pop()
                if i == FREESECT or i >= len(self.dir_entries) or i in seen:
                    continue
                seen.add(i)
                e = self.dir_entries[i]
                path = prefix + e["name"]
                out[path] = e
                stack.append(e["left"])
                stack.append(e["right"])
                if e["type"] == 1 and e["child"] != FREESECT:
                    walk(e["child"], path + "/")

        walk(self.dir_entries[0]["child"], "")
        return out

    def stream(self, entry):
        if entry["size"] < self.cutoff:
            out, s = [], entry["start"]
            seen = set()
            while s not in (ENDOFCHAIN, FREESECT) and s < len(self.minifat) and s not in seen:
                seen.add(s)
                out.append(self.mini_stream[s * self.mini_sec: (s + 1) * self.mini_sec])
                s = self.minifat[s]
            return b"".join(out)[: entry["size"]]
        return self._read_chain_bytes(entry["start"], entry["size"])


def _para_text(rec):
    """PARA_TEXT 레코드(UTF-16LE) -> 문자열. 제어문자: 10/13 줄바꿈, 1~9·11~12·14~23은 8글자(16바이트) 차지."""
    out, i, n = [], 0, len(rec)
    while i + 1 < n:
        ch = rec[i] | (rec[i + 1] << 8)
        if ch >= 32:
            out.append(chr(ch))
            i += 2
        elif ch in (10, 13):
            out.append("\n")
            i += 2
        elif ch == 0 or ch >= 24:
            i += 2
        else:
            if ch == 9:
                out.append("\t")
            i += 16
    return "".join(out)


def _records(data):
    i, n = 0, len(data)
    while i + 4 <= n:
        header = struct.unpack_from("<I", data, i)[0]
        tag, size = header & 0x3FF, header >> 20
        i += 4
        if size == 0xFFF:
            if i + 4 > n:
                break
            size = struct.unpack_from("<I", data, i)[0]
            i += 4
        yield tag, data[i: i + size]
        i += size


def hwp_to_text(data):
    """구버전 .hwp 바이트 -> 본문 텍스트(문단마다 줄바꿈). 지원 불가면 HwpUnsupported."""
    cfb = _CFB(data)
    paths = cfb.paths()
    if "FileHeader" not in paths:
        raise HwpUnsupported("FileHeader 없음(한글 문서가 아님)")
    header = cfb.stream(paths["FileHeader"])
    if not header.startswith(b"HWP Document File"):
        raise HwpUnsupported("HWP 서명이 아님")
    flags = struct.unpack_from("<I", header, 36)[0]
    compressed, encrypted, distribution = bool(flags & 1), bool(flags & 2), bool(flags & 4)
    if encrypted:
        raise HwpUnsupported("암호가 걸린 문서")
    prefix = "ViewText/" if distribution else "BodyText/"
    if distribution and "BodyText/Section0" not in paths:
        raise HwpUnsupported("배포용 문서(본문 암호화)")
    sections = sorted((p for p in paths if p.startswith("BodyText/Section")), key=lambda p: int(p.rsplit("Section", 1)[1]))
    if not sections:
        raise HwpUnsupported("본문 섹션 없음")
    out = []
    for p in sections:
        raw = cfb.stream(paths[p])
        if compressed:
            try:
                raw = zlib.decompress(raw, -15)
            except zlib.error as e:
                raise HwpUnsupported(f"압축 해제 실패: {e}")
        for tag, rec in _records(raw):
            if tag == HWPTAG_PARA_TEXT:
                t = _para_text(rec)
                if t.strip():
                    out.append(t.rstrip("\n"))
    return "\n".join(out)
