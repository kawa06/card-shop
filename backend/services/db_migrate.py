"""Non-destructive schema upgrades. Never drops tables or deletes rows."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

from config import settings
from database import engine

logger = logging.getLogger(__name__)


def run_schema_upgrades() -> None:
    """Apply additive migrations only."""
    import models  # noqa: F401 — register models with Base.metadata

    inspector = inspect(engine)
    _ensure_table_exists(inspector, "packs")
    _create_table_if_missing("favorites", models.Favorite)
    _migrate_cards_image_url_to_text()


def _ensure_table_exists(inspector, table_name: str) -> None:
    if table_name in inspector.get_table_names():
        return
    logger.warning("Table %s missing — create_all should create it on next startup", table_name)


def _create_table_if_missing(table_name: str, model) -> None:
    inspector = inspect(engine)
    if table_name in inspector.get_table_names():
        return
    try:
        model.__table__.create(bind=engine, checkfirst=True)
        logger.info("Created missing table: %s", table_name)
    except Exception as exc:
        logger.error("Failed to create table %s: %s", table_name, exc)


def _migrate_cards_image_url_to_text() -> None:
    url = settings.DATABASE_URL
    inspector = inspect(engine)
    if "cards" not in inspector.get_table_names():
        return

    columns = {col["name"]: col for col in inspector.get_columns("cards")}
    if "image_url" not in columns:
        return

    col_type = str(columns["image_url"]["type"]).upper()
    if "TEXT" in col_type and "VARCHAR" not in col_type:
        return

    if url.startswith("postgresql") or url.startswith("postgres"):
        try:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE cards ALTER COLUMN image_url TYPE TEXT"))
                conn.commit()
            logger.info("Migrated cards.image_url to TEXT (PostgreSQL)")
        except Exception as exc:
            logger.error("Failed to migrate cards.image_url to TEXT: %s", exc)
        return

    if url.startswith("sqlite"):
        try:
            with engine.connect() as conn:
                conn.execute(text("PRAGMA table_info(cards)"))
                # SQLite cannot ALTER COLUMN type in place; recreate column via table rebuild is risky.
                # New installs use Text from SQLAlchemy create_all. Existing SQLite stores long strings in practice.
                conn.execute(text("UPDATE cards SET image_url = image_url WHERE 0"))
                conn.commit()
            logger.info("SQLite cards.image_url left as-is (SQLite does not enforce VARCHAR length strictly)")
        except Exception as exc:
            logger.error("SQLite image_url check failed: %s", exc)
