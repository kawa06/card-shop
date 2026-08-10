"""Phase 3-9 Step 8: cancel / refund / recovery gates (no number resale)."""

from __future__ import annotations

import random

import models
import models_oripa
from services.admin_seed import seed_admin_rbac
from services.oripa_admin import OripaError, create_oripa, generate_entries, update_oripa
from services.oripa_assignment import assign_oripa_entries, mark_purchase_failed_idempotent
from services.oripa_constants import (
    ENTRY_ASSIGNMENT_AVAILABLE,
    ENTRY_ASSIGNMENT_RETIRED,
    ENTRY_SHIPMENT_HELD,
    ORIPA_PURCHASE_CANCELLED,
    ORIPA_PURCHASE_FAILED,
    ORIPA_STATUS_ON_SALE,
)
from services.oripa_recovery import cancel_oripa_purchase, cancel_oripa_shipment, record_failed_pre_assignment
from services.oripa_shipment import create_oripa_shipment, update_shipment
from tests.conftest import admin_headers, create_admin_user


def _on_sale(db, *, total=8, title="S8"):
    user = models.User(email=f"{title}-{random.randint(1, 999999)}@t.com", name="U", password_hash="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    oripa = create_oripa(
        db,
        title=title,
        description=None,
        price_per_entry=300,
        total_entries=total,
        max_entries_per_purchase=total,
    )
    db.commit()
    generate_entries(db, oripa.id)
    update_oripa(db, oripa.id, status=ORIPA_STATUS_ON_SALE)
    db.commit()
    db.refresh(oripa)
    return user, oripa


def test_payment_failure_no_numbers(db):
    user, oripa = _on_sale(db, total=5, title="Fail")
    row = record_failed_pre_assignment(
        db,
        oripa_id=oripa.id,
        user_id=user.id,
        quantity=2,
        idempotency_key="fail-key-1",
        reason="stripe_failed",
    )
    db.commit()
    assert row.status == ORIPA_PURCHASE_FAILED
    again = mark_purchase_failed_idempotent(
        db,
        oripa_id=oripa.id,
        user_id=user.id,
        quantity=2,
        idempotency_key="fail-key-1",
        reason="dup",
    )
    assert again.id == row.id
    assigned = (
        db.query(models_oripa.OripaEntry)
        .filter(models_oripa.OripaEntry.oripa_id == oripa.id, models_oripa.OripaEntry.assignment_status != ENTRY_ASSIGNMENT_AVAILABLE)
        .count()
    )
    assert assigned == 0


def test_cancel_after_assign_retires_no_resale(db):
    user, oripa = _on_sale(db, total=6, title="Retire")
    purchase = assign_oripa_entries(
        db, oripa_id=oripa.id, user_id=user.id, quantity=2, idempotency_key="ret-1", rng=random.Random(7)
    )
    db.commit()
    nums = [
        e.entry_number
        for e in db.query(models_oripa.OripaEntry)
        .filter(models_oripa.OripaEntry.assigned_purchase_id == purchase.id)
        .all()
    ]
    cancel_oripa_purchase(db, purchase_id=purchase.id, reason="customer_request")
    db.commit()
    db.refresh(purchase)
    assert purchase.status == ORIPA_PURCHASE_CANCELLED
    for n in nums:
        entry = (
            db.query(models_oripa.OripaEntry)
            .filter(models_oripa.OripaEntry.oripa_id == oripa.id, models_oripa.OripaEntry.entry_number == n)
            .first()
        )
        assert entry.assignment_status == ENTRY_ASSIGNMENT_RETIRED
        assert entry.assignment_status != ENTRY_ASSIGNMENT_AVAILABLE

    # Same numbers must never be reassigned
    available = (
        db.query(models_oripa.OripaEntry)
        .filter(
            models_oripa.OripaEntry.oripa_id == oripa.id,
            models_oripa.OripaEntry.assignment_status == ENTRY_ASSIGNMENT_AVAILABLE,
        )
        .all()
    )
    assert all(e.entry_number not in nums for e in available)

    # Duplicate cancel (full refund webhook replay) is idempotent
    again = cancel_oripa_purchase(db, purchase_id=purchase.id, reason="dup_webhook")
    db.commit()
    assert again.status == ORIPA_PURCHASE_CANCELLED


def test_shipment_cancel_releases_to_held(api_client, db):
    seed_admin_rbac(db)
    admin = create_admin_user(db, email="s8-ship-admin@test.com", role_code="admin")
    user, oripa = _on_sale(db, total=5, title="ShipCancel")
    purchase = assign_oripa_entries(db, oripa_id=oripa.id, user_id=user.id, quantity=2, rng=random.Random(3))
    db.commit()
    entries = (
        db.query(models_oripa.OripaEntry)
        .filter(models_oripa.OripaEntry.assigned_purchase_id == purchase.id)
        .all()
    )
    ids = [e.id for e in entries]
    ship = create_oripa_shipment(db, user_id=user.id, entry_ids=ids, actor_admin_user_id=admin.id)
    db.commit()
    cancel_oripa_shipment(db, shipment_id=ship.id, reason="ops_mistake")
    db.commit()
    db.refresh(ship)
    assert ship.status == "cancelled"
    for eid in ids:
        e = db.query(models_oripa.OripaEntry).filter(models_oripa.OripaEntry.id == eid).first()
        assert e.shipment_status == ENTRY_SHIPMENT_HELD
        assert e.shipment_id is None
        assert e.assignment_status != ENTRY_ASSIGNMENT_AVAILABLE


def test_shipped_purchase_cancel_blocked(db):
    user, oripa = _on_sale(db, total=4, title="ShippedBlock")
    purchase = assign_oripa_entries(db, oripa_id=oripa.id, user_id=user.id, quantity=1, rng=random.Random(9))
    db.commit()
    entry = (
        db.query(models_oripa.OripaEntry)
        .filter(models_oripa.OripaEntry.assigned_purchase_id == purchase.id)
        .first()
    )
    ship = create_oripa_shipment(db, user_id=user.id, entry_ids=[entry.id])
    db.commit()
    update_shipment(db, ship.id, status="shipped", tracking_number="T-1")
    db.commit()
    try:
        cancel_oripa_purchase(db, purchase_id=purchase.id)
        assert False, "expected block"
    except OripaError as exc:
        assert exc.status_code == 409


def test_shipped_shipment_cancel_blocked(db):
    user, oripa = _on_sale(db, total=4, title="ShipBlock")
    purchase = assign_oripa_entries(db, oripa_id=oripa.id, user_id=user.id, quantity=1, rng=random.Random(11))
    db.commit()
    entry = (
        db.query(models_oripa.OripaEntry)
        .filter(models_oripa.OripaEntry.assigned_purchase_id == purchase.id)
        .first()
    )
    ship = create_oripa_shipment(db, user_id=user.id, entry_ids=[entry.id])
    db.commit()
    update_shipment(db, ship.id, status="shipped", tracking_number="T-2")
    db.commit()
    try:
        cancel_oripa_shipment(db, shipment_id=ship.id)
        assert False
    except OripaError as exc:
        assert exc.status_code == 409


def test_admin_cancel_purchase_api(api_client, db):
    seed_admin_rbac(db)
    admin = create_admin_user(db, email="s8-api-admin@test.com", role_code="admin")
    user, oripa = _on_sale(db, total=5, title="ApiCancel")
    purchase = assign_oripa_entries(db, oripa_id=oripa.id, user_id=user.id, quantity=1, rng=random.Random(5))
    db.commit()
    headers = admin_headers(admin.email)
    res = api_client.post(
        f"/api/admin/oripa-purchases/{purchase.id}/cancel",
        headers=headers,
        json={"reason": "full_refund"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "cancelled"
    # duplicate refund webhook
    res2 = api_client.post(
        f"/api/admin/oripa-purchases/{purchase.id}/cancel",
        headers=headers,
        json={"reason": "dup"},
    )
    assert res2.status_code == 200
    entry = (
        db.query(models_oripa.OripaEntry)
        .filter(models_oripa.OripaEntry.assigned_purchase_id == purchase.id)
        .first()
    )
    assert entry.assignment_status == ENTRY_ASSIGNMENT_RETIRED


def test_cancel_pending_ship_purchase_empties_shipment(db):
    user, oripa = _on_sale(db, total=5, title="PendCancel")
    purchase = assign_oripa_entries(db, oripa_id=oripa.id, user_id=user.id, quantity=2, rng=random.Random(13))
    db.commit()
    entries = (
        db.query(models_oripa.OripaEntry)
        .filter(models_oripa.OripaEntry.assigned_purchase_id == purchase.id)
        .all()
    )
    ship = create_oripa_shipment(db, user_id=user.id, entry_ids=[e.id for e in entries])
    db.commit()
    cancel_oripa_purchase(db, purchase_id=purchase.id, reason="pre_ship_refund")
    db.commit()
    db.refresh(ship)
    assert ship.status == "cancelled"
    for e in entries:
        db.refresh(e)
        assert e.assignment_status == ENTRY_ASSIGNMENT_RETIRED
        assert e.shipment_id is None
