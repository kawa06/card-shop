"""Label-ya CSV and 72265 layout tests (Phase 7)."""

from __future__ import annotations

from unittest.mock import patch

from auth import hash_password
import models
import models_buyback
from services.buyback_cart import add_cart_item
from services.buyback_label_yasan import (
    FACES,
    LABEL_HEIGHT_MM,
    LABEL_WIDTH_MM,
    MARGIN_LEFT_MM,
    MARGIN_TOP_MM,
    get_72265_layout,
)
from services.buyback_requests import submit_request_from_cart
from tests.conftest import auth_headers, create_admin_user


def _customer(db, email: str = "label-customer@example.com") -> models.User:
    user = models.User(
        email=email,
        name="ラベルテスト客",
        password_hash=hash_password("secret123"),
        is_verified=True,
        postal_code="6500001",
        region="兵庫県",
        city="神戸市",
        address_line1="中央区1-1",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _issue_packages(db, api_client, admin, customer, boxes: int = 2):
    add_cart_item(
        db,
        user_id=customer.id,
        firestore_item_id="fs_label_001",
        product_name="ラベルカード",
        category="raw",
        condition_code="A",
        unit_price=400,
        quantity=1,
    )
    with patch("services.buyback_requests.notify_buyback_request_submitted"):
        request = submit_request_from_cart(
            db,
            user=customer,
            rejected_item_handling="return_rejected_only",
            agreed_prepaid_shipping=True,
            agreed_cod_consequence=True,
            agreed_condition_rejection=True,
        )
    request.status = models_buyback.BuybackRequestStatus.assessed.value
    for item in request.items:
        item.line_status = models_buyback.BuybackItemLineStatus.rejected.value
        item.is_return_target = True
        item.rejection_reason_code = "other"
        item.rejection_reason_text = "返送"
    db.commit()

    issued = api_client.post(
        f"/api/admin/buyback/requests/{request.id}/packages",
        headers=auth_headers(admin),
        json={"total_boxes": boxes, "package_kind": "return"},
    )
    assert issued.status_code == 200
    return request, issued.json()


def test_72265_layout_uses_official_face_size():
    layout = get_72265_layout()
    assert layout["product_code"] == "72265"
    assert layout["format_code"] == "F65A4-1"
    assert layout["faces"] == FACES == 65
    assert layout["label_width_mm"] == LABEL_WIDTH_MM == 38.1
    assert layout["label_height_mm"] == LABEL_HEIGHT_MM == 21.2
    assert layout["columns"] == 5
    assert layout["rows"] == 13
    assert layout["margins_confirmed"] is False
    assert layout["margin_left_mm"] == MARGIN_LEFT_MM == 9.75
    assert layout["margin_top_mm"] == MARGIN_TOP_MM == 10.7


def test_label_layout_api(api_client, db):
    admin = create_admin_user(db, email="label-layout@test.com", role_code="shipping_manager")
    res = api_client.get("/api/admin/buyback/labels/layout", headers=auth_headers(admin))
    assert res.status_code == 200
    assert res.json()["faces"] == 65


def test_label_csv_export(api_client, db):
    admin = create_admin_user(db, email="label-csv@test.com", role_code="buyback_manager")
    customer = _customer(db)
    _, packages = _issue_packages(db, api_client, admin, customer, boxes=2)
    ids = [p["id"] for p in packages]

    res = api_client.post(
        "/api/admin/buyback/labels/csv",
        headers=auth_headers(admin),
        json={"package_ids": ids, "include_applicant_name": False},
    )
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    text = res.content.decode("utf-8-sig")
    lines = text.strip().split("\r\n")
    assert lines[0].startswith("管理ID,バーコード番号,商品名")
    assert len(lines) == 3  # header + 2 packages
    assert packages[0]["package_code"] in text
    assert "取扱注意" in text
    # No address / phone / email in CSV
    assert "6500001" not in text
    assert "ラベルテスト客" not in text
    assert customer.email not in text


def test_label_csv_with_name_requires_pii(api_client, db):
    admin = create_admin_user(db, email="label-csv-name@test.com", role_code="buyback_manager")
    customer = _customer(db, email="label-name@example.com")
    _, packages = _issue_packages(db, api_client, admin, customer, boxes=1)

    res = api_client.post(
        "/api/admin/buyback/labels/csv",
        headers=auth_headers(admin),
        json={"package_ids": [packages[0]["id"]], "include_applicant_name": True},
    )
    assert res.status_code == 200
    text = res.content.decode("utf-8-sig")
    assert "ラベルテスト客" in text
    assert "6500001" not in text


def test_label_sheet_start_position(api_client, db):
    admin = create_admin_user(db, email="label-sheet@test.com", role_code="shipping_manager")
    customer = _customer(db, email="label-sheet@example.com")
    _, packages = _issue_packages(db, api_client, admin, customer, boxes=1)

    res = api_client.post(
        "/api/admin/buyback/labels/sheet",
        headers=auth_headers(admin),
        json={
            "package_ids": [packages[0]["id"]],
            "start_position": 10,
            "copies": 2,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["start_position"] == 10
    assert body["copies"] == 2
    assert len(body["labels"]) == 2
    assert body["labels"][0]["scan_token"]
    assert body["layout"]["faces"] == 65


def test_viewer_cannot_export_label_csv(api_client, db):
    admin = create_admin_user(db, email="label-viewer@test.com", role_code="viewer")
    res = api_client.post(
        "/api/admin/buyback/labels/csv",
        headers=auth_headers(admin),
        json={"package_ids": [1]},
    )
    assert res.status_code == 403
