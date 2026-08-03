"""Age / guardian requirement tests."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from services.buyback_age import (
    age_on_date,
    age_profile_for_user,
    requires_guardian_consent_for_birth_date,
    today_jst,
)


def test_age_on_date():
    assert age_on_date(date(2010, 5, 10), date(2026, 5, 9)) == 15
    assert age_on_date(date(2010, 5, 10), date(2026, 5, 10)) == 16
    assert age_on_date(date(2008, 1, 1), date(2026, 8, 1)) == 18


def test_requires_guardian_for_minors():
    assert requires_guardian_consent_for_birth_date(date(2010, 1, 1)) is True
    assert requires_guardian_consent_for_birth_date(date(2000, 1, 1)) is False
    assert requires_guardian_consent_for_birth_date(None) is False
    # 18歳の誕生日当日から成年（保護者同意不要）
    assert (
        requires_guardian_consent_for_birth_date(
            date(2008, 8, 2), on_date=date(2026, 8, 2)
        )
        is False
    )
    assert (
        requires_guardian_consent_for_birth_date(
            date(2008, 8, 3), on_date=date(2026, 8, 2)
        )
        is True
    )


def test_today_jst_uses_japan_calendar_day():
    from datetime import datetime

    from services.buyback_age import JST, today_jst

    with patch("services.buyback_age.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 8, 1, 0, 30, tzinfo=JST)
        assert today_jst() == date(2026, 8, 1)


def test_age_profile_uses_jst_calendar_day():
    from datetime import datetime

    from services.buyback_age import JST

    user = type("User", (), {"birth_date": date(2008, 1, 1)})()
    with patch("services.buyback_age.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 8, 1, 0, 30, tzinfo=JST)
        age, as_of = age_profile_for_user(user)
    assert age == 18
    assert as_of == date(2026, 8, 1)
