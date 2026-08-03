#!/usr/bin/env python3
"""Send a test email through production mail stack (Resend + SMTP fallback)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import sessionmaker

from config import settings
from database import engine
from services.email_delivery import send_templated_email
from services.verification import email_configured, smtp_configured


def main() -> int:
    to = (sys.argv[1] if len(sys.argv) > 1 else settings.MAIL_REPLY_TO).strip()
    if not to:
        print("Usage: test_email_delivery.py [recipient@example.com]", file=sys.stderr)
        return 1

    print(f"RESEND_API_KEY: {'yes' if settings.RESEND_API_KEY else 'no'}")
    print(f"SMTP configured: {'yes' if smtp_configured() else 'no'}")
    print(f"email_configured: {'yes' if email_configured() else 'no'}")
    print(f"MAIL_FROM: {settings.MAIL_FROM}")
    print(f"MAIL_USERNAME: {settings.MAIL_USERNAME or '(unset)'}")
    print(f"Sending test to: {to}")

    Session = sessionmaker(bind=engine)
    with Session() as db:
        result = send_templated_email(
            db,
            template_key="buyback_guardian_consent",
            to_email=to,
            variables={"name": "テスト", "content": "<p>メール送信テスト</p>", "url": "https://example.com"},
            fallback_subject="【KRX TCG】メール送信テスト",
            fallback_html="<p>メール送信テストです。</p>",
            raw_variable_keys={"content"},
            force=True,
            is_test=True,
        )
        db.commit()

    print(f"ok={result.ok}")
    if result.error_code:
        print(f"error_code={result.error_code}")
    if result.user_message:
        print(f"user_message={result.user_message}")
    if result.error:
        print(f"technical={result.error}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
