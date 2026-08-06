"""Render Code 128-B SVG without exposing the encoded credential as text."""

from __future__ import annotations

from html import escape

CODE128_PATTERNS = (
    "212222", "222122", "222221", "121223", "121322", "131222", "122213",
    "122312", "132212", "221213", "221312", "231212", "112232", "122132",
    "122231", "113222", "123122", "123221", "223211", "221132", "221231",
    "213212", "223112", "312131", "311222", "321122", "321221", "312212",
    "322112", "322211", "212123", "212321", "232121", "111323", "131123",
    "131321", "112313", "132113", "132311", "211313", "231113", "231311",
    "112133", "112331", "132131", "113123", "113321", "133121", "313121",
    "211331", "231131", "213113", "213311", "213131", "311123", "311321",
    "331121", "312113", "312311", "332111", "314111", "221411", "431111",
    "111224", "111422", "121124", "121421", "141122", "141221", "112214",
    "112412", "122114", "122411", "142112", "142211", "241211", "221114",
    "413111", "241112", "134111", "111242", "121142", "121241", "114212",
    "124112", "124211", "411212", "421112", "421211", "212141", "214121",
    "412121", "111143", "111341", "131141", "114113", "114311", "411113",
    "411311", "113141", "114131", "311141", "411131", "211412", "211214",
    "211232", "2331112",
)


def render_code128_svg(
    value: str,
    *,
    module_width: int = 2,
    bar_height: int = 64,
    aria_label: str = "物流バーコード",
) -> str:
    if not value or any(ord(char) < 32 or ord(char) > 126 for char in value):
        raise ValueError("Code 128-B supports printable ASCII only")

    start_code = 104
    data_codes = [ord(char) - 32 for char in value]
    checksum = (start_code + sum(code * index for index, code in enumerate(data_codes, 1))) % 103
    codes = [start_code, *data_codes, checksum, 106]
    patterns = [CODE128_PATTERNS[code] for code in codes]

    quiet_modules = 10
    content_modules = sum(sum(int(width) for width in pattern) for pattern in patterns)
    width = (content_modules + quiet_modules * 2) * module_width
    x = quiet_modules * module_width
    bars: list[str] = []
    for pattern in patterns:
        draw_bar = True
        for width_code in pattern:
            segment_width = int(width_code) * module_width
            if draw_bar:
                bars.append(
                    f'<rect x="{x}" y="0" width="{segment_width}" '
                    f'height="{bar_height}" fill="#000"/>'
                )
            x += segment_width
            draw_bar = not draw_bar

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="{escape(aria_label)}" viewBox="0 0 {width} {bar_height}" '
        f'width="{width}" height="{bar_height}" shape-rendering="crispEdges">'
        f'<rect width="{width}" height="{bar_height}" fill="#fff"/>'
        f'{"".join(bars)}</svg>'
    )


# --- Phase 2 order fulfillment helpers (barcodes, shipment logs, dashboard KPIs) ---

import re
import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

import models
import models_buyback


SCAN_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")


def generate_order_scan_token() -> str:
    return secrets.token_urlsafe(32)


def append_order_shipment_log(
    db: Session,
    *,
    order: models.Order,
    event_type: str,
    from_shipping_status: Optional[str] = None,
    to_shipping_status: Optional[str] = None,
    tracking_number: Optional[str] = None,
    shipping_carrier: Optional[str] = None,
    admin_user_id: Optional[int] = None,
    note: Optional[str] = None,
) -> models.OrderShipmentLog:
    row = models.OrderShipmentLog(
        order_id=order.id,
        event_type=event_type,
        from_shipping_status=from_shipping_status,
        to_shipping_status=to_shipping_status or order.shipping_status,
        tracking_number=tracking_number or order.tracking_number,
        shipping_carrier=shipping_carrier or order.shipping_carrier,
        admin_user_id=admin_user_id,
        note=note,
    )
    db.add(row)
    db.flush()
    return row


def list_order_shipment_logs(
    db: Session,
    order_id: int,
    *,
    limit: int = 100,
) -> list[models.OrderShipmentLog]:
    return (
        db.query(models.OrderShipmentLog)
        .filter(models.OrderShipmentLog.order_id == order_id)
        .order_by(models.OrderShipmentLog.created_at.desc())
        .limit(limit)
        .all()
    )


def ensure_order_barcode(
    db: Session,
    *,
    order: models.Order,
    barcode_type: str = "order_fulfillment",
) -> models.OrderBarcode:
    existing = get_active_order_barcode(db, order_id=order.id, barcode_type=barcode_type)
    if existing:
        return existing
    human = order.order_number or f"ORD-{order.id}"
    for _ in range(10):
        token = generate_order_scan_token()
        exists = (
            db.query(models.OrderBarcode.id)
            .filter(models.OrderBarcode.scan_token == token)
            .first()
        )
        if exists:
            continue
        row = models.OrderBarcode(
            scan_token=token,
            barcode_type=barcode_type,
            order_id=order.id,
            human_readable=human,
        )
        db.add(row)
        db.flush()
        return row
    raise RuntimeError("Failed to generate unique order scan token")


def get_active_order_barcode(
    db: Session,
    *,
    order_id: int,
    barcode_type: Optional[str] = None,
) -> models.OrderBarcode | None:
    query = db.query(models.OrderBarcode).filter(
        models.OrderBarcode.order_id == order_id,
        models.OrderBarcode.is_active.is_(True),
    )
    if barcode_type:
        query = query.filter(models.OrderBarcode.barcode_type == barcode_type)
    return query.order_by(models.OrderBarcode.created_at.desc()).first()


def lookup_order_barcode_by_token(
    db: Session, scan_token: str
) -> models.OrderBarcode | None:
    token = (scan_token or "").strip()
    if not SCAN_TOKEN_PATTERN.fullmatch(token):
        return None
    return (
        db.query(models.OrderBarcode)
        .filter(
            models.OrderBarcode.scan_token == token,
            models.OrderBarcode.is_active.is_(True),
        )
        .first()
    )


def resolve_order_by_scan_code(db: Session, code: str) -> models.Order | None:
    token = (code or "").strip()
    if not token:
        return None

    barcode = lookup_order_barcode_by_token(db, token)
    if barcode:
        return db.query(models.Order).filter(models.Order.id == barcode.order_id).first()

    order = db.query(models.Order).filter(models.Order.order_number == token).first()
    if order:
        return order

    if token.startswith("#") and token[1:].isdigit():
        return db.query(models.Order).filter(models.Order.id == int(token[1:])).first()

    if token.isdigit():
        return db.query(models.Order).filter(models.Order.id == int(token)).first()

    barcode_hr = (
        db.query(models.OrderBarcode)
        .filter(
            models.OrderBarcode.human_readable == token,
            models.OrderBarcode.is_active.is_(True),
        )
        .first()
    )
    if barcode_hr:
        return db.query(models.Order).filter(models.Order.id == barcode_hr.order_id).first()

    return None


def _day_bounds_utc(now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or datetime.utcnow()
    start = datetime(now.year, now.month, now.day)
    return start, start + timedelta(days=1)


def _month_bounds_utc(now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or datetime.utcnow()
    start = datetime(now.year, now.month, 1)
    if now.month == 12:
        end = datetime(now.year + 1, 1, 1)
    else:
        end = datetime(now.year, now.month + 1, 1)
    return start, end


def get_admin_dashboard_stats(db: Session) -> dict[str, int]:
    from services.buyback_admin import identity_stats, request_stats

    today_start, today_end = _day_bounds_utc()
    month_start, month_end = _month_bounds_utc()
    paid_filter = models.Order.payment_status == "paid"

    today_sales = (
        db.query(func.coalesce(func.sum(models.Order.total_amount), 0))
        .filter(paid_filter, models.Order.paid_at >= today_start, models.Order.paid_at < today_end)
        .scalar()
    ) or 0
    month_sales = (
        db.query(func.coalesce(func.sum(models.Order.total_amount), 0))
        .filter(paid_filter, models.Order.paid_at >= month_start, models.Order.paid_at < month_end)
        .scalar()
    ) or 0
    orders_today = (
        db.query(func.count(models.Order.id))
        .filter(models.Order.created_at >= today_start, models.Order.created_at < today_end)
        .scalar()
    ) or 0
    pending_ship = (
        db.query(func.count(models.Order.id))
        .filter(paid_filter, models.Order.shipping_status.in_(["unshipped", "preparing", "packing"]))
        .scalar()
    ) or 0
    assessing_statuses = [
        models_buyback.BuybackRequestStatus.received.value,
        models_buyback.BuybackRequestStatus.assessing.value,
        models_buyback.BuybackRequestStatus.store_visited.value,
    ]
    pending_assess = (
        db.query(func.count(models_buyback.BuybackRequest.id))
        .filter(models_buyback.BuybackRequest.status.in_(assessing_statuses))
        .scalar()
    ) or 0
    new_members_today = (
        db.query(func.count(models.User.id))
        .filter(models.User.created_at >= today_start, models.User.created_at < today_end)
        .scalar()
    ) or 0
    unreplied = (
        db.query(func.count(models.Inquiry.id))
        .filter(models.Inquiry.shop_id == 1, models.Inquiry.admin_unread_count > 0)
        .scalar()
    ) or 0
    draft_announcements = (
        db.query(func.count(models.Announcement.id))
        .filter(models.Announcement.status == "draft")
        .scalar()
    ) or 0
    kyc = identity_stats(db)
    buyback = request_stats(db)
    from services.live_streams import count_live_sessions

    live_count = count_live_sessions(db)
    return {
        "today_sales": int(today_sales),
        "month_sales": int(month_sales),
        "orders_today": int(orders_today),
        "pending_ship": int(pending_ship),
        "pending_assess": int(pending_assess),
        "live_sessions": int(live_count),
        "auction_sessions": 0,
        "new_members_today": int(new_members_today),
        "unread_inquiries": int(unreplied),
        "draft_announcements": int(draft_announcements),
        "buyback_pending_kyc": int(kyc.get("pending_count", 0)),
        "buyback_submitted_requests": int(buyback.get("submitted_count", 0)),
        "buyback_payout_pending": int(buyback.get("payout_pending_count", 0)),
    }
