"""Age helpers for minor / guardian consent rules."""

from __future__ import annotations

from datetime import date

import models


def age_on_date(birth_date: date, on_date: date | None = None) -> int:
    on_date = on_date or date.today()
    years = on_date.year - birth_date.year
    if (on_date.month, on_date.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


def requires_guardian_consent_for_birth_date(birth_date: date | None) -> bool:
    """True when the user is 18 years old or younger as of today."""
    if birth_date is None:
        return False
    return age_on_date(birth_date) <= 18


def requires_guardian_consent_for_user(user: models.User) -> bool:
    return requires_guardian_consent_for_birth_date(user.birth_date)
