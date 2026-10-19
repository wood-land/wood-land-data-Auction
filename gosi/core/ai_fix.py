"""
core/ai_fix.py - 규칙으로 PNU 변환이 안 된 주소를 DeepSeek 으로 정리해 다시 시도한다.

- AI 는 '정리'만 한다(시도/시군구/읍면동/리/지번을 JSON 으로). 최종 판정은 카카오가 한다:
  카카오 결과의 지번(본번·부번·산 여부)이 원문 지번과 정확히 같고, 지자체(시·군·구)가 맞을 때만 PNU 로 인정.
- 같은 입력은 ai_cache 표에 저장해 다시 부르지 않는다(실패 포함).
- 키: 환경변수 DEEPSEEK_API_KEY (GitHub Secret) 또는 500_local/101. Deepseek API key/ 안 파일('API key : ...' 또는 sk-...).
  키가 없으면 enabled=False 로 조용히 건너뛴다.
- 이미 읍면동·리까지 온전한 소재지는 AI 가 해줄 게 없어 호출하지 않는다(없는 지번일 뿐).
"""
import json
import os
import re
from pathlib import Path

import requests

from core.local_dir import find_dirs

URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"
MAX_CALLS_PER_RUN = 1500

SYSTEM = (
    "너는 한국 토지 주소 정규화기다. 입력은 고시공고에서 추출한 소재지·지번 조각이며 시도/시군구/읍면/리가 "
    "빠지거나 글자가 깨져 있을 수 있다. 입력의 지자체명(city)과 제목을 단서로 정식 행정구역명으로 복원해 JSON 만 출력한다. "
    '형식: {"sido":..., "sigungu":..., "eupmyeondong":..., "ri":..., "jibun":...}. '
    "규칙: 지번의 숫자와 '산'은 절대 바꾸지 마라. 확실하지 않으면 해당 값을 null 로 둬라. 추측으로 지어내지 마라."
)


def load_key():
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        return key
    for folder in find_dirs(r"deepseek"):
        for f in folder.rglob("*"):
            if not f.is_file():
                continue
            text = f.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"sk-[A-Za-z0-9]{20,}", text) or re.search(r"API\s*key\s*[:：]\s*([A-Za-z0-9_\-]{20,})", text, re.I)
            if m:
                return m.group(m.lastindex or 0)
    return ""


def _complete(sojaeji):
    """시·군·구 + 읍면동 + 리/동 까지 다 있으면 True (AI 가 보탤 정보가 없다)."""
    w = (sojaeji or "").split()
    has_sigun = any(re.search(r"[가-힣]{1,5}[시군구]$", x) for x in w)
    has_eup = any(re.search(r"[가-힣0-9]{1,5}[읍면동가]$", x) for x in w)
    has_ri = bool(w) and re.search(r"[가-힣0-9]{1,6}[리동가]$", w[-1]) is not None
    return has_sigun and has_eup and has_ri


class AiFixer:
    def __init__(self, resolver):
        self.r = resolver
        self.key = load_key()
        self.enabled = bool(self.key)
        self.calls = 0
        resolver.con.execute(
            "CREATE TABLE IF NOT EXISTS cache.ai_cache (key TEXT PRIMARY KEY, answer TEXT, created_at TEXT)"
        )

    def _ask(self, payload):
        try:
            resp = requests.post(
                URL, timeout=40,
                headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
                json={"model": MODEL, "temperature": 0, "response_format": {"type": "json_object"},
                      "messages": [{"role": "system", "content": SYSTEM},
                                   {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]},
            )
            resp.raise_for_status()
            return json.loads(resp.json()["choices"][0]["message"]["content"])
        except (requests.RequestException, KeyError, ValueError, IndexError):
            return "ERR"

    def fix(self, sojaeji, jibun, city, title="", project=""):
        from core.pnu import parse_jibun

        want = parse_jibun(jibun)
        if not want or _complete(sojaeji):
            return None
        con = self.r.con
        ck = f"{sojaeji}|{jibun}|{city}"
        row = con.execute("SELECT answer FROM cache.ai_cache WHERE key=?", (ck,)).fetchone()
        if row:
            ans = json.loads(row[0])
        else:
            if self.calls >= MAX_CALLS_PER_RUN:
                return None
            self.calls += 1
            self.r.stats["ai_call"] += 1
            ans = self._ask({"city": city, "title": (title or "")[:120], "sojaeji": sojaeji, "jibun": jibun,
                             "project": (project or "")[:60]})
            if ans == "ERR":
                self.r._transient = True  # 일시 오류: 캐시하지 않고 다음 실행에서 재시도
                return None
            con.execute("INSERT OR REPLACE INTO cache.ai_cache VALUES (?,?,datetime('now'))",
                        (ck, json.dumps(ans, ensure_ascii=False)))
            con.commit()
        if not isinstance(ans, dict):
            return None
        parts = [ans.get(k) for k in ("sido", "sigungu", "eupmyeondong", "ri")]
        if not parts[3] and not parts[2]:
            return None
        # 환각 방지(2026-10-18): AI 가 돌려준 읍면동·리 이름은 입력(소재지 조각·제목·사업명)에 실제로 적힌 것이어야 한다.
        # 지번 숫자만 지키고 지명은 지어내게 두면, 쓰레기 행('착공일로부터 60일간' 의 60)에 '사벌국면 덕가리' 를 붙여 카카오에
        # 실존하는 엉뚱한 필지로 저장된다(상주시 견적 공고에서 실제로 5건 발생).
        evidence = re.sub(r"\s+", "", f"{sojaeji} {title or ''} {project or ''}")
        for name in (parts[2], parts[3]):
            stem = re.sub(r"(읍|면|동|리|가)$", "", str(name or "").strip())
            if stem and stem not in evidence:
                return None
        tail = f"{'산' if want[0] else ''}{want[1]}" + (f"-{want[2]}" if want[2] else "")
        query = " ".join(str(x) for x in parts if x) + " " + tail
        data, state = self.r._call(query)
        self.r.stats["api"] += 1
        if state != "ok":
            return None
        stem = re.sub(r"(특별자치시|특별시|광역시|시|군|구)$", "", city or "")
        constrain = bool(city) and city.endswith(("시", "군", "구")) and len(stem) >= 2
        for d in data.get("documents", []):
            m = self.r._match(d, want)
            if not m:
                continue
            if constrain and stem not in m[2]:
                continue  # AI 가 다른 지자체로 추정한 경우 거부
            self.r.stats["ai_ok"] += 1
            self.r.last_full = m[3]
            return m[0]
        return None
