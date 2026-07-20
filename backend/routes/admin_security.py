"""Admin security management APIs (RBAC, audit logs, session)."""

from __future__ import annotations

import math
import secrets
from datetime import datetime
from typing import Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

import models
import models_admin
import schemas_admin
from admin_emails import normalize_email
from auth import get_current_user
from database import get_db
from services.admin_audit import write_audit_log
from services.admin_auth import (
    AdminAccessError,
    AdminContext,
    can_assign_role,
    can_modify_admin,
    get_admin_user_for_user,
    mark_reauth_verified,
    record_admin_login_failure,
    record_admin_login_success,
    record_admin_logout,
    require_permission,
    resolve_admin_context,
)
from services.admin_rbac import OWNER_ROLE_CODE, ROLE_PERMISSION_CODES
from services.db_persist import PersistDep, safe_commit

router = APIRouter(
    prefix="/api/admin/security",
    tags=["admin-security"],
    dependencies=[PersistDep],
)


def _admin_context_dep(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> AdminContext:
    try:
        return resolve_admin_context(db, user, request=request, log_failure=False)
    except AdminAccessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def _require_perm(permission: str):
    def _dep(ctx: AdminContext = Depends(_admin_context_dep)) -> AdminContext:
        try:
            require_permission(ctx, permission)
        except AdminAccessError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
        return ctx

    return _dep


def _serialize_admin_user(admin_user: models_admin.AdminUser) -> schemas_admin.AdminUserSummary:
    user = admin_user.user
    return schemas_admin.AdminUserSummary(
        id=admin_user.id,
        user_id=admin_user.user_id,
        email=user.email if user else "",
        name=user.name if user else "",
        display_name=admin_user.display_name,
        role=admin_user.role,
        is_active=admin_user.is_active,
        failed_login_count=admin_user.failed_login_count or 0,
        locked_until=admin_user.locked_until,
        last_login_at=admin_user.last_login_at,
        created_at=admin_user.created_at,
        deactivated_at=admin_user.deactivated_at,
    )


@router.get("/me", response_model=schemas_admin.AdminSessionOut)
def admin_session(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        ctx = resolve_admin_context(db, user, request=request, log_failure=True)
    except AdminAccessError:
        record_admin_login_failure(
            db,
            user=user,
            reason="not_admin",
            request=request,
        )
        return schemas_admin.AdminSessionOut(is_admin=False, email=user.email)

    from services.admin_auth import is_reauth_valid

    return schemas_admin.AdminSessionOut(
        is_admin=True,
        admin_user_id=ctx.admin_user.id,
        role_code=ctx.admin_user.role.code if ctx.admin_user.role else None,
        permissions=sorted(ctx.permissions),
        email=user.email,
        reauth_valid=is_reauth_valid(ctx.admin_user),
    )


@router.post("/session/login", response_model=schemas_admin.AdminSessionOut)
def admin_session_login(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        ctx = resolve_admin_context(db, user, request=request, log_failure=True)
    except AdminAccessError as exc:
        record_admin_login_failure(db, user=user, reason="access_denied", request=request)
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    record_admin_login_success(db, ctx, request=request)
    from services.admin_auth import is_reauth_valid

    return schemas_admin.AdminSessionOut(
        is_admin=True,
        admin_user_id=ctx.admin_user.id,
        role_code=ctx.admin_user.role.code if ctx.admin_user.role else None,
        permissions=sorted(ctx.permissions),
        email=user.email,
        reauth_valid=is_reauth_valid(ctx.admin_user),
    )


@router.post("/session/login-failed", status_code=status.HTTP_204_NO_CONTENT)
def admin_session_login_failed(
    payload: schemas_admin.AdminLoginEvent,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    record_admin_login_failure(
        db,
        user=user,
        reason=payload.reason or "client_reported_failure",
        request=request,
    )


@router.post("/session/logout", status_code=status.HTTP_204_NO_CONTENT)
def admin_session_logout(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    admin_user = get_admin_user_for_user(db, user, require_active=False)
    if admin_user is None:
        return None
    ctx = AdminContext(
        user=user,
        admin_user=admin_user,
        permissions=set(),
    )
    record_admin_logout(db, ctx, request=request)
    return None


@router.post("/reauth", response_model=schemas_admin.AdminSessionOut)
def admin_reauth(
    payload: schemas_admin.AdminReauthRequest,
    request: Request,
    ctx: AdminContext = Depends(_require_perm("admin.reauth")),
    db: Session = Depends(get_db),
):
    if not payload.confirmed:
        raise HTTPException(status_code=400, detail="再認証が確認されていません")
    mark_reauth_verified(db, ctx.admin_user)
    write_audit_log(
        db,
        action="admin.reauth.success",
        admin_user=ctx.admin_user,
        actor_email=normalize_email(ctx.user.email),
        resource_type="admin_user",
        resource_id=ctx.admin_user.id,
        request=request,
    )
    safe_commit(db, action="再認証")
    from services.admin_auth import is_reauth_valid

    return schemas_admin.AdminSessionOut(
        is_admin=True,
        admin_user_id=ctx.admin_user.id,
        role_code=ctx.admin_user.role.code if ctx.admin_user.role else None,
        permissions=sorted(ctx.permissions),
        email=ctx.user.email,
        reauth_valid=is_reauth_valid(ctx.admin_user),
    )


@router.get("/admins", response_model=schemas_admin.PaginatedAdminUsers)
def list_admins(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    q: Optional[str] = None,
    ctx: AdminContext = Depends(_require_perm("admin.users.read")),
    db: Session = Depends(get_db),
):
    query = (
        db.query(models_admin.AdminUser)
        .options(
            joinedload(models_admin.AdminUser.user),
            joinedload(models_admin.AdminUser.role),
        )
        .join(models.User)
    )
    if q:
        like = f"%{q.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(models.User.email).like(like),
                func.lower(models.User.name).like(like),
                func.lower(models_admin.AdminUser.display_name).like(like),
            )
        )
    total = query.count()
    items = (
        query.order_by(models_admin.AdminUser.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {
        "items": [_serialize_admin_user(item) for item in items],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": math.ceil(total / per_page) if total else 1,
    }


@router.post("/admins", response_model=schemas_admin.AdminUserDetail, status_code=201)
def create_admin(
    payload: schemas_admin.AdminUserCreate,
    request: Request,
    ctx: AdminContext = Depends(_require_perm("admin.users.write")),
    db: Session = Depends(get_db),
):
    if not can_assign_role(ctx, payload.role_code):
        raise HTTPException(status_code=403, detail="この役割を割り当てる権限がありません")

    role = (
        db.query(models_admin.AdminRole)
        .filter(models_admin.AdminRole.code == payload.role_code)
        .first()
    )
    if role is None:
        raise HTTPException(status_code=400, detail="指定された役割が見つかりません")

    email = normalize_email(payload.email)
    user = db.query(models.User).filter(func.lower(models.User.email) == email).first()
    if user is None:
        user = models.User(
            email=email,
            name=payload.name.strip(),
            password_hash=bcrypt.hashpw(
                secrets.token_urlsafe(32).encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8"),
            is_admin=True,
            is_verified=True,
        )
        db.add(user)
        db.flush()
    else:
        user.is_admin = True

    existing = (
        db.query(models_admin.AdminUser)
        .filter(models_admin.AdminUser.user_id == user.id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="このユーザーは既に管理者です")

    admin_user = models_admin.AdminUser(
        user_id=user.id,
        role_id=role.id,
        is_active=True,
        display_name=payload.display_name or payload.name,
        created_by_admin_id=ctx.admin_user.id,
    )
    db.add(admin_user)
    db.flush()

    write_audit_log(
        db,
        action="admin.user.created",
        admin_user=ctx.admin_user,
        actor_email=normalize_email(ctx.user.email),
        resource_type="admin_user",
        resource_id=admin_user.id,
        after_data={
            "email": email,
            "role_code": payload.role_code,
            "display_name": admin_user.display_name,
        },
        request=request,
    )
    safe_commit(db, action="管理者追加")
    db.refresh(admin_user)
    admin_user = (
        db.query(models_admin.AdminUser)
        .options(
            joinedload(models_admin.AdminUser.user),
            joinedload(models_admin.AdminUser.role),
        )
        .filter(models_admin.AdminUser.id == admin_user.id)
        .first()
    )
    detail = _serialize_admin_user(admin_user)
    return schemas_admin.AdminUserDetail(
        **detail.model_dump(),
        permissions=sorted(ROLE_PERMISSION_CODES.get(role.code, set())),
        last_login_ip=admin_user.last_login_ip,
    )


@router.get("/admins/{admin_id}", response_model=schemas_admin.AdminUserDetail)
def get_admin_detail(
    admin_id: int,
    ctx: AdminContext = Depends(_require_perm("admin.users.read")),
    db: Session = Depends(get_db),
):
    admin_user = (
        db.query(models_admin.AdminUser)
        .options(
            joinedload(models_admin.AdminUser.user),
            joinedload(models_admin.AdminUser.role),
        )
        .filter(models_admin.AdminUser.id == admin_id)
        .first()
    )
    if admin_user is None:
        raise HTTPException(status_code=404, detail="管理者が見つかりません")

    if admin_user.role and admin_user.role.code == OWNER_ROLE_CODE:
        if ctx.admin_user.role.code != OWNER_ROLE_CODE:
            raise HTTPException(status_code=403, detail="オーナー情報を閲覧する権限がありません")

    detail = _serialize_admin_user(admin_user)
    perms = ROLE_PERMISSION_CODES.get(admin_user.role.code if admin_user.role else "", set())
    return schemas_admin.AdminUserDetail(
        **detail.model_dump(),
        permissions=sorted(perms),
        last_login_ip=admin_user.last_login_ip,
    )


@router.patch("/admins/{admin_id}", response_model=schemas_admin.AdminUserDetail)
def update_admin(
    admin_id: int,
    payload: schemas_admin.AdminUserUpdate,
    request: Request,
    ctx: AdminContext = Depends(_require_perm("admin.users.write")),
    db: Session = Depends(get_db),
):
    admin_user = (
        db.query(models_admin.AdminUser)
        .options(
            joinedload(models_admin.AdminUser.user),
            joinedload(models_admin.AdminUser.role),
        )
        .filter(models_admin.AdminUser.id == admin_id)
        .first()
    )
    if admin_user is None:
        raise HTTPException(status_code=404, detail="管理者が見つかりません")

    if not can_modify_admin(ctx, admin_user):
        raise HTTPException(status_code=403, detail="この管理者を変更する権限がありません")

    before = {
        "role_code": admin_user.role.code if admin_user.role else None,
        "is_active": admin_user.is_active,
        "display_name": admin_user.display_name,
    }

    if payload.role_code is not None:
        if not can_assign_role(ctx, payload.role_code):
            raise HTTPException(status_code=403, detail="この役割を割り当てる権限がありません")
        role = (
            db.query(models_admin.AdminRole)
            .filter(models_admin.AdminRole.code == payload.role_code)
            .first()
        )
        if role is None:
            raise HTTPException(status_code=400, detail="指定された役割が見つかりません")
        admin_user.role_id = role.id

    if payload.display_name is not None:
        admin_user.display_name = payload.display_name

    if payload.is_active is not None:
        admin_user.is_active = payload.is_active
        if not payload.is_active:
            admin_user.deactivated_at = datetime.utcnow()
            admin_user.deactivated_by_admin_id = ctx.admin_user.id
            if admin_user.user:
                admin_user.user.is_admin = False
            action = "admin.user.deactivated"
        else:
            admin_user.deactivated_at = None
            admin_user.deactivated_by_admin_id = None
            if admin_user.user:
                admin_user.user.is_admin = True
            action = "admin.user.reactivated"
    else:
        action = "admin.user.updated"

    db.flush()
    db.refresh(admin_user)
    admin_user = (
        db.query(models_admin.AdminUser)
        .options(
            joinedload(models_admin.AdminUser.user),
            joinedload(models_admin.AdminUser.role),
        )
        .filter(models_admin.AdminUser.id == admin_id)
        .first()
    )

    after = {
        "role_code": admin_user.role.code if admin_user.role else None,
        "is_active": admin_user.is_active,
        "display_name": admin_user.display_name,
    }

    if before.get("role_code") != after.get("role_code"):
        write_audit_log(
            db,
            action="admin.permission.changed",
            admin_user=ctx.admin_user,
            actor_email=normalize_email(ctx.user.email),
            resource_type="admin_user",
            resource_id=admin_user.id,
            before_data=before,
            after_data=after,
            reason=payload.reason,
            request=request,
        )

    write_audit_log(
        db,
        action=action,
        admin_user=ctx.admin_user,
        actor_email=normalize_email(ctx.user.email),
        resource_type="admin_user",
        resource_id=admin_user.id,
        before_data=before,
        after_data=after,
        reason=payload.reason,
        request=request,
    )
    safe_commit(db, action="管理者更新")
    db.refresh(admin_user)

    detail = _serialize_admin_user(admin_user)
    perms = ROLE_PERMISSION_CODES.get(admin_user.role.code if admin_user.role else "", set())
    return schemas_admin.AdminUserDetail(
        **detail.model_dump(),
        permissions=sorted(perms),
        last_login_ip=admin_user.last_login_ip,
    )


@router.get("/roles", response_model=list[schemas_admin.AdminRoleOut])
def list_roles(
    ctx: AdminContext = Depends(_require_perm("admin.roles.read")),
    db: Session = Depends(get_db),
):
    _ = ctx
    return db.query(models_admin.AdminRole).order_by(models_admin.AdminRole.id).all()


@router.get("/permissions/matrix", response_model=schemas_admin.AdminPermissionsMatrixOut)
def permissions_matrix(
    ctx: AdminContext = Depends(_require_perm("admin.roles.read")),
    db: Session = Depends(get_db),
):
    _ = ctx
    roles = db.query(models_admin.AdminRole).order_by(models_admin.AdminRole.id).all()
    permissions = (
        db.query(models_admin.AdminPermission)
        .order_by(models_admin.AdminPermission.category, models_admin.AdminPermission.code)
        .all()
    )
    return schemas_admin.AdminPermissionsMatrixOut(
        roles=roles,
        permissions=permissions,
        role_permissions={
            role.code: sorted(ROLE_PERMISSION_CODES.get(role.code, set())) for role in roles
        },
    )


@router.get("/audit-logs", response_model=schemas_admin.PaginatedAuditLogs)
def list_audit_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    action: Optional[str] = None,
    ctx: AdminContext = Depends(_require_perm("admin.audit.read")),
    db: Session = Depends(get_db),
):
    query = db.query(models_admin.AdminAuditLog)
    if action:
        query = query.filter(models_admin.AdminAuditLog.action.like(f"{action}%"))
    total = query.count()
    items = (
        query.order_by(models_admin.AdminAuditLog.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": math.ceil(total / per_page) if total else 1,
    }


@router.get("/audit-logs/{log_id}", response_model=schemas_admin.AdminAuditLogOut)
def get_audit_log(
    log_id: int,
    ctx: AdminContext = Depends(_require_perm("admin.audit.read")),
    db: Session = Depends(get_db),
):
    _ = ctx
    entry = db.query(models_admin.AdminAuditLog).filter(models_admin.AdminAuditLog.id == log_id).first()
    if entry is None:
        raise HTTPException(status_code=404, detail="監査ログが見つかりません")
    return entry
