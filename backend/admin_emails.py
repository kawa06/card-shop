ADMIN_EMAILS = {"rikukai0609@icloud.com"}


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_admin_email(email: str) -> bool:
    return normalize_email(email) in ADMIN_EMAILS


def ensure_admin(user, db):
    """Promote configured admin emails; never revoke existing admins."""
    if is_admin_email(user.email) and not user.is_admin:
        user.is_admin = True
        db.commit()
        db.refresh(user)
    return user
