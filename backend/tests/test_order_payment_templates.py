"""Tests for order/payment email templates and registry."""

from __future__ import annotations

from services.email_order_layout import ORDER_EMAIL_BODY_SKELETON, build_buttons_block
from services.email_template_seed import seed_email_templates
from services.order_email_templates_seed import seed_order_payment_templates
from services.payment_email_registry import resolve_order_template_key


def test_resolve_template_key_payment_method_override():
    assert resolve_order_template_key("payment_pending", "stripe_bank_transfer") == "order_bank_transfer"
    assert resolve_order_template_key("payment_pending", "konbini") == "order_konbini_pending"
    assert resolve_order_template_key("payment_pending", "stripe_card") == "order_payment_pending"


def test_order_payment_templates_seed(db):
    seed_email_templates(db)
    count = seed_order_payment_templates(db)
    assert count >= 10
    db.commit()

    from importlib import import_module

    models_email = import_module("models_email")
    tpl = (
        db.query(models_email.EmailTemplate)
        .filter(models_email.EmailTemplate.template_key == "order_payment_confirmed")
        .first()
    )
    assert tpl is not None
    assert "{{bodyTitle}}" in tpl.html_body
    assert tpl.preheader is not None
    assert tpl.text_body is not None


def test_buttons_block_empty_when_no_buttons():
    assert build_buttons_block([]) == ""


def test_order_email_skeleton_has_required_slots():
    for slot in ("{{bodyTitle}}", "{{bodyDescription}}", "{{orderSummaryBlock}}", "{{itemsTable}}"):
        assert slot in ORDER_EMAIL_BODY_SKELETON
