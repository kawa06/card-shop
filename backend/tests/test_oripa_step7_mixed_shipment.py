"""Phase 3-9 Step 7: normal order items + oripa entries → one shipment."""

from __future__ import annotations

import models
import models_oripa
from services.admin_seed import seed_admin_rbac
from services.oripa_assignment import assign_oripa_entries
from tests.conftest import admin_headers, create_admin_user


def _paid_order(db, *, user: models.User, card: models.Card, shipping_fee: int = 650) -> models.Order:
    order = models.Order(
        user_id=user.id,
        total_amount=float(card.price) + shipping_fee,
        status=models.OrderStatus.processing,
        shipping_status="unshipped",
        shipping_fee=shipping_fee,
        packaging_fee=0,
        payment_status="paid",
        postal_code=user.postal_code or "1000001",
        region=user.region or "東京都",
        city=user.city or "千代田区",
        address_line1=user.address_line1 or "1-1",
    )
    db.add(order)
    db.flush()
    db.add(
        models.OrderItem(
            order_id=order.id,
            card_id=card.id,
            quantity=1,
            unit_price=float(card.price),
            product_name=card.name,
        )
    )
    db.commit()
    db.refresh(order)
    return order


def _held_oripa(api_client, db, headers, buyer, *, key="s7"):
    oid = api_client.post(
        "/api/admin/oripas",
        headers=headers,
        json={"title": f"S7 {key}", "price_per_entry": 100, "total_entries": 5},
    ).json()["id"]
    api_client.post(f"/api/admin/oripas/{oid}/generate-entries", headers=headers, json={})
    api_client.patch(f"/api/admin/oripas/{oid}", headers=headers, json={"status": "on_sale"})
    assign_oripa_entries(db, oripa_id=oid, user_id=buyer.id, quantity=2, idempotency_key=f"s7-{key}")
    db.commit()
    return [
        e.id
        for e in db.query(models_oripa.OripaEntry)
        .filter(
            models_oripa.OripaEntry.assigned_user_id == buyer.id,
            models_oripa.OripaEntry.shipment_status == "held",
        )
        .all()
    ]


def test_order_plus_oripa_one_shipment(api_client, db):
    seed_admin_rbac(db)
    admin = create_admin_user(db, email="s7-admin@test.com", role_code="admin")
    buyer = models.User(
        email="s7-buyer@test.com",
        name="Buyer",
        password_hash="x",
        postal_code="1500001",
        region="東京都",
        city="渋谷区",
        address_line1="1-2-3",
    )
    card = models.Card(name="Normal BOX", price=3000, stock=5)
    db.add_all([buyer, card])
    db.commit()
    db.refresh(buyer)
    db.refresh(card)
    headers = admin_headers(admin.email)

    order = _paid_order(db, user=buyer, card=card, shipping_fee=650)
    fee_before = order.shipping_fee
    held = _held_oripa(api_client, db, headers, buyer, key="mix")

    created = api_client.post(
        "/api/admin/shipments",
        headers=headers,
        json={"user_id": buyer.id, "entry_ids": held[:1], "order_ids": [order.id]},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    types = {it["item_type"] for it in body["items"]}
    assert "oripa_entry" in types
    assert "order_item" in types
    assert any(it.get("order_id") == order.id for it in body["items"])

    db.refresh(order)
    assert order.shipping_status == "preparing"
    assert order.shipping_fee == fee_before  # no fee mutation

    sid = body["id"]
    shipped = api_client.patch(
        f"/api/admin/shipments/{sid}",
        headers=headers,
        json={"status": "shipped", "tracking_number": "MIX-TRACK", "shipping_carrier": "yamato"},
    )
    assert shipped.status_code == 200, shipped.text
    db.refresh(order)
    assert order.shipping_status == "shipped"
    assert order.tracking_number == "MIX-TRACK"
    assert order.shipping_fee == fee_before

    # Double attach blocked
    again = api_client.post(
        "/api/admin/shipments",
        headers=headers,
        json={"user_id": buyer.id, "order_ids": [order.id]},
    )
    assert again.status_code == 409


def test_orders_only_shipment(api_client, db):
    seed_admin_rbac(db)
    admin = create_admin_user(db, email="s7b-admin@test.com", role_code="admin")
    buyer = models.User(email="s7b-buyer@test.com", name="B", password_hash="x")
    card = models.Card(name="Sleeve", price=500, stock=10)
    db.add_all([buyer, card])
    db.commit()
    db.refresh(buyer)
    db.refresh(card)
    headers = admin_headers(admin.email)
    order = _paid_order(db, user=buyer, card=card, shipping_fee=500)
    created = api_client.post(
        "/api/admin/shipments",
        headers=headers,
        json={"user_id": buyer.id, "order_ids": [order.id]},
    )
    assert created.status_code == 200, created.text
    assert all(it["item_type"] == "order_item" for it in created.json()["items"])


def test_other_user_order_rejected(api_client, db):
    seed_admin_rbac(db)
    admin = create_admin_user(db, email="s7c-admin@test.com", role_code="admin")
    buyer = models.User(email="s7c-buyer@test.com", name="B", password_hash="x")
    other = models.User(email="s7c-other@test.com", name="O", password_hash="x")
    card = models.Card(name="X", price=100, stock=2)
    db.add_all([buyer, other, card])
    db.commit()
    db.refresh(buyer)
    db.refresh(other)
    db.refresh(card)
    headers = admin_headers(admin.email)
    order = _paid_order(db, user=buyer, card=card)
    bad = api_client.post(
        "/api/admin/shipments",
        headers=headers,
        json={"user_id": other.id, "order_ids": [order.id]},
    )
    assert bad.status_code in (403, 409)


def test_unpaid_order_rejected(api_client, db):
    seed_admin_rbac(db)
    admin = create_admin_user(db, email="s7d-admin@test.com", role_code="admin")
    buyer = models.User(email="s7d-buyer@test.com", name="B", password_hash="x")
    card = models.Card(name="Y", price=200, stock=3)
    db.add_all([buyer, card])
    db.commit()
    db.refresh(buyer)
    db.refresh(card)
    headers = admin_headers(admin.email)
    order = _paid_order(db, user=buyer, card=card)
    order.payment_status = "pending"
    db.commit()
    bad = api_client.post(
        "/api/admin/shipments",
        headers=headers,
        json={"user_id": buyer.id, "order_ids": [order.id]},
    )
    assert bad.status_code == 409
