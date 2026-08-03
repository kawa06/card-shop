"""Age / guardian requirement tests."""

from __future__ import annotations

from datetime import date

from services.buyback_age import (
    age_on_date,
    requires_guardian_consent_for_birth_date,
)


def test_age_on_date():
    assert age_on_date(date(2010, 5, 10), date(2026, 5, 9)) == 15
    assert age_on_date(date(2010, 5, 10), date(2026, 5, 10)) == 16
    assert age_on_date(date(2008, 1, 1), date(2026, 8, 1)) == 18


def test_requires_guardian_for_minors():
    assert requires_guardian_consent_for_birth_date(date(2010, 1, 1)) is True
    assert requires_guardian_consent_for_birth_date(date(2000, 1, 1)) is False
    assert requires_guardian_consent_for_birth_date(None) is False
