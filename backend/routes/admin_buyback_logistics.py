"""Admin buyback logistics routes (scan / receive / packages / labels)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

import schemas_buyback
from auth import get_current_admin_context
from database import get_db
from services.admin_auth import AdminAccessError, AdminContext, require_permission
from services.buyback_label_yasan import (
    build_label_yasan_csv,
    csv_filename,
    get_72265_layout,
    list_label_rows_for_print,
)
from services.buyback_logistics_logs import (
    list_logistics_logs,
    write_buyback_audit,
    write_package_print_log,
)
from services.buyback_packages import (
    complete_package,
    get_package_label_payload,
    issue_packages_for_request,
    list_packages_for_request,
)
from services.buyback_receiving import receive_inbound_package, scan_inbound_barcode
from services.buyback_shipping import confirm_shipment, scan_for_ship_verify
from services.db_persist import PersistDep

router = APIRouter(
    prefix="/api/admin/buyback",
    tags=["admin-buyback-logistics"],
    dependencies=[PersistDep],
)


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _require_perm(permission: str):
    def _dep(ctx: AdminContext = Depends(get_current_admin_context)) -> AdminContext:
        try:
            require_permission(ctx, permission)
        except AdminAccessError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
        return ctx

    return _dep


@router.post("/scan", response_model=schemas_buyback.AdminBuybackScanOut)
def admin_scan_buyback_barcode(
    payload: schemas_buyback.AdminBuybackScanIn,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.receive")),
):
    include_pii = "admin.pii.read" in ctx.permissions
    result = scan_inbound_barcode(
        db,
        admin_user=ctx.user,
        code=payload.code,
        include_pii=include_pii,
        ip_address=_client_ip(request),
        device_info=payload.device_info,
    )
    return schemas_buyback.AdminBuybackScanOut(**result)


@router.post("/inbound/receive", response_model=schemas_buyback.AdminBuybackScanOut)
def admin_receive_inbound(
    payload: schemas_buyback.AdminBuybackReceiveIn,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.receive")),
):
    include_pii = "admin.pii.read" in ctx.permissions
    result = receive_inbound_package(
        db,
        admin_user=ctx.user,
        inbound_shipment_id=payload.inbound_shipment_id,
        scanned_code=payload.scanned_code,
        box_count=payload.box_count,
        actual_item_count=payload.actual_item_count,
        condition_note=payload.condition_note,
        admin_note=payload.admin_note,
        device_info=payload.device_info,
        ip_address=_client_ip(request),
    )
    if not include_pii:
        result["user_email"] = None
        result["phone_number"] = None
        result["address"] = None
    return schemas_buyback.AdminBuybackScanOut(**result)


@router.get(
    "/requests/{request_id}/packages",
    response_model=list[schemas_buyback.AdminBuybackPackageOut],
)
def admin_list_packages(
    request_id: int,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.package.read")),
):
    return [
        schemas_buyback.AdminBuybackPackageOut(**row)
        for row in list_packages_for_request(db, request_id)
    ]


@router.post(
    "/requests/{request_id}/packages",
    response_model=list[schemas_buyback.AdminBuybackPackageOut],
)
def admin_issue_packages(
    request_id: int,
    payload: schemas_buyback.AdminBuybackPackageIssueIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.package.write")),
):
    rows = issue_packages_for_request(
        db,
        admin_user=ctx.user,
        request_id=request_id,
        total_boxes=payload.total_boxes,
        package_kind=payload.package_kind,
        shipping_method=payload.shipping_method,
        preferred_ship_date=payload.preferred_ship_date,
        preferred_time_slot=payload.preferred_time_slot,
        return_reference=payload.return_reference,
        admin_note=payload.admin_note,
        request_item_ids=payload.request_item_ids,
        replace_existing=payload.replace_existing,
    )
    return [schemas_buyback.AdminBuybackPackageOut(**row) for row in rows]


@router.post(
    "/packages/{package_id}/complete",
    response_model=schemas_buyback.AdminBuybackPackageOut,
)
def admin_complete_package(
    package_id: int,
    payload: schemas_buyback.AdminBuybackPackageCompleteIn | None = None,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.package.write")),
):
    body = payload or schemas_buyback.AdminBuybackPackageCompleteIn()
    row = complete_package(
        db,
        admin_user=ctx.user,
        package_id=package_id,
        tracking_number=body.tracking_number,
        admin_note=body.admin_note,
    )
    return schemas_buyback.AdminBuybackPackageOut(**row)


@router.get(
    "/packages/{package_id}/label",
    response_model=schemas_buyback.AdminBuybackPackageLabelOut,
)
def admin_get_package_label(
    package_id: int,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.package.read")),
):
    include_pii = (
        "admin.pii.read" in ctx.permissions and "buyback.print.pii" in ctx.permissions
    )
    row = get_package_label_payload(
        db,
        admin_user=ctx.user,
        package_id=package_id,
        include_pii=include_pii,
        mark_print=False,
    )
    return schemas_buyback.AdminBuybackPackageLabelOut(**row)


@router.post(
    "/packages/{package_id}/label/print",
    response_model=schemas_buyback.AdminBuybackPackageLabelOut,
)
def admin_print_package_label(
    package_id: int,
    payload: schemas_buyback.AdminBuybackPackagePrintIn | None = None,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.print.internal")),
):
    body = payload or schemas_buyback.AdminBuybackPackagePrintIn()
    include_pii = (
        "admin.pii.read" in ctx.permissions and "buyback.print.pii" in ctx.permissions
    )
    row = get_package_label_payload(
        db,
        admin_user=ctx.user,
        package_id=package_id,
        include_pii=include_pii,
        mark_print=True,
        is_reprint=body.is_reprint,
        device_info=body.device_info,
    )
    return schemas_buyback.AdminBuybackPackageLabelOut(**row)


@router.post("/ship/scan", response_model=schemas_buyback.AdminBuybackShipVerifyOut)
def admin_ship_verify_scan(
    payload: schemas_buyback.AdminBuybackScanIn,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.ship.read")),
):
    # Address/phone require admin.pii.read (shipping_manager has it via role mapping).
    include_pii = "admin.pii.read" in ctx.permissions
    result = scan_for_ship_verify(
        db,
        admin_user=ctx.user,
        code=payload.code,
        include_pii=include_pii,
        ip_address=_client_ip(request),
        device_info=payload.device_info,
    )
    return schemas_buyback.AdminBuybackShipVerifyOut(**result)


@router.post("/ship/confirm", response_model=schemas_buyback.AdminBuybackShipVerifyOut)
def admin_ship_confirm(
    payload: schemas_buyback.AdminBuybackShipConfirmIn,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.ship.confirm")),
):
    include_pii = "admin.pii.read" in ctx.permissions
    result = confirm_shipment(
        db,
        admin_user=ctx.user,
        package_id=payload.package_id,
        checklist=payload.checklist,
        scanned_code=payload.scanned_code,
        tracking_number=payload.tracking_number,
        shipping_method=payload.shipping_method,
        device_info=payload.device_info,
        ip_address=_client_ip(request),
    )
    if not include_pii:
        result["destination_phone"] = None
        result["destination_address"] = None
    return schemas_buyback.AdminBuybackShipVerifyOut(**result)


@router.get("/labels/layout", response_model=schemas_buyback.AdminBuybackLabelLayoutOut)
def admin_buyback_label_layout(
    ctx: AdminContext = Depends(_require_perm("buyback.print.internal")),
):
    return schemas_buyback.AdminBuybackLabelLayoutOut(**get_72265_layout())


@router.post("/labels/csv")
def admin_export_label_yasan_csv(
    payload: schemas_buyback.AdminBuybackLabelCsvExportIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("admin.csv.export")),
):
    if "buyback.package.read" not in ctx.permissions and "buyback.print.internal" not in ctx.permissions:
        raise HTTPException(status_code=403, detail="梱包ラベルCSVの出力権限がありません")

    # Name on CSV also requires print.pii + pii.read (box sticker convenience only)
    include_name = bool(payload.include_applicant_name)
    if include_name and not (
        "admin.pii.read" in ctx.permissions and "buyback.print.pii" in ctx.permissions
    ):
        raise HTTPException(
            status_code=403,
            detail="申込者名をCSVに含める権限がありません",
        )

    content, count = build_label_yasan_csv(
        db,
        package_ids=payload.package_ids,
        include_applicant_name=include_name,
    )
    for package_id in payload.package_ids:
        write_package_print_log(
            db,
            actor_user_id=ctx.user.id,
            print_type="label_yasan_csv",
            entity_type="buyback_shipment_package",
            entity_id=package_id,
            includes_pii=include_name,
            is_reprint=False,
        )
    write_buyback_audit(
        db,
        actor_user_id=ctx.user.id,
        action="label_yasan_csv_exported",
        entity_type="buyback_shipment_package",
        entity_id=",".join(str(i) for i in payload.package_ids[:20]),
        details={
            "package_ids": payload.package_ids,
            "count": count,
            "include_applicant_name": include_name,
        },
    )
    db.commit()

    filename = csv_filename()
    return Response(
        content=content.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/labels/sheet", response_model=schemas_buyback.AdminBuybackLabelSheetOut)
def admin_buyback_label_sheet(
    payload: schemas_buyback.AdminBuybackLabelSheetIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.print.internal")),
):
    layout = get_72265_layout()
    start = max(1, min(int(payload.start_position or 1), layout["faces"]))
    copies = max(1, min(int(payload.copies or 1), 20))

    include_name = bool(payload.include_applicant_name) and (
        "admin.pii.read" in ctx.permissions and "buyback.print.pii" in ctx.permissions
    )
    base_rows = list_label_rows_for_print(
        db,
        package_ids=payload.package_ids,
        include_pii_name=include_name,
    )
    labels: list[schemas_buyback.AdminBuybackLabelSheetCellOut] = []
    for _ in range(copies):
        for row in base_rows:
            labels.append(schemas_buyback.AdminBuybackLabelSheetCellOut(**row))

    for package_id in payload.package_ids:
        write_package_print_log(
            db,
            actor_user_id=ctx.user.id,
            print_type="label_sheet_72265",
            entity_type="buyback_shipment_package",
            entity_id=package_id,
            includes_pii=include_name,
            is_reprint=False,
        )
    write_buyback_audit(
        db,
        actor_user_id=ctx.user.id,
        action="label_sheet_prepared",
        entity_type="buyback_shipment_package",
        entity_id=",".join(str(i) for i in payload.package_ids[:20]),
        details={
            "package_ids": payload.package_ids,
            "start_position": start,
            "copies": copies,
            "include_applicant_name": include_name,
            "product_code": layout["product_code"],
        },
    )
    db.commit()

    return schemas_buyback.AdminBuybackLabelSheetOut(
        layout=schemas_buyback.AdminBuybackLabelLayoutOut(**layout),
        start_position=start,
        copies=copies,
        labels=labels,
    )


@router.get("/logs", response_model=schemas_buyback.AdminBuybackLogisticsLogsOut)
def admin_list_buyback_logistics_logs(
    log_type: str | None = None,
    request_id: int | None = None,
    package_id: int | None = None,
    page: int = 1,
    per_page: int = 50,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.logs.read")),
):
    _ = ctx
    page = max(1, page)
    per_page = max(1, min(per_page, 100))
    items, total = list_logistics_logs(
        db,
        log_type=log_type,
        request_id=request_id,
        package_id=package_id,
        limit=per_page,
        offset=(page - 1) * per_page,
    )
    pages = (total + per_page - 1) // per_page if total else 1
    return schemas_buyback.AdminBuybackLogisticsLogsOut(
        items=[schemas_buyback.AdminBuybackLogisticsLogOut(**row) for row in items],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )
