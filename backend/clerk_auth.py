"""Verify Clerk session JWTs for admin API access (no backend-sync required)."""

from __future__ import annotations

import base64
import logging
from functools import lru_cache
from typing import Any, Optional

import httpx
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from admin_emails import normalize_email
from services.user_linking import LinkResult, resolve_clerk_user
import models

logger = logging.getLogger(__name__)

CLERK_SECRET_KEY = (__import__("os").getenv("CLERK_SECRET_KEY") or "").strip()
CLERK_PUBLISHABLE_KEY = (
    __import__("os").getenv("CLERK_PUBLISHABLE_KEY")
    or __import__("os").getenv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY")
    or "pk_test_c3F1YXJlLWxlbW1pbmctNzguY2xlcmsuYWNjb3VudHMuZGV2JA"
).strip()


def clerk_frontend_api_from_publishable_key(publishable_key: str) -> Optional[str]:
    try:
        encoded = publishable_key.split("_", 2)[2]
        padded = encoded + "=" * (-len(encoded) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        return decoded.split("$")[0]
    except (IndexError, ValueError, UnicodeDecodeError):
        return None


@lru_cache(maxsize=4)
def _clerk_jwks_url(publishable_key: str) -> Optional[str]:
    frontend_api = clerk_frontend_api_from_publishable_key(publishable_key)
    if not frontend_api:
        return None
    return f"https://{frontend_api}/.well-known/jwks.json"


@lru_cache(maxsize=4)
def _clerk_issuer(publishable_key: str) -> Optional[str]:
    frontend_api = clerk_frontend_api_from_publishable_key(publishable_key)
    if not frontend_api:
        return None
    return f"https://{frontend_api}"


def _fetch_clerk_jwks() -> list[dict[str, Any]]:
    if not CLERK_PUBLISHABLE_KEY:
        return []
    url = _clerk_jwks_url(CLERK_PUBLISHABLE_KEY)
    if not url:
        return []
    try:
        res = httpx.get(url, timeout=10.0)
        res.raise_for_status()
        return res.json().get("keys", [])
    except httpx.HTTPError:
        logger.warning("Failed to fetch Clerk JWKS")
        return []


def _email_from_clerk_claims(payload: dict[str, Any]) -> Optional[str]:
    for key in ("email", "primary_email_address", "email_address"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return normalize_email(value)

    emails = payload.get("email_addresses")
    if isinstance(emails, list):
        for item in emails:
            if isinstance(item, str) and item.strip():
                return normalize_email(item)
            if isinstance(item, dict):
                addr = item.get("email_address") or item.get("email")
                if isinstance(addr, str) and addr.strip():
                    return normalize_email(addr)
    return None


def _email_from_clerk_api(clerk_user_id: str) -> Optional[str]:
    if not CLERK_SECRET_KEY:
        return None
    try:
        res = httpx.get(
            f"https://api.clerk.com/v1/users/{clerk_user_id}",
            headers={"Authorization": f"Bearer {CLERK_SECRET_KEY}"},
            timeout=10.0,
        )
        if res.status_code != 200:
            return None
        data = res.json()
        primary_id = data.get("primary_email_address_id")
        for item in data.get("email_addresses", []):
            if not isinstance(item, dict):
                continue
            email = item.get("email_address")
            if not isinstance(email, str):
                continue
            if primary_id and item.get("id") == primary_id:
                return normalize_email(email)
            if not primary_id:
                return normalize_email(email)
    except httpx.HTTPError:
        logger.warning("Failed to fetch Clerk user")
    return None


def verify_clerk_session_token(token: str) -> Optional[dict[str, Any]]:
    if not CLERK_PUBLISHABLE_KEY:
        return None
    issuer = _clerk_issuer(CLERK_PUBLISHABLE_KEY)
    if not issuer:
        return None

    keys = _fetch_clerk_jwks()
    if not keys:
        return None

    last_error: Optional[Exception] = None
    for key in keys:
        try:
            return jwt.decode(
                token,
                key,
                algorithms=[key.get("alg", "RS256")],
                issuer=issuer,
                options={"verify_aud": False},
            )
        except JWTError as exc:
            last_error = exc
            continue

    if last_error:
        logger.debug("Clerk JWT verification failed: %s", last_error)
    return None


def _name_from_clerk_claims(payload: dict[str, Any]) -> Optional[str]:
    for key in ("name", "full_name", "first_name"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def clerk_identity_from_token(token: str) -> Optional[tuple[str, str, Optional[str]]]:
    """Return (clerk_user_id, email, name) from a Clerk session JWT."""
    payload = verify_clerk_session_token(token)
    if not payload:
        return None

    clerk_user_id = payload.get("sub")
    if not isinstance(clerk_user_id, str) or not clerk_user_id.strip():
        return None

    email = _email_from_clerk_claims(payload) or _email_from_clerk_api(clerk_user_id)
    if not email:
        return None

    return clerk_user_id.strip(), email, _name_from_clerk_claims(payload)


def authenticate_clerk_session(token: str, db: Session) -> Optional[models.User]:
    payload = verify_clerk_session_token(token)
    if not payload:
        return None

    clerk_user_id = payload.get("sub")
    if not isinstance(clerk_user_id, str) or not clerk_user_id.strip():
        return None

    email = _email_from_clerk_claims(payload) or _email_from_clerk_api(clerk_user_id)
    if not email:
        return None

    name = _name_from_clerk_claims(payload)
    outcome = resolve_clerk_user(
        db,
        clerk_user_id=clerk_user_id,
        email=email,
        name=name,
    )
    if outcome.result in (LinkResult.email_ambiguous, LinkResult.clerk_id_conflict):
        logger.warning(
            "Clerk link blocked for %s: %s",
            clerk_user_id,
            outcome.result.value,
        )
        return None
    return outcome.user
