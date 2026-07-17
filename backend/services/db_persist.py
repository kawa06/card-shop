"""Database persistence helpers — admin data must never be wiped by deploys."""

from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from config import settings

logger = logging.getLogger(__name__)


def is_sqlite_database() -> bool:
    return settings.DATABASE_URL.startswith("sqlite")


def is_persistent_database() -> bool:
    return not is_sqlite_database()


def database_info() -> dict:
    url = settings.DATABASE_URL
    if url.startswith("sqlite"):
        return {
            "engine": "sqlite",
            "persistent": False,
            "warning": "SQLiteファイルは再デプロイで消える可能性があります。Railway PostgreSQLを使用してください。",
        }
    if url.startswith("postgresql") or url.startswith("postgres"):
        return {"engine": "postgresql", "persistent": True, "warning": None}
    return {"engine": "other", "persistent": True, "warning": None}


def require_persistent_database():
    """Block admin mutations when production uses ephemeral SQLite."""
    if settings.DEBUG or is_persistent_database():
        return
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            "本番環境でデータベースが永続化されていません。"
            "Railwayの oripa-kawa-api に PostgreSQL を追加し、"
            "DATABASE_URL 環境変数を設定してください。"
            "設定しないとデプロイのたびにパック・カード等のデータが消えます。"
        ),
    )


def safe_commit(db: Session, *, action: str = "保存") -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        message = str(getattr(exc, "orig", exc)).lower()
        if "slug" in message or "unique" in message:
            raise HTTPException(status_code=400, detail="同じスラッグ/識別子が既に存在します") from exc
        if "foreign key" in message or "pack_id" in message:
            raise HTTPException(status_code=400, detail="参照先（パック等）が見つかりません") from exc
        raise HTTPException(status_code=400, detail=f"{action}に失敗しました（データの重複または参照エラー）") from exc
    except OperationalError as exc:
        db.rollback()
        message = str(getattr(exc, "orig", exc)).lower()
        if "too long" in message or "value too long" in message or "string data right truncation" in message:
            raise HTTPException(
                status_code=400,
                detail="画像データが長すぎます。URLを直接入力するか、再度アップロードしてください。",
            ) from exc
        if "no such column" in message or "does not exist" in message:
            raise HTTPException(
                status_code=503,
                detail="データベースのスキーマが古いです。APIを再デプロイしてください。",
            ) from exc
        logger.exception("Database operational error during %s", action)
        raise HTTPException(status_code=500, detail=f"{action}中にデータベースエラーが発生しました") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Database error during %s", action)
        raise HTTPException(status_code=500, detail=f"{action}に失敗しました") from exc


PersistDep = Depends(require_persistent_database)
