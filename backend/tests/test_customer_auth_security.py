"""Tests for customer auth security (lockout, login history, OTP)."""

from __future__ import annotations

from unittest.mock import patch

from auth import hash_password
import models
from services.customer_auth_security import (
    create_login_otp_challenge,
    is_user_locked,
    record_login_failure,
    record_login_success,
    verify_login_otp,
)
from services.email_template_seed import seed_email_templates


def _user(db, email: str = "customer@example.com") -> models.User:
    user = models.User(
        email=email,
        name="Customer",
        password_hash=hash_password("secret123"),
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class _FakeRequest:
    client = type("C", (), {"host": "203.0.113.1"})()
    headers = {"user-agent": "pytest"}


def test_account_lockout_after_failures(db):
    seed_email_templates(db)
    user = _user(db)
    req = _FakeRequest()

    for _ in range(5):
        record_login_failure(db, user, req)
        db.commit()
        db.refresh(user)

    assert is_user_locked(user) is True
    assert user.locked_until is not None


def test_record_login_success_clears_failures(db):
    seed_email_templates(db)
    user = _user(db)
    user.failed_login_attempts = 3
    db.commit()

    with patch("services.customer_auth_security.send_templated_email") as mock_send:
        from services.email_delivery import SendResult

        mock_send.return_value = SendResult(ok=True)
        record_login_success(db, user, method="legacy", request=_FakeRequest())

    db.refresh(user)
    assert user.failed_login_attempts == 0
    assert user.last_login_at is not None


def test_login_otp_verify(db):
    seed_email_templates(db)
    user = _user(db)
    user.two_factor_enabled = True
    db.commit()

    with patch("services.customer_auth_security.send_templated_email") as mock_send:
        from services.email_delivery import SendResult

        mock_send.return_value = SendResult(ok=True)
        challenge_id, code = create_login_otp_challenge(db, user)

    assert code is not None
    verified = verify_login_otp(db, challenge_id=challenge_id, user_id=user.id, code=code)
    assert verified.id == user.id
