"""Tests for shipping/delivery email template platform."""

from unittest.mock import patch

from services.carrier_registry import CARRIER_REGISTRY, build_carrier_tracking_url
from services.email_delivery import preview_template
from services.email_template_seed import seed_email_templates
from services.shipping_email_templates_seed import seed_shipping_email_templates
from services.shipping_email_variables import build_shipping_sample_variables
from services.shipping_emails import send_shipping_completion_email
from services.tracking_urls import build_tracking_url


def test_carrier_registry_extensible():
    assert "japan_post" in CARRIER_REGISTRY
    assert "yamato" in CARRIER_REGISTRY
    url = build_carrier_tracking_url("12345678901", carrier_id="japan_post")
    assert url and "12345678901" in url


def test_tracking_urls_delegates_to_registry(db):
    url = build_tracking_url(
        "12345678901",
        shipping_method="yu_pack_60",
        shipping_carrier="日本郵便",
    )
    assert url and "trackings.post.japanpost.jp" in url


def test_seed_shipping_templates(db):
    seed_email_templates(db)
    count = seed_shipping_email_templates(db, force_upgrade=True)
    assert count >= 10

    from models_email import EmailTemplate

    tpl = (
        db.query(EmailTemplate)
        .filter(EmailTemplate.template_key == "shipping_shipped")
        .first()
    )
    assert tpl is not None
    assert tpl.category == "shipping"
    assert "{{shippingInfoBlock}}" in tpl.html_body
    assert "{{signatureBlock}}" in tpl.html_body


def test_shipping_sample_variables_include_blocks():
    sample = build_shipping_sample_variables("shipping_shipped")
    assert sample["trackingNo"] == "1234-5678-9012"
    assert "shippingInfoBlock" in sample
    assert sample["shippingInfoBlock"]
    assert "1234-5678-9012" in sample["shippingInfoBlock"]


def test_shipping_preview_with_sample_data(db):
    seed_email_templates(db)
    seed_shipping_email_templates(db, force_upgrade=True)
    db.commit()

    result = preview_template(db, template_key="shipping_shipped")
    assert "ORD-20260801-001" in result["html"] or "1234-5678-9012" in result["html"]
    assert result["subject"]


@patch("services.shipping_emails.send_templated_email")
def test_send_shipping_email_success(mock_send, db, paid_order):
    from services.email_delivery import SendResult

    seed_shipping_email_templates(db, force_upgrade=True)
    db.commit()

    mock_send.return_value = SendResult(ok=True)
    paid_order.tracking_number = "12345678901"
    paid_order.shipping_carrier = "日本郵便"
    db.commit()

    ok, err = send_shipping_completion_email(db, paid_order.id)
    assert ok is True
    assert err is None

    assert mock_send.call_args.kwargs["template_key"] == "shipping_shipped"
    variables = mock_send.call_args.kwargs["variables"]
    assert variables["trackingNo"] == "12345678901"
    assert "trackings.post.japanpost.jp" in variables["trackingUrl"]

    fallback = mock_send.call_args.kwargs["fallback_html"]
    assert "12345678901" in fallback


@patch("services.shipping_emails.send_templated_email")
def test_legacy_template_key_resolves_to_shipping_shipped(mock_send, db, paid_order):
    from models_email import EmailTemplate
    from services.email_delivery import SendResult, send_templated_email

    seed_shipping_email_templates(db, force_upgrade=True)
    db.commit()

    tpl = db.query(EmailTemplate).filter(EmailTemplate.template_key == "shipping_shipped").first()
    assert tpl and tpl.is_active

    mock_send.return_value = SendResult(ok=True, used_template=True)
    paid_order.tracking_number = "999"
    db.commit()

    send_shipping_completion_email(db, paid_order.id)
    assert mock_send.call_args.kwargs["template_key"] == "shipping_shipped"

    # Direct send with legacy key should still find shipping template
    send_templated_email(
        db,
        template_key="order_shipped",
        to_email="test@example.com",
        variables=build_shipping_sample_variables("shipping_shipped"),
        fallback_subject="fallback",
        fallback_html="<p>fallback</p>",
        raw_variable_keys={"shippingInfoBlock", "signatureBlock"},
    )
    db.commit()
