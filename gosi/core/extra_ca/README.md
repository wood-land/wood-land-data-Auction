# 추가 중간 인증서 (공개 인증서)

서버가 중간 인증서를 보내지 않아 `requests` 가 `unable to get local issuer certificate` 로 실패하는 사이트용입니다.
인증서 검증을 끄지 않고, 빠진 중간 인증서만 보태서 검증합니다(`core/http_fetch.py` 의 `EXTRA_CA_HOSTS`).

| 파일 | 대상 사이트 | 인증서 | 만료 |
|---|---|---|---|
| `gokseong_intermediate.pem` | eminwon.gokseong.go.kr (곡성군) | Thawte TLS RSA CA G1 (DigiCert) | 2027-11-02 |

새로 받는 법: 사이트 인증서의 `Authority Information Access > CA Issuers` 주소(곡성은 `http://cacerts.thawte.com/ThawteTLSRSACAG1.crt`)에서
중간 인증서를 받아 PEM 으로 저장하고, `http_fetch.EXTRA_CA_HOSTS` 에 호스트와 파일명을 한 줄 추가합니다.
이 인증서는 공개 정보라 저장소에 올려도 됩니다(개인키 아님).
