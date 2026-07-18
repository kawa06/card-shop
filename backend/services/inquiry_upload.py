"""Private inquiry attachment storage and signed download tokens."""

from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile, status
from jose import JWTError, jwt

from config import settings

ALLOWED_INQUIRY_MIME_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

DOWNLOAD_TOKEN_MINUTES = 30
_TOKEN_TYP = "inquiry_attachment"


def get_inquiry_upload_dir() -> Path:
    if os.getenv("INQUIRY_UPLOAD_DIR"):
        return Path(os.getenv("INQUIRY_UPLOAD_DIR"))
    if Path("/app/data").is_dir():
        return Path("/app/data/inquiry-uploads")
    return Path("./data/inquiry-uploads")


def _sanitize_filename(name: str) -> str:
    base = (name or "attachment").strip()
    base = re.sub(r"[^\w.\-()（）ぁ-んァ-ヶ一-龥]", "_", base)
    return base[:200] or "attachment"


async def read_inquiry_upload(
    file: UploadFile,
    *,
    max_bytes: int,
) -> tuple[bytes, str, str]:
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_INQUIRY_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="JPEG、PNG、WebP、GIF の画像のみアップロードできます",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="空のファイルです")
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{max_bytes // (1024 * 1024)}MB以下の画像を選択してください",
        )

    original = _sanitize_filename(file.filename or "image")
    return data, content_type, original


def save_inquiry_bytes(
    data: bytes,
    content_type: str,
) -> str:
    upload_dir = get_inquiry_upload_dir()
    upload_dir.mkdir(parents=True, exist_ok=True)
    ext = ALLOWED_INQUIRY_MIME_TYPES[content_type]
    filename = f"{uuid.uuid4().hex}{ext}"
    (upload_dir / filename).write_bytes(data)
    return filename


def resolve_storage_path(storage_path: str) -> Path:
    upload_dir = get_inquiry_upload_dir().resolve()
    full = (upload_dir / storage_path).resolve()
    if upload_dir not in full.parents and full != upload_dir:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid path")
    return full


def create_attachment_download_token(
    attachment_id: int,
    *,
    user_id: int | None = None,
    is_admin: bool = False,
) -> str:
    expire = datetime.utcnow() + timedelta(minutes=DOWNLOAD_TOKEN_MINUTES)
    payload: dict[str, Any] = {
        "typ": _TOKEN_TYP,
        "aid": attachment_id,
        "adm": is_admin,
        "exp": expire,
    }
    if user_id is not None:
        payload["uid"] = user_id
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_attachment_download_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ダウンロードリンクが無効です") from exc

    if payload.get("typ") != _TOKEN_TYP:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ダウンロードリンクが無効です")
    attachment_id = payload.get("aid")
    if not isinstance(attachment_id, int):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ダウンロードリンクが無効です")
    return payload


def build_download_path(attachment_id: int, token: str) -> str:
    return f"/api/inquiries/attachments/{attachment_id}/download?token={token}"
