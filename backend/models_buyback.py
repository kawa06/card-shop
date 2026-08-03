"""Buyback domain models (Phase 2: schema only, no API routes yet)."""

from __future__ import annotations

from datetime import datetime
import enum

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database import Base


class BuybackRequestStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    identity_pending = "identity_pending"
    awaiting_shipment = "awaiting_shipment"
    awaiting_visit = "awaiting_visit"
    shipped = "shipped"
    received = "received"
    store_visited = "store_visited"
    assessing = "assessing"
    assessed = "assessed"
    awaiting_customer = "awaiting_customer"
    accepted = "accepted"
    rejected = "rejected"
    payout_pending = "payout_pending"
    paid = "paid"
    return_preparing = "return_preparing"
    returned = "returned"
    completed = "completed"
    cancelled = "cancelled"
    sent_back = "sent_back"
    on_hold = "on_hold"


class IdentityVerificationStatus(str, enum.Enum):
    not_submitted = "not_submitted"
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    resubmit_requested = "resubmit_requested"
    expired = "expired"


class PayoutTransferStatus(str, enum.Enum):
    unpaid = "unpaid"
    scheduled = "scheduled"
    completed = "completed"


class GuardianConsentStatus(str, enum.Enum):
    pending = "pending"
    signed = "signed"
    expired = "expired"
    revoked = "revoked"


class BuybackItemLineStatus(str, enum.Enum):
    pending = "pending"
    buyable = "buyable"
    reduced = "reduced"
    rejected = "rejected"


class RejectedItemHandling(str, enum.Enum):
    return_rejected_only = "return_rejected_only"
    dispose_rejected = "dispose_rejected"
    return_all_if_any_rejected = "return_all_if_any_rejected"


class BuybackItemReturnStatus(str, enum.Enum):
    none = "none"
    pending = "pending"
    shipped = "shipped"
    completed = "completed"


class BuybackInboundShipmentStatus(str, enum.Enum):
    awaiting_shipment = "awaiting_shipment"
    customer_shipped = "customer_shipped"
    arrived = "arrived"
    received = "received"


class BuybackBarcodeType(str, enum.Enum):
    application_inbound = "application_inbound"
    package_outbound = "package_outbound"
    shelf = "shelf"


class BuybackBarcodeEntityType(str, enum.Enum):
    inbound_shipment = "inbound_shipment"
    shipment_package = "shipment_package"


class BuybackShipmentPackageStatus(str, enum.Enum):
    packing = "packing"
    packed = "packed"
    awaiting_verify = "awaiting_verify"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"


REJECTION_REASON_CODES = {
    "major_damage": "大きな折れ、破れ、欠損がある",
    "water_stain": "水濡れや強い汚れがある",
    "mold_odor": "カビ、異臭、べたつきがある",
    "dent_scratch": "大きなへこみや深い傷がある",
    "counterfeit": "偽造品、コピー品、正規品と確認できないもの",
    "other": "その他、再販売が困難だと判断したもの",
}


class BuybackProduct(Base):
    __tablename__ = "buyback_products"

    id = Column(Integer, primary_key=True, index=True)
    firestore_item_id = Column(String(128), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(64), nullable=False, index=True)
    card_number = Column(String(128), nullable=True)
    rarity = Column(String(128), nullable=True)
    pack_name = Column(String(255), nullable=True)
    image_url = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    promo_badge_text = Column(String(32), nullable=True)
    promo_badge_bg = Column(String(32), nullable=True)
    promo_badge_fg = Column(String(32), nullable=True)
    promo_badge_starts_at = Column(DateTime, nullable=True)
    promo_badge_ends_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    prices = relationship("BuybackProductPrice", back_populates="product", cascade="all, delete-orphan")


class BuybackProductPrice(Base):
    __tablename__ = "buyback_product_prices"
    __table_args__ = (
        UniqueConstraint("product_id", "condition_code", name="uq_buyback_product_condition"),
    )

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("buyback_products.id", ondelete="CASCADE"), nullable=False, index=True)
    condition_code = Column(String(32), nullable=False)
    price_normal = Column(Integer, nullable=False, default=0)
    price_high = Column(Integer, nullable=True)
    purchase_limit = Column(Integer, nullable=True)
    tier_overflow_price = Column(Integer, nullable=True)
    effective_from = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("BuybackProduct", back_populates="prices")


class BuybackPriceHistory(Base):
    __tablename__ = "buyback_price_history"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("buyback_products.id", ondelete="CASCADE"), nullable=False, index=True)
    condition_code = Column(String(32), nullable=False)
    price_normal = Column(Integer, nullable=False)
    price_high = Column(Integer, nullable=True)
    changed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    source = Column(String(64), nullable=True)
    changed_at = Column(DateTime, default=datetime.utcnow)


class BuybackCart(Base):
    __tablename__ = "buyback_carts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = relationship("BuybackCartItem", back_populates="cart", cascade="all, delete-orphan")


class BuybackCartItem(Base):
    __tablename__ = "buyback_cart_items"
    __table_args__ = (
        UniqueConstraint("cart_id", "product_id", "condition_code", name="uq_buyback_cart_line"),
    )

    id = Column(Integer, primary_key=True, index=True)
    cart_id = Column(Integer, ForeignKey("buyback_carts.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("buyback_products.id"), nullable=False, index=True)
    condition_code = Column(String(32), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price_snapshot = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    cart = relationship("BuybackCart", back_populates="items")
    product = relationship("BuybackProduct")


class BuybackRequestNumberSequence(Base):
    __tablename__ = "buyback_request_number_sequences"

    seq_date = Column(String(8), primary_key=True)
    last_seq = Column(Integer, nullable=False, default=0)


class BuybackNumberSequence(Base):
    """Daily sequences for public-facing KRX-* codes."""

    __tablename__ = "buyback_number_sequences"
    __table_args__ = (UniqueConstraint("seq_kind", "seq_date", name="uq_buyback_number_seq_kind_date"),)

    id = Column(Integer, primary_key=True, index=True)
    seq_kind = Column(String(32), nullable=False, index=True)
    seq_date = Column(String(8), nullable=False, index=True)
    last_seq = Column(Integer, nullable=False, default=0)


class BuybackRequest(Base):
    __tablename__ = "buyback_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    request_number = Column(String(32), unique=True, nullable=True, index=True)
    public_buyback_code = Column(String(32), unique=True, nullable=True, index=True)
    inbound_mgmt_id = Column(String(32), unique=True, nullable=True, index=True)
    status = Column(String(32), nullable=False, default=BuybackRequestStatus.draft.value, index=True)
    shipping_method = Column(String(64), nullable=True)
    tracking_number = Column(String(128), nullable=True)
    customer_note = Column(Text, nullable=True)
    admin_note = Column(Text, nullable=True)
    customer_status_note = Column(Text, nullable=True)
    estimated_total = Column(Integer, nullable=True)
    assessed_total = Column(Integer, nullable=True)
    payout_total = Column(Integer, nullable=True)
    rejected_item_handling = Column(String(64), nullable=True)
    agreed_prepaid_shipping = Column(Boolean, default=False, nullable=False)
    agreed_cod_consequence = Column(Boolean, default=False, nullable=False)
    agreed_condition_rejection = Column(Boolean, default=False, nullable=False)
    submitted_at = Column(DateTime, nullable=True)
    application_form_issued_at = Column(DateTime, nullable=True)
    customer_planned_ship_date = Column(Date, nullable=True)
    customer_shipped_at = Column(DateTime, nullable=True)
    buyback_method = Column(String(16), nullable=True, index=True)
    store_visit_at = Column(DateTime, nullable=True, index=True)
    logistics_note = Column(Text, nullable=True)
    received_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    received_at = Column(DateTime, nullable=True)
    assessed_at = Column(DateTime, nullable=True)
    customer_confirmed_at = Column(DateTime, nullable=True)
    customer_confirmed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    store_checked_in_at = Column(DateTime, nullable=True)
    store_checked_in_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    assessment_started_at = Column(DateTime, nullable=True)
    assessment_started_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    assessment_presented_at = Column(DateTime, nullable=True)
    assessment_presented_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    assessment_result_version = Column(Integer, nullable=False, default=0)
    store_payment_method = Column(String(32), nullable=True)
    store_payment_amount = Column(Integer, nullable=True)
    store_payment_note = Column(Text, nullable=True)
    transaction_completed_at = Column(DateTime, nullable=True)
    transaction_completed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    paid_at = Column(DateTime, nullable=True)
    payout_transfer_status = Column(String(32), nullable=True, index=True)
    payout_scheduled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = relationship("BuybackRequestItem", back_populates="request", cascade="all, delete-orphan")
    status_history = relationship("BuybackStatusHistory", back_populates="request", cascade="all, delete-orphan")
    inbound_shipment = relationship(
        "BuybackInboundShipment",
        back_populates="request",
        uselist=False,
        cascade="all, delete-orphan",
    )


class BuybackRequestItem(Base):
    __tablename__ = "buyback_request_items"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("buyback_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("buyback_products.id"), nullable=True, index=True)
    product_name_snapshot = Column(String(255), nullable=False)
    condition_code = Column(String(32), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    listed_unit_price = Column(Integer, nullable=False, default=0)
    assessed_unit_price = Column(Integer, nullable=True)
    accepted_unit_price = Column(Integer, nullable=True)
    assessment_lines_json = Column(Text, nullable=True)
    line_status = Column(String(32), nullable=True)
    rejection_reason_code = Column(String(64), nullable=True)
    rejection_reason_text = Column(Text, nullable=True)
    is_return_target = Column(Boolean, default=False, nullable=False)
    is_disposal_target = Column(Boolean, default=False, nullable=False)
    return_status = Column(String(32), nullable=True)
    return_tracking_number = Column(String(128), nullable=True)
    return_shipping_cost = Column(Integer, nullable=True)
    customer_decision = Column(String(32), nullable=True)
    customer_decision_lines_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    request = relationship("BuybackRequest", back_populates="items")


class BuybackAppraisalEstimate(Base):
    __tablename__ = "buyback_appraisal_estimates"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(
        Integer,
        ForeignKey("buyback_requests.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    estimated_minutes = Column(Integer, nullable=False)
    message = Column(Text, nullable=True)
    sent_at = Column(DateTime, nullable=False)
    sent_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    revision_count = Column(Integer, nullable=False, default=1)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    request = relationship("BuybackRequest", backref="appraisal_estimate")


class IdentityVerification(Base):
    __tablename__ = "identity_verifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(32), nullable=False, default=IdentityVerificationStatus.not_submitted.value, index=True)
    document_type = Column(String(64), nullable=True)
    storage_key_front = Column(String(512), nullable=True)
    storage_key_back = Column(String(512), nullable=True)
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    admin_memo = Column(Text, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    submitted_full_name = Column(String(200), nullable=True)
    submitted_name_kana = Column(String(200), nullable=True)
    submitted_birth_date = Column(Date, nullable=True)
    submitted_postal_code = Column(String(20), nullable=True)
    submitted_prefecture = Column(String(100), nullable=True)
    submitted_city = Column(String(100), nullable=True)
    submitted_address_line1 = Column(String(255), nullable=True)
    submitted_address_line2 = Column(String(255), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class GuardianConsent(Base):
    __tablename__ = "guardian_consents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    guardian_name = Column(String(100), nullable=True)
    guardian_email = Column(String(255), nullable=True)
    guardian_relationship = Column(String(50), nullable=True)
    guardian_phone = Column(String(20), nullable=True)
    consent_token_hash = Column(String(128), nullable=True, index=True)
    status = Column(String(32), nullable=False, default=GuardianConsentStatus.pending.value, index=True)
    document_type = Column(String(64), nullable=True)
    storage_key_front = Column(String(512), nullable=True)
    storage_key_back = Column(String(512), nullable=True)
    signed_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PayoutAccount(Base):
    __tablename__ = "payout_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    bank_name = Column(String(100), nullable=False)
    branch_name = Column(String(100), nullable=True)
    account_type = Column(String(32), nullable=False)
    account_number_encrypted = Column(Text, nullable=False)
    account_holder = Column(String(100), nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BuybackStatusHistory(Base):
    __tablename__ = "buyback_status_history"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("buyback_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    from_status = Column(String(32), nullable=True)
    to_status = Column(String(32), nullable=False)
    changed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    note = Column(Text, nullable=True)
    related_barcode_id = Column(Integer, ForeignKey("buyback_barcodes.id"), nullable=True, index=True)
    device_info = Column(String(255), nullable=True)
    change_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    request = relationship("BuybackRequest", back_populates="status_history")


class BuybackBarcode(Base):
    __tablename__ = "buyback_barcodes"

    id = Column(Integer, primary_key=True, index=True)
    scan_token = Column(String(64), unique=True, nullable=False, index=True)
    barcode_type = Column(String(32), nullable=False, index=True)
    entity_type = Column(String(32), nullable=False, index=True)
    entity_id = Column(Integer, nullable=False, index=True)
    human_readable = Column(String(64), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BuybackInboundShipment(Base):
    __tablename__ = "buyback_inbound_shipments"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(
        Integer,
        ForeignKey("buyback_requests.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    inbound_mgmt_id = Column(String(32), unique=True, nullable=False, index=True)
    status = Column(
        String(32),
        nullable=False,
        default=BuybackInboundShipmentStatus.awaiting_shipment.value,
        index=True,
    )
    expected_box_count = Column(Integer, nullable=False, default=1)
    declared_item_count = Column(Integer, nullable=True)
    actual_item_count = Column(Integer, nullable=True)
    condition_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    request = relationship("BuybackRequest", back_populates="inbound_shipment")


class BuybackPackageReceipt(Base):
    __tablename__ = "buyback_package_receipts"

    id = Column(Integer, primary_key=True, index=True)
    inbound_shipment_id = Column(
        Integer,
        ForeignKey("buyback_inbound_shipments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    received_at = Column(DateTime, nullable=False)
    received_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    scanned_barcode_id = Column(Integer, ForeignKey("buyback_barcodes.id"), nullable=True, index=True)
    device_info = Column(String(255), nullable=True)
    box_count = Column(Integer, nullable=True)
    actual_item_count = Column(Integer, nullable=True)
    condition_note = Column(Text, nullable=True)
    admin_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class BuybackShipmentPackage(Base):
    __tablename__ = "buyback_shipment_packages"
    __table_args__ = (
        UniqueConstraint("request_id", "package_kind", "box_index", name="uq_buyback_pkg_request_kind_box"),
    )

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("buyback_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    package_code = Column(String(32), unique=True, nullable=False, index=True)
    package_kind = Column(String(32), nullable=False, index=True)
    box_index = Column(Integer, nullable=False)
    total_boxes = Column(Integer, nullable=False)
    return_reference = Column(String(64), nullable=True, index=True)
    destination_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    shipping_method = Column(String(64), nullable=True)
    preferred_ship_date = Column(Date, nullable=True)
    preferred_time_slot = Column(String(64), nullable=True)
    tracking_number = Column(String(128), nullable=True, unique=True, index=True)
    status = Column(String(32), nullable=False, default=BuybackShipmentPackageStatus.packing.value, index=True)
    packed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    packed_at = Column(DateTime, nullable=True)
    shipped_at = Column(DateTime, nullable=True)
    admin_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BuybackPackageItem(Base):
    __tablename__ = "buyback_package_items"
    __table_args__ = (
        UniqueConstraint("package_id", "request_item_id", name="uq_buyback_package_item"),
    )

    id = Column(Integer, primary_key=True, index=True)
    package_id = Column(
        Integer,
        ForeignKey("buyback_shipment_packages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    request_item_id = Column(
        Integer,
        ForeignKey("buyback_request_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quantity = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)


class BuybackShipmentConfirmation(Base):
    __tablename__ = "buyback_shipment_confirmations"

    id = Column(Integer, primary_key=True, index=True)
    package_id = Column(
        Integer,
        ForeignKey("buyback_shipment_packages.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    confirmed_at = Column(DateTime, nullable=False)
    confirmed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    scanned_barcode_id = Column(Integer, ForeignKey("buyback_barcodes.id"), nullable=True, index=True)
    tracking_number = Column(String(128), nullable=True)
    shipping_method = Column(String(64), nullable=True)
    checklist_json = Column(Text, nullable=False)
    device_info = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class BuybackShipmentAddressSnapshot(Base):
    __tablename__ = "buyback_shipment_address_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    confirmation_id = Column(
        Integer,
        ForeignKey("buyback_shipment_confirmations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    recipient_name = Column(String(100), nullable=False)
    postal_code = Column(String(20), nullable=True)
    region = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    phone_number = Column(String(20), nullable=True)
    shipping_method = Column(String(64), nullable=True)
    preferred_time_slot = Column(String(64), nullable=True)
    snapshot_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class BuybackPackageScanLog(Base):
    __tablename__ = "buyback_package_scan_logs"

    id = Column(Integer, primary_key=True, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    scan_token = Column(String(64), nullable=False, index=True)
    barcode_id = Column(Integer, ForeignKey("buyback_barcodes.id"), nullable=True, index=True)
    action = Column(String(64), nullable=False, index=True)
    result = Column(String(32), nullable=False, index=True)
    request_id = Column(Integer, ForeignKey("buyback_requests.id"), nullable=True, index=True)
    package_id = Column(Integer, ForeignKey("buyback_shipment_packages.id"), nullable=True, index=True)
    ip_address = Column(String(64), nullable=True)
    device_info = Column(String(255), nullable=True)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class BuybackPackagePrintLog(Base):
    __tablename__ = "buyback_package_print_logs"

    id = Column(Integer, primary_key=True, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    print_type = Column(String(64), nullable=False, index=True)
    entity_type = Column(String(64), nullable=False, index=True)
    entity_id = Column(Integer, nullable=False, index=True)
    includes_pii = Column(Boolean, default=False, nullable=False)
    is_reprint = Column(Boolean, default=False, nullable=False)
    device_info = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class BuybackAuditLog(Base):
    __tablename__ = "buyback_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(64), nullable=False, index=True)
    entity_type = Column(String(64), nullable=False, index=True)
    entity_id = Column(String(64), nullable=True, index=True)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class BuybackShopSettings(Base):
    """Singleton (id=1): buylist public shop display settings."""

    __tablename__ = "buyback_shop_settings"

    id = Column(Integer, primary_key=True)
    shop_key = Column(String(64), nullable=False, default="main")
    name = Column(String(128), nullable=False, default="KRX TCG")
    slug = Column(String(128), nullable=False, default="card-vault")
    notice_text = Column(Text, nullable=True)
    show_notice = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BuybackChannelSettings(Base):
    """Singleton (id=1): store/mail availability and store hours."""

    __tablename__ = "buyback_channel_settings"

    id = Column(Integer, primary_key=True)
    store_enabled = Column(Boolean, default=True, nullable=False)
    mail_enabled = Column(Boolean, default=True, nullable=False)
    slot_interval_minutes = Column(Integer, default=30, nullable=False)
    business_hours_json = Column(Text, nullable=True)
    closed_dates_json = Column(Text, nullable=True)
    email_auto_send_json = Column(Text, nullable=True)
    kyc_email_auto_send_json = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BuybackPromoBanner(Base):
    __tablename__ = "buyback_promo_banners"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    target_channel = Column(String(16), nullable=False, default="both", index=True)
    starts_at = Column(DateTime, nullable=False, index=True)
    ends_at = Column(DateTime, nullable=False, index=True)
    background_color = Column(String(32), nullable=False, default="#1a1a2e")
    text_color = Column(String(32), nullable=False, default="#ffffff")
    sort_order = Column(Integer, nullable=False, default=0, index=True)
    is_visible = Column(Boolean, default=True, nullable=False, index=True)
    linked_product_ids_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BuybackStoreReservation(Base):
    __tablename__ = "buyback_store_reservations"
    __table_args__ = (
        UniqueConstraint("visit_at", name="uq_buyback_store_reservation_visit_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("buyback_requests.id"), nullable=False, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    visit_at = Column(DateTime, nullable=False, index=True)
    status = Column(String(32), nullable=False, default="confirmed", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    channel = Column(String(32), nullable=False)
    template_key = Column(String(64), nullable=False)
    reference_type = Column(String(64), nullable=True)
    reference_id = Column(String(64), nullable=True)
    status = Column(String(32), nullable=False, default="pending", index=True)
    provider_message_id = Column(String(128), nullable=True)
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
