"""Shared fixtures for backend unit tests (SQLite in-memory)."""

from __future__ import annotations

from datetime import datetime
import os
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from auth import create_access_token, hash_password
from config import settings
from database import Base, get_db
import models  # noqa: F401 — register models on Base.metadata
import models_buyback  # noqa: F401 — register buyback tables
import models_admin  # noqa: F401 — register admin security tables
import models_email  # noqa: F401 — register email platform tables
import models_live  # noqa: F401
import models_live_auction  # noqa: F401 — register live sales tables
import models_live_offer  # noqa: F401 — register live offer tables
import models_points  # noqa: F401 — register points tables
import models_coupons  # noqa: F401 — register coupon tables
import models_notifications  # noqa: F401 — register notification tables
import models_analytics  # noqa: F401 — register analytics tables
import models_inventory  # noqa: F401 — register inventory tables
from admin_emails import ADMIN_EMAILS, normalize_email
from services.admin_auth import bootstrap_admin_user
from services.admin_seed import seed_admin_rbac


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        hide_parameters=True,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def buyback_test_settings(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", True)
    monkeypatch.setattr(settings, "BUYBACK_PAYOUT_ENCRYPTION_KEY", "test-key-for-buyback-payout-32b")
    monkeypatch.setenv("ADMIN_PROXY_SECRET", "test-only-admin-proxy-secret")


@pytest.fixture(autouse=True)
def seed_admin_rbac_data(db):
    for email in ADMIN_EMAILS:
        norm = normalize_email(email)
        user = db.query(models.User).filter(func.lower(models.User.email) == norm).first()
        if user is None:
            db.add(
                models.User(
                    email=norm,
                    name="Owner Admin",
                    password_hash=hash_password("owner-test-password"),
                    is_admin=True,
                    is_verified=True,
                )
            )
    db.commit()
    seed_admin_rbac(db)


@pytest.fixture
def api_client(db):
    """FastAPI TestClient backed by the in-memory SQLite session."""
    from main import app

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def auth_headers(user: models.User) -> dict[str, str]:
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def admin_headers(email: str = "rikukai0609@icloud.com") -> dict[str, str]:
    from internal_admin_auth import build_admin_proxy_signature

    timestamp = str(int(time.time()))
    secret = os.getenv("ADMIN_PROXY_SECRET", "")
    return {
        "X-Admin-Email": email,
        "X-Admin-Timestamp": timestamp,
        "X-Admin-Signature": build_admin_proxy_signature(
            secret=secret,
            email=email,
            timestamp=timestamp,
        ),
    }


def create_admin_user(
    db,
    *,
    email: str = "admin@test.com",
    name: str = "Admin User",
    role_code: str = "admin",
    is_active: bool = True,
) -> models.User:
    user = models.User(
        email=email,
        name=name,
        password_hash=hash_password("admin-test-password"),
        is_admin=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    admin_user = bootstrap_admin_user(db, user, role_code=role_code)
    admin_user.is_active = is_active
    db.commit()
    db.refresh(user)
    return user


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
