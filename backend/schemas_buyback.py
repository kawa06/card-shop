"""Pydantic schemas for buyback API (Phase 3 skeleton)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class BuybackHealthOut(BaseModel):
    status: str
    phase: str = "8"
    products_source: str = "postgresql+firestore_stub"


class BuybackUserOut(BaseModel):
    id: int
    email: str
    name: str
    clerk_user_id: Optional[str] = None
    is_admin: bool
    is_verified: bool

    class Config:
        from_attributes = True


class BuybackSyncResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: BuybackUserOut
    link_result: str
    auth_provider: str = "clerk"


class BuybackProductPriceOut(BaseModel):
    condition_code: str
    price_normal: int
    price_high: Optional[int] = None
    purchase_limit: Optional[int] = None


class BuybackProductOut(BaseModel):
    id: int
    name: str
    category: str
    image_url: Optional[str] = None
    notes: Optional[str] = None
    prices: List[BuybackProductPriceOut] = []

    class Config:
        from_attributes = True


class BuybackCartItemCreate(BaseModel):
    firestore_item_id: str
    product_name: str
    category: str
    condition_code: str
    unit_price: int
    quantity: int = 1
    image_url: Optional[str] = None


class BuybackCartItemUpdate(BaseModel):
    quantity: int


class BuybackCartItemOut(BaseModel):
    id: int
    product_id: int
    firestore_item_id: Optional[str] = None
    condition_code: str
    quantity: int
    unit_price_snapshot: int
    product_name: Optional[str] = None
    category: Optional[str] = None

    class Config:
        from_attributes = True


class BuybackCartOut(BaseModel):
    items: List[BuybackCartItemOut] = []
    item_count: int = 0
    estimated_total: int = 0


class BuybackRequestCreate(BaseModel):
    customer_note: Optional[str] = None
    shipping_method: Optional[str] = None


class BuybackRequestItemOut(BaseModel):
    id: int
    product_id: Optional[int] = None
    product_name_snapshot: str
    condition_code: str
    quantity: int
    listed_unit_price: int
    line_status: Optional[str] = None

    class Config:
        from_attributes = True


class BuybackRequestSummaryOut(BaseModel):
    id: int
    request_number: Optional[str] = None
    status: str
    status_label: str
    estimated_total: Optional[int] = None
    item_count: int = 0
    submitted_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class BuybackRequestDetailOut(BaseModel):
    id: int
    request_number: Optional[str] = None
    status: str
    status_label: str
    shipping_method: Optional[str] = None
    tracking_number: Optional[str] = None
    customer_note: Optional[str] = None
    estimated_total: Optional[int] = None
    assessed_total: Optional[int] = None
    payout_total: Optional[int] = None
    submitted_at: Optional[datetime] = None
    created_at: datetime
    items: List[BuybackRequestItemOut] = []

    class Config:
        from_attributes = True


class IdentityVerificationOut(BaseModel):
    status: str
    status_label: str
    document_type: Optional[str] = None
    has_front: bool = False
    has_back: bool = False
    rejection_reason: Optional[str] = None
    submitted_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class IdentitySubmitIn(BaseModel):
    document_type: str


class GuardianConsentOut(BaseModel):
    status: str
    status_label: str
    guardian_name: Optional[str] = None
    guardian_email: Optional[str] = None
    signed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class GuardianConsentRequestIn(BaseModel):
    guardian_name: str
    guardian_email: str


class GuardianConsentSignIn(BaseModel):
    token: str


class GuardianConsentPreviewOut(BaseModel):
    guardian_name: Optional[str] = None
    status: str
    status_label: str
    expires_at: Optional[datetime] = None


class PayoutAccountCreate(BaseModel):
    bank_name: str
    branch_name: Optional[str] = None
    account_type: str
    account_number: str
    account_holder: str
    set_default: bool = False


class PayoutAccountOut(BaseModel):
    id: int
    bank_name: str
    branch_name: Optional[str] = None
    account_type: str
    account_holder: str
    account_number_masked: str
    is_default: bool
    created_at: datetime
    updated_at: datetime


class ComplianceStatusOut(BaseModel):
    identity_status: str
    identity_status_label: str
    identity_ready: bool
    has_identity_documents: bool
    requires_guardian_consent: bool
    guardian_status: Optional[str] = None
    guardian_status_label: Optional[str] = None
    guardian_ready: bool
    payout_account_count: int
    payout_account_ready: bool
    ready_for_payout: bool


class AdminBuybackStatsOut(BaseModel):
    pending_kyc_count: int = 0
    submitted_request_count: int = 0
    in_progress_request_count: int = 0
    payout_pending_count: int = 0


class AdminIdentityListOut(BaseModel):
    id: int
    user_id: int
    user_email: str
    user_name: str
    status: str
    status_label: str
    document_type: Optional[str] = None
    document_type_label: Optional[str] = None
    has_front: bool = False
    has_back: bool = False
    submitted_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AdminIdentityDetailOut(AdminIdentityListOut):
    rejection_reason: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    reviewer_name: Optional[str] = None


class AdminIdentityRejectIn(BaseModel):
    rejection_reason: str


class AdminBuybackRequestListOut(BaseModel):
    id: int
    request_number: Optional[str] = None
    status: str
    status_label: str
    user_id: int
    user_email: str
    user_name: str
    item_count: int = 0
    estimated_total: Optional[int] = None
    payout_total: Optional[int] = None
    submitted_at: Optional[datetime] = None
    created_at: datetime


class AdminPayoutAccountOut(BaseModel):
    id: int
    bank_name: str
    branch_name: Optional[str] = None
    account_type: str
    account_type_label: str
    account_holder: str
    account_number: str
    account_number_masked: str
    is_default: bool
    created_at: datetime
    updated_at: datetime


class AdminBuybackStatusHistoryOut(BaseModel):
    id: int
    from_status: Optional[str] = None
    from_status_label: Optional[str] = None
    to_status: str
    to_status_label: str
    note: Optional[str] = None
    created_at: datetime


class AdminBuybackRequestDetailOut(BaseModel):
    id: int
    request_number: Optional[str] = None
    status: str
    status_label: str
    user_id: int
    user_email: str
    user_name: str
    shipping_method: Optional[str] = None
    tracking_number: Optional[str] = None
    customer_note: Optional[str] = None
    admin_note: Optional[str] = None
    estimated_total: Optional[int] = None
    assessed_total: Optional[int] = None
    payout_total: Optional[int] = None
    submitted_at: Optional[datetime] = None
    created_at: datetime
    items: List[BuybackRequestItemOut] = []
    status_history: List[AdminBuybackStatusHistoryOut] = []
    allowed_next_statuses: List[str] = []
    payout_account: Optional[AdminPayoutAccountOut] = None
    ready_for_payout: bool = False
    payout_email_sent: bool = False
    paid_at: Optional[datetime] = None


class AdminCompletePayoutIn(BaseModel):
    payout_total: Optional[int] = None
    admin_note: Optional[str] = None
    send_email: bool = True
    force_email: bool = False


class AdminBuybackRequestUpdateIn(BaseModel):
    status: str
    admin_note: Optional[str] = None
    tracking_number: Optional[str] = None
    assessed_total: Optional[int] = None
    payout_total: Optional[int] = None
