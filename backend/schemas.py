from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, field_validator
from models import OrderStatus, CARD_RARITIES


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
    slug: str
    parent_id: Optional[int] = None
    sort_order: int = 0


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None


class CategoryOut(CategoryBase):
    id: int
    children: List[CategoryOut] = []

    class Config:
        from_attributes = True


# ─────────────────────────── Card ────────────────────────────

class CardBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    stock: int = 0
    image_url: Optional[str] = None
    image_urls: Optional[str] = None  # JSON array string
    category_id: Optional[int] = None
    rarity: Optional[str] = None
    set_name: Optional[str] = None
    condition: Optional[str] = None
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
    description: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    image_url: Optional[str] = None
    image_urls: Optional[str] = None
    category_id: Optional[int] = None
    rarity: Optional[str] = None
    set_name: Optional[str] = None
    condition: Optional[str] = None
    is_active: Optional[bool] = None


class CardOut(CardBase):
    id: int
    created_at: datetime
    category: Optional[CategoryOut] = None

    class Config:
        from_attributes = True


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


# ─────────────────────────── Order ───────────────────────────

class OrderItemOut(BaseModel):
    id: int
    card_id: int
    quantity: int
    unit_price: float
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
    created_at: datetime
    items: List[OrderItemOut] = []

    class Config:
        from_attributes = True


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


# ─────────────────────────── Announcement ────────────────────

class AnnouncementBase(BaseModel):
    title: str
    content: str
    is_active: bool = True
    priority: int = 0


class AnnouncementCreate(AnnouncementBase):
    pass


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None


class AnnouncementOut(AnnouncementBase):
    id: int
    created_at: datetime

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
