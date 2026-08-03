"""Age helpers for minor / guardian consent rules."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import models

JST = timezone(timedelta(hours=9))


def today_jst() -> date:
    """Reference date for age checks (Japan local calendar day)."""
    return datetime.now(JST).date()


def age_on_date(birth_date: date, on_date: date | None = None) -> int:
    on_date = on_date or today_jst()
    years = on_date.year - birth_date.year
    if (on_date.month, on_date.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


def requires_guardian_consent_for_birth_date(
    birth_date: date | None,
    *,
    on_date: date | None = None,
) -> bool:
    """True when the user is under 18 on the given calendar day (満18歳未満)."""
    if birth_date is None:
        return False
    return age_on_date(birth_date, on_date or today_jst()) < 18


def requires_guardian_consent_for_user(user: models.User | None) -> bool:
    if user is None:
        return False
    return requires_guardian_consent_for_birth_date(user.birth_date)


def age_profile_for_user(user: models.User | None) -> tuple[int | None, date | None]:
    if not user or not user.birth_date:
        return None, None
    as_of = today_jst()
    return age_on_date(user.birth_date, as_of), as_of
