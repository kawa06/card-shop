"""Phase 3-9 Step 1: Oripa admin CRUD / entries / RBAC / audit."""

from __future__ import annotations

import models
import models_oripa
from services.admin_seed import seed_admin_rbac
from services.oripa_admin import create_oripa, generate_entries, link_entry_product, update_oripa
from services.oripa_constants import ORIPA_STATUS_ON_SALE, format_entry_number
from tests.conftest import admin_headers, create_admin_user


def test_create_oripa_and_generate_unique_entries(db):
    row = create_oripa(
        db,
        title="Step1 Oripa",
        description="test",
        price_per_entry=500,
        total_entries=5,
    )
    db.commit()
    n = generate_entries(db, row.id)
    db.commit()
    assert n == 5
    entries = (
        db.query(models_oripa.OripaEntry)
        .filter(models_oripa.OripaEntry.oripa_id == row.id)
        .order_by(models_oripa.OripaEntry.entry_number)
        .all()
    )
    assert [e.entry_number for e in entries] == [1, 2, 3, 4, 5]
    assert format_entry_number(1) == "No.001"
    # unique constraint: same number twice should fail at DB layer when inserted
    assert (
        db.query(models_oripa.OripaEntry)
        .filter(models_oripa.OripaEntry.oripa_id == row.id)
        .count()
        == 5
    )


def test_link_product_and_audit(db):
    card = models.Card(name="Prize Card", price=1000, stock=1)
    db.add(card)
    db.commit()
    db.refresh(card)
    oripa = create_oripa(db, title="Link", description=None, price_per_entry=300, total_entries=2)
    db.commit()
    generate_entries(db, oripa.id)
    db.commit()
    entry = (
        db.query(models_oripa.OripaEntry)
        .filter(models_oripa.OripaEntry.oripa_id == oripa.id, models_oripa.OripaEntry.entry_number == 1)
        .first()
    )
    link_entry_product(db, entry.id, card.id)
    db.commit()
    db.refresh(entry)
    assert entry.linked_product_id == card.id
    audits = (
        db.query(models_oripa.OripaAuditLog)
        .filter(models_oripa.OripaAuditLog.action == "oripa_entry_linked")
        .count()
    )
    assert audits >= 1


def test_status_transition_and_invalid(db):
    oripa = create_oripa(db, title="Status", description=None, price_per_entry=100, total_entries=1)
    db.commit()
    update_oripa(db, oripa.id, status=ORIPA_STATUS_ON_SALE)
    db.commit()
    db.refresh(oripa)
    assert oripa.status == ORIPA_STATUS_ON_SALE
    try:
        update_oripa(db, oripa.id, status="draft")
        assert False, "expected error"
    except Exception as exc:
        assert "不正な状態遷移" in str(exc)


def test_rbac_oripa_api(api_client, db):
    seed_admin_rbac(db)
    admin = create_admin_user(db, email="oripa-admin@test.com", role_code="admin")
    viewer = create_admin_user(db, email="oripa-viewer@test.com", role_code="viewer")
    headers = admin_headers(admin.email)

    created = api_client.post(
        "/api/admin/oripas",
        headers=headers,
        json={
            "title": "API Oripa",
            "description": "d",
            "price_per_entry": 1000,
            "total_entries": 3,
            "max_entries_per_purchase": 2,
        },
    )
    assert created.status_code == 200, created.text
    oid = created.json()["id"]

    gen = api_client.post(f"/api/admin/oripas/{oid}/generate-entries", headers=headers, json={})
    assert gen.status_code == 200
    assert gen.json()["generated"] == 3

    listed = api_client.get("/api/admin/oripas", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1

    entries = api_client.get(f"/api/admin/oripas/{oid}/entries", headers=headers)
    assert entries.status_code == 200
    assert entries.json()["total"] == 3

    vheaders = admin_headers(viewer.email)
    ok_read = api_client.get("/api/admin/oripas", headers=vheaders)
    assert ok_read.status_code == 200
    forbidden = api_client.post(
        "/api/admin/oripas",
        headers=vheaders,
        json={"title": "x", "price_per_entry": 1, "total_entries": 1},
    )
    assert forbidden.status_code == 403
