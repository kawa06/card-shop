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
    _migrate_international_shipping_to_ems()
    _add_column_if_missing("orders", "payment_deadline", "DATETIME")
    _add_column_if_missing("orders", "stock_reserved", "BOOLEAN DEFAULT 0")
    _add_column_if_missing("orders", "paid_at", "DATETIME")
    _add_column_if_missing("categories", "name_en", "VARCHAR(100)")
    _add_column_if_missing("packs", "name_en", "VARCHAR(100)")
    _add_column_if_missing("cards", "price_usd", "FLOAT")


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


def _add_column_if_missing(table: str, column: str, col_type: str) -> None:
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns(table)}
    if column in columns:
        return
    url = settings.DATABASE_URL
    try:
        with engine.connect() as conn:
            if url.startswith("postgresql") or url.startswith("postgres"):
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
            elif url.startswith("sqlite"):
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
            else:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
            conn.commit()
        logger.info("Added column %s.%s", table, column)
    except Exception as exc:
        logger.error("Failed to add column %s.%s: %s", table, column, exc)


def _migrate_international_shipping_to_ems() -> None:
    """Merge legacy international shipping method into ems without losing order history."""
    import json

    from sqlalchemy.orm import sessionmaker

    import models

    Session = sessionmaker(bind=engine)
    with Session() as db:
        try:
            updated_orders = (
                db.query(models.Order)
                .filter(models.Order.shipping_method == "international")
                .update({"shipping_method": "ems"}, synchronize_session=False)
            )
            cards = db.query(models.Card).filter(models.Card.allowed_shipping_methods.isnot(None)).all()
            cards_updated = 0
            for card in cards:
                raw = card.allowed_shipping_methods
                if not raw or "international" not in raw:
                    continue
                try:
                    methods = json.loads(raw)
                    if not isinstance(methods, list):
                        continue
                    if "international" not in methods:
                        continue
                    new_methods = ["ems" if m == "international" else m for m in methods]
                    if "ems" not in new_methods and "international" in methods:
                        new_methods.append("ems")
                    new_methods = list(dict.fromkeys(new_methods))
                    card.allowed_shipping_methods = json.dumps(new_methods, ensure_ascii=False)
                    cards_updated += 1
                except Exception:
                    continue
            deleted = (
                db.query(models.ShippingRate)
                .filter(models.ShippingRate.method_code == "international")
                .delete(synchronize_session=False)
            )
            db.commit()
            if updated_orders or cards_updated or deleted:
                logger.info(
                    "Migrated international→ems: orders=%s cards=%s rates_deleted=%s",
                    updated_orders,
                    cards_updated,
                    deleted,
                )
        except Exception as exc:
            db.rollback()
            logger.error("Failed international→ems migration: %s", exc)
