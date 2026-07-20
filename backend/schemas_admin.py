"""Pydantic schemas for admin security APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class AdminRoleOut(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None
    is_system: bool

    model_config = {"from_attributes": True}


class AdminPermissionOut(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None

    model_config = {"from_attributes": True}


class AdminUserSummary(BaseModel):
    id: int
    user_id: int
    email: str
    name: str
    display_name: Optional[str] = None
    role: AdminRoleOut
    is_active: bool
    failed_login_count: int
    locked_until: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    created_at: datetime
    deactivated_at: Optional[datetime] = None


class AdminUserDetail(AdminUserSummary):
    permissions: list[str] = Field(default_factory=list)
    last_login_ip: Optional[str] = None


class AdminUserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    role_code: str = Field(min_length=1, max_length=64)
    display_name: Optional[str] = Field(default=None, max_length=128)


class AdminUserUpdate(BaseModel):
    role_code: Optional[str] = None
    display_name: Optional[str] = Field(default=None, max_length=128)
    is_active: Optional[bool] = None
    reason: Optional[str] = None


class AdminRolePermissionsOut(BaseModel):
    role: AdminRoleOut
    permissions: list[AdminPermissionOut]


class AdminPermissionsMatrixOut(BaseModel):
    roles: list[AdminRoleOut]
    permissions: list[AdminPermissionOut]
    role_permissions: dict[str, list[str]]


class AdminAuditLogOut(BaseModel):
    id: int
    admin_user_id: Optional[int] = None
    actor_email: Optional[str] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    before_data: Optional[str] = None
    after_data: Optional[str] = None
    reason: Optional[str] = None
    result: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedAdminUsers(BaseModel):
    items: list[AdminUserSummary]
    total: int
    page: int
    per_page: int
    pages: int


class PaginatedAuditLogs(BaseModel):
    items: list[AdminAuditLogOut]
    total: int
    page: int
    per_page: int
    pages: int


class AdminSessionOut(BaseModel):
    is_admin: bool
    admin_user_id: Optional[int] = None
    role_code: Optional[str] = None
    permissions: list[str] = Field(default_factory=list)
    email: Optional[str] = None
    reauth_valid: bool = False


class AdminReauthRequest(BaseModel):
    confirmed: bool = True


class AdminLoginEvent(BaseModel):
    success: bool
    reason: Optional[str] = None
