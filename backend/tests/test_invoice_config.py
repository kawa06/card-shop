"""Tests for qualified invoice configuration."""

from services.invoice_config import (
    is_qualified_invoice_enabled,
    normalize_registration_number,
    update_invoice_settings,
)
import schemas
import models


def test_normalize_registration_number_valid():
    assert normalize_registration_number("T1234567890123") == "T1234567890123"


def test_normalize_registration_number_rejects_partial():
    assert normalize_registration_number("T") is None
    assert normalize_registration_number("") is None
    assert normalize_registration_number("  ") is None
    assert normalize_registration_number("未登録") is None
    assert normalize_registration_number("T123") is None


def test_is_qualified_invoice_disabled_when_not_enabled():
    assert not is_qualified_invoice_enabled(
        invoice_enabled=False,
        invoice_registration_number="T1234567890123",
        invoice_issuer_name="川村 海斗",
    )


def test_is_qualified_invoice_enabled_all_conditions():
    assert is_qualified_invoice_enabled(
        invoice_enabled=True,
        invoice_registration_number="T1234567890123",
        invoice_issuer_name="川村 海斗",
        default_tax_rate=10,
    )


def test_update_invoice_settings_rejects_invalid_number(db):
    try:
        update_invoice_settings(
            db,
            schemas.InvoiceSettingsUpdate(
                invoice_enabled=True,
                invoice_registration_number="T123",
                invoice_issuer_name="Test Shop",
            ),
        )
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "T + 13" in str(exc)


def test_update_invoice_settings_stores_valid_config(db):
    result = update_invoice_settings(
        db,
        schemas.InvoiceSettingsUpdate(
            invoice_enabled=True,
            invoice_registration_number="T1234567890123",
            invoice_issuer_name="KRX TCG",
            default_tax_rate=10,
        ),
    )
    assert result.qualified_invoice_enabled is True
    assert result.invoice_registration_number == "T1234567890123"
    row = db.query(models.ShopSettings).filter(models.ShopSettings.id == 1).first()
    assert row.invoice_enabled is True
