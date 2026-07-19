"""Buyback domain models (Phase 2: schema only, no API routes yet)."""

from __future__ import annotations

from datetime import datetime
import enum

from sqlalchemy import (
    Boolean,
    Column,
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
    received = "received"
    assessing = "assessing"
    assessed = "assessed"
    awaiting_customer = "awaiting_customer"
    accepted = "accepted"
    rejected = "rejected"
    payout_pending = "payout_pending"
    paid = "paid"
    returned = "returned"
    cancelled = "cancelled"


class IdentityVerificationStatus(str, enum.Enum):
    not_submitted = "not_submitted"
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"


class GuardianConsentStatus(str, enum.Enum):
    pending = "pending"
    signed = "signed"
    expired = "expired"
    revoked = "revoked"


class BuybackProduct(Base):
    __tablename__ = "buyback_products"

    id = Column(Integer, primary_key=True, index=True)
    firestore_item_id = Column(String(128), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(64), nullable=False, index=True)
    image_url = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
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


class BuybackRequest(Base):
    __tablename__ = "buyback_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    request_number = Column(String(32), unique=True, nullable=True, index=True)
    status = Column(String(32), nullable=False, default=BuybackRequestStatus.draft.value, index=True)
    shipping_method = Column(String(64), nullable=True)
    tracking_number = Column(String(128), nullable=True)
    customer_note = Column(Text, nullable=True)
    admin_note = Column(Text, nullable=True)
    estimated_total = Column(Integer, nullable=True)
    assessed_total = Column(Integer, nullable=True)
    payout_total = Column(Integer, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    assessed_at = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = relationship("BuybackRequestItem", back_populates="request", cascade="all, delete-orphan")
    status_history = relationship("BuybackStatusHistory", back_populates="request", cascade="all, delete-orphan")


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
    line_status = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    request = relationship("BuybackRequest", back_populates="items")


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
    submitted_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class GuardianConsent(Base):
    __tablename__ = "guardian_consents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    guardian_name = Column(String(100), nullable=True)
    guardian_email = Column(String(255), nullable=True)
    consent_token_hash = Column(String(128), nullable=True, index=True)
    status = Column(String(32), nullable=False, default=GuardianConsentStatus.pending.value, index=True)
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
    created_at = Column(DateTime, default=datetime.utcnow)

    request = relationship("BuybackRequest", back_populates="status_history")


class BuybackAuditLog(Base):
    __tablename__ = "buyback_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(64), nullable=False, index=True)
    entity_type = Column(String(64), nullable=False, index=True)
    entity_id = Column(String(64), nullable=True, index=True)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


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
