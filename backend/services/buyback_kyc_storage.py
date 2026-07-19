"""KYC document storage (Cloudflare R2 or local DEBUG fallback)."""

from __future__ import annotations

import logging
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_KYC_BYTES = 5 * 1024 * 1024

_LOCAL_KYC_ROOT = Path(__file__).resolve().parent.parent / "data" / "kyc"


def kyc_storage_configured() -> bool:
    return bool(
        settings.R2_ACCOUNT_ID
        and settings.R2_ACCESS_KEY_ID
        and settings.R2_SECRET_ACCESS_KEY
        and settings.R2_BUCKET_NAME
    )


def _validate_upload(content_type: str | None, data: bytes) -> str:
    if not data:
        raise ValueError("ファイルが空です")
    if len(data) > MAX_KYC_BYTES:
        raise ValueError("ファイルサイズは5MB以下にしてください")
    ct = (content_type or "").split(";")[0].strip().lower()
    ext = ALLOWED_CONTENT_TYPES.get(ct)
    if not ext:
        raise ValueError("JPEG / PNG / WebP 形式の画像のみアップロードできます")
    return ext


def build_storage_key(*, user_id: int, verification_id: int, side: str, ext: str) -> str:
    safe_side = "front" if side == "front" else "back"
    return f"kyc/{user_id}/{verification_id}/{safe_side}{ext}"


def upload_kyc_document(
    *,
    user_id: int,
    verification_id: int,
    side: str,
    content_type: str | None,
    data: bytes,
) -> str:
    ext = _validate_upload(content_type, data)
    key = build_storage_key(
        user_id=user_id, verification_id=verification_id, side=side, ext=ext
    )

    if kyc_storage_configured():
        _upload_r2(key=key, data=data, content_type=content_type or "application/octet-stream")
        return key

    if settings.DEBUG:
        path = _LOCAL_KYC_ROOT / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        logger.info("[KYC LOCAL] stored %s", path)
        return key

    raise RuntimeError("KYC storage is not configured (R2 env vars required in production)")


def _upload_r2(*, key: str, data: bytes, content_type: str) -> None:
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("boto3 is required for R2 uploads") from exc

    endpoint = f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )
    client.put_object(
        Bucket=settings.R2_BUCKET_NAME,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
