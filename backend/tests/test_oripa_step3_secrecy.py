"""Phase 3-9 Step 3: content secrecy for customer APIs."""

from __future__ import annotations

import json

import models
from services.admin_seed import seed_admin_rbac
from services.oripa_admin import create_oripa, generate_entries, link_entry_product, update_oripa
from services.oripa_constants import ORIPA_STATUS_ON_SALE
from tests.conftest import admin_headers, auth_headers, create_admin_user


FORBIDDEN = {
    "linked_product_id",
    "linked_product_name",
    "linked_inventory_id",
    "prize_tier",
    "rarity",
    "cost",
    "market_price",
}


def _assert_no_forbidden(payload):
    raw = json.dumps(payload, ensure_ascii=False)
    for key in FORBIDDEN:
        assert key not in raw
    assert "当たり" not in raw
    assert "ハズレ" not in raw


def test_customer_apis_hide_linked_product(api_client, db):
    seed_admin_rbac(db)
    admin = create_admin_user(db, email="sec-admin@test.com", role_code="admin")
    buyer = models.User(email="sec-buyer@test.com", name="B", password_hash="x")
    db.add(buyer)
    card = models.Card(name="SECRET PRIZE CARD XYZ", price=9999, stock=1, rarity="SSR")
    db.add(card)
    db.commit()
    db.refresh(buyer)
    db.refresh(card)

    aheaders = admin_headers(admin.email)
    created = api_client.post(
        "/api/admin/oripas",
        headers=aheaders,
        json={"title": "Secret Oripa", "price_per_entry": 500, "total_entries": 3},
    )
    assert created.status_code == 200
    oid = created.json()["id"]
    assert api_client.post(f"/api/admin/oripas/{oid}/generate-entries", headers=aheaders, json={}).status_code == 200
    entries = api_client.get(f"/api/admin/oripas/{oid}/entries", headers=aheaders).json()["items"]
    eid = entries[0]["id"]
    linked = api_client.patch(
        f"/api/admin/oripa-entries/{eid}",
        headers=aheaders,
        json={"linked_product_id": card.id},
    )
    assert linked.status_code == 200
    assert linked.json()["linked_product_id"] == card.id
    assert linked.json()["linked_product_name"] == "SECRET PRIZE CARD XYZ"

    api_client.patch(f"/api/admin/oripas/{oid}", headers=aheaders, json={"status": "on_sale"})

    pub = api_client.get(f"/api/oripas/{oid}")
    assert pub.status_code == 200
    body = pub.json()
    _assert_no_forbidden(body)
    assert "SECRET PRIZE" not in json.dumps(body)

    listed = api_client.get("/api/oripas")
    assert listed.status_code == 200
    _assert_no_forbidden(listed.json())

    uheaders = auth_headers(buyer)
    purchased = api_client.post(
        f"/api/oripas/{oid}/purchase",
        headers=uheaders,
        json={"quantity": 1, "idempotency_key": "sec-1"},
    )
    assert purchased.status_code == 200, purchased.text
    _assert_no_forbidden(purchased.json())
    assert "SECRET" not in json.dumps(purchased.json())
    assert purchased.json()["entry_labels"][0].startswith("No.")

    held = api_client.get("/api/me/oripa-entries", headers=uheaders)
    assert held.status_code == 200
    _assert_no_forbidden(held.json())
    assert "SECRET" not in json.dumps(held.json())

    # Non-admin cannot read admin entry detail
    deny = api_client.get(f"/api/admin/oripas/{oid}/entries", headers=uheaders)
    assert deny.status_code in (401, 403)

    # IDOR: another user must not see buyer's held entries
    other = models.User(email="sec-other@test.com", name="O", password_hash="x")
    db.add(other)
    db.commit()
    db.refresh(other)
    other_held = api_client.get("/api/me/oripa-entries", headers=auth_headers(other))
    assert other_held.status_code == 200
    assert other_held.json()["total"] == 0
    assert other_held.json()["items"] == []


def test_admin_still_sees_content(api_client, db):
    seed_admin_rbac(db)
    admin = create_admin_user(db, email="sec-admin2@test.com", role_code="admin")
    card = models.Card(name="Admin Visible", price=100, stock=1)
    db.add(card)
    db.commit()
    db.refresh(card)
    headers = admin_headers(admin.email)
    oid = api_client.post(
        "/api/admin/oripas",
        headers=headers,
        json={"title": "A", "price_per_entry": 100, "total_entries": 1},
    ).json()["id"]
    api_client.post(f"/api/admin/oripas/{oid}/generate-entries", headers=headers, json={})
    eid = api_client.get(f"/api/admin/oripas/{oid}/entries", headers=headers).json()["items"][0]["id"]
    linked = api_client.patch(
        f"/api/admin/oripa-entries/{eid}",
        headers=headers,
        json={"linked_product_id": card.id},
    ).json()
    assert linked["linked_product_name"] == "Admin Visible"
