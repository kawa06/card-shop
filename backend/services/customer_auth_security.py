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
from services.email_delivery import send_templated_email

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


def record_login_failure(db: Session, user: models.User, request: Optional[Request] = None) -> None:
    user.failed_login_attempts = int(user.failed_login_attempts or 0) + 1
    if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
        user.locked_until = _utcnow() + timedelta(minutes=LOGIN_LOCKOUT_MINUTES)
    record_login_history(db, user_id=user.id, success=False, method="legacy", request=request)


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
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = _utcnow()
    user.last_login_ip = ip or _client_ip(request)
    record_login_history(
        db,
        user_id=user.id,
        success=True,
        method=method,
        request=request,
        ip=ip,
        user_agent=user_agent,
    )
    if send_notify:
        notify_login(db, user, ip=ip or _client_ip(request), user_agent=user_agent or _client_ua(request))


def notify_login(
    db: Session,
    user: models.User,
    *,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    send_templated_email(
        db,
        template_key="member_login_notify",
        to_email=user.email,
        variables={
            "name": user.name,
            "email": user.email,
            "ip": ip or "—",
            "userAgent": user_agent or "—",
            "date": _utcnow().strftime("%Y/%m/%d %H:%M"),
            "content": f"ログインが検出されました。心当たりがない場合はパスワードを変更してください。",
        },
        reference_type="user",
        reference_id=str(user.id),
        fallback_subject=f"【{settings.SITE_NAME}】ログインのお知らせ",
        fallback_html=(
            "<p>{{name}} 様</p>"
            "<p>アカウントへのログインを検知しました。</p>"
            "<p>日時: {{date}}<br>IP: {{ip}}</p>"
        ),
    )


def _hash_otp(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def create_login_otp_challenge(db: Session, user: models.User) -> tuple[int, str]:
    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge = models_email.UserOtpChallenge(
        user_id=user.id,
        code_hash=_hash_otp(code),
        purpose="login_2fa",
        expires_at=_utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES),
    )
    db.add(challenge)
    db.flush()
    send_templated_email(
        db,
        template_key="member_2fa_otp",
        to_email=user.email,
        variables={
            "name": user.name,
            "email": user.email,
            "code": code,
            "content": f"認証コード: {code}（{OTP_EXPIRE_MINUTES}分間有効）",
        },
        reference_type="otp_challenge",
        reference_id=str(challenge.id),
        fallback_subject=f"【{settings.SITE_NAME}】認証コード",
        fallback_html="<p>{{name}} 様</p><p>認証コード: <strong>{{code}}</strong></p>",
    )
    return challenge.id, code


def verify_login_otp(db: Session, *, challenge_id: int, code: str, user_id: int) -> models.User:
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
    if challenge.code_hash != _hash_otp(code.strip()):
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
