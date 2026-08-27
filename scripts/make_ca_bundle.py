"""certifi 기본 번들 + 사내 루트 CA를 합쳐 certs/ca-bundle.pem 을 만든다.

사내망은 자체 루트 CA(C=KR, O=daou, CN=daou)로 TLS를 가로채는데, httpx/OpenAI SDK는
Windows 인증서 저장소가 아니라 certifi 번들만 보므로 CERTIFICATE_VERIFY_FAILED 가 난다
(SDK가 "Connection error." 로 감싸 원인이 드러나지 않는다).

생성한 번들 경로를 .env 의 SSL_CERT_FILE 로 지정하면 프로세스 전체 TLS에 적용된다.
SSL_CERT_FILE 은 기본 번들을 **대체**하므로 공인 CA까지 포함한 결합본이어야 한다.

  python scripts/make_ca_bundle.py

certifi 를 업그레이드하면 새 번들로 다시 만들어야 한다(사내 CA가 빠지므로).
"""
import sys
from pathlib import Path

import certifi

CERTS_DIR = Path(__file__).resolve().parent.parent / "certs"
CORP_CA = CERTS_DIR / "daou-root.pem"
OUTPUT = CERTS_DIR / "ca-bundle.pem"


def main() -> int:
    if not CORP_CA.exists():
        print(f"사내 CA 파일이 없습니다: {CORP_CA}", file=sys.stderr)
        return 1

    corp = CORP_CA.read_text(encoding="ascii")
    bundle = certifi.contents() + "\n" + corp
    OUTPUT.write_text(bundle, encoding="ascii")

    print(f"certifi: {certifi.where()}")
    print(f"생성 완료: {OUTPUT} ({OUTPUT.stat().st_size:,} bytes)")
    print(f".env 에 추가: SSL_CERT_FILE={OUTPUT.relative_to(CERTS_DIR.parent).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
