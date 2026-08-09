"""Phase 3-7 admin analytics tests."""

from __future__ import annotations

from datetime import datetime, timedelta
from io import BytesIO
import zipfile

import models
import models_analytics
import models_coupons
import models_live
import models_live_auction
import models_points
from services.admin_seed import seed_admin_rbac
from tests.conftest import admin_headers, create_admin_user


def _seed_admin(db):
    seed_admin_rbac(db)
    return create_admin_user(db, email="analytics-admin@test.com", role_code="admin")


def test_kpi_and_sales_list(api_client, db):
    admin = _seed_admin(db)
    user = models.User(email="buyer-analytics@test.com", name="Buyer", password_hash="x")
    db.add(user)
    db.commit()
    db.refresh(user)

    now = datetime.utcnow()
    order = models.Order(
        user_id=user.id,
        total_amount=1500,
        payment_status="paid",
        shipping_status="unshipped",
        order_number="AN-1001",
        coupon_code="SAVE100",
        discount_amount=100,
        points_used=50,
        points_earned=10,
        paid_at=now,
    )
    db.add(order)
    db.commit()

    headers = admin_headers(admin.email)
    kpi = api_client.get("/api/admin/analytics/kpi", headers=headers)
    assert kpi.status_code == 200
    body = kpi.json()
    assert body["paid_order_count"] >= 1
    assert body["paid_sales_yen"] >= 1500

    sales = api_client.get(
        "/api/admin/analytics/sales",
        headers=headers,
        params={"q": "AN-1001", "payment_status": "paid", "sort": "total_amount", "order": "desc"},
    )
    assert sales.status_code == 200
    payload = sales.json()
    assert payload["domain"] == "sales"
    assert payload["total"] >= 1
    assert any(i["order_number"] == "AN-1001" for i in payload["items"])


def test_domain_filters_sort_and_exports(api_client, db):
    admin = _seed_admin(db)
    headers = admin_headers(admin.email)

    stream = models_live.LiveStream(title="Analytics Live", status="ended", visibility="public")
    db.add(stream)
    db.commit()
    db.refresh(stream)

    card = models.Card(name="Analytics Card", price=1000, stock=1)
    db.add(card)
    db.commit()
    db.refresh(card)
    product = models_live.LiveProduct(stream_id=stream.id, card_id=card.id, sort_order=0)
    db.add(product)
    db.commit()
    db.refresh(product)

    auction = models_live_auction.LiveAuction(
        stream_id=stream.id,
        live_product_id=product.id,
        status="ended",
        start_price=1000,
        winning_amount=2500,
        bid_count=3,
        bidder_count=2,
    )
    db.add(auction)

    coupon = models_coupons.Coupon(
        code="ANALYTICS10",
        name="Analytics Coupon",
        coupon_type="fixed_amount",
        audience="public",
        amount_yen=100,
        is_active=True,
    )
    db.add(coupon)
    db.commit()
    db.refresh(coupon)

    user = models.User(email="points-analytics@test.com", name="P", password_hash="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    tx = models_points.PointTransaction(
        user_id=user.id,
        type="earn",
        amount=100,
        balance_after=100,
        idempotency_key="analytics-earn-1",
        source_type="admin",
    )
    db.add(tx)
    db.commit()

    live = api_client.get(
        "/api/admin/analytics/live",
        headers=headers,
        params={"q": "Analytics", "status": "ended", "sort": "title", "order": "asc"},
    )
    assert live.status_code == 200
    assert live.json()["total"] >= 1

    auctions = api_client.get(
        "/api/admin/analytics/auctions",
        headers=headers,
        params={"status": "ended", "sort": "winning_amount", "order": "desc"},
    )
    assert auctions.status_code == 200
    assert auctions.json()["total"] >= 1

    coupons = api_client.get(
        "/api/admin/analytics/coupons",
        headers=headers,
        params={"q": "ANALYTICS10", "status": "active"},
    )
    assert coupons.status_code == 200
    assert coupons.json()["total"] >= 1

    points = api_client.get(
        "/api/admin/analytics/points",
        headers=headers,
        params={"status": "earn", "sort": "amount", "order": "desc"},
    )
    assert points.status_code == 200
    assert points.json()["total"] >= 1

    for fmt, magic in (("csv", b"\xef\xbb\xbf"), ("xlsx", b"PK"), ("pdf", b"%PDF")):
        res = api_client.get(
            "/api/admin/analytics/export",
            headers=headers,
            params={"domain": "sales", "format": fmt},
        )
        assert res.status_code == 200, res.text
        assert res.content.startswith(magic)

    xlsx = api_client.get(
        "/api/admin/analytics/export",
        headers=headers,
        params={"domain": "kpi", "format": "xlsx"},
    )
    assert xlsx.status_code == 200
    with zipfile.ZipFile(BytesIO(xlsx.content)) as zf:
        assert "xl/worksheets/sheet1.xml" in zf.namelist()

    logs = db.query(models_analytics.AnalyticsExportLog).count()
    assert logs >= 4


def test_rbac_blocks_without_permission(api_client, db):
    seed_admin_rbac(db)
    viewer = create_admin_user(db, email="analytics-viewer@test.com", role_code="viewer")
    headers = admin_headers(viewer.email)

    ok = api_client.get("/api/admin/analytics/kpi", headers=headers)
    assert ok.status_code == 200

    blocked = api_client.get(
        "/api/admin/analytics/export",
        headers=headers,
        params={"domain": "sales", "format": "csv"},
    )
    assert blocked.status_code == 403
