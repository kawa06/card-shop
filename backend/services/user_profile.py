"""Shared customer profile helpers."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

import models
from services.buyback_age import today_jst


def legal_full_name(user: models.User | None) -> str:
    if not user:
        return ""
    parts = [user.family_name or "", user.given_name or ""]
    joined = "".join(p for p in parts if p).strip()
    if joined:
        return joined
    return (user.name or "").strip()


def legal_name_kana(user: models.User | None) -> str:
    if not user:
        return ""
    parts = [user.family_name_kana or "", user.given_name_kana or ""]
    return "".join(p for p in parts if p).strip()


def format_address(
    *,
    postal_code: str | None,
    prefecture: str | None,
    city: str | None,
    address_line1: str | None,
    address_line2: str | None,
) -> str:
    parts = [
        f"〒{postal_code}" if postal_code else "",
        prefecture or "",
        city or "",
        address_line1 or "",
        address_line2 or "",
    ]
    return " ".join(p for p in parts if p).strip()


def user_address_text(user: models.User | None) -> str:
    if not user:
        return ""
    return format_address(
        postal_code=user.postal_code,
        prefecture=user.region,
        city=user.city,
        address_line1=user.address_line1,
        address_line2=user.address_line2,
    )


def update_customer_profile(
    db: Session,
    *,
    user: models.User,
    family_name: Optional[str] = None,
    given_name: Optional[str] = None,
    family_name_kana: Optional[str] = None,
    given_name_kana: Optional[str] = None,
    name: Optional[str] = None,
    birth_date: Optional[date] = None,
    phone_number: Optional[str] = None,
    postal_code: Optional[str] = None,
    region: Optional[str] = None,
    city: Optional[str] = None,
    address_line1: Optional[str] = None,
    address_line2: Optional[str] = None,
    country: Optional[str] = None,
) -> models.User:
    if family_name is not None:
        user.family_name = family_name.strip() or None
    if given_name is not None:
        user.given_name = given_name.strip() or None
    if family_name_kana is not None:
        user.family_name_kana = family_name_kana.strip() or None
    if given_name_kana is not None:
        user.given_name_kana = given_name_kana.strip() or None
    if name is not None:
        user.name = name.strip() or user.name
    if birth_date is not None:
        today = today_jst()
        if birth_date > today:
            raise HTTPException(status_code=400, detail="生年月日が未来の日付です")
        if birth_date.year < 1900:
            raise HTTPException(status_code=400, detail="生年月日が不正です")
        user.birth_date = birth_date
    if phone_number is not None:
        user.phone_number = phone_number.strip() or None
    if postal_code is not None:
        user.postal_code = postal_code.strip() or None
    if region is not None:
        user.region = region.strip() or None
    if city is not None:
        user.city = city.strip() or None
    if address_line1 is not None:
        user.address_line1 = address_line1.strip() or None
    if address_line2 is not None:
        user.address_line2 = address_line2.strip() or None
    if country is not None:
        user.country = country.strip() or None

    db.commit()
    db.refresh(user)
    return user
