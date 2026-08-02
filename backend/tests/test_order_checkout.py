"""Order checkout price snapshot tests."""

import models
from services.order_checkout import create_order_from_cart


def _cart_item(db, test_user, card):
    item = models.CartItem(user_id=test_user.id, card_id=card.id, quantity=2)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def test_create_order_persists_price_breakdown(db, test_user):
    card = models.Card(
        name="スナップショットカード",
        price=1000,
        stock=5,
        condition="a",
        is_active=True,
    )
    db.add(card)
    db.commit()

    cart_item = _cart_item(db, test_user, card)

    order = create_order_from_cart(
        db,
        user=test_user,
        cart_items=[cart_item],
        postal_code="6500001",
        country="Japan",
        region="兵庫県",
        city="神戸市",
        address_line1="テスト1-1",
        address_line2=None,
        shipping_address="兵庫県神戸市テスト1-1",
        shipping_method="takkyubin_compact",
        shipping_fee=650,
        packaging_fee=77,
        items_subtotal=2000,
        tax_rate_snapshot=10,
        payment_method="stripe_card",
        payment_status="awaiting_payment",
        finalize=False,
    )

    assert order.items_subtotal == 2000
    assert order.shipping_fee == 650
    assert order.packaging_fee == 77
    assert order.total_amount == 2727
    assert order.tax_rate_snapshot == 10
    assert len(order.items) == 1
    assert order.items[0].unit_price == 1000
    assert order.items[0].quantity == 2
    assert order.items[0].product_name == "スナップショットカード"
