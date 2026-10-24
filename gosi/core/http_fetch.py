"""
core/http_fetch.py - 지자체 사이트에서 첨부를 받을 때 쓰는 공통 보강(재시도 + 서버 인증서 체인 보완).

1) 일시 오류 재시도 (retry_call): 같은 파일이 처음엔 400/5xx/시간초과였다가 다시 받으면 되는 경우가 실제로 있다
   (2026-10-25 점검: 영천시·안동시 eminwon FileDown 400, 합천군 ReadTimeout 이 재시도하면 성공). 401/403/404 처럼
   다시 해도 같은 결과일 오류는 재시도하지 않는다. SSL 오류도 재시도하지 않는다(인증서 문제는 아래 2번으로 푼다).
2) 서버가 중간 인증서를 보내지 않는 사이트: 브라우저는 AIA 로 빠진 중간 인증서를 알아서 받아 열리지만 requests 는 못 받아
   'unable to get local issuer certificate' 로 실패한다(곡성군 eminwon.gokseong.go.kr 실측). 인증서 검증을 끄는 대신 그 사이트가 빠뜨린
   중간 인증서(공개 인증서)를 core/extra_ca/*.pem 으로 저장소에 두고, EXTRA_CA_HOSTS 에 적은 호스트에만 certifi 번들 + 그 인증서로 검증한다.
   중간 인증서는 만료일이 있다(곡성: Thawte TLS RSA CA G1, 2027-11-02). 만료 전에 새로 받아 교체한다 - 받는 법은 extra_ca/README.md.

사용: 세션을 만든 직후 http_fetch.install(session). 다운로드 함수는 retry_call(lambda: ...)로 감싼다.
"""
import atexit
import os
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter

EXTRA_CA_DIR = Path(__file__).with_name("extra_ca")
# 호스트(소문자) -> 그 사이트에 필요한 추가 중간 인증서 파일(EXTRA_CA_DIR 안). 새 사이트가 생기면 한 줄만 추가한다.
EXTRA_CA_HOSTS = {
    "eminwon.gokseong.go.kr": "gokseong_intermediate.pem",
}
RETRY_STATUS = {400, 408, 425, 429, 500, 502, 503, 504}  # 다시 받아 볼 만한 HTTP 상태
_bundle_cache = {}


def _bundle_for(filename):
    """certifi 기본 번들 + 추가 중간 인증서를 합친 임시 파일 경로(프로세스당 한 번만 만든다)."""
    if filename in _bundle_cache:
        return _bundle_cache[filename]
    import certifi

    extra = (EXTRA_CA_DIR / filename).read_bytes()
    fd, path = tempfile.mkstemp(prefix="ca_bundle_", suffix=".pem")
    with os.fdopen(fd, "wb") as f:
        f.write(Path(certifi.where()).read_bytes())
        f.write(b"\n")
        f.write(extra)
    atexit.register(lambda p=path: os.path.exists(p) and os.remove(p))
    _bundle_cache[filename] = path
    return path


class ExtraCaAdapter(HTTPAdapter):
    """EXTRA_CA_HOSTS 에 있는 호스트로 가는 요청에만 검증용 CA 번들을 바꿔 끼운다(다른 호스트는 그대로)."""

    def send(self, request, **kwargs):
        host = (urlparse(request.url).hostname or "").lower()
        fn = EXTRA_CA_HOSTS.get(host)
        if fn and kwargs.get("verify", True) is True and (EXTRA_CA_DIR / fn).exists():
            kwargs["verify"] = _bundle_for(fn)
        return super().send(request, **kwargs)


def install(session):
    """세션에 인증서 체인 보완 어댑터를 붙인다. 이미 다른 https 어댑터(예: 구형 TLS)가 있으면 건드리지 않는다."""
    current = session.get_adapter("https://example.invalid/")
    if type(current) is HTTPAdapter:
        session.mount("https://", ExtraCaAdapter())
    return session


def is_retryable(exc):
    """다시 받아 볼 만한 오류인가."""
    if isinstance(exc, requests.exceptions.SSLError):
        return False
    if isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        return True
    if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
        return exc.response.status_code in RETRY_STATUS
    return False


def retry_call(func, tries=3, base_delay=1.5, sleep=time.sleep):
    """func() 를 최대 tries 번 호출한다. 다시 받아 볼 만한 오류(is_retryable)일 때만 1.5초, 3초 ... 쉬고 재시도한다."""
    last = None
    for i in range(tries):
        try:
            return func()
        except Exception as e:  # noqa: BLE001 - 재시도 대상이 아니면 그대로 다시 던진다
            last = e
            if i == tries - 1 or not is_retryable(e):
                raise
            sleep(base_delay * (i + 1))
    raise last  # pragma: no cover
