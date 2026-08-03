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
    _migrate_buyback_logistics_schema()
    _migrate_buyback_channel_schema()
    _migrate_buyback_shop_settings_schema()
    _migrate_announcements_schema()
    _migrate_admin_security_schema()
    _migrate_order_pricing_snapshots()
    _migrate_email_auth_schema()


def _migrate_order_pricing_snapshots() -> None:
    """Persist checkout price breakdown on orders and line item names."""
    order_cols = [
        ("items_subtotal", "INTEGER DEFAULT 0"),
        ("tax_rate_snapshot", "INTEGER"),
    ]
    for col, col_type in order_cols:
        _add_column_if_missing("orders", col, col_type)
    _add_column_if_missing("order_items", "product_name", "VARCHAR(200)")


def _migrate_admin_security_schema() -> None:
    """Admin RBAC tables, seed data, and PostgreSQL RLS policies."""
    import models_admin  # noqa: F401
    from services.admin_rls import apply_admin_rls_policies
    from services.admin_seed import seed_admin_rbac

    admin_tables = [
        ("admin_roles", models_admin.AdminRole),
        ("admin_permissions", models_admin.AdminPermission),
        ("admin_role_permissions", models_admin.AdminRolePermission),
        ("admin_users", models_admin.AdminUser),
        ("admin_audit_logs", models_admin.AdminAuditLog),
    ]
    for table_name, model in admin_tables:
        _create_table_if_missing(table_name, model)

    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=engine)
    with Session() as db:
        try:
            seed_admin_rbac(db)
        except Exception:
            db.rollback()
            logger.error("admin RBAC seed failed")

    try:
        apply_admin_rls_policies()
    except Exception:
        logger.error("admin RLS apply failed")


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
    _create_unique_index_if_missing(
        "buyback_products", "ix_buyback_products_firestore_item_id", "firestore_item_id"
    )
    _migrate_buyback_catalog_columns()
    _migrate_buyback_request_columns()


def _migrate_buyback_catalog_columns() -> None:
    """Additive catalog identity columns for admin buyback product CRUD."""
    catalog_cols = [
        ("card_number", "VARCHAR(128)"),
        ("rarity", "VARCHAR(128)"),
        ("pack_name", "VARCHAR(255)"),
    ]
    for col, col_type in catalog_cols:
        _add_column_if_missing("buyback_products", col, col_type)

    promo_cols = [
        ("promo_badge_text", "VARCHAR(32)"),
        ("promo_badge_bg", "VARCHAR(32)"),
        ("promo_badge_fg", "VARCHAR(32)"),
        ("promo_badge_starts_at", "DATETIME"),
        ("promo_badge_ends_at", "DATETIME"),
    ]
    for col, col_type in promo_cols:
        _add_column_if_missing("buyback_products", col, col_type)


def _migrate_buyback_request_columns() -> None:
    request_cols = [
        ("rejected_item_handling", "VARCHAR(64)"),
        ("agreed_prepaid_shipping", "BOOLEAN DEFAULT 0"),
        ("agreed_cod_consequence", "BOOLEAN DEFAULT 0"),
        ("agreed_condition_rejection", "BOOLEAN DEFAULT 0"),
    ]
    for col, col_type in request_cols:
        _add_column_if_missing("buyback_requests", col, col_type)

    item_cols = [
        ("rejection_reason_code", "VARCHAR(64)"),
        ("rejection_reason_text", "TEXT"),
        ("is_return_target", "BOOLEAN DEFAULT 0"),
        ("is_disposal_target", "BOOLEAN DEFAULT 0"),
        ("return_status", "VARCHAR(32)"),
        ("return_tracking_number", "VARCHAR(128)"),
        ("return_shipping_cost", "INTEGER"),
        ("assessment_lines_json", "TEXT"),
    ]
    for col, col_type in item_cols:
        _add_column_if_missing("buyback_request_items", col, col_type)

    _add_column_if_missing("buyback_requests", "customer_status_note", "TEXT")
    _add_column_if_missing("buyback_request_items", "customer_decision", "VARCHAR(32)")
    _add_column_if_missing("users", "birth_date", "DATE")
    guardian_doc_cols = [
        ("document_type", "VARCHAR(64)"),
        ("storage_key_front", "VARCHAR(512)"),
        ("storage_key_back", "VARCHAR(512)"),
    ]
    for col, col_type in guardian_doc_cols:
        _add_column_if_missing("guardian_consents", col, col_type)


def _migrate_buyback_logistics_schema() -> None:
    """Additive buyback logistics tables and columns (barcode / inbound / packages)."""
    import models_buyback  # noqa: F401

    _add_column_if_missing("users", "public_member_id", "VARCHAR(32)")
    _create_unique_index_if_missing("users", "ix_users_public_member_id", "public_member_id")

    request_logistics_cols = [
        ("public_buyback_code", "VARCHAR(32)"),
        ("inbound_mgmt_id", "VARCHAR(32)"),
        ("application_form_issued_at", "DATETIME"),
        ("customer_planned_ship_date", "DATE"),
        ("customer_shipped_at", "DATETIME"),
        ("logistics_note", "TEXT"),
        ("received_by_user_id", "INTEGER"),
        ("received_at", "DATETIME"),
    ]
    for col, col_type in request_logistics_cols:
        _add_column_if_missing("buyback_requests", col, col_type)

    _create_unique_index_if_missing(
        "buyback_requests", "ix_buyback_requests_public_buyback_code", "public_buyback_code"
    )
    _create_unique_index_if_missing(
        "buyback_requests", "ix_buyback_requests_inbound_mgmt_id", "inbound_mgmt_id"
    )

    status_history_cols = [
        ("related_barcode_id", "INTEGER"),
        ("device_info", "VARCHAR(255)"),
        ("change_reason", "TEXT"),
    ]
    for col, col_type in status_history_cols:
        _add_column_if_missing("buyback_status_history", col, col_type)

    logistics_tables = [
        ("buyback_number_sequences", models_buyback.BuybackNumberSequence),
        ("buyback_barcodes", models_buyback.BuybackBarcode),
        ("buyback_inbound_shipments", models_buyback.BuybackInboundShipment),
        ("buyback_package_receipts", models_buyback.BuybackPackageReceipt),
        ("buyback_shipment_packages", models_buyback.BuybackShipmentPackage),
        ("buyback_package_items", models_buyback.BuybackPackageItem),
        ("buyback_shipment_confirmations", models_buyback.BuybackShipmentConfirmation),
        ("buyback_shipment_address_snapshots", models_buyback.BuybackShipmentAddressSnapshot),
        ("buyback_package_scan_logs", models_buyback.BuybackPackageScanLog),
        ("buyback_package_print_logs", models_buyback.BuybackPackagePrintLog),
    ]
    for table_name, model in logistics_tables:
        _create_table_if_missing(table_name, model)

    _create_unique_index_if_missing(
        "buyback_barcodes", "ix_buyback_barcodes_scan_token", "scan_token"
    )
    _create_unique_index_if_missing(
        "buyback_inbound_shipments", "ix_buyback_inbound_shipments_request_id", "request_id"
    )
    _create_unique_index_if_missing(
        "buyback_inbound_shipments",
        "ix_buyback_inbound_shipments_inbound_mgmt_id",
        "inbound_mgmt_id",
    )
    _create_unique_index_if_missing(
        "buyback_shipment_packages", "ix_buyback_shipment_packages_package_code", "package_code"
    )


def _migrate_buyback_channel_schema() -> None:
    """Store/mail channel settings, promo banners, store reservations."""
    import json

    import models_buyback  # noqa: F401
    from services.buyback_channel import (
        DEFAULT_BUSINESS_HOURS,
        get_or_create_channel_settings,
        seed_starter_content_if_empty,
    )

    channel_tables = [
        ("buyback_channel_settings", models_buyback.BuybackChannelSettings),
        ("buyback_promo_banners", models_buyback.BuybackPromoBanner),
        ("buyback_store_reservations", models_buyback.BuybackStoreReservation),
    ]
    for table_name, model in channel_tables:
        _create_table_if_missing(table_name, model)

    _add_column_if_missing("buyback_requests", "buyback_method", "VARCHAR(16)")
    _add_column_if_missing("buyback_requests", "store_visit_at", "DATETIME")
    _add_column_if_missing("buyback_promo_banners", "linked_product_ids_json", "TEXT")

    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=engine)
    with Session() as db:
        try:
            row = get_or_create_channel_settings(db)
            if not row.business_hours_json:
                row.business_hours_json = json.dumps(DEFAULT_BUSINESS_HOURS, ensure_ascii=False)
            if not row.closed_dates_json:
                row.closed_dates_json = json.dumps([], ensure_ascii=False)
            seed_starter_content_if_empty(db)
            db.commit()
        except Exception:
            db.rollback()
            logger.error("buyback channel settings seed failed")


def _migrate_buyback_shop_settings_schema() -> None:
    """Buylist shop display settings (notice text, name, slug)."""
    import models_buyback  # noqa: F401
    from services.buyback_shop_settings import get_or_create_shop_settings

    _create_table_if_missing("buyback_shop_settings", models_buyback.BuybackShopSettings)

    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=engine)
    with Session() as db:
        try:
            get_or_create_shop_settings(db)
            db.commit()
        except Exception:
            db.rollback()
            logger.error("buyback shop settings seed failed")


def _migrate_announcements_schema() -> None:
    import models as shop_models

    _create_table_if_missing("announcement_images", shop_models.AnnouncementImage)
    _create_table_if_missing("announcement_reads", shop_models.AnnouncementRead)

    for col, col_type in [
        ("title_ja", "VARCHAR(200)"),
        ("title_en", "VARCHAR(200)"),
        ("content_ja", "TEXT"),
        ("content_en", "TEXT"),
        ("status", "VARCHAR(20) DEFAULT 'draft'"),
        ("publish_at", "DATETIME"),
        ("expire_at", "DATETIME"),
        ("thumbnail", "VARCHAR(500)"),
        ("updated_at", "DATETIME"),
    ]:
        _add_column_if_missing("announcements", col, col_type)

    inspector = inspect(engine)
    if "announcements" not in inspector.get_table_names():
        return

    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "UPDATE announcements SET title_ja = title "
                    "WHERE title_ja IS NULL OR title_ja = ''"
                )
            )
            conn.execute(
                text(
                    "UPDATE announcements SET content_ja = content "
                    "WHERE content_ja IS NULL OR content_ja = ''"
                )
            )
            conn.execute(
                text(
                    "UPDATE announcements SET title_en = title "
                    "WHERE title_en IS NULL OR title_en = ''"
                )
            )
            conn.execute(
                text(
                    "UPDATE announcements SET content_en = content "
                    "WHERE content_en IS NULL OR content_en = ''"
                )
            )
            conn.execute(
                text(
                    "UPDATE announcements SET status = 'published' "
                    "WHERE (status IS NULL OR status = '') AND is_active = 1"
                )
            )
            conn.execute(
                text(
                    "UPDATE announcements SET status = 'draft' "
                    "WHERE (status IS NULL OR status = '') AND (is_active = 0 OR is_active IS NULL)"
                )
            )
            conn.execute(
                text(
                    "UPDATE announcements SET publish_at = created_at "
                    "WHERE publish_at IS NULL AND status = 'published'"
                )
            )
            conn.execute(
                text(
                    "UPDATE announcements SET updated_at = created_at "
                    "WHERE updated_at IS NULL"
                )
            )
            conn.commit()
        logger.info("Backfilled announcement bilingual columns")
    except Exception:
        logger.error("Failed to backfill announcement columns")


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
    except Exception:
        logger.error("Failed to create unique index %s", index_name)


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
        except Exception:
            db.rollback()
            logger.error("order document backfill failed")


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
        except Exception:
            db.rollback()
            logger.error("shop_settings seed failed")


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
        except Exception:
            db.rollback()
            logger.error("inquiry seed failed")


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
        except Exception:
            db.rollback()
            logger.error("shipping_status backfill failed")


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
    except Exception:
        logger.error("Failed to create table %s", table_name)


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
        except Exception:
            logger.error("Failed to migrate cards.image_url to TEXT")
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
        except Exception:
            logger.error("SQLite image_url check failed")


def _pg_column_type(col_type: str) -> str:
    """Map SQLite-oriented DDL fragments to PostgreSQL-safe types."""
    mapped = col_type
    # BOOLEAN DEFAULT 0/1 is invalid on Postgres; use TRUE/FALSE.
    mapped = mapped.replace("BOOLEAN DEFAULT 0", "BOOLEAN DEFAULT FALSE")
    mapped = mapped.replace("BOOLEAN DEFAULT 1", "BOOLEAN DEFAULT TRUE")
    # DATETIME is SQLite/MySQL; Postgres wants TIMESTAMP.
    mapped = mapped.replace("DATETIME", "TIMESTAMP")
    return mapped


def _add_column_if_missing(table: str, column: str, col_type: str) -> None:
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns(table)}
    if column in columns:
        return
    url = (settings.DATABASE_URL or "").lower()
    ddl_type = col_type
    if url.startswith("postgresql") or url.startswith("postgres"):
        ddl_type = _pg_column_type(col_type)
    try:
        with engine.connect() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))
            conn.commit()
        logger.info("Added column %s.%s", table, column)
    except Exception:
        logger.error("Failed to add column %s.%s", table, column)


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
        except Exception:
            db.rollback()
            logger.error("Failed international→ems migration")


def _migrate_email_auth_schema() -> None:
    """Email template platform + customer auth security tables."""
    import models_email  # noqa: F401
    from services.email_template_seed import seed_email_templates

    email_tables = [
        ("email_brand_settings", models_email.EmailBrandSettings),
        ("email_templates", models_email.EmailTemplate),
        ("email_send_logs", models_email.EmailSendLog),
        ("email_scheduled_sends", models_email.EmailScheduledSend),
        ("login_histories", models_email.LoginHistory),
        ("user_otp_challenges", models_email.UserOtpChallenge),
    ]
    for table_name, model in email_tables:
        _create_table_if_missing(table_name, model)

    user_cols = [
        ("failed_login_attempts", "INTEGER DEFAULT 0"),
        ("locked_until", "DATETIME"),
        ("two_factor_enabled", "BOOLEAN DEFAULT 0"),
        ("two_factor_method", "VARCHAR(16)"),
        ("last_login_at", "DATETIME"),
        ("last_login_ip", "VARCHAR(64)"),
    ]
    for col, col_type in user_cols:
        _add_column_if_missing("users", col, col_type)

    from sqlalchemy.orm import sessionmaker
    from services.admin_seed import seed_admin_rbac

    Session = sessionmaker(bind=engine)
    with Session() as db:
        try:
            seed_admin_rbac(db)
        except Exception:
            db.rollback()
            logger.error("admin RBAC re-seed for email permissions failed")
        try:
            seed_email_templates(db)
        except Exception:
            db.rollback()
            logger.error("email template seed failed")
