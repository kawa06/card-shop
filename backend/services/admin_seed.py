"""Seed admin roles, permissions, and bootstrap owner from legacy admin emails."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

import models
import models_admin
from admin_emails import is_admin_email, normalize_email
from services.admin_auth import bootstrap_admin_user
from services.admin_rbac import (
    ADMIN_PERMISSION_DEFINITIONS,
    ADMIN_ROLE_DEFINITIONS,
    OWNER_ROLE_CODE,
    ROLE_PERMISSION_CODES,
)

logger = logging.getLogger(__name__)


def seed_admin_rbac(db: Session) -> None:
    role_by_code: dict[str, models_admin.AdminRole] = {}
    for code, name in ADMIN_ROLE_DEFINITIONS.items():
        role = (
            db.query(models_admin.AdminRole)
            .filter(models_admin.AdminRole.code == code)
            .first()
        )
        if role is None:
            role = models_admin.AdminRole(code=code, name=name, is_system=True)
            db.add(role)
            db.flush()
        role_by_code[code] = role

    perm_by_code: dict[str, models_admin.AdminPermission] = {}
    for code, name, category in ADMIN_PERMISSION_DEFINITIONS:
        perm = (
            db.query(models_admin.AdminPermission)
            .filter(models_admin.AdminPermission.code == code)
            .first()
        )
        if perm is None:
            perm = models_admin.AdminPermission(
                code=code, name=name, category=category
            )
            db.add(perm)
            db.flush()
        perm_by_code[code] = perm

    for role_code, perm_codes in ROLE_PERMISSION_CODES.items():
        role = role_by_code.get(role_code)
        if role is None:
            continue
        for perm_code in perm_codes:
            perm = perm_by_code.get(perm_code)
            if perm is None:
                continue
            exists = (
                db.query(models_admin.AdminRolePermission)
                .filter(
                    models_admin.AdminRolePermission.role_id == role.id,
                    models_admin.AdminRolePermission.permission_id == perm.id,
                )
                .first()
            )
            if exists is None:
                db.add(
                    models_admin.AdminRolePermission(
                        role_id=role.id, permission_id=perm.id
                    )
                )

    db.flush()
    _bootstrap_owner_admins(db, role_by_code[OWNER_ROLE_CODE])
    _migrate_existing_admins(db, role_by_code)
    db.commit()
    logger.info("Admin RBAC seed completed")


def _bootstrap_owner_admins(db: Session, owner_role: models_admin.AdminRole) -> None:
    for user in db.query(models.User).all():
        if not user.is_admin or not is_admin_email(user.email):
            continue
        existing = (
            db.query(models_admin.AdminUser)
            .filter(models_admin.AdminUser.user_id == user.id)
            .first()
        )
        if existing:
            if existing.role_id != owner_role.id:
                existing.role_id = owner_role.id
            if not existing.is_active:
                existing.is_active = True
            if not user.is_admin:
                user.is_admin = True
            continue
        bootstrap_admin_user(db, user, role_code=OWNER_ROLE_CODE)
        user.is_admin = True


def _migrate_existing_admins(
    db: Session, role_by_code: dict[str, models_admin.AdminRole]
) -> None:
    admin_role = role_by_code.get("admin")
    if admin_role is None:
        return
    for user in db.query(models.User).filter(models.User.is_admin.is_(True)).all():
        if is_admin_email(user.email):
            continue
        existing = (
            db.query(models_admin.AdminUser)
            .filter(models_admin.AdminUser.user_id == user.id)
            .first()
        )
        if existing:
            continue
        bootstrap_admin_user(db, user, role_code="admin")
