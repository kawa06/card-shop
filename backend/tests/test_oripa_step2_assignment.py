"""Phase 3-9 Step 2: assignment engine gates."""

from __future__ import annotations

import random

import models
import models_oripa
from services.oripa_admin import OripaError, create_oripa, generate_entries, update_oripa
from services.oripa_assignment import (
    assign_oripa_entries,
    list_purchase_entry_numbers,
    mark_purchase_failed_idempotent,
)
from services.oripa_constants import (
    ENTRY_ASSIGNMENT_ASSIGNED,
    ENTRY_ASSIGNMENT_AVAILABLE,
    ORIPA_PURCHASE_FAILED,
    ORIPA_STATUS_ON_SALE,
    ORIPA_STATUS_SOLD_OUT,
)


def _setup_on_sale(db, *, total: int = 10, max_per: int = 10, seed_title: str = "Assign"):
    user = models.User(email=f"{seed_title}-{random.randint(1,999999)}@t.com", name="U", password_hash="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    oripa = create_oripa(
        db,
        title=seed_title,
        description=None,
        price_per_entry=500,
        total_entries=total,
        max_entries_per_purchase=max_per,
    )
    db.commit()
    generate_entries(db, oripa.id)
    update_oripa(db, oripa.id, status=ORIPA_STATUS_ON_SALE)
    db.commit()
    db.refresh(oripa)
    return user, oripa


def test_assign_single_entry(db):
    user, oripa = _setup_on_sale(db, total=5, seed_title="Single")
    purchase = assign_oripa_entries(db, oripa_id=oripa.id, user_id=user.id, quantity=1, rng=random.Random(1))
    db.commit()
    nums = list_purchase_entry_numbers(db, purchase.id)
    assert len(nums) == 1
    entry = (
        db.query(models_oripa.OripaEntry)
        .filter(models_oripa.OripaEntry.assigned_purchase_id == purchase.id)
        .first()
    )
    assert entry.assignment_status == ENTRY_ASSIGNMENT_ASSIGNED
    assert entry.assigned_user_id == user.id


def test_assign_multiple_entries(db):
    user, oripa = _setup_on_sale(db, total=10, seed_title="Multi")
    purchase = assign_oripa_entries(db, oripa_id=oripa.id, user_id=user.id, quantity=5, rng=random.Random(2))
    db.commit()
    nums = list_purchase_entry_numbers(db, purchase.id)
    assert len(nums) == 5
    assert len(set(nums)) == 5


def test_sold_out_and_final_one(db):
    user, oripa = _setup_on_sale(db, total=2, max_per=2, seed_title="Sold")
    assign_oripa_entries(db, oripa_id=oripa.id, user_id=user.id, quantity=1, rng=random.Random(3))
    db.commit()
    assign_oripa_entries(db, oripa_id=oripa.id, user_id=user.id, quantity=1, rng=random.Random(4))
    db.commit()
    db.refresh(oripa)
    assert oripa.status == ORIPA_STATUS_SOLD_OUT
    try:
        assign_oripa_entries(db, oripa_id=oripa.id, user_id=user.id, quantity=1)
        assert False
    except OripaError as exc:
        assert ("sold out" in exc.detail.lower()) or ("在庫不足" in exc.detail) or ("販売中ではありません" in exc.detail)


def test_idempotent_webhook_retry(db):
    user, oripa = _setup_on_sale(db, total=5, seed_title="Idem")
    key = "wh-retry-1"
    p1 = assign_oripa_entries(
        db, oripa_id=oripa.id, user_id=user.id, quantity=2, idempotency_key=key, rng=random.Random(5)
    )
    db.commit()
    nums1 = list_purchase_entry_numbers(db, p1.id)
    p2 = assign_oripa_entries(
        db, oripa_id=oripa.id, user_id=user.id, quantity=2, idempotency_key=key, rng=random.Random(6)
    )
    db.commit()
    assert p1.id == p2.id
    assert list_purchase_entry_numbers(db, p2.id) == nums1
    assigned = (
        db.query(models_oripa.OripaEntry)
        .filter(
            models_oripa.OripaEntry.oripa_id == oripa.id,
            models_oripa.OripaEntry.assignment_status == ENTRY_ASSIGNMENT_ASSIGNED,
        )
        .count()
    )
    assert assigned == 2


def test_duplicate_request_same_key_no_double_assign(db):
    user, oripa = _setup_on_sale(db, total=3, seed_title="Dup")
    key = "dup-key"
    assign_oripa_entries(db, oripa_id=oripa.id, user_id=user.id, quantity=1, idempotency_key=key)
    db.commit()
    assign_oripa_entries(db, oripa_id=oripa.id, user_id=user.id, quantity=1, idempotency_key=key)
    db.commit()
    assert (
        db.query(models_oripa.OripaEntry)
        .filter(models_oripa.OripaEntry.assignment_status == ENTRY_ASSIGNMENT_ASSIGNED)
        .count()
        == 1
    )


def test_payment_failure_no_assignment(db):
    user, oripa = _setup_on_sale(db, total=4, seed_title="Fail")
    key = "pay-fail"
    # simulate failed payment recorded without assignment
    mark_purchase_failed_idempotent(
        db, oripa_id=oripa.id, user_id=user.id, quantity=2, idempotency_key=key, reason="payment_failed"
    )
    db.commit()
    assert (
        db.query(models_oripa.OripaEntry)
        .filter(models_oripa.OripaEntry.assignment_status == ENTRY_ASSIGNMENT_AVAILABLE)
        .count()
        == 4
    )
    failed = (
        db.query(models_oripa.OripaPurchase)
        .filter(models_oripa.OripaPurchase.idempotency_key == key)
        .first()
    )
    assert failed.status == ORIPA_PURCHASE_FAILED


def test_transaction_rollback_clears_assignment(db):
    user, oripa = _setup_on_sale(db, total=3, seed_title="Rollback")
    try:
        assign_oripa_entries(db, oripa_id=oripa.id, user_id=user.id, quantity=2, rng=random.Random(7))
        raise RuntimeError("force rollback")
    except RuntimeError:
        db.rollback()
    available = (
        db.query(models_oripa.OripaEntry)
        .filter(
            models_oripa.OripaEntry.oripa_id == oripa.id,
            models_oripa.OripaEntry.assignment_status == ENTRY_ASSIGNMENT_AVAILABLE,
        )
        .count()
    )
    assert available == 3


def test_no_double_assign_same_number_across_users(db):
    user1, oripa = _setup_on_sale(db, total=2, max_per=2, seed_title="Race")
    user2 = models.User(email="race2@t.com", name="U2", password_hash="x")
    db.add(user2)
    db.commit()
    db.refresh(user2)
    p1 = assign_oripa_entries(db, oripa_id=oripa.id, user_id=user1.id, quantity=1, rng=random.Random(8))
    db.commit()
    p2 = assign_oripa_entries(db, oripa_id=oripa.id, user_id=user2.id, quantity=1, rng=random.Random(9))
    db.commit()
    n1 = set(list_purchase_entry_numbers(db, p1.id))
    n2 = set(list_purchase_entry_numbers(db, p2.id))
    assert n1.isdisjoint(n2)
    assert len(n1 | n2) == 2


def test_concurrent_last_entry(db):
    """Two sequential competing claims on last entry via CAS — second must fail."""
    user, oripa = _setup_on_sale(db, total=1, max_per=1, seed_title="Last")
    user2 = models.User(email="last2@t.com", name="U2", password_hash="x")
    db.add(user2)
    db.commit()
    db.refresh(user2)

    # Simulate race: both sessions load available=1 then try CAS assign
    engine = db.get_bind()
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=engine)
    s1 = Session()
    s2 = Session()
    results: list[str] = []
    try:
        try:
            assign_oripa_entries(s1, oripa_id=oripa.id, user_id=user.id, quantity=1, rng=random.Random(1))
            s1.commit()
            results.append("ok")
        except Exception:
            s1.rollback()
            results.append("fail")
        try:
            assign_oripa_entries(s2, oripa_id=oripa.id, user_id=user2.id, quantity=1, rng=random.Random(2))
            s2.commit()
            results.append("ok")
        except Exception:
            s2.rollback()
            results.append("fail")
    finally:
        s1.close()
        s2.close()

    assert results.count("ok") == 1
    assert results.count("fail") == 1
    assigned = (
        db.query(models_oripa.OripaEntry)
        .filter(
            models_oripa.OripaEntry.oripa_id == oripa.id,
            models_oripa.OripaEntry.assignment_status == ENTRY_ASSIGNMENT_ASSIGNED,
        )
        .count()
    )
    assert assigned == 1
