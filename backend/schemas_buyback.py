"""Pydantic schemas for buyback API (Phase 3 skeleton)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional, List

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)


class BuybackHealthOut(BaseModel):
    status: str
    phase: str = "10"
    products_source: str = "postgresql"
    cutover_complete: bool = False


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
    firestore_item_id: Optional[str] = None
    name: str
    category: str
    image_url: Optional[str] = None
    notes: Optional[str] = None
    prices: List[BuybackProductPriceOut] = []

    class Config:
        from_attributes = True


class AdminBuybackCatalogPriceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    condition_code: StrictStr = Field(default="default", min_length=1, max_length=32)
    price_normal: StrictInt = Field(ge=0)
    price_high: Optional[StrictInt] = Field(default=None, ge=0)
    purchase_limit: Optional[StrictInt] = Field(default=None, ge=0)
    tier_overflow_price: Optional[StrictInt] = Field(default=None, ge=0)

    @field_validator("condition_code")
    @classmethod
    def trim_condition_code(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("condition_code is required")
        return value


class AdminBuybackCatalogProductIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: StrictStr = Field(min_length=1, max_length=255)
    category: StrictStr = Field(min_length=1, max_length=64)
    card_number: Optional[StrictStr] = Field(default=None, max_length=128)
    rarity: Optional[StrictStr] = Field(default=None, max_length=128)
    pack_name: Optional[StrictStr] = Field(default=None, max_length=255)
    image_url: Optional[StrictStr] = None
    notes: Optional[StrictStr] = None
    is_active: StrictBool = True
    sort_order: StrictInt = 0
    prices: List[AdminBuybackCatalogPriceIn] = Field(min_length=1)

    @field_validator("name", "category")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value is required")
        return value

    @field_validator("card_number", "rarity", "pack_name", "image_url", "notes")
    @classmethod
    def trim_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def unique_conditions(self) -> "AdminBuybackCatalogProductIn":
        codes = [price.condition_code.casefold() for price in self.prices]
        if len(codes) != len(set(codes)):
            raise ValueError("condition_code must be unique")
        return self


class AdminBuybackCatalogPriceOut(BaseModel):
    id: int
    condition_code: str
    price_normal: int
    price_high: Optional[int] = None
    purchase_limit: Optional[int] = None
    tier_overflow_price: Optional[int] = None
    effective_from: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AdminBuybackCatalogProductOut(BaseModel):
    id: int
    name: str
    category: str
    card_number: Optional[str] = None
    rarity: Optional[str] = None
    pack_name: Optional[str] = None
    image_url: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool
    sort_order: int
    prices: List[AdminBuybackCatalogPriceOut]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


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
    customer_planned_ship_date: Optional[date] = None
    rejected_item_handling: str
    agreed_prepaid_shipping: bool = False
    agreed_cod_consequence: bool = False
    agreed_condition_rejection: bool = False

    @model_validator(mode="after")
    def validate_submission_agreements(self) -> "BuybackRequestCreate":
        if not self.agreed_prepaid_shipping:
            raise ValueError("送料元払いでの発送に同意してください")
        if not self.agreed_cod_consequence:
            raise ValueError("着払い発送時の返送・返送料自己負担について確認してください")
        if not self.agreed_condition_rejection:
            raise ValueError("状態による買取不可の可能性について確認してください")
        allowed = {
            "return_rejected_only",
            "dispose_rejected",
            "return_all_if_any_rejected",
        }
        if self.rejected_item_handling not in allowed:
            raise ValueError("買取不可商品の対応方法を選択してください")
        return self


class BuybackRequestItemOut(BaseModel):
    id: int
    product_id: Optional[int] = None
    product_name_snapshot: str
    condition_code: str
    quantity: int
    listed_unit_price: int
    assessed_unit_price: Optional[int] = None
    accepted_unit_price: Optional[int] = None
    line_status: Optional[str] = None
    line_status_label: Optional[str] = None
    rejection_reason_code: Optional[str] = None
    rejection_reason_text: Optional[str] = None
    rejection_reason_label: Optional[str] = None
    is_return_target: bool = False
    is_disposal_target: bool = False
    return_status: Optional[str] = None
    return_status_label: Optional[str] = None
    return_tracking_number: Optional[str] = None
    return_shipping_cost: Optional[int] = None

    class Config:
        from_attributes = True


class BuybackRequestSummaryOut(BaseModel):
    id: int
    request_number: Optional[str] = None
    public_buyback_code: Optional[str] = None
    inbound_mgmt_id: Optional[str] = None
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
    public_buyback_code: Optional[str] = None
    inbound_mgmt_id: Optional[str] = None
    public_member_id: Optional[str] = None
    inbound_status: Optional[str] = None
    inbound_status_label: Optional[str] = None
    status: str
    status_label: str
    shipping_method: Optional[str] = None
    tracking_number: Optional[str] = None
    customer_note: Optional[str] = None
    customer_planned_ship_date: Optional[date] = None
    estimated_total: Optional[int] = None
    assessed_total: Optional[int] = None
    payout_total: Optional[int] = None
    rejected_item_handling: Optional[str] = None
    rejected_item_handling_label: Optional[str] = None
    submitted_at: Optional[datetime] = None
    application_form_issued_at: Optional[datetime] = None
    assessed_at: Optional[datetime] = None
    created_at: datetime
    items: List[BuybackRequestItemOut] = []

    class Config:
        from_attributes = True


class BuybackApplicationFormItemOut(BaseModel):
    product_name: str
    condition_code: str
    quantity: int


class BuybackApplicationFormOut(BaseModel):
    """PII-minimized payload for customer application form printing."""

    shop_name: str
    request_id: int
    request_number: Optional[str] = None
    public_buyback_code: Optional[str] = None
    inbound_mgmt_id: Optional[str] = None
    public_member_id: Optional[str] = None
    applicant_name: str
    submitted_at: Optional[datetime] = None
    customer_planned_ship_date: Optional[str] = None
    declared_item_count: int = 0
    items: List[BuybackApplicationFormItemOut] = []
    identity_status: Optional[str] = None
    identity_status_label: Optional[str] = None
    guardian_status: Optional[str] = None
    guardian_status_label: Optional[str] = None
    requires_guardian_consent: bool = False
    barcode_human_readable: Optional[str] = None
    application_form_issued_at: Optional[datetime] = None
    is_reprint: bool = False
    notices: List[str] = []


class BuybackApplicationFormIssueIn(BaseModel):
    print_type: str = "application_a4"
    device_info: Optional[str] = None


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
    rejected_item_handling: Optional[str] = None
    rejected_item_handling_label: Optional[str] = None
    agreed_prepaid_shipping: bool = False
    agreed_cod_consequence: bool = False
    agreed_condition_rejection: bool = False
    submitted_at: Optional[datetime] = None
    created_at: datetime
    items: List[BuybackRequestItemOut] = []
    status_history: List[AdminBuybackStatusHistoryOut] = []
    allowed_next_statuses: List[str] = []
    payout_account: Optional[AdminPayoutAccountOut] = None
    ready_for_payout: bool = False
    payout_email_sent: bool = False
    paid_at: Optional[datetime] = None
    rejection_reason_options: List[dict[str, str]] = []


class AdminBuybackRequestItemUpdateIn(BaseModel):
    id: int
    line_status: Optional[str] = None
    assessed_unit_price: Optional[int] = None
    accepted_unit_price: Optional[int] = None
    rejection_reason_code: Optional[str] = None
    rejection_reason_text: Optional[str] = None
    is_return_target: Optional[bool] = None
    is_disposal_target: Optional[bool] = None
    return_status: Optional[str] = None
    return_tracking_number: Optional[str] = None
    return_shipping_cost: Optional[int] = None


class AdminBuybackRequestItemsUpdateIn(BaseModel):
    items: List[AdminBuybackRequestItemUpdateIn]
    recalculate_assessed_total: bool = True
    apply_handling_policy: bool = True


class AdminCompletePayoutIn(BaseModel):
    payout_total: Optional[int] = None
    admin_note: Optional[str] = None
    send_email: bool = True
    force_email: bool = False


class AdminFirestoreImportIn(BaseModel):
    items: List[dict]
    images: dict[str, str] = {}
    dry_run: bool = False


class AdminFirestoreImportOut(BaseModel):
    created: int
    updated: int
    skipped: int
    price_rows_upserted: int
    image_failures: List[str]
    errors: List[str]
    dry_run: bool
    validation: dict[str, int]


class AdminBuybackRequestUpdateIn(BaseModel):
    status: str
    admin_note: Optional[str] = None
    tracking_number: Optional[str] = None
    assessed_total: Optional[int] = None
    payout_total: Optional[int] = None


class AdminBuybackScanIn(BaseModel):
    # Kept nullable at the request boundary so missing/null attempts reach the
    # service and are rejected with a generic response plus a safe audit row.
    code: Optional[str] = None
    device_info: Optional[str] = None

    @field_validator("code", mode="before")
    @classmethod
    def hide_invalid_scanner_value(cls, value):
        return value if value is None or isinstance(value, str) else None


class AdminBuybackScanItemOut(BaseModel):
    id: int
    product_name: str
    condition_code: str
    quantity: int


class AdminBuybackScanHistoryOut(BaseModel):
    id: int
    from_status: Optional[str] = None
    from_status_label: Optional[str] = None
    to_status: str
    to_status_label: str
    note: Optional[str] = None
    created_at: Optional[datetime] = None


class AdminBuybackReceiptOut(BaseModel):
    id: int
    received_at: datetime
    received_by_name: Optional[str] = None
    box_count: Optional[int] = None
    actual_item_count: Optional[int] = None
    condition_note: Optional[str] = None
    admin_note: Optional[str] = None
    device_info: Optional[str] = None


class AdminBuybackAddressOut(BaseModel):
    postal_code: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None


class AdminBuybackScanOut(BaseModel):
    found: bool
    message: Optional[str] = None
    request_id: Optional[int] = None
    inbound_shipment_id: Optional[int] = None
    barcode_id: Optional[int] = None
    request_number: Optional[str] = None
    public_buyback_code: Optional[str] = None
    inbound_mgmt_id: Optional[str] = None
    applicant_name: Optional[str] = None
    public_member_id: Optional[str] = None
    submitted_at: Optional[datetime] = None
    request_status: Optional[str] = None
    request_status_label: Optional[str] = None
    inbound_status: Optional[str] = None
    inbound_status_label: Optional[str] = None
    shipping_method: Optional[str] = None
    declared_item_count: Optional[int] = None
    actual_item_count: Optional[int] = None
    expected_box_count: Optional[int] = None
    items: List[AdminBuybackScanItemOut] = []
    identity_status: Optional[str] = None
    identity_status_label: Optional[str] = None
    guardian_status: Optional[str] = None
    guardian_status_label: Optional[str] = None
    admin_note: Optional[str] = None
    logistics_note: Optional[str] = None
    already_received: bool = False
    is_cancelled: bool = False
    can_receive: bool = False
    status_history: List[AdminBuybackScanHistoryOut] = []
    receipts: List[AdminBuybackReceiptOut] = []
    notices: List[str] = []
    user_email: Optional[str] = None
    phone_number: Optional[str] = None
    address: Optional[AdminBuybackAddressOut] = None


class AdminBuybackReceiveIn(BaseModel):
    inbound_shipment_id: int
    scanned_code: Optional[str] = None
    box_count: Optional[int] = 1
    actual_item_count: Optional[int] = None
    condition_note: Optional[str] = None
    admin_note: Optional[str] = None
    device_info: Optional[str] = None

    @field_validator("scanned_code", mode="before")
    @classmethod
    def hide_invalid_scanner_value(cls, value):
        return value if value is None or isinstance(value, str) else None


class AdminBuybackPackageItemOut(BaseModel):
    request_item_id: int
    quantity: int
    product_name: Optional[str] = None
    condition_code: Optional[str] = None


class AdminBuybackPackageOut(BaseModel):
    id: int
    request_id: int
    package_code: str
    package_kind: str
    package_kind_label: Optional[str] = None
    box_index: int
    total_boxes: int
    return_reference: Optional[str] = None
    shipping_method: Optional[str] = None
    preferred_ship_date: Optional[str] = None
    preferred_time_slot: Optional[str] = None
    tracking_number: Optional[str] = None
    status: str
    status_label: Optional[str] = None
    packed_by_name: Optional[str] = None
    packed_at: Optional[datetime] = None
    shipped_at: Optional[datetime] = None
    admin_note: Optional[str] = None
    barcode_human_readable: Optional[str] = None
    items: List[AdminBuybackPackageItemOut] = []
    created_at: Optional[datetime] = None


class AdminBuybackPackageIssueIn(BaseModel):
    total_boxes: int = 1
    package_kind: str = "return"
    shipping_method: Optional[str] = None
    preferred_ship_date: Optional[date] = None
    preferred_time_slot: Optional[str] = None
    return_reference: Optional[str] = None
    admin_note: Optional[str] = None
    request_item_ids: Optional[List[int]] = None
    replace_existing: bool = False


class AdminBuybackPackageCompleteIn(BaseModel):
    tracking_number: Optional[str] = None
    admin_note: Optional[str] = None


class AdminBuybackPackageLabelOut(AdminBuybackPackageOut):
    shop_name: str = "KRX TCG"
    public_buyback_code: Optional[str] = None
    request_number: Optional[str] = None
    inbound_mgmt_id: Optional[str] = None
    applicant_name: Optional[str] = None
    destination_name: Optional[str] = None
    destination_phone: Optional[str] = None
    destination_address: Optional[AdminBuybackAddressOut] = None
    request_status: Optional[str] = None
    request_status_label: Optional[str] = None
    item_count: int = 0
    handling_note: str = "取扱注意"
    is_reprint: bool = False


class AdminBuybackPackagePrintIn(BaseModel):
    is_reprint: bool = False
    device_info: Optional[str] = None


class AdminBuybackShipCheckItemOut(BaseModel):
    code: str
    label: str


class AdminBuybackShipVerifyOut(BaseModel):
    found: bool
    message: Optional[str] = None
    package_id: Optional[int] = None
    barcode_id: Optional[int] = None
    package_code: Optional[str] = None
    package_kind: Optional[str] = None
    package_kind_label: Optional[str] = None
    box_index: Optional[int] = None
    total_boxes: Optional[int] = None
    request_id: Optional[int] = None
    request_number: Optional[str] = None
    public_buyback_code: Optional[str] = None
    return_reference: Optional[str] = None
    request_status: Optional[str] = None
    request_status_label: Optional[str] = None
    package_status: Optional[str] = None
    package_status_label: Optional[str] = None
    shipping_method: Optional[str] = None
    preferred_ship_date: Optional[str] = None
    preferred_time_slot: Optional[str] = None
    tracking_number: Optional[str] = None
    applicant_name: Optional[str] = None
    destination_name: Optional[str] = None
    destination_phone: Optional[str] = None
    destination_address: Optional[AdminBuybackAddressOut] = None
    items: List[AdminBuybackPackageItemOut] = []
    checklist_items: List[AdminBuybackShipCheckItemOut] = []
    warnings: List[str] = []
    notices: List[str] = []
    already_shipped: bool = False
    is_cancelled: bool = False
    address_complete: bool = False
    can_confirm: bool = False


class AdminBuybackShipConfirmIn(BaseModel):
    package_id: int
    checklist: dict[str, bool]
    scanned_code: Optional[str] = None
    tracking_number: Optional[str] = None
    shipping_method: Optional[str] = None
    device_info: Optional[str] = None

    @field_validator("scanned_code", mode="before")
    @classmethod
    def hide_invalid_scanner_value(cls, value):
        return value if value is None or isinstance(value, str) else None


class AdminBuybackLabelLayoutOut(BaseModel):
    product_code: str
    format_code: str
    sheet_width_mm: float
    sheet_height_mm: float
    label_width_mm: float
    label_height_mm: float
    columns: int
    rows: int
    faces: int
    gap_h_mm: float
    gap_v_mm: float
    margin_left_mm: float
    margin_top_mm: float
    margin_right_mm: float
    margin_bottom_mm: float
    margins_confirmed: bool
    margins_note: str
    source_url: str
    shop_name: str


class AdminBuybackLabelCsvExportIn(BaseModel):
    package_ids: List[int]
    include_applicant_name: bool = False


class AdminBuybackLabelSheetIn(BaseModel):
    package_ids: List[int]
    start_position: int = 1  # 1-based face index on 72265 sheet
    copies: int = 1
    include_applicant_name: bool = False


class AdminBuybackLabelSheetCellOut(BaseModel):
    package_id: int
    package_code: str
    barcode_human_readable: Optional[str] = None
    public_buyback_code: Optional[str] = None
    request_number: Optional[str] = None
    inbound_mgmt_id: Optional[str] = None
    box_index: Optional[int] = None
    total_boxes: Optional[int] = None
    package_kind: Optional[str] = None
    package_kind_label: Optional[str] = None
    applicant_name: Optional[str] = None
    handling_note: str = "取扱注意"
    shop_name: str = "KRX TCG"
    title: Optional[str] = None


class AdminBuybackLabelSheetOut(BaseModel):
    layout: AdminBuybackLabelLayoutOut
    start_position: int
    copies: int
    labels: List[AdminBuybackLabelSheetCellOut]


class AdminBuybackLogisticsLogOut(BaseModel):
    id: str
    log_type: str
    action: str
    result: Optional[str] = None
    actor_user_id: Optional[int] = None
    actor_name: Optional[str] = None
    request_id: Optional[int] = None
    package_id: Optional[int] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    includes_pii: Optional[bool] = None
    is_reprint: Optional[bool] = None
    details: Optional[dict] = None
    device_info: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: Optional[datetime] = None


class AdminBuybackLogisticsLogsOut(BaseModel):
    items: List[AdminBuybackLogisticsLogOut]
    total: int
    page: int
    per_page: int
    pages: int
