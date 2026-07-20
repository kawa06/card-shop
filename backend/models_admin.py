"""KRX admin RBAC and audit models (additive; does not replace users.is_admin)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database import Base


class AdminRole(Base):
    __tablename__ = "admin_roles"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    is_system = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    admin_users = relationship("AdminUser", back_populates="role")
    role_permissions = relationship(
        "AdminRolePermission",
        back_populates="role",
        cascade="all, delete-orphan",
    )


class AdminPermission(Base):
    __tablename__ = "admin_permissions"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(128), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    role_permissions = relationship(
        "AdminRolePermission",
        back_populates="permission",
        cascade="all, delete-orphan",
    )


class AdminRolePermission(Base):
    __tablename__ = "admin_role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_admin_role_permissions"),
    )

    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey("admin_roles.id"), nullable=False, index=True)
    permission_id = Column(
        Integer, ForeignKey("admin_permissions.id"), nullable=False, index=True
    )
    created_at = Column(DateTime, default=datetime.utcnow)

    role = relationship("AdminRole", back_populates="role_permissions")
    permission = relationship("AdminPermission", back_populates="role_permissions")


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    role_id = Column(Integer, ForeignKey("admin_roles.id"), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    display_name = Column(String(128), nullable=True)
    failed_login_count = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    last_login_ip = Column(String(64), nullable=True)
    reauth_verified_at = Column(DateTime, nullable=True)
    created_by_admin_id = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deactivated_at = Column(DateTime, nullable=True)
    deactivated_by_admin_id = Column(Integer, ForeignKey("admin_users.id"), nullable=True)

    user = relationship("User", foreign_keys=[user_id])
    role = relationship("AdminRole", back_populates="admin_users")
    created_by = relationship("AdminUser", foreign_keys=[created_by_admin_id], remote_side=[id])
    deactivated_by = relationship(
        "AdminUser", foreign_keys=[deactivated_by_admin_id], remote_side=[id]
    )


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    admin_user_id = Column(Integer, ForeignKey("admin_users.id"), nullable=True, index=True)
    actor_email = Column(String(255), nullable=True, index=True)
    action = Column(String(128), nullable=False, index=True)
    resource_type = Column(String(128), nullable=True, index=True)
    resource_id = Column(String(128), nullable=True, index=True)
    before_data = Column(Text, nullable=True)
    after_data = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    result = Column(String(32), nullable=False, default="success")
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    admin_user = relationship("AdminUser", foreign_keys=[admin_user_id])
