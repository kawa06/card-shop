"""Phase 3-8 inventory alerts and restock tests."""

from __future__ import annotations

import models
import models_inventory
from services.inventory_alerts import (
    evaluate_card_inventory,
    inventory_status_for_card,
    manually_resolve_alert,
)
from services.inventory_constants import (
    ALERT_STATUS_OPEN,
    ALERT_STATUS_RESOLVED,
    ALERT_TYPE_LOW_STOCK,
    ALERT_TYPE_OUT_OF_STOCK,
    DEFAULT_LOW_STOCK_THRESHOLD,
    INVENTORY_STATUS_IN_STOCK,
    INVENTORY_STATUS_LOW_STOCK,
    INVENTORY_STATUS_OUT_OF_STOCK,
)
from services.inventory_restock import RestockError, create_restock, receive_restock, update_restock
from services.admin_seed import seed_admin_rbac
from services.order_checkout import apply_inventory_for_order
from tests.conftest import admin_headers, create_admin_user


def _card(db, *, stock: int, threshold: int | None = 3, enabled: bool = True, name: str = "Inv Card"):
    card = models.Card(
        name=name,
        price=1000,
        stock=stock,
        low_stock_threshold=threshold,
        inventory_alert_enabled=enabled,
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


def test_status_in_stock(db):
    card = _card(db, stock=10, threshold=3)
    assert inventory_status_for_card(card) == INVENTORY_STATUS_IN_STOCK


def test_status_low_stock_at_threshold(db):
    card = _card(db, stock=3, threshold=3)
    assert inventory_status_for_card(card) == INVENTORY_STATUS_LOW_STOCK


def test_status_out_of_stock(db):
    card = _card(db, stock=0, threshold=3)
    assert inventory_status_for_card(card) == INVENTORY_STATUS_OUT_OF_STOCK


def test_order_creates_low_stock_alert(db):
    card = _card(db, stock=5, threshold=3)
    user = models.User(email="inv-buyer@test.com", name="B", password_hash="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    order = models.Order(user_id=user.id, total_amount=2000, payment_status="pending")
    db.add(order)
    db.commit()
    db.refresh(order)
    db.add(models.OrderItem(order_id=order.id, card_id=card.id, quantity=2, unit_price=1000))
    db.commit()
    db.refresh(order)
    apply_inventory_for_order(db, order)
    db.commit()
    db.refresh(card)
    assert card.stock == 3
    alert = (
        db.query(models_inventory.InventoryAlert)
        .filter(
            models_inventory.InventoryAlert.product_id == card.id,
            models_inventory.InventoryAlert.alert_type == ALERT_TYPE_LOW_STOCK,
            models_inventory.InventoryAlert.status == ALERT_STATUS_OPEN,
        )
        .first()
    )
    assert alert is not None


def test_stock_zero_creates_out_of_stock(db):
    card = _card(db, stock=1, threshold=3)
    evaluate_card_inventory(db, card.id, source="test")
    db.commit()
    card.stock = 0
    evaluate_card_inventory(db, card.id, source="test")
    db.commit()
    oos = (
        db.query(models_inventory.InventoryAlert)
        .filter(
            models_inventory.InventoryAlert.product_id == card.id,
            models_inventory.InventoryAlert.alert_type == ALERT_TYPE_OUT_OF_STOCK,
            models_inventory.InventoryAlert.status == ALERT_STATUS_OPEN,
        )
        .count()
    )
    assert oos == 1


def test_duplicate_open_alert_not_created(db):
    card = _card(db, stock=2, threshold=3)
    evaluate_card_inventory(db, card.id, source="a")
    evaluate_card_inventory(db, card.id, source="b")
    db.commit()
    count = (
        db.query(models_inventory.InventoryAlert)
        .filter(
            models_inventory.InventoryAlert.product_id == card.id,
            models_inventory.InventoryAlert.alert_type == ALERT_TYPE_LOW_STOCK,
            models_inventory.InventoryAlert.status == ALERT_STATUS_OPEN,
        )
        .count()
    )
    assert count == 1


def test_restock_requested_persisted(db):
    card = _card(db, stock=1)
    row = create_restock(db, product_id=card.id, requested_quantity=10, note="need more")
    db.commit()
    db.refresh(row)
    assert row.status == "requested"
    assert row.requested_quantity == 10


def test_restock_received_adds_stock(db):
    card = _card(db, stock=2, threshold=3)
    evaluate_card_inventory(db, card.id)
    db.commit()
    row = create_restock(db, product_id=card.id, requested_quantity=10)
    db.commit()
    receive_restock(db, row.id, received_quantity=10)
    db.commit()
    db.refresh(card)
    db.refresh(row)
    assert card.stock == 12
    assert row.status == "received"
    open_alerts = (
        db.query(models_inventory.InventoryAlert)
        .filter(
            models_inventory.InventoryAlert.product_id == card.id,
            models_inventory.InventoryAlert.status == ALERT_STATUS_OPEN,
        )
        .count()
    )
    assert open_alerts == 0


def test_restock_receive_idempotent(db):
    card = _card(db, stock=2)
    row = create_restock(db, product_id=card.id, requested_quantity=5)
    db.commit()
    receive_restock(db, row.id, received_quantity=5)
    db.commit()
    db.refresh(card)
    assert card.stock == 7
    receive_restock(db, row.id, received_quantity=5)
    db.commit()
    db.refresh(card)
    assert card.stock == 7


def test_restock_after_receive_resolves_alerts(db):
    card = _card(db, stock=0, threshold=3)
    evaluate_card_inventory(db, card.id)
    db.commit()
    assert (
        db.query(models_inventory.InventoryAlert)
        .filter(
            models_inventory.InventoryAlert.product_id == card.id,
            models_inventory.InventoryAlert.alert_type == ALERT_TYPE_OUT_OF_STOCK,
            models_inventory.InventoryAlert.status == ALERT_STATUS_OPEN,
        )
        .count()
        == 1
    )
    row = create_restock(db, product_id=card.id, requested_quantity=10)
    db.commit()
    receive_restock(db, row.id)
    db.commit()
    resolved = (
        db.query(models_inventory.InventoryAlert)
        .filter(
            models_inventory.InventoryAlert.product_id == card.id,
            models_inventory.InventoryAlert.alert_type == ALERT_TYPE_OUT_OF_STOCK,
            models_inventory.InventoryAlert.status == ALERT_STATUS_RESOLVED,
        )
        .count()
    )
    assert resolved == 1


def test_rbac_read_write_and_forbidden(api_client, db):
    seed_admin_rbac(db)
    admin = create_admin_user(db, email="inv-admin@test.com", role_code="admin")
    viewer = create_admin_user(db, email="inv-viewer@test.com", role_code="viewer")
    card = _card(db, stock=0)
    evaluate_card_inventory(db, card.id)
    db.commit()

    headers = admin_headers(admin.email)
    listed = api_client.get("/api/admin/inventory-alerts", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1

    created = api_client.post(
        "/api/admin/inventory-restocks",
        headers=headers,
        json={"product_id": card.id, "requested_quantity": 4, "note": "rbac"},
    )
    assert created.status_code == 200

    vheaders = admin_headers(viewer.email)
    ok_read = api_client.get("/api/admin/inventory-alerts", headers=vheaders)
    assert ok_read.status_code == 200
    forbidden = api_client.post(
        "/api/admin/inventory-restocks",
        headers=vheaders,
        json={"product_id": card.id, "requested_quantity": 1},
    )
    assert forbidden.status_code == 403


def test_invalid_state_transition(db):
    card = _card(db, stock=1)
    row = create_restock(db, product_id=card.id, requested_quantity=3)
    db.commit()
    receive_restock(db, row.id)
    db.commit()
    try:
        update_restock(db, row.id, status="ordered")
        assert False, "expected RestockError"
    except RestockError:
        pass


def test_analytics_inventory_integration(api_client, db):
    seed_admin_rbac(db)
    admin = create_admin_user(db, email="inv-analytics@test.com", role_code="admin")
    _card(db, stock=0, name="OOS Analytics")
    _card(db, stock=2, threshold=3, name="Low Analytics")
    headers = admin_headers(admin.email)
    kpi = api_client.get("/api/admin/analytics/kpi", headers=headers)
    assert kpi.status_code == 200
    body = kpi.json()
    assert body["out_of_stock_products"] >= 1
    assert body["low_stock_products"] >= 1
    inv = api_client.get("/api/admin/analytics/inventory", headers=headers, params={"status": "out_of_stock"})
    assert inv.status_code == 200
    assert inv.json()["total"] >= 1
    export = api_client.get(
        "/api/admin/analytics/export",
        headers=headers,
        params={"domain": "inventory", "format": "csv"},
    )
    assert export.status_code == 200
    assert export.content.startswith(b"\xef\xbb\xbf")


def test_manual_resolve_allows_reopen(db):
    card = _card(db, stock=1, threshold=3)
    evaluate_card_inventory(db, card.id)
    db.commit()
    alert = (
        db.query(models_inventory.InventoryAlert)
        .filter(models_inventory.InventoryAlert.product_id == card.id)
        .first()
    )
    manually_resolve_alert(db, alert.id)
    db.commit()
    assert alert.status == ALERT_STATUS_RESOLVED
    evaluate_card_inventory(db, card.id)
    db.commit()
    open_count = (
        db.query(models_inventory.InventoryAlert)
        .filter(
            models_inventory.InventoryAlert.product_id == card.id,
            models_inventory.InventoryAlert.status == ALERT_STATUS_OPEN,
        )
        .count()
    )
    assert open_count == 1


def test_default_threshold_constant(db):
    card = _card(db, stock=DEFAULT_LOW_STOCK_THRESHOLD, threshold=None)
    assert inventory_status_for_card(card) == INVENTORY_STATUS_LOW_STOCK
