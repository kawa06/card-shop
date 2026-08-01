ADMIN_EMAILS = {"rikukai0609@icloud.com"}


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_admin_email(email: str) -> bool:
    return normalize_email(email) in ADMIN_EMAILS
