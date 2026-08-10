"""Phase 3-9 Step 6: multi-oripa consolidated shipment + concurrency."""

from __future__ import annotations

import models
import models_oripa
from services.admin_seed import seed_admin_rbac
from services.oripa_assignment import assign_oripa_entries
from tests.conftest import admin_headers, create_admin_user


def _prepare(api_client, db, *, buy=3):
    seed_admin_rbac(db)
    admin = create_admin_user(db, email="m6-admin@test.com", role_code="admin")
    buyer = models.User(email="m6-buyer@test.com", name="Buyer", password_hash="x")
    db.add(buyer)
    db.commit()
    db.refresh(buyer)
    headers = admin_headers(admin.email)

    oid = api_client.post(
        "/api/admin/oripas",
        headers=headers,
        json={"title": "Multi Ship Oripa", "price_per_entry": 100, "total_entries": 10},
    ).json()["id"]
    api_client.post(f"/api/admin/oripas/{oid}/generate-entries", headers=headers, json={})
    api_client.patch(f"/api/admin/oripas/{oid}", headers=headers, json={"status": "on_sale"})
    assign_oripa_entries(db, oripa_id=oid, user_id=buyer.id, quantity=buy, idempotency_key="m6-buy")
    db.commit()
    held = [
        e.id
        for e in db.query(models_oripa.OripaEntry)
        .filter(
            models_oripa.OripaEntry.assigned_user_id == buyer.id,
            models_oripa.OripaEntry.shipment_status == "held",
        )
        .order_by(models_oripa.OripaEntry.id.asc())
        .all()
    ]
    return headers, buyer, held


def test_multi_oripa_entries_one_shipment(api_client, db):
    headers, buyer, held = _prepare(api_client, db, buy=3)
    assert len(held) == 3
    created = api_client.post(
        "/api/admin/shipments",
        headers=headers,
        json={"user_id": buyer.id, "entry_ids": held},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert len(body["entry_labels"]) == 3
    assert len(body["items"]) == 3
    for eid in held:
        e = db.query(models_oripa.OripaEntry).filter(models_oripa.OripaEntry.id == eid).first()
        db.refresh(e)
        assert e.shipment_id == body["id"]
        assert e.shipment_status == "pending_ship"


def test_same_entry_two_shipments_blocked(api_client, db):
    headers, buyer, held = _prepare(api_client, db, buy=2)
    a, b = held[0], held[1]
    first = api_client.post(
        "/api/admin/shipments",
        headers=headers,
        json={"user_id": buyer.id, "entry_ids": [a]},
    )
    assert first.status_code == 200
    second = api_client.post(
        "/api/admin/shipments",
        headers=headers,
        json={"user_id": buyer.id, "entry_ids": [a, b]},
    )
    assert second.status_code == 409


def test_shipped_entry_not_reusable(api_client, db):
    headers, buyer, held = _prepare(api_client, db, buy=1)
    sid = api_client.post(
        "/api/admin/shipments",
        headers=headers,
        json={"user_id": buyer.id, "entry_ids": held},
    ).json()["id"]
    assert (
        api_client.patch(
            f"/api/admin/shipments/{sid}",
            headers=headers,
            json={"status": "shipped", "tracking_number": "T6"},
        ).status_code
        == 200
    )
    again = api_client.post(
        "/api/admin/shipments",
        headers=headers,
        json={"user_id": buyer.id, "entry_ids": held},
    )
    assert again.status_code == 409


def test_other_user_blocked(api_client, db):
    headers, buyer, held = _prepare(api_client, db, buy=2)
    other = models.User(email="m6-other@test.com", name="O", password_hash="x")
    db.add(other)
    db.commit()
    db.refresh(other)
    bad = api_client.post(
        "/api/admin/shipments",
        headers=headers,
        json={"user_id": other.id, "entry_ids": held},
    )
    assert bad.status_code in (403, 409)


def test_double_click_same_payload(api_client, db):
    """Sequential double-submit (double-click) — second must conflict."""
    headers, buyer, held = _prepare(api_client, db, buy=2)
    payload = {"user_id": buyer.id, "entry_ids": held}
    first = api_client.post("/api/admin/shipments", headers=headers, json=payload)
    second = api_client.post("/api/admin/shipments", headers=headers, json=payload)
    assert first.status_code == 200, first.text
    assert second.status_code == 409, second.text

    listed = api_client.get("/api/admin/shipments", headers=headers, params={"user_id": buyer.id})
    assert listed.status_code == 200
    ships = listed.json()["items"]
    assert len(ships) == 1
    assert {it["oripa_entry_id"] for it in ships[0]["items"]} == set(held)
