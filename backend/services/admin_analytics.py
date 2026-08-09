"""Phase 3-7 admin analytics aggregations (read-only over existing tables)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

import models
import models_coupons
import models_live
import models_live_auction
import models_points
import schemas_analytics


ALLOWED_DOMAINS = ("sales", "live", "auctions", "coupons", "points")
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200
MAX_EXPORT_ROWS = 5000


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"Invalid datetime: {value}") from exc
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt


def parse_range(
    from_at: Optional[str],
    to_at: Optional[str],
) -> tuple[Optional[datetime], Optional[datetime]]:
    start = _parse_dt(from_at)
    end = _parse_dt(to_at)
    if start and end and start > end:
        raise ValueError("from_at must be <= to_at")
    return start, end


def _clamp_paging(page: int, size: int) -> tuple[int, int]:
    page = max(1, int(page or 1))
    size = min(MAX_PAGE_SIZE, max(1, int(size or DEFAULT_PAGE_SIZE)))
    return page, size


def _apply_created_range(query, column, start: Optional[datetime], end: Optional[datetime]):
    if start is not None:
        query = query.filter(column >= start)
    if end is not None:
        query = query.filter(column < end)
    return query


def build_kpi(
    db: Session,
    *,
    from_at: Optional[datetime] = None,
    to_at: Optional[datetime] = None,
) -> schemas_analytics.AnalyticsKpiOut:
    paid_q = db.query(models.Order).filter(models.Order.payment_status == "paid")
    paid_q = _apply_created_range(paid_q, models.Order.paid_at, from_at, to_at)
    paid_order_count = paid_q.count()

    sales_q = db.query(func.coalesce(func.sum(models.Order.total_amount), 0)).filter(
        models.Order.payment_status == "paid"
    )
    sales_q = _apply_created_range(sales_q, models.Order.paid_at, from_at, to_at)
    paid_sales = int(sales_q.scalar() or 0)

    discount_q = db.query(func.coalesce(func.sum(models.Order.discount_amount), 0)).filter(
        models.Order.payment_status == "paid"
    )
    discount_q = _apply_created_range(discount_q, models.Order.paid_at, from_at, to_at)
    coupon_discount = int(discount_q.scalar() or 0)

    points_used_q = db.query(func.coalesce(func.sum(models.Order.points_used), 0)).filter(
        models.Order.payment_status == "paid"
    )
    points_used_q = _apply_created_range(points_used_q, models.Order.paid_at, from_at, to_at)
    points_used = int(points_used_q.scalar() or 0)

    points_earned_q = db.query(func.coalesce(func.sum(models.Order.points_earned), 0)).filter(
        models.Order.payment_status == "paid"
    )
    points_earned_q = _apply_created_range(points_earned_q, models.Order.paid_at, from_at, to_at)
    points_earned = int(points_earned_q.scalar() or 0)

    live_q = db.query(func.count(models_live.LiveStream.id))
    live_q = _apply_created_range(live_q, models_live.LiveStream.created_at, from_at, to_at)
    live_stream_count = int(live_q.scalar() or 0)

    live_live_q = db.query(func.count(models_live.LiveStream.id)).filter(
        models_live.LiveStream.status == "live"
    )
    live_live_count = int(live_live_q.scalar() or 0)

    auction_q = db.query(func.count(models_live_auction.LiveAuction.id))
    auction_q = _apply_created_range(auction_q, models_live_auction.LiveAuction.created_at, from_at, to_at)
    auction_count = int(auction_q.scalar() or 0)

    sold_statuses = ("sold", "completed", "won", "ended")
    sold_q = db.query(func.count(models_live_auction.LiveAuction.id)).filter(
        or_(
            models_live_auction.LiveAuction.winner_user_id.isnot(None),
            models_live_auction.LiveAuction.status.in_(sold_statuses),
        )
    )
    sold_q = _apply_created_range(sold_q, models_live_auction.LiveAuction.created_at, from_at, to_at)
    auction_sold_count = int(sold_q.scalar() or 0)

    gmv_q = db.query(func.coalesce(func.sum(models_live_auction.LiveAuction.winning_amount), 0))
    gmv_q = gmv_q.filter(models_live_auction.LiveAuction.winning_amount.isnot(None))
    gmv_q = _apply_created_range(gmv_q, models_live_auction.LiveAuction.created_at, from_at, to_at)
    auction_gmv = int(gmv_q.scalar() or 0)

    coupon_active = int(
        db.query(func.count(models_coupons.Coupon.id))
        .filter(models_coupons.Coupon.is_active.is_(True))
        .scalar()
        or 0
    )
    redemption_q = db.query(func.count(models_coupons.CouponRedemption.id)).filter(
        models_coupons.CouponRedemption.status == "used"
    )
    redemption_q = _apply_created_range(
        redemption_q, models_coupons.CouponRedemption.created_at, from_at, to_at
    )
    coupon_redemption_count = int(redemption_q.scalar() or 0)

    members_q = db.query(func.count(models.User.id))
    members_q = _apply_created_range(members_q, models.User.created_at, from_at, to_at)
    new_members = int(members_q.scalar() or 0)

    avg_order = int(paid_sales / paid_order_count) if paid_order_count else 0

    return schemas_analytics.AnalyticsKpiOut(
        from_at=from_at,
        to_at=to_at,
        paid_order_count=paid_order_count,
        paid_sales_yen=paid_sales,
        avg_order_yen=avg_order,
        coupon_discount_yen=coupon_discount,
        points_used=points_used,
        points_earned=points_earned,
        live_stream_count=live_stream_count,
        live_live_count=live_live_count,
        auction_count=auction_count,
        auction_sold_count=auction_sold_count,
        auction_gmv_yen=auction_gmv,
        coupon_active_count=coupon_active,
        coupon_redemption_count=coupon_redemption_count,
        new_members=new_members,
    )


def _sales_series(db: Session, start: Optional[datetime], end: Optional[datetime]) -> list[schemas_analytics.AnalyticsSeriesPoint]:
    day_col = func.date(models.Order.paid_at)
    q = (
        db.query(day_col.label("d"), func.coalesce(func.sum(models.Order.total_amount), 0))
        .filter(models.Order.payment_status == "paid", models.Order.paid_at.isnot(None))
    )
    q = _apply_created_range(q, models.Order.paid_at, start, end)
    rows = q.group_by(day_col).order_by(day_col.asc()).limit(366).all()
    out: list[schemas_analytics.AnalyticsSeriesPoint] = []
    for d, value in rows:
        if d is None:
            continue
        out.append(schemas_analytics.AnalyticsSeriesPoint(date=str(d), value=int(value or 0)))
    return out


def list_sales(
    db: Session,
    *,
    from_at: Optional[datetime] = None,
    to_at: Optional[datetime] = None,
    q: Optional[str] = None,
    payment_status: Optional[str] = None,
    shipping_status: Optional[str] = None,
    sort: str = "paid_at",
    order: str = "desc",
    page: int = 1,
    size: int = DEFAULT_PAGE_SIZE,
) -> schemas_analytics.AnalyticsListOut:
    page, size = _clamp_paging(page, size)
    query = db.query(models.Order)
    query = _apply_created_range(query, models.Order.paid_at, from_at, to_at)
    if payment_status:
        query = query.filter(models.Order.payment_status == payment_status)
    if shipping_status:
        query = query.filter(models.Order.shipping_status == shipping_status)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                models.Order.order_number.ilike(like),
                models.Order.coupon_code.ilike(like),
                models.Order.coupon_name.ilike(like),
            )
        )

    sort_map = {
        "paid_at": models.Order.paid_at,
        "created_at": models.Order.created_at,
        "total_amount": models.Order.total_amount,
        "discount_amount": models.Order.discount_amount,
        "order_id": models.Order.id,
    }
    sort_col = sort_map.get(sort, models.Order.paid_at)
    sort_expr = sort_col.asc() if order == "asc" else sort_col.desc()

    total = query.count()
    rows = query.order_by(sort_expr, models.Order.id.desc()).offset((page - 1) * size).limit(size).all()
    items = [
        schemas_analytics.AnalyticsSalesRow(
            order_id=r.id,
            order_number=r.order_number,
            user_id=r.user_id,
            payment_status=r.payment_status,
            shipping_status=r.shipping_status,
            total_amount=int(r.total_amount or 0),
            discount_amount=int(r.discount_amount or 0),
            coupon_code=r.coupon_code,
            points_used=int(r.points_used or 0),
            points_earned=int(r.points_earned or 0),
            paid_at=r.paid_at,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return schemas_analytics.AnalyticsListOut(
        domain="sales",
        total=total,
        page=page,
        size=size,
        sort=sort if sort in sort_map else "paid_at",
        order="asc" if order == "asc" else "desc",
        items=items,
        series=_sales_series(db, from_at, to_at),
    )


def list_live(
    db: Session,
    *,
    from_at: Optional[datetime] = None,
    to_at: Optional[datetime] = None,
    q: Optional[str] = None,
    status: Optional[str] = None,
    sort: str = "created_at",
    order: str = "desc",
    page: int = 1,
    size: int = DEFAULT_PAGE_SIZE,
) -> schemas_analytics.AnalyticsListOut:
    page, size = _clamp_paging(page, size)
    product_count = (
        db.query(
            models_live.LiveProduct.stream_id.label("sid"),
            func.count(models_live.LiveProduct.id).label("cnt"),
        )
        .group_by(models_live.LiveProduct.stream_id)
        .subquery()
    )
    comment_count = (
        db.query(
            models_live.LiveComment.stream_id.label("sid"),
            func.count(models_live.LiveComment.id).label("cnt"),
        )
        .filter(models_live.LiveComment.deleted_at.is_(None))
        .group_by(models_live.LiveComment.stream_id)
        .subquery()
    )

    query = (
        db.query(
            models_live.LiveStream,
            func.coalesce(product_count.c.cnt, 0),
            func.coalesce(comment_count.c.cnt, 0),
        )
        .outerjoin(product_count, product_count.c.sid == models_live.LiveStream.id)
        .outerjoin(comment_count, comment_count.c.sid == models_live.LiveStream.id)
    )
    query = _apply_created_range(query, models_live.LiveStream.created_at, from_at, to_at)
    if status:
        query = query.filter(models_live.LiveStream.status == status)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                models_live.LiveStream.title.ilike(like),
                models_live.LiveStream.description.ilike(like),
            )
        )

    sort_map = {
        "created_at": models_live.LiveStream.created_at,
        "started_at": models_live.LiveStream.started_at,
        "title": models_live.LiveStream.title,
        "status": models_live.LiveStream.status,
        "stream_id": models_live.LiveStream.id,
    }
    sort_col = sort_map.get(sort, models_live.LiveStream.created_at)
    sort_expr = sort_col.asc() if order == "asc" else sort_col.desc()

    total = query.count()
    rows = query.order_by(sort_expr, models_live.LiveStream.id.desc()).offset((page - 1) * size).limit(size).all()
    items = [
        schemas_analytics.AnalyticsLiveRow(
            stream_id=stream.id,
            title=stream.title,
            status=stream.status,
            visibility=stream.visibility,
            product_count=int(pc or 0),
            comment_count=int(cc or 0),
            scheduled_at=stream.scheduled_at,
            started_at=stream.started_at,
            ended_at=stream.ended_at,
            created_at=stream.created_at,
        )
        for stream, pc, cc in rows
    ]
    return schemas_analytics.AnalyticsListOut(
        domain="live",
        total=total,
        page=page,
        size=size,
        sort=sort if sort in sort_map else "created_at",
        order="asc" if order == "asc" else "desc",
        items=items,
    )


def list_auctions(
    db: Session,
    *,
    from_at: Optional[datetime] = None,
    to_at: Optional[datetime] = None,
    q: Optional[str] = None,
    status: Optional[str] = None,
    sort: str = "created_at",
    order: str = "desc",
    page: int = 1,
    size: int = DEFAULT_PAGE_SIZE,
) -> schemas_analytics.AnalyticsListOut:
    page, size = _clamp_paging(page, size)
    query = db.query(models_live_auction.LiveAuction)
    query = _apply_created_range(query, models_live_auction.LiveAuction.created_at, from_at, to_at)
    if status:
        query = query.filter(models_live_auction.LiveAuction.status == status)
    if q:
        like = f"%{q.strip()}%"
        # numeric id search or status text
        if q.strip().isdigit():
            query = query.filter(
                or_(
                    models_live_auction.LiveAuction.id == int(q.strip()),
                    models_live_auction.LiveAuction.stream_id == int(q.strip()),
                )
            )
        else:
            query = query.filter(models_live_auction.LiveAuction.status.ilike(like))

    sort_map = {
        "created_at": models_live_auction.LiveAuction.created_at,
        "ends_at": models_live_auction.LiveAuction.ends_at,
        "winning_amount": models_live_auction.LiveAuction.winning_amount,
        "bid_count": models_live_auction.LiveAuction.bid_count,
        "auction_id": models_live_auction.LiveAuction.id,
        "status": models_live_auction.LiveAuction.status,
    }
    sort_col = sort_map.get(sort, models_live_auction.LiveAuction.created_at)
    sort_expr = sort_col.asc() if order == "asc" else sort_col.desc()

    total = query.count()
    rows = (
        query.order_by(sort_expr, models_live_auction.LiveAuction.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    items = [
        schemas_analytics.AnalyticsAuctionRow(
            auction_id=r.id,
            stream_id=r.stream_id,
            status=r.status,
            start_price=int(r.start_price or 0),
            current_price=r.current_price,
            winning_amount=r.winning_amount,
            bid_count=int(r.bid_count or 0),
            bidder_count=int(r.bidder_count or 0),
            winner_user_id=r.winner_user_id,
            ends_at=r.ends_at,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return schemas_analytics.AnalyticsListOut(
        domain="auctions",
        total=total,
        page=page,
        size=size,
        sort=sort if sort in sort_map else "created_at",
        order="asc" if order == "asc" else "desc",
        items=items,
    )


def list_coupons(
    db: Session,
    *,
    from_at: Optional[datetime] = None,
    to_at: Optional[datetime] = None,
    q: Optional[str] = None,
    status: Optional[str] = None,
    sort: str = "created_at",
    order: str = "desc",
    page: int = 1,
    size: int = DEFAULT_PAGE_SIZE,
) -> schemas_analytics.AnalyticsListOut:
    page, size = _clamp_paging(page, size)
    used_red = (
        db.query(
            models_coupons.CouponRedemption.coupon_id.label("cid"),
            func.count(models_coupons.CouponRedemption.id).label("rcnt"),
            func.coalesce(func.sum(models_coupons.CouponRedemption.discount_amount), 0).label("dsum"),
        )
        .filter(models_coupons.CouponRedemption.status == "used")
        .group_by(models_coupons.CouponRedemption.coupon_id)
        .subquery()
    )
    assigns = (
        db.query(
            models_coupons.CouponAssignment.coupon_id.label("cid"),
            func.count(models_coupons.CouponAssignment.id).label("acnt"),
        )
        .group_by(models_coupons.CouponAssignment.coupon_id)
        .subquery()
    )

    query = (
        db.query(
            models_coupons.Coupon,
            func.coalesce(used_red.c.rcnt, 0),
            func.coalesce(used_red.c.dsum, 0),
            func.coalesce(assigns.c.acnt, 0),
        )
        .outerjoin(used_red, used_red.c.cid == models_coupons.Coupon.id)
        .outerjoin(assigns, assigns.c.cid == models_coupons.Coupon.id)
    )
    query = _apply_created_range(query, models_coupons.Coupon.created_at, from_at, to_at)
    if status == "active":
        query = query.filter(models_coupons.Coupon.is_active.is_(True))
    elif status == "inactive":
        query = query.filter(models_coupons.Coupon.is_active.is_(False))
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                models_coupons.Coupon.code.ilike(like),
                models_coupons.Coupon.name.ilike(like),
                models_coupons.Coupon.coupon_type.ilike(like),
            )
        )

    sort_map = {
        "created_at": models_coupons.Coupon.created_at,
        "code": models_coupons.Coupon.code,
        "name": models_coupons.Coupon.name,
        "coupon_id": models_coupons.Coupon.id,
    }
    sort_col = sort_map.get(sort, models_coupons.Coupon.created_at)
    sort_expr = sort_col.asc() if order == "asc" else sort_col.desc()

    total = query.count()
    rows = query.order_by(sort_expr, models_coupons.Coupon.id.desc()).offset((page - 1) * size).limit(size).all()
    items = [
        schemas_analytics.AnalyticsCouponRow(
            coupon_id=c.id,
            code=c.code,
            name=c.name,
            coupon_type=c.coupon_type,
            audience=c.audience,
            is_active=bool(c.is_active),
            redemption_count=int(rc or 0),
            discount_total_yen=int(ds or 0),
            assignment_count=int(ac or 0),
            created_at=c.created_at,
        )
        for c, rc, ds, ac in rows
    ]
    return schemas_analytics.AnalyticsListOut(
        domain="coupons",
        total=total,
        page=page,
        size=size,
        sort=sort if sort in sort_map else "created_at",
        order="asc" if order == "asc" else "desc",
        items=items,
    )


def list_points(
    db: Session,
    *,
    from_at: Optional[datetime] = None,
    to_at: Optional[datetime] = None,
    q: Optional[str] = None,
    status: Optional[str] = None,
    sort: str = "created_at",
    order: str = "desc",
    page: int = 1,
    size: int = DEFAULT_PAGE_SIZE,
) -> schemas_analytics.AnalyticsListOut:
    page, size = _clamp_paging(page, size)
    query = db.query(models_points.PointTransaction)
    query = _apply_created_range(query, models_points.PointTransaction.created_at, from_at, to_at)
    if status:
        query = query.filter(models_points.PointTransaction.type == status)
    if q:
        like = f"%{q.strip()}%"
        if q.strip().isdigit():
            query = query.filter(
                or_(
                    models_points.PointTransaction.user_id == int(q.strip()),
                    models_points.PointTransaction.id == int(q.strip()),
                )
            )
        else:
            query = query.filter(
                or_(
                    models_points.PointTransaction.type.ilike(like),
                    models_points.PointTransaction.source_type.ilike(like),
                )
            )

    sort_map = {
        "created_at": models_points.PointTransaction.created_at,
        "amount": models_points.PointTransaction.amount,
        "transaction_id": models_points.PointTransaction.id,
        "type": models_points.PointTransaction.type,
    }
    sort_col = sort_map.get(sort, models_points.PointTransaction.created_at)
    sort_expr = sort_col.asc() if order == "asc" else sort_col.desc()

    total = query.count()
    rows = (
        query.order_by(sort_expr, models_points.PointTransaction.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    items = [
        schemas_analytics.AnalyticsPointRow(
            transaction_id=r.id,
            user_id=r.user_id,
            type=r.type,
            amount=int(r.amount or 0),
            balance_after=int(r.balance_after or 0),
            source_type=r.source_type,
            source_id=r.source_id,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return schemas_analytics.AnalyticsListOut(
        domain="points",
        total=total,
        page=page,
        size=size,
        sort=sort if sort in sort_map else "created_at",
        order="asc" if order == "asc" else "desc",
        items=items,
    )


def list_domain(db: Session, domain: str, **kwargs: Any) -> schemas_analytics.AnalyticsListOut:
    if domain == "sales":
        return list_sales(db, **kwargs)
    if domain == "live":
        return list_live(db, **kwargs)
    if domain == "auctions":
        return list_auctions(db, **kwargs)
    if domain == "coupons":
        return list_coupons(db, **kwargs)
    if domain == "points":
        return list_points(db, **kwargs)
    raise ValueError(f"Unknown domain: {domain}")


def rows_for_export(db: Session, domain: str, **kwargs: Any) -> tuple[list[str], list[list[Any]]]:
    kwargs = {**kwargs, "page": 1, "size": MAX_EXPORT_ROWS}
    result = list_domain(db, domain, **kwargs)
    if not result.items:
        return [], []
    first = result.items[0]
    if hasattr(first, "model_dump"):
        keys = list(first.model_dump().keys())
        rows = []
        for item in result.items:
            data = item.model_dump()
            rows.append([_cell(data.get(k)) for k in keys])
        return keys, rows
    return [], []


def _cell(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return ""
    return value


def default_range_last_30_days() -> tuple[datetime, datetime]:
    end = datetime.utcnow() + timedelta(seconds=1)
    start = end - timedelta(days=30)
    return start, end
