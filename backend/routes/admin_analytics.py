"""Phase 3-7 admin analytics / dashboard enhancement API."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

import schemas_analytics
from auth import get_current_admin_context
from database import get_db
from services import admin_analytics, analytics_export
from services.admin_auth import AdminAccessError, AdminContext, require_permission

router = APIRouter(prefix="/api/admin/analytics", tags=["admin-analytics"])


def _handle_admin_error(exc: Exception) -> None:
    if isinstance(exc, AdminAccessError):
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    raise exc


def _parse_range(from_at: Optional[str], to_at: Optional[str]):
    try:
        return admin_analytics.parse_range(from_at, to_at)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/kpi", response_model=schemas_analytics.AnalyticsKpiOut)
def analytics_kpi(
    from_at: Optional[str] = Query(None),
    to_at: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    try:
        require_permission(ctx, "analytics.read")
        start, end = _parse_range(from_at, to_at)
        return admin_analytics.build_kpi(db, from_at=start, to_at=end)
    except Exception as exc:
        _handle_admin_error(exc)


def _list_common(
    *,
    domain: str,
    from_at: Optional[str],
    to_at: Optional[str],
    q: Optional[str],
    status: Optional[str],
    payment_status: Optional[str],
    shipping_status: Optional[str],
    sort: str,
    order: str,
    page: int,
    size: int,
    db: Session,
    ctx: AdminContext,
):
    try:
        require_permission(ctx, "analytics.read")
        start, end = _parse_range(from_at, to_at)
        kwargs = {
            "from_at": start,
            "to_at": end,
            "q": q,
            "sort": sort,
            "order": order,
            "page": page,
            "size": size,
        }
        if domain == "sales":
            kwargs["payment_status"] = payment_status
            kwargs["shipping_status"] = shipping_status
        else:
            kwargs["status"] = status
        return admin_analytics.list_domain(db, domain, **kwargs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        _handle_admin_error(exc)


@router.get("/sales", response_model=schemas_analytics.AnalyticsListOut)
def analytics_sales(
    from_at: Optional[str] = Query(None),
    to_at: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    payment_status: Optional[str] = Query(None),
    shipping_status: Optional[str] = Query(None),
    sort: str = Query("paid_at"),
    order: str = Query("desc"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    return _list_common(
        domain="sales",
        from_at=from_at,
        to_at=to_at,
        q=q,
        status=None,
        payment_status=payment_status,
        shipping_status=shipping_status,
        sort=sort,
        order=order,
        page=page,
        size=size,
        db=db,
        ctx=ctx,
    )


@router.get("/live", response_model=schemas_analytics.AnalyticsListOut)
def analytics_live(
    from_at: Optional[str] = Query(None),
    to_at: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    return _list_common(
        domain="live",
        from_at=from_at,
        to_at=to_at,
        q=q,
        status=status,
        payment_status=None,
        shipping_status=None,
        sort=sort,
        order=order,
        page=page,
        size=size,
        db=db,
        ctx=ctx,
    )


@router.get("/auctions", response_model=schemas_analytics.AnalyticsListOut)
def analytics_auctions(
    from_at: Optional[str] = Query(None),
    to_at: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    return _list_common(
        domain="auctions",
        from_at=from_at,
        to_at=to_at,
        q=q,
        status=status,
        payment_status=None,
        shipping_status=None,
        sort=sort,
        order=order,
        page=page,
        size=size,
        db=db,
        ctx=ctx,
    )


@router.get("/coupons", response_model=schemas_analytics.AnalyticsListOut)
def analytics_coupons(
    from_at: Optional[str] = Query(None),
    to_at: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    return _list_common(
        domain="coupons",
        from_at=from_at,
        to_at=to_at,
        q=q,
        status=status,
        payment_status=None,
        shipping_status=None,
        sort=sort,
        order=order,
        page=page,
        size=size,
        db=db,
        ctx=ctx,
    )


@router.get("/points", response_model=schemas_analytics.AnalyticsListOut)
def analytics_points(
    from_at: Optional[str] = Query(None),
    to_at: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="Point transaction type filter"),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    return _list_common(
        domain="points",
        from_at=from_at,
        to_at=to_at,
        q=q,
        status=status,
        payment_status=None,
        shipping_status=None,
        sort=sort,
        order=order,
        page=page,
        size=size,
        db=db,
        ctx=ctx,
    )


@router.get("/export")
def analytics_export_route(
    domain: str = Query(..., pattern="^(sales|live|auctions|coupons|points|kpi)$"),
    format: str = Query("csv", alias="format", pattern="^(csv|xlsx|pdf)$"),
    from_at: Optional[str] = Query(None),
    to_at: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    payment_status: Optional[str] = Query(None),
    shipping_status: Optional[str] = Query(None),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    try:
        require_permission(ctx, "analytics.export")
        start, end = _parse_range(from_at, to_at)
        filters = {
            "from_at": from_at,
            "to_at": to_at,
            "q": q,
            "status": status,
            "payment_status": payment_status,
            "shipping_status": shipping_status,
            "sort": sort,
            "order": order,
        }

        if domain == "kpi":
            kpi = admin_analytics.build_kpi(db, from_at=start, to_at=end)
            data = kpi.model_dump()
            headers = list(data.keys())
            rows = [["" if data[k] is None else str(data[k]) for k in headers]]
        else:
            kwargs = {
                "from_at": start,
                "to_at": end,
                "q": q,
                "sort": sort,
                "order": order,
            }
            if domain == "sales":
                kwargs["payment_status"] = payment_status
                kwargs["shipping_status"] = shipping_status
                if sort == "created_at":
                    kwargs["sort"] = "paid_at"
            else:
                kwargs["status"] = status
            headers, rows = admin_analytics.rows_for_export(db, domain, **kwargs)

        if format == "csv":
            payload = analytics_export.build_csv(headers, rows)
        elif format == "xlsx":
            payload = analytics_export.build_xlsx(headers, rows, sheet_name=domain)
        else:
            payload = analytics_export.build_pdf(headers, rows, title=f"Analytics {domain}")

        analytics_export.record_export(
            db,
            actor_admin_user_id=getattr(ctx.user, "id", None),
            domain=domain,
            export_format=format,
            row_count=len(rows),
            filters=filters,
        )
        return Response(
            content=payload,
            media_type=analytics_export.content_type_for(format),
            headers={
                "Content-Disposition": f'attachment; filename="{analytics_export.filename_for(domain, format)}"'
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        _handle_admin_error(exc)
