from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Float,
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


class User(Base):
    """User model with full address support for Japan standards"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)
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
    created_at = Column(DateTime, default=datetime.utcnow)

    cart_items = relationship("CartItem", back_populates="user", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="user")
    favorites = relationship("Favorite", back_populates="user", cascade="all, delete-orphan")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
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
    stock = Column(Integer, default=0)
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
    payment_method = Column(String(50), nullable=True)
    payment_status = Column(String(50), default="pending")
    stripe_checkout_session_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)

    order = relationship("Order", back_populates="items")
    card = relationship("Card", back_populates="order_items")


class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


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
