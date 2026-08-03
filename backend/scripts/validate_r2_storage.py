"""Validate Cloudflare R2 KYC storage configuration (run on Railway or locally with env)."""

from __future__ import annotations

import sys

from services.buyback_kyc_storage import (
    _normalize_access_key_id,
    _use_r2_api,
    _use_r2_s3,
    delete_kyc_object,
    kyc_storage_configured,
    upload_kyc_document,
)


def main() -> int:
    if not kyc_storage_configured():
        print("FAIL config: R2 storage is not configured")
        return 1

    mode = "s3" if _use_r2_s3() else "api" if _use_r2_api() else "unknown"
    print(f"OK config mode={mode} s3={_use_r2_s3()} api={_use_r2_api()}")

    raw_key = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    if raw_key:
        normalized = _normalize_access_key_id(raw_key)
        print(f"sample_normalize in_len={len(raw_key.replace('-', ''))} out_len={len(normalized)}")
        return 0

    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    key = upload_kyc_document(
        user_id=0,
        verification_id=0,
        side="front",
        content_type="image/png",
        data=png,
    )
    print(f"OK upload key_prefix={'/'.join(key.split('/')[:3])}")
    delete_kyc_object(key)
    print("OK delete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
