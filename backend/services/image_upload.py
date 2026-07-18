"""Save admin-uploaded card images to persistent storage."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def get_upload_dir() -> Path:
    if os.getenv("UPLOAD_DIR"):
        return Path(os.getenv("UPLOAD_DIR"))
    if Path("/app/data").is_dir():
        return Path("/app/data/uploads")
    return Path("./data/uploads")


def get_public_api_url() -> str:
    domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
    if domain:
        return f"https://{domain}"
    return os.getenv("PUBLIC_API_URL", "http://localhost:8000").rstrip("/")


async def save_uploaded_image(file: UploadFile) -> str:
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="JPEG、PNG、WebP、GIF の画像のみアップロードできます",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="空のファイルです")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="5MB以下の画像を選択してください",
        )

    upload_dir = get_upload_dir()
    upload_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4().hex}{ALLOWED_CONTENT_TYPES[content_type]}"
    (upload_dir / filename).write_bytes(data)

    base = get_public_api_url()
    return f"{base}/api/media/uploads/{filename}"
