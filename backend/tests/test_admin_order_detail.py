"""Tests for admin order detail API (Step A)."""

from datetime import datetime

import models
from routes.admin import _to_admin_order_detail


def test_to_admin_order_detail_includes_document_fields(db, test_user, paid_order):
    paid_order.discount_amount = 0
    paid_order.payment_fee = 0
    paid_order.packaging_fee = 77
    paid_order.buyer_phone = "070-1234-5678"
    paid_order.stripe_checkout_session_id = "cs_test_abc"
    paid_order.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(paid_order)

    detail = _to_admin_order_detail(paid_order)
    assert detail.id == paid_order.id
    assert detail.order_number == paid_order.order_number
    assert detail.buyer_name == test_user.name
    assert detail.buyer_email == test_user.email
    assert detail.buyer_phone == "070-1234-5678"
    assert detail.packaging_fee == 77
    assert detail.stripe_checkout_session_id == "cs_test_abc"
    assert detail.updated_at is not None


def test_order_document_columns_exist_on_model(db, test_user):
    order = models.Order(
        user_id=test_user.id,
        total_amount=500,
        status=models.OrderStatus.pending,
        discount_amount=100,
        coupon_code="SAVE10",
        coupon_name="10% off",
        payment_fee=0,
        packaging_fee=50,
        buyer_note="玄関前へ",
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    assert order.discount_amount == 100
    assert order.coupon_code == "SAVE10"
    assert order.buyer_note == "玄関前へ"
    assert order.updated_at is not None
