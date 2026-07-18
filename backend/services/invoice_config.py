"""Qualified invoice (インボイス) settings and validation."""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy.orm import Session

import models
import schemas
from config import settings

INVOICE_NUMBER_PATTERN = re.compile(r"^T\d{13}$")


def normalize_registration_number(raw: str | None) -> str | None:
    """Return valid T+13 registration number, or None (never partial/placeholder values)."""
    value = (raw or "").strip()
    if not value:
        return None
    if INVOICE_NUMBER_PATTERN.match(value):
        return value
    return None


def can_compute_tax_breakdown(default_tax_rate: int) -> bool:
    return default_tax_rate in (8, 10)


def is_qualified_invoice_enabled(
    *,
    invoice_enabled: bool,
    invoice_registration_number: str | None,
    invoice_issuer_name: str | None,
    default_tax_rate: int = 10,
) -> bool:
    reg = normalize_registration_number(invoice_registration_number)
    issuer = (invoice_issuer_name or "").strip()
    return (
        invoice_enabled
        and reg is not None
        and bool(issuer)
        and can_compute_tax_breakdown(default_tax_rate)
    )


def get_or_create_shop_settings(db: Session) -> models.ShopSettings:
    row = db.query(models.ShopSettings).filter(models.ShopSettings.id == 1).first()
    if row:
        return row
    row = models.ShopSettings(id=1)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _settings_to_out(row: models.ShopSettings) -> schemas.InvoiceConfigOut:
    reg = normalize_registration_number(row.invoice_registration_number)
    enabled = bool(row.invoice_enabled)
    issuer = (row.invoice_issuer_name or "").strip() or None
    rate = row.default_tax_rate or 10
    qualified = is_qualified_invoice_enabled(
        invoice_enabled=enabled,
        invoice_registration_number=reg,
        invoice_issuer_name=issuer,
        default_tax_rate=rate,
    )
    return schemas.InvoiceConfigOut(
        invoice_enabled=enabled,
        invoice_registration_number=reg,
        invoice_issuer_name=issuer,
        default_tax_rate=rate,
        qualified_invoice_enabled=qualified,
    )


def get_invoice_config(db: Session) -> schemas.InvoiceConfigOut:
    row = get_or_create_shop_settings(db)
    return _settings_to_out(row)


def update_invoice_settings(
    db: Session,
    payload: schemas.InvoiceSettingsUpdate,
) -> schemas.InvoiceConfigOut:
    row = get_or_create_shop_settings(db)

    if payload.invoice_enabled is not None:
        row.invoice_enabled = payload.invoice_enabled

    if payload.invoice_registration_number is not None:
        raw = payload.invoice_registration_number.strip()
        if raw and normalize_registration_number(raw) is None:
            raise ValueError("登録番号は T + 13桁の数字（例: T1234567890123）で入力してください")
        row.invoice_registration_number = normalize_registration_number(raw)

    if payload.invoice_issuer_name is not None:
        row.invoice_issuer_name = payload.invoice_issuer_name.strip() or None

    if payload.default_tax_rate is not None:
        if payload.default_tax_rate not in (8, 10):
            raise ValueError("適用税率は 8 または 10 のみ設定できます")
        row.default_tax_rate = payload.default_tax_rate

    if row.invoice_enabled:
        reg = normalize_registration_number(row.invoice_registration_number)
        issuer = (row.invoice_issuer_name or "").strip()
        if not reg:
            raise ValueError("適格請求書を有効にするには、有効な登録番号（T+13桁）が必要です")
        if not issuer:
            raise ValueError("適格請求書を有効にするには、発行事業者名が必要です")

    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _settings_to_out(row)


def seed_shop_settings_from_env(db: Session) -> None:
    """One-time seed: copy env vars into shop_settings if row is empty."""
    row = get_or_create_shop_settings(db)
    changed = False
    env_reg = normalize_registration_number(settings.INVOICE_REGISTRATION_NUMBER)
    if env_reg and not row.invoice_registration_number:
        row.invoice_registration_number = env_reg
        changed = True
    env_issuer = (getattr(settings, "INVOICE_ISSUER_NAME", "") or "").strip()
    if env_issuer and not row.invoice_issuer_name:
        row.invoice_issuer_name = env_issuer
        changed = True
    if changed:
        row.updated_at = datetime.utcnow()
        db.commit()
