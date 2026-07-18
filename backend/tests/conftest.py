"""Shared fixtures for backend unit tests (SQLite in-memory)."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
import models  # noqa: F401 — register models on Base.metadata


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user(db):
    user = models.User(
        email="buyer@example.com",
        password_hash="hashed",
        name="テスト購入者",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def paid_order(db, test_user):
    order = models.Order(
        user_id=test_user.id,
        total_amount=1500.0,
        status=models.OrderStatus.processing,
        payment_status="paid",
        shipping_status="preparing",
        order_number="KRX-20260719-0001",
        shipping_method="click_post",
        shipping_address="兵庫県テスト市",
        paid_at=datetime.utcnow(),
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order
