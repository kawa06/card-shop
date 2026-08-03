"""Customer profile fields for buyback (birth date, etc.)."""

from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

import models
from services.user_profile import update_customer_profile


def update_user_birth_date(
    db: Session,
    *,
    user: models.User,
    birth_date: date,
) -> models.User:
    return update_customer_profile(db, user=user, birth_date=birth_date)


def update_buyback_customer_profile(
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
    return update_customer_profile(
        db,
        user=user,
        family_name=family_name,
        given_name=given_name,
        family_name_kana=family_name_kana,
        given_name_kana=given_name_kana,
        name=name,
        birth_date=birth_date,
        phone_number=phone_number,
        postal_code=postal_code,
        region=region,
        city=city,
        address_line1=address_line1,
        address_line2=address_line2,
        country=country,
    )
