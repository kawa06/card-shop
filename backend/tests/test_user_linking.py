"""Tests for Clerk ↔ users linking rules."""

from __future__ import annotations

from auth import hash_password
import models
from services.user_linking import LinkResult, resolve_clerk_user


def test_link_by_existing_clerk_user_id(db):
    user = models.User(
        email="linked@example.com",
        name="Linked",
        password_hash=hash_password("secret123"),
        clerk_user_id="user_clerk_abc",
        is_verified=True,
    )
    db.add(user)
    db.commit()

    outcome = resolve_clerk_user(
        db,
        clerk_user_id="user_clerk_abc",
        email="other@example.com",
    )
    assert outcome.result == LinkResult.found_by_clerk_id
    assert outcome.user.id == user.id


def test_link_existing_email_sets_clerk_user_id(db):
    user = models.User(
        email="shop@example.com",
        name="Shop User",
        password_hash=hash_password("secret123"),
        is_verified=True,
    )
    db.add(user)
    db.commit()
    original_hash = user.password_hash

    outcome = resolve_clerk_user(
        db,
        clerk_user_id="user_new_clerk",
        email="shop@example.com",
        name="Shop User",
    )
    assert outcome.result == LinkResult.linked_existing
    assert outcome.user.clerk_user_id == "user_new_clerk"
    assert outcome.user.password_hash == original_hash


def test_link_clerk_id_conflict_blocked(db):
    user = models.User(
        email="conflict@example.com",
        name="Conflict",
        password_hash=hash_password("secret123"),
        clerk_user_id="user_existing_clerk",
        is_verified=True,
    )
    db.add(user)
    db.commit()

    outcome = resolve_clerk_user(
        db,
        clerk_user_id="user_different_clerk",
        email="conflict@example.com",
    )
    assert outcome.result == LinkResult.clerk_id_conflict
    assert outcome.user is None


def test_link_creates_new_user(db):
    outcome = resolve_clerk_user(
        db,
        clerk_user_id="user_brand_new",
        email="newbuyback@example.com",
        name="New Buyback",
    )
    assert outcome.result == LinkResult.created
    assert outcome.user is not None
    assert outcome.user.clerk_user_id == "user_brand_new"
    assert outcome.user.email == "newbuyback@example.com"
