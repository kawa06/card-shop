"""Customer profile fields for buyback (birth date, etc.)."""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session

import models


def update_user_birth_date(
    db: Session,
    *,
    user: models.User,
    birth_date: date,
) -> models.User:
    today = date.today()
    if birth_date > today:
        raise HTTPException(status_code=400, detail="生年月日が未来の日付です")
    if birth_date.year < 1900:
        raise HTTPException(status_code=400, detail="生年月日が不正です")

    user.birth_date = birth_date
    db.commit()
    db.refresh(user)
    return user
