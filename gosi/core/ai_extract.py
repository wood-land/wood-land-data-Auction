"""
core/ai_extract.py - 규칙(표 열 판별·본문 정규식)으로 필지를 못 뽑은 첨부문서를 DeepSeek 으로 읽는다.

언제: core/jose_extractor.extract_from_attachment 가 표·본문 규칙으로 0행이거나 모든 행의 소재지를 못 찾았을 때만.
방식: 문서 본문 텍스트를 조각내 DeepSeek 에 보내 {소재지, 지번, 지목, 면적} 목록을 JSON 으로 받는다.
안전장치(환각 방지): 돌려받은 지번이 문서 본문에 실제로 적힌 숫자(본번-부번)일 때만 인정한다.
  최종 판정은 PNU 변환(카카오 검증)이 한 번 더 한다.
비용 방지: 같은 본문은 data/gosi/.cache/ai_doc_cache.sqlite 에 캐시(git 제외, 실패 포함), 실행당 호출 상한 MAX_CALLS_PER_RUN.
키: core/ai_fix.load_key() 와 같다(DEEPSEEK_API_KEY 또는 500_local). 키가 없으면 enabled=False 로 조용히 건너뛴다.
"""
import hashlib
import json
import os
import re
import sqlite3
import threading
from pathlib import Path

import requests

from core.ai_fix import MODEL, URL, load_key
from core.paths import DATA_DIR

MAX_CALLS_PER_RUN = 60
CHUNK_CHARS = 6000
MAX_CHUNKS = 8

SYSTEM = (
    "너는 한국 토지보상·고시공고 문서에서 '편입(수용·사용) 토지 목록'만 뽑는 추출기다. 입력은 문서 본문 텍스트 조각이다. "
    "표 머리글·합계·사업 개요·소유자 이름은 무시하고, 필지(소재지+지번)만 JSON 으로 출력한다. "
    '형식: {"parcels":[{"sojaeji":"시도 시군구 읍면 리(또는 동)","jibun":"산12-3 또는 157-2","jimok":"답","area":"123.4"}]}. '
    "규칙: 지번의 숫자와 '산'은 문서에 적힌 그대로 쓰고 절대 바꾸거나 만들지 마라. 소재지가 표 위 제목줄이나 문장에 한 번만 "
    "적혀 있으면 그 아래 필지 모두에 적용하라. 소재지를 알 수 없으면 sojaeji 를 빈 문자열로 둬라. 문서에 없는 필지는 지어내지 마라. "
    "필지가 없으면 {\"parcels\":[]}."
)

_lock = threading.Lock()


def _cache_path():
    base = os.environ.get("GOSI_CACHE_DIR") or str(DATA_DIR / ".cache")
    return Path(base) / "ai_doc_cache.sqlite"


class AiDocExtractor:
    def __init__(self):
        self.key = load_key()
        self.enabled = bool(self.key)
        self.calls = 0
        self.last_error = ""
        self.last_failed = 0  # 직전 extract 에서 실패한 조각 수(0 이면 AI 가 정상 응답했다는 뜻)

    # ---- 캐시 -------------------------------------------------------------------------------
    def _cache_get(self, k):
        try:
            with _lock:
                p = _cache_path()
                p.parent.mkdir(parents=True, exist_ok=True)
                con = sqlite3.connect(p)
                con.execute("CREATE TABLE IF NOT EXISTS doc_cache (key TEXT PRIMARY KEY, answer TEXT, created_at TEXT)")
                row = con.execute("SELECT answer FROM doc_cache WHERE key=?", (k,)).fetchone()
                con.close()
            return json.loads(row[0]) if row else None
        except (sqlite3.Error, OSError, ValueError):
            return None

    def _cache_put(self, k, answer):
        try:
            with _lock:
                con = sqlite3.connect(_cache_path())
                con.execute("INSERT OR REPLACE INTO doc_cache VALUES (?,?,datetime('now'))",
                            (k, json.dumps(answer, ensure_ascii=False)))
                con.commit()
                con.close()
        except (sqlite3.Error, OSError):
            pass

    # ---- DeepSeek 호출 --------------------------------------------------------------------------
    def _ask(self, hint, chunk):
        try:
            resp = requests.post(
                URL, timeout=90,
                headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
                json={"model": MODEL, "temperature": 0, "response_format": {"type": "json_object"},
                      "messages": [{"role": "system", "content": SYSTEM},
                                   {"role": "user", "content": json.dumps({"hint": hint, "text": chunk}, ensure_ascii=False)}]},
            )
            resp.raise_for_status()
            return json.loads(resp.json()["choices"][0]["message"]["content"])
        except (requests.RequestException, KeyError, ValueError, IndexError) as e:
            self.last_error = f"{type(e).__name__}: {str(e)[:100]}"
            return None

    @staticmethod
    def _in_text(jibun, text_digits):
        """AI 가 준 지번의 본번[-부번]이 문서 본문에 숫자로 실제 있는지(공백 제거 후 비교)."""
        m = re.fullmatch(r"산?(\d+)(?:-(\d+))?", re.sub(r"\s", "", jibun or ""))
        if not m:
            return False
        want = m.group(1) + ("-" + m.group(2) if m.group(2) else "")
        return re.search(rf"(?<![\d-]){re.escape(want)}(?![\d])", text_digits) is not None

    @staticmethod
    def _place_in_text(sojaeji, text_nospace):
        """AI 가 돌려준 소재지의 읍면동·리 이름(접미사 뺀 부분)이 본문에 실제로 있는가. 읍면동·리 이름이 하나도 없으면 False."""
        names = re.findall(r"[가-힣0-9]{1,6}(?:읍|면|동|리|가)", re.sub(r"\s+", " ", sojaeji))
        if not names:
            return False
        for name in names:
            stem = re.sub(r"(읍|면|동|리|가)$", "", name)
            if stem and stem not in text_nospace:
                return False
        return True

    def extract(self, text, title="", city=""):
        """-> (필지 dict 리스트 [{sojaeji, jibun, jimok, area_incl}], 메모 문자열).
        문서 본문이 없거나 키가 없으면 ([], 사유)."""
        self.last_failed = 0
        if not self.enabled:
            return [], "DeepSeek 키 없음"
        text = (text or "").strip()
        if len(text) < 30:
            return [], "본문 텍스트 없음(이미지 문서)"
        hint = f"지자체={city}; 제목={(title or '')[:120]}"
        key = hashlib.sha1((hint + text).encode("utf-8")).hexdigest()
        cached = self._cache_get(key)
        if cached is not None:
            return cached["rows"], cached["note"] + " (캐시)"
        chunks = [text[i:i + CHUNK_CHARS] for i in range(0, len(text), CHUNK_CHARS)][:MAX_CHUNKS]
        if self.calls + len(chunks) > MAX_CALLS_PER_RUN:
            return [], f"AI 호출 상한({MAX_CALLS_PER_RUN}) 초과"
        text_digits = re.sub(r"\s*-\s*", "-", text)
        text_nospace = re.sub(r"\s+", "", text)
        rows, dropped, failed = [], 0, 0
        for ch in chunks:
            self.calls += 1
            ans = self._ask(hint, ch)
            if not isinstance(ans, dict):
                failed += 1
                continue
            for p in ans.get("parcels") or []:
                if not isinstance(p, dict):
                    continue
                j = re.sub(r"\s", "", str(p.get("jibun") or ""))
                if not self._in_text(j, text_digits):
                    dropped += 1
                    continue
                if not self._place_in_text(str(p.get("sojaeji") or ""), text_nospace):
                    dropped += 1  # 환각 방지: 지번뿐 아니라 읍면동·리 이름도 본문에 실제 있어야 한다(지어낸 지명 거부)
                    continue
                rows.append({"sojaeji": re.sub(r"\s+", " ", str(p.get("sojaeji") or "")).strip(), "jibun": j,
                             "jimok": str(p.get("jimok") or "").strip()[:4],
                             "area_incl": re.sub(r"[^\d.]", "", str(p.get("area") or ""))})
        seen, uniq = set(), []
        for r in rows:
            k = (r["sojaeji"], r["jibun"])
            if k not in seen:
                seen.add(k)
                uniq.append(r)
        self.last_failed = failed
        note = f"AI {len(uniq)}필지(본문에 없는 지번 {dropped}건 버림, 조각 {len(chunks)}개 중 실패 {failed})"
        if failed == 0:  # 일시 오류가 아닐 때만 캐시한다
            self._cache_put(key, {"rows": uniq, "note": note})
        elif not uniq:
            note += f" {self.last_error}"
        return uniq, note


AI_DOC = AiDocExtractor()
