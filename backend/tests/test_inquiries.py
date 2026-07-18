"""Tests for inquiry service (permissions, internal notes)."""

from datetime import datetime

import models
from services.inquiry_seed import seed_inquiry_data
from services.inquiry_service import (
    add_admin_reply,
    add_customer_message,
    create_inquiry,
    get_customer_inquiry,
)


def _admin(db):
    admin = models.User(
        email="admin@example.com",
        password_hash="hashed",
        name="管理者",
        is_admin=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def test_create_inquiry_assigns_number(db, test_user):
    seed_inquiry_data(db)
    inquiry = create_inquiry(
        db,
        user=test_user,
        category="order_payment",
        subject="配送について",
        message="いつ届きますか？",
    )
    db.commit()
    assert inquiry.inquiry_number.startswith("INQ-")
    assert inquiry.user_id == test_user.id
    assert inquiry.status == "waiting_admin"


def test_customer_cannot_see_internal_notes(db, test_user):
    seed_inquiry_data(db)
    admin = _admin(db)
    inquiry = create_inquiry(
        db,
        user=test_user,
        category="other",
        subject="テスト",
        message="購入者メッセージ",
    )
    db.commit()

    add_admin_reply(
        db,
        inquiry,
        admin,
        "内部のみのメモ",
        is_internal_note=True,
    )
    add_admin_reply(
        db,
        inquiry,
        admin,
        "購入者への返信",
        is_internal_note=False,
    )
    db.commit()

    customer_view = get_customer_inquiry(db, inquiry.id, test_user.id)
    assert customer_view is not None
    visible = [m.message for m in customer_view.messages if not m.is_internal_note]
    assert "内部のみのメモ" not in visible
    assert "購入者への返信" in visible


def test_customer_cannot_use_unrelated_product(db, test_user, paid_order):
    seed_inquiry_data(db)
    other_card = models.Card(
        name="他人の商品",
        description="x",
        price=100,
        stock=1,
        rarity="common",
    )
    db.add(other_card)
    db.commit()
    db.refresh(other_card)

    try:
        create_inquiry(
            db,
            user=test_user,
            category="product",
            subject="商品",
            message="テスト",
            related_product_id=other_card.id,
        )
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "関連商品" in str(exc)


def test_customer_cannot_access_other_users_inquiry(db, test_user):
    seed_inquiry_data(db)
    other = models.User(email="other@example.com", password_hash="x", name="Other")
    db.add(other)
    db.commit()
    db.refresh(other)

    inquiry = create_inquiry(
        db,
        user=other,
        category="other",
        subject="秘密",
        message="他人の問い合わせ",
    )
    db.commit()

    assert get_customer_inquiry(db, inquiry.id, test_user.id) is None


def test_closed_inquiry_rejects_customer_reply_when_reopen_disabled(db, test_user):
    seed_inquiry_data(db)
    settings = db.query(models.InquirySettings).filter(models.InquirySettings.id == 1).first()
    settings.allow_reopen_resolved = False
    db.commit()

    inquiry = create_inquiry(
        db,
        user=test_user,
        category="other",
        subject="終了テスト",
        message="内容",
    )
    inquiry.status = "closed"
    inquiry.closed_at = datetime.utcnow()
    db.commit()

    try:
        add_customer_message(db, inquiry, test_user, "追加返信")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "終了" in str(exc)
