"""Buyback channel settings, promo banners, and store reservations."""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models_buyback

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
WEEKDAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
BANNER_CHANNELS = {"store", "mail", "both"}
BUYBACK_METHODS = {"store", "mail"}

DEFAULT_BUSINESS_HOURS = {
    "mon": {"open": "10:00", "close": "19:00", "closed": False},
    "tue": {"open": "10:00", "close": "19:00", "closed": False},
    "wed": {"open": "10:00", "close": "19:00", "closed": False},
    "thu": {"open": "10:00", "close": "19:00", "closed": False},
    "fri": {"open": "10:00", "close": "19:00", "closed": False},
    "sat": {"open": "10:00", "close": "19:00", "closed": False},
    "sun": {"open": "10:00", "close": "19:00", "closed": True},
}


def now_jst() -> datetime:
    return datetime.now(JST)


def now_utc_naive() -> datetime:
    return datetime.utcnow()


def to_naive_utc(dt: datetime) -> datetime:
    """Normalize API/DB datetimes to naive UTC for consistent comparisons."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _parse_hhmm(value: str) -> time:
    parts = value.strip().split(":")
    if len(parts) != 2:
        raise ValueError("invalid time")
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("invalid time")
    return time(hour, minute)


def _weekday_key(d: date) -> str:
    return WEEKDAY_KEYS[d.weekday()]


def _serialize_business_hours(raw: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in WEEKDAY_KEYS:
        day = raw.get(key) or {}
        closed = bool(day.get("closed", False))
        open_s = str(day.get("open") or "10:00")
        close_s = str(day.get("close") or "19:00")
        if not closed:
            _parse_hhmm(open_s)
            _parse_hhmm(close_s)
        out[key] = {"open": open_s, "close": close_s, "closed": closed}
    return out


def _load_business_hours(settings: models_buyback.BuybackChannelSettings) -> dict[str, Any]:
    if not settings.business_hours_json:
        return dict(DEFAULT_BUSINESS_HOURS)
    try:
        parsed = json.loads(settings.business_hours_json)
        if not isinstance(parsed, dict):
            return dict(DEFAULT_BUSINESS_HOURS)
        return _serialize_business_hours(parsed)
    except (json.JSONDecodeError, ValueError):
        return dict(DEFAULT_BUSINESS_HOURS)


def _load_closed_dates(settings: models_buyback.BuybackChannelSettings) -> list[str]:
    if not settings.closed_dates_json:
        return []
    try:
        parsed = json.loads(settings.closed_dates_json)
        if not isinstance(parsed, list):
            return []
        out: list[str] = []
        for item in parsed:
            s = str(item).strip()
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
                date.fromisoformat(s)
                out.append(s)
        return sorted(set(out))
    except (json.JSONDecodeError, ValueError):
        return []


def get_or_create_channel_settings(db: Session) -> models_buyback.BuybackChannelSettings:
    row = (
        db.query(models_buyback.BuybackChannelSettings)
        .filter(models_buyback.BuybackChannelSettings.id == 1)
        .first()
    )
    if row:
        return row
    row = models_buyback.BuybackChannelSettings(
        id=1,
        store_enabled=True,
        mail_enabled=True,
        slot_interval_minutes=30,
        business_hours_json=json.dumps(DEFAULT_BUSINESS_HOURS, ensure_ascii=False),
        closed_dates_json=json.dumps([], ensure_ascii=False),
    )
    db.add(row)
    db.flush()
    return row


def resolve_channel_mode(settings: models_buyback.BuybackChannelSettings) -> str:
    if settings.store_enabled and settings.mail_enabled:
        return "both"
    if settings.store_enabled:
        return "store_only"
    if settings.mail_enabled:
        return "mail_only"
    return "none"


def resolve_allowed_methods(settings: models_buyback.BuybackChannelSettings) -> list[str]:
    mode = resolve_channel_mode(settings)
    if mode == "both":
        return ["store", "mail"]
    if mode == "store_only":
        return ["store"]
    if mode == "mail_only":
        return ["mail"]
    return []


def validate_buyback_method(db: Session, method: Optional[str]) -> str:
    settings = get_or_create_channel_settings(db)
    normalized = (method or "mail").strip().lower()
    if normalized not in BUYBACK_METHODS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="買取方法が不正です")
    allowed = resolve_allowed_methods(settings)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="現在買取を受け付けておりません",
        )
    if normalized not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="選択された買取方法は現在ご利用いただけません",
        )
    return normalized


def _banner_is_active(banner: models_buyback.BuybackPromoBanner, now: datetime) -> bool:
    if not banner.is_visible:
        return False
    starts = to_naive_utc(banner.starts_at)
    ends = to_naive_utc(banner.ends_at)
    now_n = to_naive_utc(now)
    return starts <= now_n <= ends


def resolve_active_product_promo_badge(
    product: models_buyback.BuybackProduct,
    now: Optional[datetime] = None,
) -> Optional[dict[str, str]]:
    text = (product.promo_badge_text or "").strip()
    if not text:
        return None
    now_n = to_naive_utc(now or now_utc_naive())
    if product.promo_badge_starts_at is not None and to_naive_utc(product.promo_badge_starts_at) > now_n:
        return None
    if product.promo_badge_ends_at is not None and to_naive_utc(product.promo_badge_ends_at) < now_n:
        return None
    bg = (product.promo_badge_bg or "").strip() or "#c0392b"
    fg = (product.promo_badge_fg or "").strip() or "#ffffff"
    if not HEX_COLOR_RE.fullmatch(bg):
        bg = "#c0392b"
    if not HEX_COLOR_RE.fullmatch(fg):
        fg = "#ffffff"
    return {"text": text, "background_color": bg, "text_color": fg}


def normalize_product_promo_badge_fields(
    *,
    text: Optional[str],
    bg: Optional[str],
    fg: Optional[str],
    starts_at: Optional[datetime],
    ends_at: Optional[datetime],
) -> tuple[Optional[str], Optional[str], Optional[str], Optional[datetime], Optional[datetime]]:
    normalized_text = (text or "").strip() or None
    if normalized_text and len(normalized_text) > 32:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="バッジ文言は32文字以内で入力してください",
        )
    if not normalized_text:
        return None, None, None, None, None

    normalized_bg = _validate_color((bg or "").strip() or "#c0392b", "バッジ背景色")
    normalized_fg = _validate_color((fg or "").strip() or "#ffffff", "バッジ文字色")
    norm_starts = to_naive_utc(starts_at) if starts_at else None
    norm_ends = to_naive_utc(ends_at) if ends_at else None
    if norm_starts and norm_ends and norm_ends <= norm_starts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="バッジ終了日時は開始日時より後に設定してください",
        )
    return normalized_text, normalized_bg, normalized_fg, norm_starts, norm_ends


def list_active_banners(
    db: Session,
    *,
    channel: Optional[str] = None,
) -> list[models_buyback.BuybackPromoBanner]:
    now = now_utc_naive()
    q = (
        db.query(models_buyback.BuybackPromoBanner)
        .filter(
            models_buyback.BuybackPromoBanner.is_visible.is_(True),
            models_buyback.BuybackPromoBanner.starts_at <= now,
            models_buyback.BuybackPromoBanner.ends_at >= now,
        )
        .order_by(
            models_buyback.BuybackPromoBanner.sort_order.asc(),
            models_buyback.BuybackPromoBanner.id.asc(),
        )
    )
    rows = q.all()
    if not channel:
        return rows
    ch = channel.strip().lower()
    return [b for b in rows if b.target_channel == "both" or b.target_channel == ch]


def list_all_banners_admin(db: Session) -> list[models_buyback.BuybackPromoBanner]:
    return (
        db.query(models_buyback.BuybackPromoBanner)
        .order_by(
            models_buyback.BuybackPromoBanner.sort_order.asc(),
            models_buyback.BuybackPromoBanner.id.desc(),
        )
        .all()
    )


def _validate_color(value: str, field: str) -> str:
    v = (value or "").strip()
    if not HEX_COLOR_RE.fullmatch(v):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field}の形式が不正です",
        )
    return v


def _validate_banner_times(starts_at: datetime, ends_at: datetime) -> None:
    if to_naive_utc(ends_at) <= to_naive_utc(starts_at):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="終了日時は開始日時より後に設定してください",
        )


def _parse_linked_product_ids(raw: Optional[str]) -> list[int]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return sorted({int(item) for item in data if int(item) > 0})
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return []


def load_banner_linked_product_ids(banner: models_buyback.BuybackPromoBanner) -> list[int]:
    return _parse_linked_product_ids(getattr(banner, "linked_product_ids_json", None))


def _dump_linked_product_ids(product_ids: Optional[list[int]]) -> Optional[str]:
    if not product_ids:
        return None
    clean = sorted({int(item) for item in product_ids if int(item) > 0})
    return json.dumps(clean, ensure_ascii=False) if clean else None


def sync_banner_product_badges(
    db: Session,
    banner: models_buyback.BuybackPromoBanner,
    product_ids: list[int],
    *,
    previous_ids: Optional[list[int]] = None,
) -> None:
    previous = set(previous_ids or [])
    new_ids = {int(item) for item in product_ids if int(item) > 0}
    badge_text = (banner.title or "")[:32]

    for product_id in previous - new_ids:
        product = (
            db.query(models_buyback.BuybackProduct)
            .filter(models_buyback.BuybackProduct.id == product_id)
            .first()
        )
        if not product:
            continue
        product.promo_badge_text = None
        product.promo_badge_bg = None
        product.promo_badge_fg = None
        product.promo_badge_starts_at = None
        product.promo_badge_ends_at = None

    for product_id in new_ids:
        product = (
            db.query(models_buyback.BuybackProduct)
            .filter(models_buyback.BuybackProduct.id == product_id)
            .first()
        )
        if not product:
            continue
        product.promo_badge_text = badge_text
        product.promo_badge_bg = banner.background_color
        product.promo_badge_fg = banner.text_color
        product.promo_badge_starts_at = banner.starts_at
        product.promo_badge_ends_at = banner.ends_at


def create_banner(
    db: Session,
    *,
    title: str,
    description: Optional[str],
    target_channel: str,
    starts_at: datetime,
    ends_at: datetime,
    background_color: str,
    text_color: str,
    sort_order: int,
    is_visible: bool,
    linked_product_ids: Optional[list[int]] = None,
) -> models_buyback.BuybackPromoBanner:
    t = (title or "").strip()
    if not t or len(t) > 200:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="タイトルを入力してください")
    ch = (target_channel or "both").strip().lower()
    if ch not in BANNER_CHANNELS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="対象チャネルが不正です")
    starts_at = to_naive_utc(starts_at)
    ends_at = to_naive_utc(ends_at)
    _validate_banner_times(starts_at, ends_at)
    banner = models_buyback.BuybackPromoBanner(
        title=t,
        description=(description or "").strip() or None,
        target_channel=ch,
        starts_at=starts_at,
        ends_at=ends_at,
        background_color=_validate_color(background_color, "背景色"),
        text_color=_validate_color(text_color, "文字色"),
        sort_order=max(0, int(sort_order)),
        is_visible=bool(is_visible),
        linked_product_ids_json=_dump_linked_product_ids(linked_product_ids),
    )
    db.add(banner)
    db.flush()
    sync_banner_product_badges(db, banner, linked_product_ids or [])
    return banner


def update_banner(
    db: Session,
    banner: models_buyback.BuybackPromoBanner,
    **fields: Any,
) -> models_buyback.BuybackPromoBanner:
    previous_linked = load_banner_linked_product_ids(banner)
    if "title" in fields:
        t = (fields["title"] or "").strip()
        if not t or len(t) > 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="タイトルを入力してください")
        banner.title = t
    if "description" in fields:
        banner.description = (fields.get("description") or "").strip() or None
    if "target_channel" in fields:
        ch = (fields["target_channel"] or "both").strip().lower()
        if ch not in BANNER_CHANNELS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="対象チャネルが不正です")
        banner.target_channel = ch
    if "starts_at" in fields:
        banner.starts_at = to_naive_utc(fields["starts_at"])
    if "ends_at" in fields:
        banner.ends_at = to_naive_utc(fields["ends_at"])
    if "starts_at" in fields or "ends_at" in fields:
        _validate_banner_times(banner.starts_at, banner.ends_at)
    if "background_color" in fields:
        banner.background_color = _validate_color(fields["background_color"], "背景色")
    if "text_color" in fields:
        banner.text_color = _validate_color(fields["text_color"], "文字色")
    if "sort_order" in fields:
        banner.sort_order = max(0, int(fields["sort_order"]))
    if "is_visible" in fields:
        banner.is_visible = bool(fields["is_visible"])
    if "linked_product_ids" in fields:
        banner.linked_product_ids_json = _dump_linked_product_ids(fields.get("linked_product_ids"))
    banner.updated_at = now_utc_naive()
    linked = load_banner_linked_product_ids(banner)
    sync_banner_product_badges(db, banner, linked, previous_ids=previous_linked)
    return banner


def get_banner(db: Session, banner_id: int) -> models_buyback.BuybackPromoBanner:
    banner = (
        db.query(models_buyback.BuybackPromoBanner)
        .filter(models_buyback.BuybackPromoBanner.id == banner_id)
        .first()
    )
    if not banner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="バナーが見つかりません")
    return banner


def delete_banner(db: Session, banner: models_buyback.BuybackPromoBanner) -> None:
    previous_linked = load_banner_linked_product_ids(banner)
    sync_banner_product_badges(db, banner, [], previous_ids=previous_linked)
    db.delete(banner)


def update_channel_settings(
    db: Session,
    *,
    store_enabled: Optional[bool] = None,
    mail_enabled: Optional[bool] = None,
    slot_interval_minutes: Optional[int] = None,
    business_hours: Optional[dict[str, Any]] = None,
    closed_dates: Optional[list[str]] = None,
) -> models_buyback.BuybackChannelSettings:
    settings = get_or_create_channel_settings(db)
    if store_enabled is not None:
        settings.store_enabled = bool(store_enabled)
    if mail_enabled is not None:
        settings.mail_enabled = bool(mail_enabled)
    if not settings.store_enabled and not settings.mail_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="店舗買取と郵送買取の両方をOFFにすることはできません",
        )
    if slot_interval_minutes is not None:
        interval = int(slot_interval_minutes)
        if interval not in (15, 30, 60):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="予約枠の間隔は15・30・60分から選択してください",
            )
        settings.slot_interval_minutes = interval
    if business_hours is not None:
        settings.business_hours_json = json.dumps(
            _serialize_business_hours(business_hours),
            ensure_ascii=False,
        )
    if closed_dates is not None:
        cleaned: list[str] = []
        for item in closed_dates:
            s = str(item).strip()
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="定休日の形式が不正です",
                )
            date.fromisoformat(s)
            cleaned.append(s)
        settings.closed_dates_json = json.dumps(sorted(set(cleaned)), ensure_ascii=False)
    settings.updated_at = now_utc_naive()
    return settings


def _is_closed_day(settings: models_buyback.BuybackChannelSettings, d: date) -> bool:
    if d.isoformat() in _load_closed_dates(settings):
        return True
    hours = _load_business_hours(settings)
    day_cfg = hours.get(_weekday_key(d), {})
    return bool(day_cfg.get("closed", False))


def _day_open_close(
    settings: models_buyback.BuybackChannelSettings, d: date
) -> tuple[time, time] | None:
    if _is_closed_day(settings, d):
        return None
    hours = _load_business_hours(settings)
    day_cfg = hours.get(_weekday_key(d), {})
    if day_cfg.get("closed"):
        return None
    return _parse_hhmm(str(day_cfg.get("open") or "10:00")), _parse_hhmm(
        str(day_cfg.get("close") or "19:00")
    )


def _slot_datetimes_for_day(
    settings: models_buyback.BuybackChannelSettings, d: date
) -> list[datetime]:
    bounds = _day_open_close(settings, d)
    if not bounds:
        return []
    open_t, close_t = bounds
    interval = max(15, int(settings.slot_interval_minutes or 30))
    slots: list[datetime] = []
    cursor = datetime.combine(d, open_t, tzinfo=JST)
    end = datetime.combine(d, close_t, tzinfo=JST)
    while cursor < end:
        slots.append(cursor.astimezone(JST).replace(tzinfo=None))
        cursor += timedelta(minutes=interval)
    return slots


def _reserved_visit_at_set(db: Session, visit_dates: list[datetime]) -> set[datetime]:
    if not visit_dates:
        return set()
    rows = (
        db.query(models_buyback.BuybackStoreReservation.visit_at)
        .filter(
            models_buyback.BuybackStoreReservation.visit_at.in_(visit_dates),
            models_buyback.BuybackStoreReservation.status == "confirmed",
        )
        .all()
    )
    return {row[0] for row in rows}


def list_available_slots(db: Session, *, target_date: date) -> list[datetime]:
    settings = get_or_create_channel_settings(db)
    if not settings.store_enabled:
        return []
    today_jst = now_jst().date()
    if target_date < today_jst:
        return []
    now_slot_cutoff = now_jst().replace(tzinfo=None)
    candidates = _slot_datetimes_for_day(settings, target_date)
    if target_date == today_jst:
        candidates = [s for s in candidates if s > now_slot_cutoff]
    reserved = _reserved_visit_at_set(db, candidates)
    return [s for s in candidates if s not in reserved]


def validate_store_visit_at(db: Session, visit_at: datetime) -> datetime:
    settings = get_or_create_channel_settings(db)
    if not settings.store_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="店舗買取は現在受け付けておりません",
        )
    if visit_at.tzinfo is not None:
        visit_local = visit_at.astimezone(JST).replace(tzinfo=None)
    else:
        visit_local = visit_at
    today_jst = now_jst().date()
    if visit_local.date() < today_jst:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="過去の日時は予約できません",
        )
    if visit_local <= now_jst().replace(tzinfo=None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="過去の日時は予約できません",
        )
    allowed = _slot_datetimes_for_day(settings, visit_local.date())
    if visit_local not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="選択された日時は予約できません",
        )
    reserved = _reserved_visit_at_set(db, [visit_local])
    if visit_local in reserved:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="選択された時間枠は既に予約されています",
        )
    return visit_local


def create_store_reservation(
    db: Session,
    *,
    request_id: int,
    user_id: int,
    visit_at: datetime,
) -> models_buyback.BuybackStoreReservation:
    validated = validate_store_visit_at(db, visit_at)
    reservation = models_buyback.BuybackStoreReservation(
        request_id=request_id,
        user_id=user_id,
        visit_at=validated,
        status="confirmed",
    )
    db.add(reservation)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="選択された時間枠は既に予約されています",
        ) from None
    return reservation


def list_reservations_admin(
    db: Session,
    *,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    limit: int = 200,
) -> list[models_buyback.BuybackStoreReservation]:
    q = db.query(models_buyback.BuybackStoreReservation).filter(
        models_buyback.BuybackStoreReservation.status == "confirmed"
    )
    if from_date:
        start = datetime.combine(from_date, time.min)
        q = q.filter(models_buyback.BuybackStoreReservation.visit_at >= start)
    if to_date:
        end = datetime.combine(to_date, time.max)
        q = q.filter(models_buyback.BuybackStoreReservation.visit_at <= end)
    return (
        q.order_by(models_buyback.BuybackStoreReservation.visit_at.asc())
        .limit(min(limit, 500))
        .all()
    )


def seed_starter_content_if_empty(db: Session) -> None:
    """Idempotent production starter: business hours + demo banners when none exist."""
    settings = update_channel_settings(
        db,
        store_enabled=True,
        mail_enabled=True,
        slot_interval_minutes=30,
        business_hours=dict(DEFAULT_BUSINESS_HOURS),
        closed_dates=[],
    )
    _ = settings
    if db.query(models_buyback.BuybackPromoBanner).count() > 0:
        return
    now = now_utc_naive()
    samples = [
        {
            "title": "店舗買取限定価格",
            "description": "買取価格10%UP",
            "target_channel": "store",
            "starts_at": now,
            "ends_at": now + timedelta(days=14),
            "background_color": "#1a1a2e",
            "text_color": "#ffffff",
            "sort_order": 1,
        },
        {
            "title": "郵送買取限定価格",
            "description": "人気カード買取強化中",
            "target_channel": "mail",
            "starts_at": now,
            "ends_at": now + timedelta(days=10),
            "background_color": "#0f3460",
            "text_color": "#ffffff",
            "sort_order": 2,
        },
    ]
    for sample in samples:
        create_banner(db, is_visible=True, **sample)


def get_reservation_for_request(
    db: Session, request_id: int
) -> Optional[models_buyback.BuybackStoreReservation]:
    return (
        db.query(models_buyback.BuybackStoreReservation)
        .filter(models_buyback.BuybackStoreReservation.request_id == request_id)
        .first()
    )
