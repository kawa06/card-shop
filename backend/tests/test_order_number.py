from datetime import datetime
from unittest.mock import patch

import models
from services.order_number import assign_order_number


def test_assign_order_number_format_and_sequence(db, test_user):
    today = datetime.utcnow().strftime("%Y%m%d")

    order1 = models.Order(user_id=test_user.id, total_amount=100, status=models.OrderStatus.pending)
    order2 = models.Order(user_id=test_user.id, total_amount=200, status=models.OrderStatus.pending)
    db.add_all([order1, order2])
    db.commit()

    num1 = assign_order_number(db, order1)
    db.commit()
    num2 = assign_order_number(db, order2)
    db.commit()

    assert num1 == f"KRX-{today}-0001"
    assert num2 == f"KRX-{today}-0002"
    assert num1 != num2


def test_assign_order_number_idempotent(db, test_user):
    order = models.Order(
        user_id=test_user.id,
        total_amount=100,
        status=models.OrderStatus.pending,
        order_number="KRX-20260101-0099",
    )
    db.add(order)
    db.commit()

    result = assign_order_number(db, order)
    assert result == "KRX-20260101-0099"


def test_assign_order_number_increments_existing_sequence_row(db, test_user):
    today = datetime.utcnow().strftime("%Y%m%d")
    db.add(models.OrderNumberSequence(seq_date=today, last_seq=5))
    db.commit()

    order = models.Order(user_id=test_user.id, total_amount=100, status=models.OrderStatus.pending)
    db.add(order)
    db.commit()

    num = assign_order_number(db, order)
    db.commit()

    assert num == f"KRX-{today}-0006"
