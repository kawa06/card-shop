"""Admin authentication helpers — server-side RBAC, lockout, re-auth."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session, joinedload

import models
import models_admin
from admin_emails import is_admin_email, normalize_email
from services.admin_audit import write_audit_log
from services.admin_rbac import (
    LOGIN_LOCKOUT_MINUTES,
    MAX_FAILED_LOGIN_ATTEMPTS,
    OWNER_ROLE_CODE,
    PROTECTED_ASSIGNMENT_ROLES,
    REAUTH_VALID_MINUTES,
    permission_codes_for_role,
)


@dataclass
class AdminContext:
    user: models.User
    admin_user: models_admin.AdminUser
    permissions: set[str]


class AdminAccessError(Exception):
    def __init__(self, detail: str, status_code: int = status.HTTP_403_FORBIDDEN):
        self.detail = detail
        self.status_code = status_code


def _utcnow() -> datetime:
    return datetime.utcnow()


def is_admin_locked(admin_user: models_admin.AdminUser) -> bool:
    if not admin_user.locked_until:
        return False
    return admin_user.locked_until > _utcnow()


def load_permissions(admin_user: models_admin.AdminUser) -> set[str]:
    role = admin_user.role
    if role is None:
        return set()
    return permission_codes_for_role(role.code)


def get_admin_user_for_user(
    db: Session, user: models.User, *, require_active: bool = True
) -> Optional[models_admin.AdminUser]:
    admin_user = (
        db.query(models_admin.AdminUser)
        .options(joinedload(models_admin.AdminUser.role))
        .filter(models_admin.AdminUser.user_id == user.id)
        .first()
    )
    if admin_user is None:
        return None
    if require_active and not admin_user.is_active:
        return None
    if require_active and is_admin_locked(admin_user):
        return None
    return admin_user


def resolve_admin_context(
    db: Session,
    user: models.User,
    *,
    request: Optional[Request] = None,
    log_failure: bool = True,
) -> AdminContext:
    admin_user = get_admin_user_for_user(db, user, require_active=False)
    email = normalize_email(user.email)

    if admin_user is None:
        if log_failure:
            write_audit_log(
                db,
                action="admin.login.failed",
                result="failure",
                actor_email=email,
                reason="admin_user_not_found",
                request=request,
            )
            db.commit()
        raise AdminAccessError("管理者権限が必要です", status.HTTP_403_FORBIDDEN)

    if not admin_user.is_active:
        if log_failure:
            write_audit_log(
                db,
                action="admin.login.failed",
                result="failure",
                admin_user=admin_user,
                actor_email=email,
                reason="admin_deactivated",
                request=request,
            )
            db.commit()
        raise AdminAccessError("管理者アカウントは無効化されています", status.HTTP_403_FORBIDDEN)

    if is_admin_locked(admin_user):
        if log_failure:
            write_audit_log(
                db,
                action="admin.login.failed",
                result="failure",
                admin_user=admin_user,
                actor_email=email,
                reason="admin_locked",
                request=request,
            )
            db.commit()
        raise AdminAccessError(
            "ログイン試行回数が上限に達しました。しばらくしてから再度お試しください。",
            status.HTTP_403_FORBIDDEN,
        )

    permissions = load_permissions(admin_user)
    return AdminContext(user=user, admin_user=admin_user, permissions=permissions)


def record_admin_login_success(
    db: Session,
    ctx: AdminContext,
    *,
    request: Optional[Request] = None,
) -> None:
    ctx.admin_user.failed_login_count = 0
    ctx.admin_user.locked_until = None
    ctx.admin_user.last_login_at = _utcnow()
    ip, _ = None, None
    if request is not None:
        from services.admin_audit import extract_client_meta

        ip, _ = extract_client_meta(request)
        ctx.admin_user.last_login_ip = ip
    write_audit_log(
        db,
        action="admin.login.success",
        admin_user=ctx.admin_user,
        actor_email=normalize_email(ctx.user.email),
        resource_type="admin_user",
        resource_id=ctx.admin_user.id,
        request=request,
    )
    db.commit()


def record_admin_login_failure(
    db: Session,
    *,
    user: Optional[models.User] = None,
    email: Optional[str] = None,
    reason: str = "invalid_credentials",
    request: Optional[Request] = None,
) -> None:
    admin_user = None
    if user is not None:
        admin_user = get_admin_user_for_user(db, user, require_active=False)

    if admin_user is not None and admin_user.is_active:
        admin_user.failed_login_count = (admin_user.failed_login_count or 0) + 1
        if admin_user.failed_login_count >= MAX_FAILED_LOGIN_ATTEMPTS:
            admin_user.locked_until = _utcnow() + timedelta(minutes=LOGIN_LOCKOUT_MINUTES)

    write_audit_log(
        db,
        action="admin.login.failed",
        result="failure",
        admin_user=admin_user,
        actor_email=normalize_email(email or (user.email if user else "")) or None,
        reason=reason,
        request=request,
    )
    db.commit()


def record_admin_logout(
    db: Session,
    ctx: AdminContext,
    *,
    request: Optional[Request] = None,
) -> None:
    write_audit_log(
        db,
        action="admin.logout",
        admin_user=ctx.admin_user,
        actor_email=normalize_email(ctx.user.email),
        resource_type="admin_user",
        resource_id=ctx.admin_user.id,
        request=request,
    )
    db.commit()


def require_permission(ctx: AdminContext, permission: str) -> None:
    if permission not in ctx.permissions:
        raise AdminAccessError(
            f"権限が不足しています: {permission}",
            status.HTTP_403_FORBIDDEN,
        )


def is_reauth_valid(admin_user: models_admin.AdminUser) -> bool:
    if not admin_user.reauth_verified_at:
        return False
    return admin_user.reauth_verified_at >= _utcnow() - timedelta(minutes=REAUTH_VALID_MINUTES)


def mark_reauth_verified(db: Session, admin_user: models_admin.AdminUser) -> None:
    admin_user.reauth_verified_at = _utcnow()
    db.flush()


def can_assign_role(actor: AdminContext, target_role_code: str) -> bool:
    if target_role_code in PROTECTED_ASSIGNMENT_ROLES:
        return actor.admin_user.role.code == OWNER_ROLE_CODE
    if target_role_code == OWNER_ROLE_CODE:
        return actor.admin_user.role.code == OWNER_ROLE_CODE
    return "admin.users.write" in actor.permissions


def can_modify_admin(actor: AdminContext, target: models_admin.AdminUser) -> bool:
    if target.role and target.role.code == OWNER_ROLE_CODE:
        return actor.admin_user.role.code == OWNER_ROLE_CODE
    if actor.admin_user.id == target.id:
        # Admins cannot change their own role or activate/deactivate themselves.
        return False
    return "admin.users.write" in actor.permissions


def bootstrap_admin_user(
    db: Session,
    user: models.User,
    *,
    role_code: str = "admin",
    created_by: Optional[models_admin.AdminUser] = None,
) -> models_admin.AdminUser:
    role = (
        db.query(models_admin.AdminRole)
        .filter(models_admin.AdminRole.code == role_code)
        .first()
    )
    if role is None:
        raise ValueError(f"Unknown admin role: {role_code}")

    existing = (
        db.query(models_admin.AdminUser)
        .filter(models_admin.AdminUser.user_id == user.id)
        .first()
    )
    if existing:
        if not existing.is_active:
            existing.is_active = True
            existing.role_id = role.id
        return existing

    admin_user = models_admin.AdminUser(
        user_id=user.id,
        role_id=role.id,
        is_active=True,
        display_name=user.name,
        created_by_admin_id=created_by.id if created_by else None,
    )
    db.add(admin_user)
    db.flush()
    return admin_user


def ensure_legacy_admin_migrated(db: Session) -> None:
    """Promote configured admin emails and existing is_admin users into admin_users."""
    owner_role = (
        db.query(models_admin.AdminRole)
        .filter(models_admin.AdminRole.code == OWNER_ROLE_CODE)
        .first()
    )
    admin_role = (
        db.query(models_admin.AdminRole)
        .filter(models_admin.AdminRole.code == "admin")
        .first()
    )
    if owner_role is None or admin_role is None:
        return

    users = db.query(models.User).all()
    for user in users:
        email = normalize_email(user.email)
        should_be_admin = bool(user.is_admin)
        if not should_be_admin:
            continue
        role = owner_role if is_admin_email(email) else admin_role
        existing = (
            db.query(models_admin.AdminUser)
            .filter(models_admin.AdminUser.user_id == user.id)
            .first()
        )
        if existing:
            if not user.is_admin:
                user.is_admin = True
            continue
        bootstrap_admin_user(db, user, role_code=role.code)
        user.is_admin = True
    db.commit()
