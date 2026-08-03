"""Payout bank account CRUD for buyback."""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import models_buyback
from services.buyback_payout_crypto import (
    PAYOUT_USER_MESSAGE,
    PayoutEncryptionUnavailable,
    decrypt_account_number,
    encrypt_account_number,
    mask_account_number,
)

logger = logging.getLogger(__name__)

MAX_ACCOUNTS_PER_USER = 3
ALLOWED_ACCOUNT_TYPES = {"ordinary", "checking"}
ACCOUNT_TYPE_LABELS = {"ordinary": "普通", "checking": "当座"}


def list_payout_accounts(db: Session, user_id: int) -> list[models_buyback.PayoutAccount]:
    return (
        db.query(models_buyback.PayoutAccount)
        .filter(models_buyback.PayoutAccount.user_id == user_id)
        .order_by(
            models_buyback.PayoutAccount.is_default.desc(),
            models_buyback.PayoutAccount.id.asc(),
        )
        .all()
    )


def _serialize_masked(account: models_buyback.PayoutAccount) -> dict:
    try:
        plain = decrypt_account_number(account.account_number_encrypted)
        masked = mask_account_number(plain)
    except Exception:
        logger.warning(
            "payout_account_decrypt_failed code=payout_decrypt_failed account_id=%s",
            account.id,
        )
        masked = "****"
    return {
        "id": account.id,
        "bank_name": account.bank_name,
        "branch_name": account.branch_name,
        "account_type": account.account_type,
        "account_holder": account.account_holder,
        "account_number_masked": masked,
        "is_default": account.is_default,
        "created_at": account.created_at,
        "updated_at": account.updated_at,
    }


def list_payout_accounts_masked(db: Session, user_id: int) -> list[dict]:
    return [_serialize_masked(a) for a in list_payout_accounts(db, user_id)]


def get_default_payout_account(db: Session, user_id: int) -> models_buyback.PayoutAccount | None:
    accounts = list_payout_accounts(db, user_id)
    if not accounts:
        return None
    for account in accounts:
        if account.is_default:
            return account
    return accounts[0]


def serialize_payout_account_for_admin(account: models_buyback.PayoutAccount) -> dict:
    try:
        plain = decrypt_account_number(account.account_number_encrypted)
    except Exception:
        plain = ""
    return {
        "id": account.id,
        "bank_name": account.bank_name,
        "branch_name": account.branch_name,
        "account_type": account.account_type,
        "account_type_label": ACCOUNT_TYPE_LABELS.get(account.account_type, account.account_type),
        "account_holder": account.account_holder,
        "account_number": plain,
        "account_number_masked": mask_account_number(plain) if plain else "****",
        "is_default": account.is_default,
        "created_at": account.created_at,
        "updated_at": account.updated_at,
    }


def create_payout_account(
    db: Session,
    *,
    user_id: int,
    bank_name: str,
    branch_name: str | None,
    account_type: str,
    account_number: str,
    account_holder: str,
    set_default: bool = False,
) -> dict:
    bank = (bank_name or "").strip()
    branch = (branch_name or "").strip() or None
    holder = (account_holder or "").strip()
    acct_type = (account_type or "").strip()
    if not bank:
        raise HTTPException(status_code=400, detail="金融機関名を入力してください")
    if acct_type not in ALLOWED_ACCOUNT_TYPES:
        raise HTTPException(status_code=400, detail="口座種別が不正です")
    if not holder:
        raise HTTPException(status_code=400, detail="口座名義を入力してください")

    existing_count = (
        db.query(models_buyback.PayoutAccount)
        .filter(models_buyback.PayoutAccount.user_id == user_id)
        .count()
    )
    if existing_count >= MAX_ACCOUNTS_PER_USER:
        raise HTTPException(status_code=400, detail=f"振込口座は{MAX_ACCOUNTS_PER_USER}件まで登録できます")

    try:
        encrypted = encrypt_account_number(account_number)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PayoutEncryptionUnavailable as exc:
        logger.error(
            "payout_account_create_failed code=payout_encryption_unconfigured user_id=%s",
            user_id,
        )
        raise HTTPException(status_code=503, detail=PAYOUT_USER_MESSAGE) from exc

    make_default = set_default or existing_count == 0
    if make_default:
        db.query(models_buyback.PayoutAccount).filter(
            models_buyback.PayoutAccount.user_id == user_id
        ).update({models_buyback.PayoutAccount.is_default: False})

    account = models_buyback.PayoutAccount(
        user_id=user_id,
        bank_name=bank,
        branch_name=branch,
        account_type=acct_type,
        account_number_encrypted=encrypted,
        account_holder=holder,
        is_default=make_default,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return _serialize_masked(account)


def set_default_payout_account(db: Session, *, user_id: int, account_id: int) -> dict:
    account = (
        db.query(models_buyback.PayoutAccount)
        .filter(
            models_buyback.PayoutAccount.id == account_id,
            models_buyback.PayoutAccount.user_id == user_id,
        )
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="振込口座が見つかりません")

    db.query(models_buyback.PayoutAccount).filter(
        models_buyback.PayoutAccount.user_id == user_id
    ).update({models_buyback.PayoutAccount.is_default: False})
    account.is_default = True
    account.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(account)
    return _serialize_masked(account)


def delete_payout_account(db: Session, *, user_id: int, account_id: int) -> None:
    account = (
        db.query(models_buyback.PayoutAccount)
        .filter(
            models_buyback.PayoutAccount.id == account_id,
            models_buyback.PayoutAccount.user_id == user_id,
        )
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="振込口座が見つかりません")

    was_default = account.is_default
    db.delete(account)
    db.commit()

    if was_default:
        replacement = (
            db.query(models_buyback.PayoutAccount)
            .filter(models_buyback.PayoutAccount.user_id == user_id)
            .order_by(models_buyback.PayoutAccount.id.asc())
            .first()
        )
        if replacement:
            replacement.is_default = True
            replacement.updated_at = datetime.utcnow()
            db.commit()
