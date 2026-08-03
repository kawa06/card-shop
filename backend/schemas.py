from __future__ import annotations
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, field_validator, model_validator
from models import OrderStatus, CARD_RARITIES
from services.pokemon_names import translate_pokemon_name


# ─────────────────────────── Token ───────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[int] = None


# ─────────────────────────── User ────────────────────────────

class UserBase(BaseModel):
    email: EmailStr
    name: str


class UserCreate(UserBase):
    password: str
    phone_number: Optional[str] = None
    phone_verification_code: Optional[str] = None

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class UserOut(UserBase):
    id: int
    is_admin: bool
    is_verified: bool
    family_name: Optional[str] = None
    given_name: Optional[str] = None
    family_name_kana: Optional[str] = None
    given_name_kana: Optional[str] = None
    birth_date: Optional[date] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    address: Optional[str] = None
    phone_number: Optional[str] = None
    phone_verified: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    name: Optional[str] = None
    family_name: Optional[str] = None
    given_name: Optional[str] = None
    family_name_kana: Optional[str] = None
    given_name_kana: Optional[str] = None
    birth_date: Optional[date] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    address: Optional[str] = None
    phone_number: Optional[str] = None


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str


class PhoneAuthRequest(BaseModel):
    phone: str


class PhoneVerifyRequest(BaseModel):
    phone: str
    code: str


# ─────────────────────────── Category ────────────────────────

class CategoryBase(BaseModel):
    name: str
    name_en: Optional[str] = None
    slug: str
    parent_id: Optional[int] = None
    sort_order: int = 0


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    name_en: Optional[str] = None
    slug: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None


class CategoryOut(CategoryBase):
    id: int
    children: List[CategoryOut] = []

    class Config:
        from_attributes = True


# ─────────────────────────── Pack ──────────────────────────────

class PackBase(BaseModel):
    name: str
    name_en: Optional[str] = None
    slug: str
    sort_order: int = 0


class PackCreate(PackBase):
    pass


class PackUpdate(BaseModel):
    name: Optional[str] = None
    name_en: Optional[str] = None
    slug: Optional[str] = None
    sort_order: Optional[int] = None


class PackOut(PackBase):
    id: int

    class Config:
        from_attributes = True


# ─────────────────────────── Card ────────────────────────────

class CardBase(BaseModel):
    name: str
    name_en: Optional[str] = None
    description: Optional[str] = None
    price: float
    price_usd: Optional[float] = None
    stock: int = 0
    image_url: Optional[str] = None
    image_urls: Optional[str] = None  # JSON array string
    category_id: Optional[int] = None
    pack_id: Optional[int] = None
    rarity: Optional[str] = None
    set_name: Optional[str] = None
    condition: Optional[str] = None
    allowed_shipping_methods: Optional[str] = None  # JSON array string
    is_active: bool = True

    @field_validator("rarity")
    @classmethod
    def validate_rarity(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in CARD_RARITIES:
            raise ValueError(f"Invalid rarity. Must be one of: {', '.join(CARD_RARITIES)}")
        return v


class CardCreate(CardBase):
    pass


class CardUpdate(BaseModel):
    name: Optional[str] = None
    name_en: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    price_usd: Optional[float] = None
    stock: Optional[int] = None
    image_url: Optional[str] = None
    image_urls: Optional[str] = None
    category_id: Optional[int] = None
    pack_id: Optional[int] = None
    rarity: Optional[str] = None
    set_name: Optional[str] = None
    condition: Optional[str] = None
    allowed_shipping_methods: Optional[str] = None
    is_active: Optional[bool] = None


class CardShippingMethodsUpdate(BaseModel):
    allowed_shipping_methods: Optional[str] = None


class CardOut(CardBase):
    id: int
    created_at: datetime
    category: Optional[CategoryOut] = None
    pack: Optional[PackOut] = None

    class Config:
        from_attributes = True

    @model_validator(mode='after')
    def populate_name_en(self) -> 'CardOut':
        if self.name_en is None:
            translated = translate_pokemon_name(self.name)
            if translated:
                self.name_en = translated
        return self


# ─────────────────────────── Cart ────────────────────────────

class CartItemBase(BaseModel):
    card_id: int
    quantity: int = 1

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Quantity must be at least 1")
        return v


class CartItemCreate(CartItemBase):
    pass


class CartItemUpdate(BaseModel):
    quantity: int

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Quantity must be at least 1")
        return v


class CartItemOut(CartItemBase):
    id: int
    created_at: datetime
    card: CardOut

    class Config:
        from_attributes = True


# ─────────────────────────── Favorites ────────────────────────────

class FavoriteOut(BaseModel):
    id: int
    card_id: int
    created_at: datetime
    card: CardOut

    class Config:
        from_attributes = True


class FavoriteActionOut(BaseModel):
    id: int
    card_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────── Order ───────────────────────────

class OrderItemOut(BaseModel):
    id: int
    card_id: int
    quantity: int
    unit_price: float
    product_name: Optional[str] = None
    card: CardOut

    class Config:
        from_attributes = True


class OrderCreate(BaseModel):
    postal_code: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    shipping_address: Optional[str] = None
    shipping_method: Optional[str] = None
    shipping_fee: int = 0
    payment_method: Optional[str] = "bank_transfer"


class StripeCheckoutSessionCreate(BaseModel):
    postal_code: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    shipping_address: Optional[str] = None
    shipping_method: Optional[str] = None
    locale: Optional[str] = "ja"
    checkout_type: Optional[str] = "card"


class StripeCheckoutSessionOut(BaseModel):
    checkout_url: str
    session_id: str
    order_id: int


class StripeCheckoutConfirmOut(BaseModel):
    order: "OrderOut"
    payment_status: str
    pending_bank_transfer: bool = False


class OrderOut(BaseModel):
    id: int
    user_id: int
    total_amount: float
    status: OrderStatus
    postal_code: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    shipping_address: Optional[str]
    shipping_method: Optional[str] = None
    shipping_fee: int = 0
    items_subtotal: int = 0
    tax_rate_snapshot: Optional[int] = None
    payment_method: Optional[str] = None
    payment_status: Optional[str] = None
    payment_deadline: Optional[datetime] = None
    stock_reserved: bool = False
    paid_at: Optional[datetime] = None
    order_number: Optional[str] = None
    stripe_payment_intent_id: Optional[str] = None
    stripe_event_id: Optional[str] = None
    shipping_status: Optional[str] = "unshipped"
    shipping_carrier: Optional[str] = None
    tracking_number: Optional[str] = None
    shipped_at: Optional[datetime] = None
    purchase_email_sent_at: Optional[datetime] = None
    shipping_email_sent_at: Optional[datetime] = None
    email_send_status: Optional[str] = None
    admin_note: Optional[str] = None
    discount_amount: int = 0
    coupon_code: Optional[str] = None
    coupon_name: Optional[str] = None
    payment_fee: int = 0
    packaging_fee: int = 0
    buyer_note: Optional[str] = None
    buyer_phone: Optional[str] = None
    click_post_csv_exported_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    items: List[OrderItemOut] = []

    class Config:
        from_attributes = True


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class OrderShippingUpdate(BaseModel):
    shipping_status: Optional[str] = None
    shipping_carrier: Optional[str] = None
    tracking_number: Optional[str] = None
    shipped_at: Optional[datetime] = None
    admin_note: Optional[str] = None


class AdminOrderOut(OrderOut):
    buyer_name: Optional[str] = None
    buyer_email: Optional[str] = None

    class Config:
        from_attributes = True


class AdminOrderDetailOut(AdminOrderOut):
    """Full order payload for admin detail / printable documents."""

    stripe_checkout_session_id: Optional[str] = None

    class Config:
        from_attributes = True


class PaymentDeadlineExtend(BaseModel):
    hours: Optional[int] = None
    payment_deadline: Optional[datetime] = None


class TaxBreakdownRowOut(BaseModel):
    rate_percent: int
    amount_inclusive: int
    consumption_tax: int


class InvoiceConfigOut(BaseModel):
    invoice_enabled: bool = False
    invoice_registration_number: Optional[str] = None
    invoice_issuer_name: Optional[str] = None
    default_tax_rate: int = 10
    qualified_invoice_enabled: bool = False


class InvoiceSettingsUpdate(BaseModel):
    invoice_enabled: Optional[bool] = None
    invoice_registration_number: Optional[str] = None
    invoice_issuer_name: Optional[str] = None
    default_tax_rate: Optional[int] = None


class AdminClickPostOrderOut(BaseModel):
    id: int
    buyer_name: str
    postal_code: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    product_names: str
    created_at: datetime
    payment_status: Optional[str] = None
    click_post_csv_exported_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ClickPostExportRequest(BaseModel):
    order_ids: List[int]
    mark_exported: bool = True


# ─────────────────────────── Inquiries ───────────────────────

class InquiryMessageOut(BaseModel):
    id: int
    sender_type: str
    message: str
    is_internal_note: bool = False
    template_id: Optional[int] = None
    created_at: datetime
    sender_name: Optional[str] = None

    class Config:
        from_attributes = True


class InquiryAttachmentOut(BaseModel):
    id: int
    message_id: Optional[int] = None
    original_filename: str
    mime_type: str
    file_size: int
    created_at: datetime
    download_url: Optional[str] = None

    class Config:
        from_attributes = True


class InquiryListOut(BaseModel):
    id: int
    inquiry_number: str
    category: str
    subject: str
    related_order_number: Optional[str] = None
    status: str
    priority: str = "normal"
    last_message_at: Optional[datetime] = None
    customer_unread_count: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class InquiryDetailOut(InquiryListOut):
    reply_email: str
    related_order_id: Optional[int] = None
    related_product_id: Optional[int] = None
    related_product_name: Optional[str] = None
    messages: List[InquiryMessageOut] = []
    attachments: List[InquiryAttachmentOut] = []


class InquiryCreate(BaseModel):
    category: str
    subject: str
    message: str
    reply_email: Optional[str] = None
    related_order_id: Optional[int] = None
    related_product_id: Optional[int] = None
    template_id: Optional[int] = None


class InquiryMessageCreate(BaseModel):
    message: str


class InquiryTemplateOut(BaseModel):
    id: int
    template_type: str
    category: Optional[str] = None
    name: str
    body: str
    is_active: bool = True
    sort_order: int = 0

    class Config:
        from_attributes = True


class InquiryTemplatePreview(BaseModel):
    body: str
    warnings: List[str] = []


class AdminInquiryListOut(InquiryListOut):
    buyer_name: Optional[str] = None
    buyer_email: Optional[str] = None
    assigned_admin_name: Optional[str] = None
    admin_unread_count: int = 0


class AdminInquiryReply(BaseModel):
    message: str
    is_internal_note: bool = False
    template_id: Optional[int] = None
    status: Optional[str] = None
    assigned_admin_id: Optional[int] = None
    reason: Optional[str] = None


class AdminInquiryUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_admin_id: Optional[int] = None


class InquiryStatsOut(BaseModel):
    unreplied_count: int
    today_count: int
    in_progress_count: int
    waiting_customer_count: int
    resolved_count: int
    high_priority_count: int


class InquirySettingsOut(BaseModel):
    enabled: bool = True
    attachments_enabled: bool = True
    max_attachments: int = 5
    max_attachment_bytes: int = 5242880
    auto_reply_enabled: bool = True
    allow_reopen_resolved: bool = True
    auto_close_days: int = 30

    class Config:
        from_attributes = True


class InquirySettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    attachments_enabled: Optional[bool] = None
    max_attachments: Optional[int] = None
    max_attachment_bytes: Optional[int] = None
    auto_reply_enabled: Optional[bool] = None
    auto_reply_body: Optional[str] = None
    allow_reopen_resolved: Optional[bool] = None
    auto_close_days: Optional[int] = None


class InquiryTemplateCreate(BaseModel):
    template_type: str
    category: Optional[str] = None
    name: str
    body: str
    is_active: bool = True
    sort_order: int = 0


class InquiryTemplateUpdate(BaseModel):
    category: Optional[str] = None
    name: Optional[str] = None
    body: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


# ─────────────────────────── Announcement ────────────────────

class AnnouncementImageOut(BaseModel):
    id: int
    image_url: str
    sort_order: int

    class Config:
        from_attributes = True


class AnnouncementBase(BaseModel):
    title: str
    content: str
    is_active: bool = True
    priority: int = 0


class AnnouncementCreate(AnnouncementBase):
    title_ja: Optional[str] = None
    title_en: Optional[str] = None
    content_ja: Optional[str] = None
    content_en: Optional[str] = None
    status: Optional[str] = None
    publish_at: Optional[datetime] = None
    expire_at: Optional[datetime] = None
    thumbnail: Optional[str] = None
    image_urls: List[str] = []
    show_on_site: bool = True
    send_email: bool = False


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    title_ja: Optional[str] = None
    title_en: Optional[str] = None
    content_ja: Optional[str] = None
    content_en: Optional[str] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None
    publish_at: Optional[datetime] = None
    expire_at: Optional[datetime] = None
    clear_publish_at: Optional[bool] = None
    clear_expire_at: Optional[bool] = None
    thumbnail: Optional[str] = None
    image_urls: Optional[List[str]] = None
    show_on_site: Optional[bool] = None
    send_email: Optional[bool] = None


class AnnouncementOut(AnnouncementBase):
    id: int
    created_at: datetime
    title_ja: Optional[str] = None
    title_en: Optional[str] = None
    content_ja: Optional[str] = None
    content_en: Optional[str] = None
    status: Optional[str] = None
    publish_at: Optional[datetime] = None
    expire_at: Optional[datetime] = None
    thumbnail: Optional[str] = None
    updated_at: Optional[datetime] = None
    images: List[AnnouncementImageOut] = []
    is_new: bool = False
    is_read: Optional[bool] = None
    content_excerpt: Optional[str] = None

    class Config:
        from_attributes = True


class AnnouncementFeedOut(BaseModel):
    items: List[AnnouncementOut]
    unread_count: int = 0


class AnnouncementUnreadCountOut(BaseModel):
    count: int


class AnnouncementAdminOut(BaseModel):
    id: int
    title: str
    content: str
    title_ja: str
    title_en: str
    content_ja: str
    content_en: str
    status: str
    is_active: bool
    priority: int
    publish_at: Optional[datetime] = None
    expire_at: Optional[datetime] = None
    thumbnail: Optional[str] = None
    show_on_site: bool = True
    send_email: bool = False
    email_campaign_id: Optional[int] = None
    email_send_status: str = "none"
    email_scheduled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    images: List[AnnouncementImageOut] = []

    class Config:
        from_attributes = True


# ─────────────────────────── Pagination ──────────────────────

class PaginatedCards(BaseModel):
    items: List[CardOut]
    total: int
    page: int
    per_page: int
    pages: int


# ─────────────────────────── Exchange Rate ───────────────────

class ExchangeRateResponse(BaseModel):
    rate: float
    last_updated: int  # Timestamp


# ─────────────────────────── Shipping ────────────────────────

class ShippingRateOut(BaseModel):
    method_code: str
    carrier: Optional[str] = None
    name_ja: str
    name_en: str
    fee_jpy: int
    has_tracking: bool
    has_insurance: bool
    is_individual_available: bool
    is_international_available: bool
    international_zones: Optional[str] = None
    max_weight_international: Optional[float] = None
    insurance_max_amount: Optional[int] = None
    insurance_url: Optional[str] = None
    estimated_delivery_min_days: Optional[int] = None
    estimated_delivery_max_days: Optional[int] = None
    is_recommended: bool
    regional_rates: Optional[str] = None
    max_size: Optional[str] = None
    max_weight: Optional[str] = None
    source_url: Optional[str] = None
    updated_at: datetime

    class Config:
        from_attributes = True


class ShippingRateUpdate(BaseModel):
    name_ja: Optional[str] = None
    name_en: Optional[str] = None
    fee_jpy: Optional[int] = None
    has_tracking: Optional[bool] = None
    has_insurance: Optional[bool] = None
    is_individual_available: Optional[bool] = None
    is_international_available: Optional[bool] = None
    international_zones: Optional[str] = None
    max_weight_international: Optional[float] = None
    insurance_max_amount: Optional[int] = None
    insurance_url: Optional[str] = None
    estimated_delivery_min_days: Optional[int] = None
    estimated_delivery_max_days: Optional[int] = None
    is_recommended: Optional[bool] = None
    max_size: Optional[str] = None
    max_weight: Optional[str] = None
    source_url: Optional[str] = None
