"""Phase 3-9 Step 5: single/held oripa → shipment (no double-ship)."""

from __future__ import annotations

import models
import models_oripa
from services.admin_seed import seed_admin_rbac
from services.oripa_assignment import assign_oripa_entries
from tests.conftest import admin_headers, create_admin_user


def _seed_held(api_client, db, *, entries=3, buy=2):
    seed_admin_rbac(db)
    admin = create_admin_user(db, email="ship-admin@test.com", role_code="admin")
    buyer = models.User(email="ship-buyer@test.com", name="Buyer", password_hash="x")
    db.add(buyer)
    card = models.Card(name="Ship Prize", price=100, stock=5)
    db.add(card)
    db.commit()
    db.refresh(buyer)
    db.refresh(card)
    headers = admin_headers(admin.email)

    oid = api_client.post(
        "/api/admin/oripas",
        headers=headers,
        json={"title": "Ship Oripa", "price_per_entry": 100, "total_entries": entries},
    ).json()["id"]
    api_client.post(f"/api/admin/oripas/{oid}/generate-entries", headers=headers, json={})
    entries = api_client.get(f"/api/admin/oripas/{oid}/entries", headers=headers).json()["items"]
    for e in entries:
        api_client.patch(
            f"/api/admin/oripa-entries/{e['id']}",
            headers=headers,
            json={"linked_product_id": card.id},
        )
    api_client.patch(f"/api/admin/oripas/{oid}", headers=headers, json={"status": "on_sale"})

    assign_oripa_entries(db, oripa_id=oid, user_id=buyer.id, quantity=buy, idempotency_key="ship-buy-1")
    db.commit()

    held_ids = [
        e.id
        for e in db.query(models_oripa.OripaEntry)
        .filter(
            models_oripa.OripaEntry.assigned_user_id == buyer.id,
            models_oripa.OripaEntry.shipment_status == "held",
        )
        .all()
    ]
    return headers, buyer, held_ids


def test_single_oripa_ship_barcode_tracking_no_double(api_client, db):
    headers, buyer, held_ids = _seed_held(api_client, db, entries=5, buy=2)
    assert len(held_ids) == 2
    one = held_ids[0]

    created = api_client.post(
        "/api/admin/shipments",
        headers=headers,
        json={"user_id": buyer.id, "entry_ids": [one]},
    )
    assert created.status_code == 200, created.text
    ship = created.json()
    assert ship["status"] == "unshipped"
    assert len(ship["entry_labels"]) == 1
    assert ship["items"][0]["linked_product_name"] == "Ship Prize"
    sid = ship["id"]

    dup = api_client.post(
        "/api/admin/shipments",
        headers=headers,
        json={"user_id": buyer.id, "entry_ids": [one]},
    )
    assert dup.status_code == 409

    barcode = api_client.get(f"/api/admin/shipments/{sid}/barcode", headers=headers)
    assert barcode.status_code == 200
    assert barcode.json()["scan_token"]
    svg = api_client.get(f"/api/admin/shipments/{sid}/barcode.svg", headers=headers)
    assert svg.status_code == 200
    assert "svg" in svg.headers.get("content-type", "")

    patched = api_client.patch(
        f"/api/admin/shipments/{sid}",
        headers=headers,
        json={"status": "shipped", "tracking_number": "TRACK-1", "shipping_carrier": "yamato"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["status"] == "shipped"
    assert patched.json()["tracking_number"] == "TRACK-1"

    entry = db.query(models_oripa.OripaEntry).filter(models_oripa.OripaEntry.id == one).first()
    db.refresh(entry)
    assert entry.shipment_status == "shipped"
    assert entry.shipment_id == sid

    again = api_client.post(
        "/api/admin/shipments",
        headers=headers,
        json={"user_id": buyer.id, "entry_ids": [one]},
    )
    assert again.status_code == 409

    logs = api_client.get(f"/api/admin/shipments/{sid}/logs", headers=headers)
    assert logs.status_code == 200
    assert any(x["event_type"] == "shipping_updated" for x in logs.json())


def test_other_user_entry_rejected(api_client, db):
    headers, buyer, held_ids = _seed_held(api_client, db, entries=3, buy=1)
    other = models.User(email="other-ship@test.com", name="O", password_hash="x")
    db.add(other)
    db.commit()
    db.refresh(other)
    bad = api_client.post(
        "/api/admin/shipments",
        headers=headers,
        json={"user_id": other.id, "entry_ids": held_ids},
    )
    assert bad.status_code in (403, 409)


def test_shipments_list_ok(api_client, db):
    seed_admin_rbac(db)
    admin = create_admin_user(db, email="ship-reg@test.com", role_code="admin")
    headers = admin_headers(admin.email)
    listed = api_client.get("/api/admin/shipments", headers=headers)
    assert listed.status_code == 200
    assert "items" in listed.json()
