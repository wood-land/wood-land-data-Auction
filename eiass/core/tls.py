"""
core/tls.py - 서버가 중간 인증서를 보내지 않는 사이트(www.eiass.go.kr, 2026-10-25 Actions 에서
'CERTIFICATE_VERIFY_FAILED') 를 검증을 끄지 않고 여는 방법.

브라우저처럼 서버 인증서의 AIA(CA Issuers) 주소에서 빠진 중간 인증서를 받아
certifi 번들 + 중간 인증서로 임시 번들을 만들어 그 호스트 요청에만 쓴다.
(gosi/core/http_fetch.py 는 중간 인증서를 파일로 저장해 두는 방식. 여기서는 만료 때 교체할 필요가 없게 실행 때 받는다)
"""
import atexit
import os
import ssl
import tempfile
from pathlib import Path

import requests

_cache = {}


def _aia_chain(host, port=443, depth=3):
    from cryptography import x509
    from cryptography.hazmat.primitives.serialization import Encoding
    from cryptography.x509.oid import AuthorityInformationAccessOID, ExtensionOID

    pem = ssl.get_server_certificate((host, port))
    cert = x509.load_pem_x509_certificate(pem.encode())
    out = []
    for _ in range(depth):
        try:
            aia = cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS).value
        except x509.ExtensionNotFound:
            break
        urls = [d.access_location.value for d in aia if d.access_method == AuthorityInformationAccessOID.CA_ISSUERS]
        if not urls:
            break
        der = requests.get(urls[0], timeout=20).content
        try:
            cert = x509.load_der_x509_certificate(der)
        except ValueError:
            cert = x509.load_pem_x509_certificate(der)
        out.append(cert.public_bytes(Encoding.PEM))
        if cert.issuer == cert.subject:
            break
    return out


def bundle_for(host):
    """host 용 CA 번들 파일 경로(certifi + AIA 중간 인증서). 실패하면 None."""
    if host in _cache:
        return _cache[host]
    import certifi
    try:
        chain = _aia_chain(host)
    except Exception as e:
        print(f"[tls] {host} 중간 인증서 받기 실패: {e}")
        _cache[host] = None
        return None
    fd, path = tempfile.mkstemp(prefix="ca_", suffix=".pem")
    with os.fdopen(fd, "wb") as f:
        f.write(Path(certifi.where()).read_bytes())
        for c in chain:
            f.write(b"\n" + c)
    atexit.register(lambda p=path: os.path.exists(p) and os.remove(p))
    _cache[host] = path
    return path
