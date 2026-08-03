"""Customer login security: lockout, history, login notify, email OTP 2FA."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

import models
import models_email
from config import settings
from services.admin_rbac import LOGIN_LOCKOUT_MINUTES, MAX_FAILED_LOGIN_ATTEMPTS
from services.member_emails import (
    notify_2fa_otp_sent,
    notify_account_locked,
    notify_account_unlocked,
    notify_login_failed,
    notify_login_success,
)

OTP_EXPIRE_MINUTES = 10


def _utcnow() -> datetime:
    return datetime.utcnow()


def _client_ip(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    if request.client:
        return request.client.host[:64]
    return None


def _client_ua(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    return (request.headers.get("user-agent") or "")[:512] or None


def is_user_locked(user: models.User) -> bool:
    if not user.locked_until:
        return False
    return user.locked_until > _utcnow()


def ensure_not_locked(user: models.User) -> None:
    if is_user_locked(user):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="ログイン試行回数が上限に達しました。しばらく待ってから再試行してください。",
        )


def record_login_history(
    db: Session,
    *,
    user_id: int,
    success: bool,
    method: str,
    request: Optional[Request] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    db.add(
        models_email.LoginHistory(
            user_id=user_id,
            ip_address=ip or _client_ip(request),
            user_agent=user_agent or _client_ua(request),
            method=method,
            success=success,
        )
    )


def _is_new_device(
    db: Session,
    user_id: int,
    *,
    ip: str | None,
    user_agent: str | None,
) -> bool:
    if not ip and not user_agent:
        return False
    recent = (
        db.query(models_email.LoginHistory)
        .filter(
            models_email.LoginHistory.user_id == user_id,
            models_email.LoginHistory.success.is_(True),
        )
        .order_by(models_email.LoginHistory.created_at.desc())
        .limit(10)
        .all()
    )
    if len(recent) < 2:
        return False
    for row in recent[1:]:
        if row.ip_address == ip and (row.user_agent or "") == (user_agent or ""):
            return False
    return True


def record_login_failure(db: Session, user: models.User, request: Optional[Request] = None) -> None:
    was_locked = is_user_locked(user)
    prev_attempts = int(user.failed_login_attempts or 0)
    user.failed_login_attempts = prev_attempts + 1
    just_locked = False
    if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
        user.locked_until = _utcnow() + timedelta(minutes=LOGIN_LOCKOUT_MINUTES)
        just_locked = not was_locked
    ip = _client_ip(request)
    record_login_history(db, user_id=user.id, success=False, method="legacy", request=request)
    notify_login_failed(db, user, ip=ip, repeated=prev_attempts >= 2)
    if just_locked:
        notify_account_locked(db, user, locked_until=user.locked_until)


def record_login_success(
    db: Session,
    user: models.User,
    *,
    method: str,
    request: Optional[Request] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    send_notify: bool = True,
) -> None:
    was_locked = is_user_locked(user)
    ip_val = ip or _client_ip(request)
    ua_val = user_agent or _client_ua(request)
    new_device = _is_new_device(db, user.id, ip=ip_val, user_agent=ua_val)

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = _utcnow()
    user.last_login_ip = ip_val
    record_login_history(
        db,
        user_id=user.id,
        success=True,
        method=method,
        request=request,
        ip=ip_val,
        user_agent=ua_val,
    )
    if was_locked:
        notify_account_unlocked(db, user)
    if send_notify:
        notify_login_success(db, user, ip=ip_val, user_agent=ua_val, new_device=new_device)


def _hash_otp(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def create_login_otp_challenge(db: Session, user: models.User) -> tuple[int, str]:
    code = f"{secrets.randbelow(1_000_000):06d}"
    link_token = secrets.token_urlsafe(32)
    expires_at = _utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES)
    challenge = models_email.UserOtpChallenge(
        user_id=user.id,
        code_hash=_hash_otp(code),
        link_token_hash=_hash_otp(link_token),
        purpose="login_2fa",
        expires_at=expires_at,
    )
    db.add(challenge)
    db.flush()
    base = (settings.FRONTEND_URL or "").rstrip("/")
    verify_url = f"{base}/login/2fa?challenge={challenge.id}&token={link_token}" if base else ""
    notify_2fa_otp_sent(
        db,
        user,
        verify_url=verify_url,
        expires_at=expires_at,
        challenge_id=challenge.id,
    )
    return challenge.id, code


def verify_login_otp(db: Session, *, challenge_id: int, code: str, user_id: int) -> models.User:
    raw = (code or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="認証コードが必要です")

    challenge = (
        db.query(models_email.UserOtpChallenge)
        .filter(
            models_email.UserOtpChallenge.id == challenge_id,
            models_email.UserOtpChallenge.user_id == user_id,
            models_email.UserOtpChallenge.purpose == "login_2fa",
        )
        .first()
    )
    if not challenge or challenge.consumed_at:
        raise HTTPException(status_code=400, detail="認証コードが無効です")
    if challenge.expires_at < _utcnow():
        raise HTTPException(status_code=400, detail="認証コードの有効期限が切れています")
    if challenge.code_hash != _hash_otp(raw):
        raise HTTPException(status_code=400, detail="認証コードが正しくありません")
    challenge.consumed_at = _utcnow()
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
    return user


def list_login_history(db: Session, user_id: int, limit: int = 20) -> list[models_email.LoginHistory]:
    return (
        db.query(models_email.LoginHistory)
        .filter(models_email.LoginHistory.user_id == user_id)
        .order_by(models_email.LoginHistory.created_at.desc())
        .limit(limit)
        .all()
    )
