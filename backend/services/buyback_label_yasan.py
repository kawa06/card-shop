"""Label-ya (ラベル屋さん) CSV and A-one 72265 layout helpers for buyback packages."""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

import models
import models_buyback
from config import settings
from services.buyback_barcodes import get_active_barcode_for_entity
from services.buyback_packages import PACKAGE_KIND_LABELS

logger = logging.getLogger(__name__)

# Official A-one 72265 / format F65A4-1 (公開仕様)
LABEL_PRODUCT_CODE_DEFAULT = "72265"
LABEL_FORMAT_CODE = "F65A4-1"
SHEET_WIDTH_MM = 210.0
SHEET_HEIGHT_MM = 297.0
LABEL_WIDTH_MM = 38.1
LABEL_HEIGHT_MM = 21.2
COLUMNS = 5
ROWS = 13
FACES = COLUMNS * ROWS  # 65

# Inter-label gaps are not published on the product page.
# With official face size + sheet size + 5×13 and zero gap, edge margins derive as:
#   horizontal: (210 - 5*38.1) / 2 = 9.75mm
#   vertical:   (297 - 13*21.2) / 2 = 10.7mm
# These are marked unconfirmed until verified with a test print on store printers.
GAP_H_MM = 0.0
GAP_V_MM = 0.0
MARGIN_LEFT_MM = round(
    (SHEET_WIDTH_MM - (COLUMNS * LABEL_WIDTH_MM + (COLUMNS - 1) * GAP_H_MM)) / 2, 2
)
MARGIN_TOP_MM = round(
    (SHEET_HEIGHT_MM - (ROWS * LABEL_HEIGHT_MM + (ROWS - 1) * GAP_V_MM)) / 2, 2
)

LABEL_YASAN_HEADERS = [
    "管理ID",
    "バーコード番号",
    "商品名",
    "価格表示",
    "バーコード用文字",
    "QRコード用文字",
    "分類",
    "保管場所",
    "補足",
]


def shop_name() -> str:
    return (getattr(settings, "BUYBACK_SHOP_NAME", None) or "").strip() or "KRX TCG"


def label_product_code() -> str:
    return (
        (getattr(settings, "BUYBACK_LABEL_PRODUCT_CODE", None) or "").strip()
        or LABEL_PRODUCT_CODE_DEFAULT
    )


def get_72265_layout() -> dict[str, Any]:
    """Return layout metadata. Margins are derived, not vendor-published mm values."""
    return {
        "product_code": label_product_code(),
        "format_code": LABEL_FORMAT_CODE,
        "sheet_width_mm": SHEET_WIDTH_MM,
        "sheet_height_mm": SHEET_HEIGHT_MM,
        "label_width_mm": LABEL_WIDTH_MM,
        "label_height_mm": LABEL_HEIGHT_MM,
        "columns": COLUMNS,
        "rows": ROWS,
        "faces": FACES,
        "gap_h_mm": GAP_H_MM,
        "gap_v_mm": GAP_V_MM,
        "margin_left_mm": MARGIN_LEFT_MM,
        "margin_top_mm": MARGIN_TOP_MM,
        "margin_right_mm": MARGIN_LEFT_MM,
        "margin_bottom_mm": MARGIN_TOP_MM,
        "margins_confirmed": False,
        "margins_note": (
            "一片サイズ・面付・シートサイズはエーワン公開仕様。"
            "上下左右余白はゼロギャップ仮定から算出した値で、"
            "店舗プリンタでのテスト印刷確認が必要です。"
        ),
        "source_url": "https://www.a-one.co.jp/product/search/detail.php?id=72265",
        "shop_name": shop_name(),
    }


def _package_product_name(
    request: models_buyback.BuybackRequest,
    package: models_buyback.BuybackShipmentPackage,
) -> str:
    buy = request.public_buyback_code or request.request_number or f"#{request.id}"
    kind = PACKAGE_KIND_LABELS.get(package.package_kind, package.package_kind or "梱包")
    return f"{shop_name()} {kind} {buy} ({package.box_index}/{package.total_boxes})"


def _build_csv_row(
    request: models_buyback.BuybackRequest,
    package: models_buyback.BuybackShipmentPackage,
    barcode: models_buyback.BuybackBarcode | None,
    *,
    include_applicant_name: bool,
    dest: models.User | None,
) -> list[str]:
    token = (barcode.scan_token if barcode else "") or ""
    human = (barcode.human_readable if barcode else None) or package.package_code
    note_parts = ["取扱注意"]
    if include_applicant_name and dest and (dest.name or "").strip():
        # Optional name for box stickers; never put address/phone/email in CSV.
        note_parts.append((dest.name or "").strip()[:40])
    return [
        package.package_code,
        human,
        _package_product_name(request, package),
        "",  # 価格表示 — not used for logistics packages
        token or human,  # バーコード生成用（scan_token優先）
        package.package_code,  # QR用は公開梱包ID
        PACKAGE_KIND_LABELS.get(package.package_kind, package.package_kind or ""),
        request.inbound_mgmt_id or "",
        " / ".join(note_parts),
    ]


def build_label_yasan_csv(
    db: Session,
    *,
    package_ids: list[int],
    include_applicant_name: bool = False,
) -> tuple[str, int]:
    if not package_ids:
        raise HTTPException(status_code=400, detail="出力する梱包を選択してください")

    packages = (
        db.query(models_buyback.BuybackShipmentPackage)
        .filter(models_buyback.BuybackShipmentPackage.id.in_(package_ids))
        .order_by(
            models_buyback.BuybackShipmentPackage.request_id.asc(),
            models_buyback.BuybackShipmentPackage.box_index.asc(),
            models_buyback.BuybackShipmentPackage.id.asc(),
        )
        .all()
    )
    if not packages:
        raise HTTPException(status_code=404, detail="対象の梱包が見つかりません")

    found_ids = {p.id for p in packages}
    missing = [pid for pid in package_ids if pid not in found_ids]
    if missing:
        raise HTTPException(status_code=404, detail=f"梱包が見つかりません: {missing}")

    request_ids = {p.request_id for p in packages}
    requests = {
        r.id: r
        for r in db.query(models_buyback.BuybackRequest)
        .filter(models_buyback.BuybackRequest.id.in_(request_ids))
        .all()
    }
    dest_ids = {p.destination_user_id for p in packages if p.destination_user_id}
    destinations = (
        {
            u.id: u
            for u in db.query(models.User).filter(models.User.id.in_(dest_ids)).all()
        }
        if dest_ids
        else {}
    )

    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(LABEL_YASAN_HEADERS)

    for package in packages:
        request = requests.get(package.request_id)
        if not request:
            raise HTTPException(
                status_code=404,
                detail=f"買取申込が見つかりません (package_id={package.id})",
            )
        barcode = get_active_barcode_for_entity(
            db,
            entity_type=models_buyback.BuybackBarcodeEntityType.shipment_package.value,
            entity_id=package.id,
        )
        dest = (
            destinations.get(package.destination_user_id)
            if package.destination_user_id
            else None
        )
        writer.writerow(
            _build_csv_row(
                request,
                package,
                barcode,
                include_applicant_name=include_applicant_name,
                dest=dest,
            )
        )

    return output.getvalue(), len(packages)


def list_label_rows_for_print(
    db: Session,
    *,
    package_ids: list[int],
    include_pii_name: bool,
) -> list[dict[str, Any]]:
    """Compact rows for 72265 browser print (scan_token + display fields)."""
    if not package_ids:
        raise HTTPException(status_code=400, detail="印刷する梱包を選択してください")

    packages = (
        db.query(models_buyback.BuybackShipmentPackage)
        .filter(models_buyback.BuybackShipmentPackage.id.in_(package_ids))
        .order_by(
            models_buyback.BuybackShipmentPackage.request_id.asc(),
            models_buyback.BuybackShipmentPackage.box_index.asc(),
            models_buyback.BuybackShipmentPackage.id.asc(),
        )
        .all()
    )
    if not packages:
        raise HTTPException(status_code=404, detail="対象の梱包が見つかりません")

    requests = {
        r.id: r
        for r in db.query(models_buyback.BuybackRequest)
        .filter(models_buyback.BuybackRequest.id.in_({p.request_id for p in packages}))
        .all()
    }
    destinations: dict[int, models.User] = {}
    if include_pii_name:
        dest_ids = {p.destination_user_id for p in packages if p.destination_user_id}
        if dest_ids:
            destinations = {
                u.id: u
                for u in db.query(models.User).filter(models.User.id.in_(dest_ids)).all()
            }

    rows: list[dict[str, Any]] = []
    for package in packages:
        request = requests.get(package.request_id)
        if not request:
            continue
        barcode = get_active_barcode_for_entity(
            db,
            entity_type=models_buyback.BuybackBarcodeEntityType.shipment_package.value,
            entity_id=package.id,
        )
        dest = destinations.get(package.destination_user_id) if include_pii_name else None
        rows.append(
            {
                "package_id": package.id,
                "package_code": package.package_code,
                "scan_token": barcode.scan_token if barcode else None,
                "barcode_human_readable": (barcode.human_readable if barcode else None)
                or package.package_code,
                "public_buyback_code": request.public_buyback_code,
                "request_number": request.request_number,
                "inbound_mgmt_id": request.inbound_mgmt_id,
                "box_index": package.box_index,
                "total_boxes": package.total_boxes,
                "package_kind": package.package_kind,
                "package_kind_label": PACKAGE_KIND_LABELS.get(
                    package.package_kind, package.package_kind
                ),
                "applicant_name": (dest.name if dest else None),
                "handling_note": "取扱注意",
                "shop_name": shop_name(),
                "title": _package_product_name(request, package),
            }
        )
    return rows


def csv_filename() -> str:
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    code = label_product_code()
    return f"label_yasan_buyback_{code}_{stamp}.csv"
