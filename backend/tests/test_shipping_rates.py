"""Shipping fee calculation tests."""

from services.shipping_rates import calculate_shipping_fee, calculate_shipping_quote
from services.order_checkout import validate_shipping_method, resolve_shipping_quote
import models
import json


def test_flat_domestic_same_nationwide():
    tokyo = calculate_shipping_fee("click_post", "東京都", "JP")
    okinawa = calculate_shipping_fee("click_post", "沖縄県", "JP")
    assert tokyo == okinawa == 185


def test_regional_fee_differs_by_prefecture():
    hyogo = calculate_shipping_fee("takkyubin_60", "兵庫県", "Japan")
    okinawa = calculate_shipping_fee("takkyubin_60", "沖縄県", "Japan")
    assert hyogo > 0
    assert okinawa > hyogo


def test_packaging_surcharge_split_in_quote():
    quote = calculate_shipping_quote("takkyubin_compact", "兵庫県", "Japan")
    assert quote["packaging_fee_jpy"] == 77
    assert quote["fee_jpy"] == quote["base_shipping_fee_jpy"] + 77


def test_international_ems_fee():
    fee = calculate_shipping_fee("ems", None, "US")
    assert fee >= 3000


def test_international_alias_normalized_in_validation(db, test_user):
    card = models.Card(
        name="Ship Test",
        price=100,
        stock=1,
        condition="a",
        is_active=True,
        allowed_shipping_methods=json.dumps(["international"]),
    )
    db.add(card)
    db.commit()
    item = models.CartItem(user_id=test_user.id, card_id=card.id, quantity=1)
    db.add(item)
    db.commit()
    db.refresh(item)

    validate_shipping_method([item], "ems", "US")


def test_resolve_shipping_quote_matches_calculate(db):
    quote = resolve_shipping_quote("click_post", "大阪府", "Japan", db)
    assert quote["fee_jpy"] == calculate_shipping_fee("click_post", "大阪府", "Japan", db)
