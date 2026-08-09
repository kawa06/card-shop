from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Date, Float,
    ForeignKey, Text, Enum as SAEnum, UniqueConstraint
)
from sqlalchemy.orm import relationship
from database import Base
import enum


class OrderStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"


class ShippingStatus(str, enum.Enum):
    unshipped = "unshipped"
    preparing = "preparing"
    packing = "packing"
    shipped = "shipped"
    in_transit = "in_transit"
    delivered = "delivered"
    received = "received"
    cancelled = "cancelled"


class User(Base):
    """User model with full address support for Japan standards"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)
    family_name = Column(String(50), nullable=True)
    given_name = Column(String(50), nullable=True)
    family_name_kana = Column(String(50), nullable=True)
    given_name_kana = Column(String(50), nullable=True)
    is_admin = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    verification_token = Column(String(255), nullable=True)
    postal_code = Column(String(20), nullable=True)
    country = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    phone_number = Column(String(20), nullable=True)
    phone_verified = Column(Boolean, default=False)
    clerk_user_id = Column(String(255), unique=True, nullable=True, index=True)
    public_member_id = Column(String(32), unique=True, nullable=True, index=True)
    birth_date = Column(Date, nullable=True)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    two_factor_enabled = Column(Boolean, default=False, nullable=False)
    two_factor_method = Column(String(16), nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    last_login_ip = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    cart_items = relationship("CartItem", back_populates="user", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="user")
    favorites = relationship("Favorite", back_populates="user", cascade="all, delete-orphan")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    name_en = Column(String(100), nullable=True)
    slug = Column(String(100), unique=True, index=True, nullable=False)
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    sort_order = Column(Integer, default=0)

    parent = relationship("Category", remote_side=[id], back_populates="children")
    children = relationship("Category", back_populates="parent")
    cards = relationship("Card", back_populates="category")


class Pack(Base):
    __tablename__ = "packs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    name_en = Column(String(100), nullable=True)
    slug = Column(String(100), unique=True, index=True, nullable=False)
    sort_order = Column(Integer, default=0)

    cards = relationship("Card", back_populates="pack")


CARD_RARITIES = ['C', 'U', 'R', 'RR', 'AR', 'SR', 'SAR', 'MUR', 'SSR', 'ミラー', 'MA', 'PROMO', 'CLASSIC', 'パック', 'BOX', 'PSA10']


class Card(Base):
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    name_en = Column(String(200), nullable=True, index=True)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    price_usd = Column(Float, nullable=True)
    stock = Column(Integer, default=0)
    low_stock_threshold = Column(Integer, nullable=True)  # Phase 3-8; None => DEFAULT_LOW_STOCK_THRESHOLD
    inventory_alert_enabled = Column(Boolean, default=True, nullable=True)  # Phase 3-8
    image_url = Column(Text, nullable=True)
    image_urls = Column(Text, nullable=True)  # JSON array of up to 10 image URLs
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    pack_id = Column(Integer, ForeignKey("packs.id"), nullable=True)
    rarity = Column(String(50), nullable=True)
    set_name = Column(String(100), nullable=True)
    condition = Column(String(10), nullable=True)  # a/b/c/d/e
    allowed_shipping_methods = Column(Text, nullable=True)  # JSON array or comma-separated string
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    category = relationship("Category", back_populates="cards")
    pack = relationship("Pack", back_populates="cards")
    cart_items = relationship("CartItem", back_populates="card")
    order_items = relationship("OrderItem", back_populates="card")
    favorites = relationship("Favorite", back_populates="card", cascade="all, delete-orphan")


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "card_id", name="uq_favorites_user_card"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="favorites")
    card = relationship("Card", back_populates="favorites")


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False)
    quantity = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="cart_items")
    card = relationship("Card", back_populates="cart_items")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    total_amount = Column(Float, nullable=False)
    status = Column(SAEnum(OrderStatus), default=OrderStatus.pending, nullable=False)
    postal_code = Column(String(20), nullable=True)
    country = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    shipping_address = Column(Text, nullable=True)
    shipping_method = Column(String(50), nullable=True)
    shipping_fee = Column(Integer, default=0)
    items_subtotal = Column(Integer, default=0)
    tax_rate_snapshot = Column(Integer, nullable=True)
    payment_method = Column(String(50), nullable=True)
    payment_status = Column(String(50), default="pending")
    stripe_checkout_session_id = Column(String(255), nullable=True)
    stripe_payment_intent_id = Column(String(255), nullable=True)
    stripe_event_id = Column(String(255), nullable=True)
    order_number = Column(String(32), unique=True, nullable=True, index=True)
    shipping_status = Column(String(32), default="unshipped")
    shipping_carrier = Column(String(100), nullable=True)
    tracking_number = Column(String(100), nullable=True, index=True)
    shipped_at = Column(DateTime, nullable=True)
    purchase_email_sent_at = Column(DateTime, nullable=True)
    shipping_email_sent_at = Column(DateTime, nullable=True)
    email_send_status = Column(String(50), nullable=True)
    admin_note = Column(Text, nullable=True)
    discount_amount = Column(Integer, default=0)
    coupon_code = Column(String(64), nullable=True)
    coupon_name = Column(String(128), nullable=True)
    payment_fee = Column(Integer, default=0)
    packaging_fee = Column(Integer, default=0)
    buyer_note = Column(Text, nullable=True)
    buyer_phone = Column(String(20), nullable=True)
    payment_deadline = Column(DateTime, nullable=True)
    stock_reserved = Column(Boolean, default=False)
    points_used = Column(Integer, default=0, nullable=False)
    points_earned = Column(Integer, default=0, nullable=False)
    points_earn_status = Column(String(16), default="none", nullable=False)
    points_reserved = Column(Integer, default=0, nullable=False)
    paid_at = Column(DateTime, nullable=True)
    click_post_csv_exported_at = Column(DateTime, nullable=True)
    shipping_box_type = Column(String(32), nullable=True)
    shipping_weight_g = Column(Integer, nullable=True)
    shipping_size_label = Column(String(32), nullable=True)
    shipped_by_admin_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderNumberSequence(Base):
    __tablename__ = "order_number_sequences"

    seq_date = Column(String(8), primary_key=True)
    last_seq = Column(Integer, nullable=False, default=0)


class StripeProcessedEvent(Base):
    __tablename__ = "stripe_processed_events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(255), unique=True, nullable=False, index=True)
    event_type = Column(String(100), nullable=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    processed_at = Column(DateTime, default=datetime.utcnow)


class ShopSettings(Base):
    """Singleton shop configuration (id=1)."""

    __tablename__ = "shop_settings"

    id = Column(Integer, primary_key=True, default=1)
    invoice_enabled = Column(Boolean, default=False, nullable=False)
    invoice_registration_number = Column(String(20), nullable=True)
    invoice_issuer_name = Column(String(128), nullable=True)
    default_tax_rate = Column(Integer, default=10, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class InquiryNumberSequence(Base):
    __tablename__ = "inquiry_number_sequences"

    seq_date = Column(String(8), primary_key=True)
    last_seq = Column(Integer, nullable=False, default=0)


class InquirySettings(Base):
    __tablename__ = "inquiry_settings"

    id = Column(Integer, primary_key=True, default=1)
    shop_id = Column(Integer, default=1, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    attachments_enabled = Column(Boolean, default=True, nullable=False)
    max_attachments = Column(Integer, default=5, nullable=False)
    max_attachment_bytes = Column(Integer, default=5 * 1024 * 1024, nullable=False)
    auto_reply_enabled = Column(Boolean, default=True, nullable=False)
    auto_reply_body = Column(Text, nullable=True)
    off_hours_message = Column(Text, nullable=True)
    receipt_message = Column(Text, nullable=True)
    allow_reopen_resolved = Column(Boolean, default=True, nullable=False)
    auto_close_days = Column(Integer, default=30, nullable=False)
    allowed_categories = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Inquiry(Base):
    __tablename__ = "inquiries"

    id = Column(Integer, primary_key=True, index=True)
    inquiry_number = Column(String(32), unique=True, nullable=False, index=True)
    shop_id = Column(Integer, default=1, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    guest_email = Column(String(255), nullable=True)
    reply_email = Column(String(255), nullable=False)
    category = Column(String(50), nullable=False)
    subject = Column(String(200), nullable=False)
    related_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    related_order_number = Column(String(32), nullable=True)
    related_product_id = Column(Integer, ForeignKey("cards.id"), nullable=True)
    status = Column(String(32), default="submitted", nullable=False, index=True)
    priority = Column(String(16), default="normal", nullable=False)
    assigned_admin_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    last_message_at = Column(DateTime, nullable=True)
    customer_last_read_at = Column(DateTime, nullable=True)
    admin_last_read_at = Column(DateTime, nullable=True)
    customer_unread_count = Column(Integer, default=0, nullable=False)
    admin_unread_count = Column(Integer, default=0, nullable=False)
    content_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    user = relationship("User", foreign_keys=[user_id])
    assigned_admin = relationship("User", foreign_keys=[assigned_admin_id])
    related_order = relationship("Order", foreign_keys=[related_order_id])
    related_product = relationship("Card", foreign_keys=[related_product_id])
    messages = relationship(
        "InquiryMessage",
        back_populates="inquiry",
        cascade="all, delete-orphan",
        order_by="InquiryMessage.created_at",
    )
    attachments = relationship("InquiryAttachment", back_populates="inquiry", cascade="all, delete-orphan")


class InquiryMessage(Base):
    __tablename__ = "inquiry_messages"

    id = Column(Integer, primary_key=True, index=True)
    inquiry_id = Column(Integer, ForeignKey("inquiries.id"), nullable=False, index=True)
    shop_id = Column(Integer, default=1, nullable=False)
    sender_type = Column(String(16), nullable=False)
    sender_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    sender_admin_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    message = Column(Text, nullable=False)
    is_internal_note = Column(Boolean, default=False, nullable=False)
    template_id = Column(Integer, ForeignKey("inquiry_templates.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    edited_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    inquiry = relationship("Inquiry", back_populates="messages")
    attachments = relationship("InquiryAttachment", back_populates="message", cascade="all, delete-orphan")


class InquiryAttachment(Base):
    __tablename__ = "inquiry_attachments"

    id = Column(Integer, primary_key=True, index=True)
    inquiry_id = Column(Integer, ForeignKey("inquiries.id"), nullable=False, index=True)
    message_id = Column(Integer, ForeignKey("inquiry_messages.id"), nullable=True)
    shop_id = Column(Integer, default=1, nullable=False)
    storage_path = Column(String(512), nullable=False)
    original_filename = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    uploaded_by_type = Column(String(16), nullable=False)
    uploaded_by_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    inquiry = relationship("Inquiry", back_populates="attachments")
    message = relationship("InquiryMessage", back_populates="attachments")


class InquiryTemplate(Base):
    __tablename__ = "inquiry_templates"

    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, default=1, nullable=False, index=True)
    template_type = Column(String(16), nullable=False, index=True)
    category = Column(String(50), nullable=True)
    name = Column(String(128), nullable=False)
    body = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class InquiryStatusHistory(Base):
    __tablename__ = "inquiry_status_history"

    id = Column(Integer, primary_key=True, index=True)
    inquiry_id = Column(Integer, ForeignKey("inquiries.id"), nullable=False, index=True)
    previous_status = Column(String(32), nullable=True)
    new_status = Column(String(32), nullable=False)
    changed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class InquiryReplyDraft(Base):
    __tablename__ = "inquiry_reply_drafts"
    __table_args__ = (UniqueConstraint("inquiry_id", name="uq_inquiry_reply_drafts_inquiry"),)

    id = Column(Integer, primary_key=True, index=True)
    inquiry_id = Column(Integer, ForeignKey("inquiries.id"), nullable=False, index=True)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message = Column(Text, nullable=False, default="")
    email_template_key = Column(String(64), nullable=True)
    new_status = Column(String(32), nullable=True)
    send_email = Column(Boolean, default=True, nullable=False)
    reason = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    inquiry = relationship("Inquiry", backref="reply_draft")
    admin = relationship("User")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    product_name = Column(String(200), nullable=True)

    order = relationship("Order", back_populates="items")
    card = relationship("Card", back_populates="order_items")


class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    title_ja = Column(String(200), nullable=True)
    title_en = Column(String(200), nullable=True)
    content_ja = Column(Text, nullable=True)
    content_en = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="draft", index=True)
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)
    publish_at = Column(DateTime, nullable=True, index=True)
    expire_at = Column(DateTime, nullable=True, index=True)
    thumbnail = Column(String(500), nullable=True)
    show_on_site = Column(Boolean, default=True, nullable=False)
    send_email = Column(Boolean, default=False, nullable=False)
    email_campaign_id = Column(Integer, nullable=True, index=True)
    email_send_status = Column(String(16), nullable=False, default="none", index=True)
    email_scheduled_at = Column(DateTime, nullable=True)
    email_template_key = Column(String(64), nullable=True)
    email_audience_key = Column(String(64), nullable=True)
    email_audience_params_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    images = relationship(
        "AnnouncementImage",
        back_populates="announcement",
        cascade="all, delete-orphan",
        order_by="AnnouncementImage.sort_order",
    )
    reads = relationship(
        "AnnouncementRead",
        back_populates="announcement",
        cascade="all, delete-orphan",
    )


class AnnouncementImage(Base):
    __tablename__ = "announcement_images"

    id = Column(Integer, primary_key=True, index=True)
    announcement_id = Column(
        Integer,
        ForeignKey("announcements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    image_url = Column(String(500), nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)

    announcement = relationship("Announcement", back_populates="images")


class AnnouncementRead(Base):
    __tablename__ = "announcement_reads"
    __table_args__ = (
        UniqueConstraint("announcement_id", "user_id", name="uq_announcement_reads_user"),
    )

    id = Column(Integer, primary_key=True, index=True)
    announcement_id = Column(
        Integer,
        ForeignKey("announcements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    read_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    announcement = relationship("Announcement", back_populates="reads")
    user = relationship("User")


class TranslationCache(Base):
    __tablename__ = "translation_cache"

    id = Column(Integer, primary_key=True, index=True)
    source_text = Column(String(2000), nullable=False, index=True)
    source_lang = Column(String(10), nullable=False, index=True)
    target_lang = Column(String(10), nullable=False, index=True)
    translated_text = Column(String(2000), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ShippingRate(Base):
    __tablename__ = "shipping_rates"

    method_code = Column(String(50), primary_key=True)
    carrier = Column(String(50), nullable=True) # yamato, japan_post, etc.
    name_ja = Column(String(100), nullable=False)
    name_en = Column(String(100), nullable=False)
    fee_jpy = Column(Integer, nullable=False)
    has_tracking = Column(Boolean, default=True)
    has_insurance = Column(Boolean, default=False)
    max_size = Column(String(100), nullable=True)
    max_weight = Column(String(100), nullable=True)
    regional_rates = Column(Text, nullable=True) # JSON dictionary of prefecture -> fee
    is_individual_available = Column(Boolean, default=True)
    is_international_available = Column(Boolean, default=False)
    international_zones = Column(Text, nullable=True) # JSON dictionary of zone -> fee
    max_weight_international = Column(Float, nullable=True)
    insurance_max_amount = Column(Integer, nullable=True)
    insurance_url = Column(String(500), nullable=True)
    estimated_delivery_min_days = Column(Integer, nullable=True)
    estimated_delivery_max_days = Column(Integer, nullable=True)
    is_recommended = Column(Boolean, default=False)
    source_url = Column(String(500), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OrderShipmentLog(Base):
    """Immutable audit trail for order shipping state changes."""

    __tablename__ = "order_shipment_logs"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    from_shipping_status = Column(String(32), nullable=True)
    to_shipping_status = Column(String(32), nullable=True)
    tracking_number = Column(String(100), nullable=True)
    shipping_carrier = Column(String(100), nullable=True)
    admin_user_id = Column(Integer, nullable=True, index=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class OrderBarcode(Base):
    """Opaque scan token for order fulfillment barcodes."""

    __tablename__ = "order_barcodes"

    id = Column(Integer, primary_key=True, index=True)
    scan_token = Column(String(64), unique=True, nullable=False, index=True)
    barcode_type = Column(String(32), nullable=False, default="order_fulfillment", index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    human_readable = Column(String(64), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


import models_buyback  # noqa: F401, E402 — register buyback tables with Base.metadata
import models_admin  # noqa: F401, E402 — register admin security tables with Base.metadata
