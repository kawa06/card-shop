"""Phase 3-10: Oripa Stripe reservation / webhook / concurrency / refund gates."""

from __future__ import annotations

from unittest.mock import MagicMock

import models
import models_oripa
from services.admin_seed import seed_admin_rbac
from services.oripa_admin import create_oripa, generate_entries, update_oripa
from services.oripa_constants import (
    ENTRY_ASSIGNMENT_ASSIGNED,
    ENTRY_ASSIGNMENT_AVAILABLE,
    ENTRY_ASSIGNMENT_RESERVED,
    ENTRY_ASSIGNMENT_RETIRED,
    ORIPA_PURCHASE_CANCELLED,
    ORIPA_PURCHASE_COMPLETED,
    ORIPA_PURCHASE_PENDING,
    ORIPA_STATUS_ON_SALE,
)
from services.oripa_payment import (
    confirm_oripa_purchase_for_order,
    list_oripa_consistency_issues,
    reserve_oripa_entries_for_payment,
    retire_oripa_for_paid_refund,
)
from services.order_checkout import cancel_unpaid_order, fulfill_order_inventory
from services.stripe_events import claim_stripe_event
from tests.conftest import admin_headers, auth_headers, create_admin_user


def _on_sale(db, *, total=5, title="P310"):
    user = models.User(email=f"{title}@t.com", name="U", password_hash="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    oripa = create_oripa(
        db,
        title=title,
        description=None,
        price_per_entry=1000,
        total_entries=total,
        max_entries_per_purchase=total,
    )
    db.commit()
    generate_entries(db, oripa.id)
    update_oripa(db, oripa.id, status=ORIPA_STATUS_ON_SALE)
    db.commit()
    db.refresh(oripa)
    return user, oripa


def test_payment_success_confirms_and_reveals(db):
    user, oripa = _on_sale(db, total=4, title="PayOK")
    purchase = reserve_oripa_entries_for_payment(
        db, oripa_id=oripa.id, user_id=user.id, quantity=2, idempotency_key="ok-1"
    )
    db.commit()
    assert purchase.status == ORIPA_PURCHASE_PENDING
    reserved = (
        db.query(models_oripa.OripaEntry)
        .filter(models_oripa.OripaEntry.assigned_purchase_id == purchase.id)
        .all()
    )
    assert all(e.assignment_status == ENTRY_ASSIGNMENT_RESERVED for e in reserved)

    order = db.query(models.Order).filter(models.Order.id == purchase.order_id).one()
    fulfill_order_inventory(db, order.id)
    db.refresh(purchase)
    assert purchase.status == ORIPA_PURCHASE_COMPLETED
    entries = (
        db.query(models_oripa.OripaEntry)
        .filter(models_oripa.OripaEntry.assigned_purchase_id == purchase.id)
        .all()
    )
    assert all(e.assignment_status == ENTRY_ASSIGNMENT_ASSIGNED for e in entries)
    assert list_oripa_consistency_issues(db) == []


def test_webhook_duplicate_safe(db):
    user, oripa = _on_sale(db, total=3, title="Dup")
    purchase = reserve_oripa_entries_for_payment(
        db, oripa_id=oripa.id, user_id=user.id, quantity=1, idempotency_key="dup-1"
    )
    db.commit()
    order = db.query(models.Order).filter(models.Order.id == purchase.order_id).one()
    assert claim_stripe_event(db, "evt_oripa_dup", "checkout.session.completed", order.id) is True
    fulfill_order_inventory(db, order.id, stripe_event_id="evt_oripa_dup")
    assert claim_stripe_event(db, "evt_oripa_dup", "checkout.session.completed", order.id) is False
    fulfill_order_inventory(db, order.id, stripe_event_id="evt_oripa_dup")  # idempotent paid
    db.refresh(purchase)
    assert purchase.status == ORIPA_PURCHASE_COMPLETED
    assert (
        db.query(models_oripa.OripaEntry)
        .filter(
            models_oripa.OripaEntry.oripa_id == oripa.id,
            models_oripa.OripaEntry.assignment_status == ENTRY_ASSIGNMENT_ASSIGNED,
        )
        .count()
        == 1
    )


def test_payment_failure_releases_to_available(db):
    user, oripa = _on_sale(db, total=3, title="Fail")
    purchase = reserve_oripa_entries_for_payment(
        db, oripa_id=oripa.id, user_id=user.id, quantity=1, idempotency_key="fail-1"
    )
    db.commit()
    order = db.query(models.Order).filter(models.Order.id == purchase.order_id).one()
    cancel_unpaid_order(db, order)
    db.refresh(purchase)
    assert purchase.status in ("failed", "cancelled")
    assert (
        db.query(models_oripa.OripaEntry)
        .filter(
            models_oripa.OripaEntry.oripa_id == oripa.id,
            models_oripa.OripaEntry.assignment_status == ENTRY_ASSIGNMENT_AVAILABLE,
        )
        .count()
        == 3
    )


def test_expiry_releases(db):
    user, oripa = _on_sale(db, total=2, title="Exp")
    purchase = reserve_oripa_entries_for_payment(
        db, oripa_id=oripa.id, user_id=user.id, quantity=1, idempotency_key="exp-1"
    )
    db.commit()
    order = db.query(models.Order).filter(models.Order.id == purchase.order_id).one()
    cancel_unpaid_order(db, order, as_expired=True)
    assert (
        db.query(models_oripa.OripaEntry)
        .filter(models_oripa.OripaEntry.assignment_status == ENTRY_ASSIGNMENT_AVAILABLE)
        .count()
        == 2
    )


def test_refund_retires_no_resale(db):
    user, oripa = _on_sale(db, total=3, title="Ref")
    purchase = reserve_oripa_entries_for_payment(
        db, oripa_id=oripa.id, user_id=user.id, quantity=1, idempotency_key="ref-1"
    )
    db.commit()
    order = db.query(models.Order).filter(models.Order.id == purchase.order_id).one()
    fulfill_order_inventory(db, order.id)
    entry = (
        db.query(models_oripa.OripaEntry)
        .filter(models_oripa.OripaEntry.assigned_purchase_id == purchase.id)
        .one()
    )
    num = entry.entry_number
    retire_oripa_for_paid_refund(db, order, reason="test_refund")
    db.commit()
    db.refresh(entry)
    assert entry.assignment_status == ENTRY_ASSIGNMENT_RETIRED
    assert entry.entry_number == num
    assert (
        db.query(models_oripa.OripaEntry)
        .filter(
            models_oripa.OripaEntry.oripa_id == oripa.id,
            models_oripa.OripaEntry.entry_number == num,
            models_oripa.OripaEntry.assignment_status == ENTRY_ASSIGNMENT_AVAILABLE,
        )
        .count()
        == 0
    )
    db.refresh(purchase)
    assert purchase.status == ORIPA_PURCHASE_CANCELLED


def test_concurrent_last_slot_one_winner(db):
    """Prove last-slot exclusivity via sequential CAS (SQLite thread races are flaky)."""
    user_a = models.User(email="ca@t.com", name="A", password_hash="x")
    user_b = models.User(email="cb@t.com", name="B", password_hash="x")
    db.add_all([user_a, user_b])
    db.commit()
    db.refresh(user_a)
    db.refresh(user_b)
    oripa = create_oripa(
        db, title="Last1", description=None, price_per_entry=100, total_entries=1, max_entries_per_purchase=1
    )
    db.commit()
    generate_entries(db, oripa.id)
    update_oripa(db, oripa.id, status=ORIPA_STATUS_ON_SALE)
    db.commit()

    first = reserve_oripa_entries_for_payment(
        db, oripa_id=oripa.id, user_id=user_a.id, quantity=1, idempotency_key="conc-a"
    )
    db.commit()
    assert first.status == ORIPA_PURCHASE_PENDING

    from services.oripa_admin import OripaError

    try:
        reserve_oripa_entries_for_payment(
            db, oripa_id=oripa.id, user_id=user_b.id, quantity=1, idempotency_key="conc-b"
        )
        assert False, "second reserve must fail"
    except OripaError as exc:
        assert exc.status_code == 409
        db.rollback()

    assert (
        db.query(models_oripa.OripaEntry)
        .filter(models_oripa.OripaEntry.assignment_status == ENTRY_ASSIGNMENT_RESERVED)
        .count()
        == 1
    )
    assert (
        db.query(models_oripa.OripaEntry)
        .filter(models_oripa.OripaEntry.assignment_status == ENTRY_ASSIGNMENT_AVAILABLE)
        .count()
        == 0
    )


def test_purchase_api_stripe_mock_and_no_leak(api_client, db, monkeypatch):
    seed_admin_rbac(db)
    admin = create_admin_user(db, email="p310-admin@test.com", role_code="admin")
    buyer = models.User(email="p310-buyer@test.com", name="B", password_hash="x")
    db.add(buyer)
    db.commit()
    db.refresh(buyer)
    aheaders = admin_headers(admin.email)
    oid = api_client.post(
        "/api/admin/oripas",
        headers=aheaders,
        json={"title": "API Oripa", "price_per_entry": 500, "total_entries": 3},
    ).json()["id"]
    api_client.post(f"/api/admin/oripas/{oid}/generate-entries", headers=aheaders, json={})
    api_client.patch(f"/api/admin/oripas/{oid}", headers=aheaders, json={"status": "on_sale"})

    session = MagicMock()
    session.id = "cs_test_oripa"
    session.url = "https://checkout.stripe.test/pay/cs_test_oripa"
    session.status = "open"
    monkeypatch.setattr("routes.oripa.stripe_key_valid", lambda: True)
    monkeypatch.setattr("routes.oripa.create_checkout_session", lambda **kwargs: session)

    uheaders = auth_headers(buyer)
    res = api_client.post(
        f"/api/oripas/{oid}/purchase",
        headers=uheaders,
        json={"quantity": 1, "idempotency_key": "api-1"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "pending"
    assert body["entry_labels"] == []
    assert body["checkout_url"].startswith("https://checkout.stripe.test")
    assert "linked_product" not in str(body)

    # Confirm via fulfill (simulates webhook)
    order_id = body["order_id"]
    fulfill_order_inventory(db, order_id)
    polled = api_client.get(f"/api/me/oripa-purchases/{body['purchase_id']}", headers=uheaders)
    assert polled.status_code == 200
    assert polled.json()["status"] == "completed"
    assert polled.json()["entry_labels"][0].startswith("No.")


def test_recovery_idempotent_confirm(db):
    user, oripa = _on_sale(db, total=2, title="Rec")
    purchase = reserve_oripa_entries_for_payment(
        db, oripa_id=oripa.id, user_id=user.id, quantity=1, idempotency_key="rec-1"
    )
    db.commit()
    order = db.query(models.Order).filter(models.Order.id == purchase.order_id).one()
    # Simulate payment marked paid without confirm (recovery case)
    order.payment_status = "paid"
    order.status = models.OrderStatus.processing
    db.commit()
    confirm_oripa_purchase_for_order(db, order)
    db.commit()
    confirm_oripa_purchase_for_order(db, order)
    db.commit()
    db.refresh(purchase)
    assert purchase.status == ORIPA_PURCHASE_COMPLETED


def test_webhook_parallel_duplicate_claim(db):
    """Same Stripe event id cannot be claimed twice (simulates parallel webhook)."""
    user, oripa = _on_sale(db, total=2, title="Par")
    purchase = reserve_oripa_entries_for_payment(
        db, oripa_id=oripa.id, user_id=user.id, quantity=1, idempotency_key="par-1"
    )
    db.commit()
    order = db.query(models.Order).filter(models.Order.id == purchase.order_id).one()
    eid = "evt_oripa_parallel"
    assert claim_stripe_event(db, eid, "checkout.session.completed", order.id) is True
    assert claim_stripe_event(db, eid, "checkout.session.completed", order.id) is False
    assert claim_stripe_event(db, eid, "checkout.session.completed", order.id) is False


def test_public_list_no_prize_leak(api_client, db):
    seed_admin_rbac(db)
    admin = create_admin_user(db, email="p310-leak@test.com", role_code="admin")
    aheaders = admin_headers(admin.email)
    oid = api_client.post(
        "/api/admin/oripas",
        headers=aheaders,
        json={"title": "LeakCheck", "price_per_entry": 100, "total_entries": 2},
    ).json()["id"]
    api_client.post(f"/api/admin/oripas/{oid}/generate-entries", headers=aheaders, json={})
    api_client.patch(f"/api/admin/oripas/{oid}", headers=aheaders, json={"status": "on_sale"})
    res = api_client.get("/api/oripas")
    assert res.status_code == 200
    raw = res.text.lower()
    for forbidden in ("linked_product", "prize_tier", "market_price", "cost", "win", "lose"):
        assert forbidden not in raw
    detail = api_client.get(f"/api/oripas/{oid}")
    assert detail.status_code == 200
    body = detail.json()
    assert set(body.keys()) <= {
        "id",
        "title",
        "description",
        "price_per_entry",
        "total_entries",
        "remaining_entries",
        "status",
        "sale_start_at",
        "sale_end_at",
        "max_entries_per_purchase",
    }
