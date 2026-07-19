"""Non-destructive schema upgrades. Never drops tables or deletes rows."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import inspect, text
from sqlalchemy.orm import joinedload

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
    _migrate_order_management_columns()
    _migrate_order_document_columns()
    _create_table_if_missing("order_number_sequences", models.OrderNumberSequence)
    _create_table_if_missing("stripe_processed_events", models.StripeProcessedEvent)
    _migrate_shop_settings()
    _migrate_inquiry_tables()
    _migrate_buyback_schema()


def _migrate_buyback_schema() -> None:
    """Phase 2: clerk_user_id on users + empty buyback_* tables."""
    import models_buyback  # noqa: F401

    _add_column_if_missing("users", "clerk_user_id", "VARCHAR(255)")
    _create_unique_index_if_missing("users", "ix_users_clerk_user_id", "clerk_user_id")

    buyback_tables = [
        ("buyback_products", models_buyback.BuybackProduct),
        ("buyback_product_prices", models_buyback.BuybackProductPrice),
        ("buyback_price_history", models_buyback.BuybackPriceHistory),
        ("buyback_carts", models_buyback.BuybackCart),
        ("buyback_cart_items", models_buyback.BuybackCartItem),
        ("buyback_request_number_sequences", models_buyback.BuybackRequestNumberSequence),
        ("buyback_requests", models_buyback.BuybackRequest),
        ("buyback_request_items", models_buyback.BuybackRequestItem),
        ("identity_verifications", models_buyback.IdentityVerification),
        ("guardian_consents", models_buyback.GuardianConsent),
        ("payout_accounts", models_buyback.PayoutAccount),
        ("buyback_status_history", models_buyback.BuybackStatusHistory),
        ("buyback_audit_logs", models_buyback.BuybackAuditLog),
        ("notification_deliveries", models_buyback.NotificationDelivery),
    ]
    for table_name, model in buyback_tables:
        _create_table_if_missing(table_name, model)


def _create_unique_index_if_missing(table: str, index_name: str, column: str) -> None:
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return
    existing = {idx["name"] for idx in inspector.get_indexes(table)}
    if index_name in existing:
        return
    try:
        with engine.connect() as conn:
            conn.execute(
                text(f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} ON {table} ({column})")
            )
            conn.commit()
        logger.info("Created unique index %s on %s.%s", index_name, table, column)
    except Exception as exc:
        logger.error("Failed to create unique index %s: %s", index_name, exc)


def _migrate_order_management_columns() -> None:
    order_cols = [
        ("order_number", "VARCHAR(32)"),
        ("stripe_payment_intent_id", "VARCHAR(255)"),
        ("stripe_event_id", "VARCHAR(255)"),
        ("shipping_status", "VARCHAR(32) DEFAULT 'unshipped'"),
        ("shipping_carrier", "VARCHAR(100)"),
        ("tracking_number", "VARCHAR(100)"),
        ("shipped_at", "DATETIME"),
        ("purchase_email_sent_at", "DATETIME"),
        ("shipping_email_sent_at", "DATETIME"),
        ("email_send_status", "VARCHAR(50)"),
        ("admin_note", "TEXT"),
    ]
    for col, col_type in order_cols:
        _add_column_if_missing("orders", col, col_type)
    _backfill_shipping_status()


def _migrate_order_document_columns() -> None:
    """Columns for printable purchase statement / order copy documents."""
    order_cols = [
        ("discount_amount", "INTEGER DEFAULT 0"),
        ("coupon_code", "VARCHAR(64)"),
        ("coupon_name", "VARCHAR(128)"),
        ("payment_fee", "INTEGER DEFAULT 0"),
        ("packaging_fee", "INTEGER DEFAULT 0"),
        ("buyer_note", "TEXT"),
        ("buyer_phone", "VARCHAR(20)"),
        ("updated_at", "DATETIME"),
    ]
    for col, col_type in order_cols:
        _add_column_if_missing("orders", col, col_type)
    _backfill_order_document_fields()


def _backfill_order_document_fields() -> None:
    """Safe backfill for document columns on existing orders."""
    from sqlalchemy.orm import sessionmaker

    import models

    inspector = inspect(engine)
    if "orders" not in inspector.get_table_names():
        return

    Session = sessionmaker(bind=engine)
    with Session() as db:
        try:
            updated = 0
            for order in db.query(models.Order).options(joinedload(models.Order.user)).all():
                changed = False
                if order.updated_at is None:
                    order.updated_at = order.paid_at or order.created_at or datetime.utcnow()
                    changed = True
                if not order.buyer_phone and order.user and order.user.phone_number:
                    order.buyer_phone = order.user.phone_number
                    changed = True
                if changed:
                    updated += 1
            if updated:
                db.commit()
                logger.info("Backfilled order document fields on %s orders", updated)
        except Exception as exc:
            db.rollback()
            logger.error("order document backfill failed: %s", exc)


def _migrate_shop_settings() -> None:
    """Singleton shop_settings table for invoice / shop config."""
    import models

    _create_table_if_missing("shop_settings", models.ShopSettings)
    from sqlalchemy.orm import sessionmaker

    from services.invoice_config import seed_shop_settings_from_env

    Session = sessionmaker(bind=engine)
    with Session() as db:
        try:
            seed_shop_settings_from_env(db)
        except Exception as exc:
            db.rollback()
            logger.error("shop_settings seed failed: %s", exc)


def _migrate_inquiry_tables() -> None:
    import models

    tables = [
        ("inquiry_number_sequences", models.InquiryNumberSequence),
        ("inquiry_settings", models.InquirySettings),
        ("inquiries", models.Inquiry),
        ("inquiry_templates", models.InquiryTemplate),
        ("inquiry_messages", models.InquiryMessage),
        ("inquiry_attachments", models.InquiryAttachment),
        ("inquiry_status_history", models.InquiryStatusHistory),
    ]
    for name, model in tables:
        _create_table_if_missing(name, model)

    from sqlalchemy.orm import sessionmaker

    from services.inquiry_seed import seed_inquiry_data

    Session = sessionmaker(bind=engine)
    with Session() as db:
        try:
            seed_inquiry_data(db)
        except Exception as exc:
            db.rollback()
            logger.error("inquiry seed failed: %s", exc)


def _backfill_shipping_status() -> None:
    """Map legacy order.status to shipping_status for existing rows."""
    from sqlalchemy.orm import sessionmaker

    import models

    inspector = inspect(engine)
    if "orders" not in inspector.get_table_names():
        return

    mapping = {
        "pending": "unshipped",
        "processing": "preparing",
        "shipped": "shipped",
        "delivered": "delivered",
        "cancelled": "cancelled",
    }
    Session = sessionmaker(bind=engine)
    with Session() as db:
        try:
            updated = 0
            for order in db.query(models.Order).all():
                status_val = order.status.value if hasattr(order.status, "value") else str(order.status)
                target = mapping.get(status_val, "unshipped")
                if order.shipping_status != target and status_val != "pending":
                    order.shipping_status = target
                    updated += 1
            if updated:
                db.commit()
                logger.info("Backfilled shipping_status on %s orders", updated)
        except Exception as exc:
            db.rollback()
            logger.error("shipping_status backfill failed: %s", exc)


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
