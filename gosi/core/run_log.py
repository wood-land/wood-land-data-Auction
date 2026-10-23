"""
core/run_log.py - 수집 중 생긴 문제를 엑셀(xlsx)로 남겨, 어떤 문제인지 즉시 단서를 찾게 한다.

저장 위치: data/logs/{지역}_수집로그.xlsx (git 에 올라가는 작은 파일, 실행할 때마다 아래에 이어 붙고 시트당 MAX_ROWS 행까지만 유지)
시트
  - 문서처리   : 첨부파일 1개 = 1행. 다운로드/형식/표 해석/AI 보정 결과와 원인코드, 조치 힌트
  - PNU실패    : PNU 로 못 바꾼 필지 1개 = 1행. 사유코드와 원인 설명, 조치 힌트
  - 게시판상태 : 공보 게시판별 수집 상태(목록 못 읽음/첨부 못 찾음 등)와 조치 힌트
  - 실행요약   : 실행 단위(고시공고/공보/재시도) 요약

사용: `from core.run_log import LOG` 로 쓰는 싱글톤. 스레드 안전(공보는 스레드 풀로 돈다).
수집 흐름은 LOG.doc(...)/LOG.pnu_fail(...)/LOG.board(...) 만 부르고, 파일은 실행 끝에 LOG.flush(경로) 한 번으로 쓴다.
로그 기록 실패(파일 열림·권한 등)는 수집을 멈추지 않는다 - 콘솔에 경고만 남긴다.

구글시트(선택): 환경변수 GOOGLE_SHEET_ID 와 서비스 계정 키(GOOGLE_CREDENTIALS_EDITER 또는 GOOGLE_SA_KEY_JSON_ADMIN 에 JSON 전체,
없으면 500_local/100. Google_credentials/google_credentials_편집자.json)가 있으면 flush 때 같은 내용을 시트에도 이어 붙인다.
시트 탭 이름은 '{지역}_{시트명}'(예: 경기_문서처리), 첫 행은 머리글. 서비스 계정을 시트의 편집자로 공유해야 한다.
"""
import json
import os
import re
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path

from core.local_dir import google_key_file, sheet_id as local_sheet_id

MAX_ROWS = 4000  # 시트당 보존 행수(오래된 것부터 버린다)
KST = timezone(timedelta(hours=9))

SHEETS = {
    "문서처리": ["시각", "지역", "지자체", "출처", "게시글 제목", "게시글 URL", "첨부파일", "형식", "결과",
              "추출 행수", "원인코드", "상세", "조치 힌트"],
    "PNU실패": ["시각", "지역", "지자체", "출처", "소재지", "지번", "지목", "사유코드", "원인 설명", "조치 힌트",
              "게시글 제목", "게시글 URL"],
    "게시판상태": ["시각", "지역", "지자체", "종류", "상태", "상세", "게시물", "첨부", "공고", "보상공고", "행수",
               "오류", "조치 힌트", "게시판 URL"],
    "실행요약": ["시각", "지역", "작업", "요약"],
}

# 문서 처리 결과 원인코드 -> (설명, 조치 힌트)
DOC_HINTS = {
    "OK": ("정상", ""),
    "DL_FAIL": ("첨부 다운로드 실패",
                "HTTP 상태/타임아웃 확인. 400·403 이면 Referer(상세 URL)·쿠키 필요, 404 이면 게시물 만료. 어댑터의 download_attachment 점검"),
    "UNSUPPORTED": ("지원하지 않는 첨부 형식",
                    "구버전 .hwp/이미지는 표 추출 불가: core/hwp_text.py 또는 OCR(synap 미리보기) 경로 검토, 급하면 수동 확인"),
    "PARSE_ERROR": ("첨부 해석 중 예외", "상세 컬럼의 예외 메시지 확인. 파일이 손상/암호화됐거나 라이브러리 미설치(pdfplumber/openpyxl)일 수 있다"),
    "ZERO_ROWS": ("표·본문에서 지번을 못 찾음",
                  "표 머리글이 COLUMN_RULES 에 없거나 이미지(스캔) PDF 일 수 있다. 첨부를 직접 열어 지번 열 이름 확인 후 core/jose_extractor.py 의 COLUMN_RULES 보강"),
    "NO_REGION": ("지번은 읽었으나 소재지(읍면동리)를 못 읽음",
                  "소재지가 표 열이 아니라 표 위 제목줄/본문에 있는 양식일 수 있다. region_heading 규칙 또는 Regions 목록(법정동/리) 보강"),
    "ADDR_CHECK": ("소재지 일부가 검증 실패(CHECK/BAD)", "Regions 에 없는 동/리일 수 있다. 상세의 미등록 지명을 지자체 regions 파일에 추가"),
    "NON_PARCEL_LOT": ("블록/획지 번호를 지번으로 오인할 뻔함(제외됨)", "정상 제외. 지구단위계획의 'A1 1-4' 같은 번호는 PNU 대상이 아니다"),
    "AI_USED": ("규칙 추출 실패 -> DeepSeek 으로 추출", "AI 추출은 원문에 지번이 실제 있는 것만 인정. 같은 양식이 반복되면 규칙(COLUMN_RULES/region_heading)으로 승격"),
    "AI_FAIL": ("규칙·AI 모두 추출 실패", "문서 원문 확인 필요(이미지 PDF/비표준 양식). 사람이 보고 규칙 추가"),
    "FORM": ("양식 첨부(의견서·신청서 등)", "정상. 필지 목록이 아니라 읽지 않았다"),
    "NOT_LAND": ("입찰·설계·계약 서류", "정상. 제목 키워드에 걸렸지만 필지 목록이 아니라 읽지 않았다. 오탐이 잦으면 해당 지자체 BLACKLIST 후보(law.md 2절: 사용자 확인 후)"),
    "ALL_PUBLIC": ("소유자가 전부 국가·지자체·공공기관", "정상. 사유지만 수집하는 규칙(사용자 지시)에 따라 제외. 사유지가 빠졌다면 소유자 열 해석(is_public_owner)을 점검"),
    "NO_PARCELS": ("문서에 필지 목록 없음(AI 확인)", "정상일 가능성이 큼. 보상 대상 공고인데 계속 이 코드면 '별첨 참조' 등 다른 첨부에 목록이 있는지 확인"),
    "NO_ATTACH": ("첨부파일을 못 찾음", "상세 페이지 구조가 바뀌었을 수 있다. 어댑터 fetch_attachments 점검"),
}

# PNU 변환 사유코드 -> (설명, 조치 힌트)
PNU_HINTS = {
    "no_match": ("카카오 주소검색에서 해당 지번을 못 찾음(규칙·AI 보정·리 코드 조립 모두 실패)",
                 "소재지 오기재/분할·폐지 지번일 수 있다. 원문 소재지와 카카오 지도에서 해당 리·지번 존재 확인"),
    "no_region": ("소재지(읍면동리)가 없어 지번만 있음", "추출 단계 문제. 문서 처리 시트에서 같은 게시글의 NO_REGION 확인 후 jose_extractor 규칙 보강"),
    "not_parcel": ("합계·필지 수·기간 같은 말이 소재지 칸에 들어간 행(필지가 아님)", "정상 제외. 추출 단계에서 자주 나오는 양식이면 jose/gazette_extractor 의 행 규칙에 제외 조건 추가"),
    "no_jibun": ("지번을 못 읽음", "지번 셀 형식 확인(parse_jibun)"),
    "no_key": ("카카오 REST 키 없음", "KAKAO_REST_API_KEY 환경변수/Secret 확인"),
    "transient": ("네트워크/API 일시 오류", "다음 실행에서 자동 재시도. 반복되면 카카오 호출 한도(429)·키 권한 확인"),
}

BOARD_HINTS = {
    "목록 못 읽음": "게시판 목록 HTML 구조가 달라졌다. 사용자 입력 URL(엑셀 L열)을 확인하고 gazette_generic 어댑터가 읽는 날짜/제N호 패턴 점검",
    "오류(목록)": "목록 요청 자체가 실패(타임아웃/차단/SSL). 오류 컬럼의 예외명 확인, 재시도 또는 URL 변경 여부 확인",
    "첨부 못 찾음": "게시글은 있으나 PDF/HWP 첨부 링크를 못 찾음. 상세 페이지의 JS 링크(fn_view 등) 또는 미리보기 경로 점검",
    "본문 추출 실패": "첨부는 받았으나 본문 텍스트 추출 실패(이미지 PDF/암호문서). OCR 경로(synap_preview) 동작 확인",
    "최근 게시물 없음": "수집 기간 내 게시물이 없다(정상일 수 있음). 오래 계속되면 URL/날짜 인식 확인",
}


def _now():
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")


class RunLog:
    def __init__(self):
        self._lock = threading.Lock()
        self._rows = {name: [] for name in SHEETS}
        self.region = ""

    def _add(self, sheet, row):
        with self._lock:
            self._rows[sheet].append(row)

    def doc(self, city, source, title, url, filename, ext, result, rows=0, code="OK", detail=""):
        """첨부파일 1개 처리 결과. result: '성공'/'실패'/'건너뜀'/'AI보정' 등 사람이 읽는 말, code: DOC_HINTS 의 키."""
        hint = DOC_HINTS.get(code, ("", ""))[1]
        self._add("문서처리", [_now(), self.region, city, source, (title or "")[:120], url or "", filename or "",
                            ext or "", result, rows, code, (detail or "")[:300], hint])

    def pnu_fail(self, city, source, sojaeji, jibun, jimok, reason, title, url):
        desc, hint = PNU_HINTS.get(reason, (reason, ""))
        self._add("PNU실패", [_now(), self.region, city, source, sojaeji or "", jibun or "", jimok or "", reason,
                            desc, hint, (title or "")[:120], url or ""])

    def board(self, r, errors=""):
        """공보 게시판 1곳의 수집 상태(run_gazette.process_board 결과 dict)."""
        status = r.get("status", "")
        hint = ""
        for k, v in BOARD_HINTS.items():
            if status.startswith(k):
                hint = v
        if not hint and r.get("errors"):
            hint = "오류 컬럼 확인"
        self._add("게시판상태", [_now(), self.region, r.get("city", ""), r.get("kind", ""), status, r.get("detail", ""),
                             r.get("posts", 0), r.get("attachments", 0), r.get("notices", 0), r.get("comp_notices", 0),
                             r.get("rows", 0), errors, hint, r.get("url", "")])

    def summary(self, job, text):
        self._add("실행요약", [_now(), self.region, job, text[:500]])

    def code_summary(self):
        """이번 실행의 문서처리 원인코드별 개수. 예: '문서 40건 [OK 9, 건너뜀(양식·입찰) 7, AI_FAIL 2]'.
        파일명 규칙으로 건너뛴 문서(FORM/NOT_LAND)가 갑자기 늘면 정상 토지조서를 놓치고 있다는 신호다."""
        with self._lock:
            codes = [r[10] for r in self._rows["문서처리"]]
        if not codes:
            return "문서 0건"
        names = {"FORM": "건너뜀(양식)", "NOT_LAND": "건너뜀(입찰·설계)"}
        cnt = {}
        for c in codes:
            cnt[names.get(c, c)] = cnt.get(names.get(c, c), 0) + 1
        top = ", ".join(f"{k} {v}" for k, v in sorted(cnt.items(), key=lambda x: -x[1]))
        return f"문서 {len(codes)}건 [{top}]"

    # ---- 접속 실패 원인 진단 -------------------------------------------------------------
    _HOST_IN_ERROR = re.compile(r"host='([^']+)', port=(\d+)")
    _DIAG_TAG = re.compile(r"진단\[(\w+)\]")

    @classmethod
    def _failed_endpoint(cls, row):
        """'오류(목록)' 행에서 실제로 실패한 (호스트, 포트). 오류·상세 문장 속 접속 예외에 호스트가 있으면 그것을, 없으면 게시판 URL 을 쓴다."""
        from urllib.parse import urlparse
        m = cls._HOST_IN_ERROR.search(f"{row[11]} {row[5]}")
        if m:
            return m.group(1), int(m.group(2))
        u = urlparse(str(row[13] or ""))
        if u.hostname:
            return u.hostname, u.port or (443 if u.scheme == "https" else 80)
        return None

    def enrich_network(self):
        """'오류(목록)' 게시판 행의 조치 힌트에 접속 단계 진단(DNS/TCP/TLS/HTTP 중 어디서 끊기는지)을 덧붙인다.
        오류 문장에는 예외 이름만 있어(ConnectTimeout 등) 러너 IP 차단인지 사이트 문제인지 알 수 없기 때문이다. 실패 직후가 아니라 기록할 때
        한 번 다시 접속해 보므로 '지금은 열림(OK)' 이면 수집 중에만 막힌 것(요청 빈도 제한·간헐 차단)이라는 단서가 된다. 여러 번 불러도 한 번만 덧붙는다."""
        from concurrent.futures import ThreadPoolExecutor
        from core import preflight as PF
        with self._lock:
            targets = [(row, self._failed_endpoint(row)) for row in self._rows["게시판상태"]
                       if str(row[4]).startswith("오류(목록)") and "진단[" not in str(row[12])]
        eps = sorted({ep for _, ep in targets if ep})
        if not eps:
            return
        try:
            with ThreadPoolExecutor(12) as ex:
                res = dict(zip(eps, ex.map(lambda ep: PF.diagnose_host(*ep), eps)))
        except Exception as e:  # noqa: BLE001 - 진단이 실패해도 로그 기록은 계속한다
            print(f"[경고] 접속 진단 실패: {type(e).__name__}: {str(e)[:120]}")
            return
        with self._lock:
            for row, ep in targets:
                if ep and "진단[" not in str(row[12]):
                    code, text = res[ep]
                    row[12] = f"{row[12]} | 진단[{code}] {ep[0]}: {text}. {PF.NET_HINTS.get(code, '')}".strip(" |")

    def network_summary(self):
        """이번 실행의 목록 오류를 접속 단계별로 세어, 러너 IP 차단인지 사이트별 문제인지 한 줄로 판정한다(없으면 빈 문자열)."""
        self.enrich_network()
        with self._lock:
            boards = [r for r in self._rows["게시판상태"] if not str(r[4]).startswith("건너뜀")]
            errs = [r for r in boards if str(r[4]).startswith("오류(목록)")]
        if not errs:
            return ""
        codes = {}
        for r in errs:
            m = self._DIAG_TAG.search(str(r[12]))
            c = m.group(1) if m else "미진단"
            codes[c] = codes.get(c, 0) + 1
        dist = ", ".join(f"{k} {v}" for k, v in sorted(codes.items(), key=lambda x: -x[1]))
        n, k = len(boards), len(errs)
        network = codes.get("TCP_TIMEOUT", 0) + codes.get("DNS", 0)
        if k >= 5 and k / n >= 0.8 and network / k >= 0.8:
            verdict = "지역 전체 접속 불가(TCP시간초과·DNS) -> 이 러너 IP 차단 의심. 국내 IP 에서 열리면 새 러너로 재시도, 계속되면 blocked_sites 후보"
        elif k >= 5 and k / n >= 0.8 and codes.get("OK", 0) / k >= 0.5:
            verdict = "사이트는 지금 열림 -> 수집 중 요청 빈도 제한이나 일시 장애 의심. --delay·재시도 점검"
        else:
            verdict = "일부 사이트만 문제 -> 게시판상태 탭의 '진단[...]' 힌트로 사이트별 원인 확인"
        return f"목록 오류 {k}/{n}곳 [{dist}] {verdict}"

    def counts(self):
        with self._lock:
            return {k: len(v) for k, v in self._rows.items()}

    @staticmethod
    def _sheets_session():
        """-> (AuthorizedSession, 시트 ID) 또는 (None, 사유). 키/ID 가 없으면 구글시트 기록을 건너뛴다."""
        sheet_id = local_sheet_id()
        if not sheet_id:
            return None, "GOOGLE_SHEET_ID 없음"
        raw = os.environ.get("GOOGLE_CREDENTIALS_EDITER") or os.environ.get("GOOGLE_SA_KEY_JSON_ADMIN") or ""
        if not raw:
            local = google_key_file()
            if local.exists():
                raw = local.read_text(encoding="utf-8")
        if not raw:
            return None, "서비스 계정 키 없음"
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_info(
            json.loads(raw), scopes=["https://www.googleapis.com/auth/spreadsheets"])
        return AuthorizedSession(creds), sheet_id

    def flush_sheets(self):
        """이번 실행 기록을 구글시트 탭('{지역}_{시트명}')에 이어 붙인다. 실패해도 예외를 던지지 않는다."""
        self.enrich_network()
        try:
            sess, sheet_id = self._sheets_session()
            if sess is None:
                print(f"[수집로그] 구글시트 건너뜀: {sheet_id}")
                return
            base = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
            meta = sess.get(base, params={"fields": "sheets.properties.title"}, timeout=30)
            meta.raise_for_status()
            have = {x["properties"]["title"] for x in meta.json().get("sheets", [])}
            with self._lock:
                snapshot = {k: list(v) for k, v in self._rows.items()}
            sent = {}
            for name, headers in SHEETS.items():
                rows = snapshot[name]
                if not rows:
                    continue
                tab = f"{self.region}_{name}"
                if tab not in have:
                    r = sess.post(f"{base}:batchUpdate", timeout=30, json={"requests": [
                        {"addSheet": {"properties": {"title": tab, "gridProperties": {"frozenRowCount": 1}}}}]})
                    r.raise_for_status()
                    r = sess.put(f"{base}/values/{tab}!A1", params={"valueInputOption": "RAW"}, timeout=30,
                                 json={"values": [headers]})
                    r.raise_for_status()
                for i in range(0, len(rows), 500):  # 한 번에 너무 크지 않게 나눠 보낸다
                    r = sess.post(f"{base}/values/{tab}!A1:append", timeout=60,
                                  params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
                                  json={"values": [[("" if v is None else v) for v in row] for row in rows[i:i + 500]]})
                    r.raise_for_status()
                sent[tab] = len(rows)
            print(f"[수집로그] 구글시트 저장 {sent}")
        except Exception as e:  # 시트 때문에 수집이 멈추면 안 된다
            print(f"[경고] 구글시트 로그 저장 실패: {type(e).__name__}: {str(e)[:200]}")

    def flush(self, path):
        """누적 엑셀에 이번 실행 기록을 이어 붙여 저장한다. 실패해도 예외를 던지지 않는다."""
        self.enrich_network()
        try:
            from openpyxl import Workbook, load_workbook
            from openpyxl.styles import Font, PatternFill
            from openpyxl.utils import get_column_letter

            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            wb = load_workbook(path) if path.exists() else Workbook()
            if "Sheet" in wb.sheetnames and len(wb.sheetnames) == 1 and wb["Sheet"].max_row == 1:
                del wb["Sheet"]
            with self._lock:
                snapshot = {k: list(v) for k, v in self._rows.items()}
            for name, headers in SHEETS.items():
                ws = wb[name] if name in wb.sheetnames else wb.create_sheet(name)
                if ws.max_row < 1 or ws.cell(1, 1).value != headers[0]:
                    ws.delete_rows(1, ws.max_row)
                    ws.append(headers)
                    for c in ws[1]:
                        c.font = Font(bold=True, color="FFFFFF")
                        c.fill = PatternFill("solid", fgColor="305496")
                    ws.freeze_panes = "A2"
                    for i in range(1, len(headers) + 1):
                        ws.column_dimensions[get_column_letter(i)].width = 14
                    for col in ("게시글 제목", "상세", "조치 힌트", "원인 설명", "요약", "오류"):
                        if col in headers:
                            ws.column_dimensions[get_column_letter(headers.index(col) + 1)].width = 48
                for row in snapshot[name]:
                    ws.append(row)
                extra = ws.max_row - 1 - MAX_ROWS
                if extra > 0:
                    ws.delete_rows(2, extra)
            wb.save(path)
            print(f"[수집로그] {path} 저장 {self.counts()}")
        except Exception as e:  # 로그 때문에 수집이 멈추면 안 된다
            print(f"[경고] 수집 로그 엑셀 저장 실패: {type(e).__name__}: {e}")


LOG = RunLog()
