"""KYC document storage (Cloudflare R2 or local DEBUG fallback)."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from config import settings

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".jpg",
    "image/heif": ".jpg",
}
MAX_KYC_BYTES = 10 * 1024 * 1024

_LOCAL_KYC_ROOT = Path(__file__).resolve().parent.parent / "data" / "kyc"

KYC_STORAGE_USER_MESSAGE = "画像の保存に失敗しました。時間をおいて再度お試しください。"


def _clean_secret(value: str | None) -> str:
    return (value or "").strip().replace("\n", "").replace("\r", "").replace(" ", "")


def _normalize_access_key_id(value: str | None) -> str:
    """Cloudflare R2 S3 access key IDs are 32 chars (UUID tokens may include dashes)."""
    return _clean_secret(value).replace("-", "").lower()


def _r2_api_config() -> tuple[str, str, str]:
    account_id = _clean_secret(settings.R2_ACCOUNT_ID)
    bucket = _clean_secret(settings.R2_BUCKET_NAME)
    api_token = _clean_secret(settings.R2_API_TOKEN)
    if not all([account_id, bucket, api_token]):
        raise RuntimeError(KYC_STORAGE_USER_MESSAGE)
    return account_id, bucket, api_token


def _r2_s3_credentials() -> tuple[str, str, str, str]:
    account_id = _clean_secret(settings.R2_ACCOUNT_ID)
    access_key = _normalize_access_key_id(settings.R2_ACCESS_KEY_ID)
    secret_key = _clean_secret(settings.R2_SECRET_ACCESS_KEY)
    bucket = _clean_secret(settings.R2_BUCKET_NAME)

    if not all([account_id, access_key, secret_key, bucket]):
        raise RuntimeError(KYC_STORAGE_USER_MESSAGE)

    if len(access_key) != 32:
        raise RuntimeError(KYC_STORAGE_USER_MESSAGE)

    if len(secret_key) < 32:
        raise RuntimeError(KYC_STORAGE_USER_MESSAGE)

    return account_id, access_key, secret_key, bucket


def _use_r2_api() -> bool:
    try:
        _r2_api_config()
        return True
    except RuntimeError:
        return False


def _use_r2_s3() -> bool:
    if _use_r2_api():
        return False
    try:
        _r2_s3_credentials()
        return True
    except RuntimeError:
        return False


def kyc_storage_configured() -> bool:
    return _use_r2_api() or _use_r2_s3()


def _detect_image_ext(content_type: str | None, data: bytes) -> str | None:
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct in ALLOWED_CONTENT_TYPES:
        return ALLOWED_CONTENT_TYPES[ct]
    if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


def _validate_upload(content_type: str | None, data: bytes) -> str:
    if not data:
        raise ValueError("ファイルが空です")
    if len(data) > MAX_KYC_BYTES:
        raise ValueError("画像サイズが大きすぎます。10MB以下の画像を選択してください")
    ext = _detect_image_ext(content_type, data)
    if not ext:
        raise ValueError("対応していない画像形式です。JPEG、PNG、WebPの画像を選択してください")
    return ext


def build_storage_key(*, user_id: int, verification_id: int, side: str, ext: str) -> str:
    safe_side = "front" if side == "front" else "back"
    file_id = uuid.uuid4().hex
    return f"kyc/{user_id}/{verification_id}/{safe_side}/{file_id}{ext}"


def build_guardian_storage_key(*, user_id: int, consent_id: int, side: str, ext: str) -> str:
    safe_side = "front" if side == "front" else "back"
    file_id = uuid.uuid4().hex
    return f"kyc/guardian/{user_id}/{consent_id}/{safe_side}/{file_id}{ext}"


def _object_url(key: str) -> tuple[str, str, str]:
    account_id, bucket, _token = _r2_api_config()
    encoded_key = quote(key, safe="/")
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
        f"/r2/buckets/{bucket}/objects/{encoded_key}"
    )
    return url, account_id, bucket


def _upload_cf_api(*, key: str, data: bytes, content_type: str) -> None:
    url, _, _ = _object_url(key)
    _, _, api_token = _r2_api_config()
    req = Request(
        url,
        data=data,
        method="PUT",
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": content_type,
        },
    )
    try:
        with urlopen(req, timeout=60) as resp:
            if resp.status >= 400:
                raise RuntimeError(KYC_STORAGE_USER_MESSAGE)
        logger.info(
            "r2_api_upload_ok key_prefix=%s size=%s mime=%s",
            "/".join(key.split("/")[:4]),
            len(data),
            content_type,
        )
    except HTTPError as exc:
        logger.error(
            "r2_api_upload_failed code=http_%s stage=put_object key_prefix=%s size=%s mime=%s",
            exc.code,
            "/".join(key.split("/")[:4]),
            len(data),
            content_type,
        )
        if exc.code == 413:
            raise RuntimeError("画像サイズが大きすぎます。10MB以下の画像を選択してください") from exc
        raise RuntimeError(KYC_STORAGE_USER_MESSAGE) from exc
    except URLError as exc:
        logger.error("r2_api_upload_failed code=network stage=put_object err=%s", type(exc).__name__)
        raise RuntimeError(KYC_STORAGE_USER_MESSAGE) from exc


def _delete_cf_api(*, key: str) -> None:
    url, _, _ = _object_url(key)
    _, _, api_token = _r2_api_config()
    req = Request(
        url,
        method="DELETE",
        headers={"Authorization": f"Bearer {api_token}"},
    )
    try:
        with urlopen(req, timeout=30) as resp:
            if resp.status >= 400:
                raise RuntimeError(KYC_STORAGE_USER_MESSAGE)
        logger.info("r2_api_delete_ok key_prefix=%s", "/".join(key.split("/")[:4]))
    except Exception as exc:
        logger.error(
            "r2_api_delete_failed key_prefix=%s err=%s",
            "/".join(key.split("/")[:4]),
            type(exc).__name__,
        )


def _fetch_cf_api(*, key: str) -> tuple[bytes, str]:
    url, _, _ = _object_url(key)
    _, _, api_token = _r2_api_config()
    req = Request(url, method="GET", headers={"Authorization": f"Bearer {api_token}"})
    try:
        with urlopen(req, timeout=60) as resp:
            data = resp.read()
            content_type = resp.headers.get("Content-Type") or _content_type_for_key(key)
            return data, content_type
    except Exception as exc:
        logger.error(
            "r2_api_fetch_failed key_prefix=%s err=%s",
            "/".join(key.split("/")[:4]),
            type(exc).__name__,
        )
        raise RuntimeError(KYC_STORAGE_USER_MESSAGE) from exc


def delete_kyc_object(key: str | None) -> None:
    if not key:
        return
    if kyc_storage_configured():
        if _use_r2_api():
            _delete_cf_api(key=key)
        else:
            _delete_r2_s3(key=key)
        return
    if settings.DEBUG:
        path = _LOCAL_KYC_ROOT / key
        if path.is_file():
            path.unlink(missing_ok=True)


def _store_object(*, key: str, data: bytes, content_type: str) -> None:
    if _use_r2_api():
        _upload_cf_api(key=key, data=data, content_type=content_type)
        return
    if _use_r2_s3():
        _upload_r2_s3(key=key, data=data, content_type=content_type)
        return
    raise RuntimeError(KYC_STORAGE_USER_MESSAGE)


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
    stored_type = "image/jpeg" if ext == ".jpg" else _content_type_for_key(key)

    if kyc_storage_configured():
        _store_object(key=key, data=data, content_type=stored_type)
        return key

    if settings.DEBUG:
        path = _LOCAL_KYC_ROOT / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        logger.info("[KYC LOCAL] stored path=%s size=%s mime=%s", key, len(data), stored_type)
        return key

    logger.error("kyc_storage_unconfigured user_id=%s verification_id=%s side=%s", user_id, verification_id, side)
    raise RuntimeError(KYC_STORAGE_USER_MESSAGE)


def upload_guardian_document(
    *,
    user_id: int,
    consent_id: int,
    side: str,
    content_type: str | None,
    data: bytes,
) -> str:
    ext = _validate_upload(content_type, data)
    key = build_guardian_storage_key(
        user_id=user_id, consent_id=consent_id, side=side, ext=ext
    )
    stored_type = "image/jpeg" if ext == ".jpg" else _content_type_for_key(key)

    if kyc_storage_configured():
        _store_object(key=key, data=data, content_type=stored_type)
        return key

    if settings.DEBUG:
        path = _LOCAL_KYC_ROOT / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        logger.info("[KYC LOCAL] guardian stored path=%s size=%s mime=%s", key, len(data), stored_type)
        return key

    logger.error("kyc_storage_unconfigured user_id=%s consent_id=%s side=%s", user_id, consent_id, side)
    raise RuntimeError(KYC_STORAGE_USER_MESSAGE)


def _s3_client():
    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:
        logger.error("r2_boto3_missing")
        raise RuntimeError(KYC_STORAGE_USER_MESSAGE) from exc

    account_id, access_key, secret_key, _bucket = _r2_s3_credentials()
    endpoint = f"https://{account_id}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
        config=Config(connect_timeout=10, read_timeout=60, retries={"max_attempts": 2}),
    )


def _map_client_error(exc: Exception) -> RuntimeError:
    try:
        from botocore.exceptions import ClientError
    except ImportError:
        return RuntimeError(KYC_STORAGE_USER_MESSAGE)

    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code", "Unknown")
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        logger.error(
            "r2_s3_upload_failed code=%s http_status=%s stage=put_object",
            code,
            status,
        )
        if status == 413:
            return RuntimeError("画像サイズが大きすぎます。10MB以下の画像を選択してください")
    else:
        logger.error("r2_s3_upload_failed code=unexpected_exception stage=put_object err=%s", type(exc).__name__)
    return RuntimeError(KYC_STORAGE_USER_MESSAGE)


def _upload_r2_s3(*, key: str, data: bytes, content_type: str) -> None:
    _, _, _, bucket = _r2_s3_credentials()
    client = _s3_client()
    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        logger.info(
            "r2_s3_upload_ok key_prefix=%s size=%s mime=%s",
            "/".join(key.split("/")[:4]),
            len(data),
            content_type,
        )
    except Exception as exc:
        raise _map_client_error(exc) from exc


def _delete_r2_s3(*, key: str) -> None:
    _, _, _, bucket = _r2_s3_credentials()
    client = _s3_client()
    try:
        client.delete_object(Bucket=bucket, Key=key)
        logger.info("r2_s3_delete_ok key_prefix=%s", "/".join(key.split("/")[:4]))
    except Exception as exc:
        logger.error(
            "r2_s3_delete_failed key_prefix=%s err=%s",
            "/".join(key.split("/")[:4]),
            type(exc).__name__,
        )


def _content_type_for_key(key: str) -> str:
    lower = key.lower()
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return "image/jpeg"
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".webp"):
        return "image/webp"
    return "application/octet-stream"


def fetch_kyc_document(*, key: str) -> tuple[bytes, str]:
    if not key:
        raise ValueError("storage key is missing")

    if kyc_storage_configured():
        if _use_r2_api():
            return _fetch_cf_api(key=key)
        _, _, _, bucket = _r2_s3_credentials()
        client = _s3_client()
        obj = client.get_object(Bucket=bucket, Key=key)
        data = obj["Body"].read()
        content_type = obj.get("ContentType") or _content_type_for_key(key)
        return data, content_type

    if settings.DEBUG:
        path = _LOCAL_KYC_ROOT / key
        if not path.is_file():
            raise FileNotFoundError(f"KYC file not found: {key}")
        return path.read_bytes(), _content_type_for_key(key)

    raise RuntimeError(KYC_STORAGE_USER_MESSAGE)
