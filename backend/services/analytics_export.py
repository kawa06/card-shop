"""Phase 3-7 analytics export builders (CSV / XLSX / PDF) without extra deps."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from typing import Any, Optional
from xml.sax.saxutils import escape

from sqlalchemy.orm import Session

import models_analytics


def build_csv(headers: list[str], rows: list[list[Any]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    if headers:
        writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    # UTF-8 BOM for Excel-friendly CSV
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


def _col_name(index: int) -> str:
    # 1-based excel column name
    name = ""
    n = index
    while n:
        n, rem = divmod(n - 1, 26)
        name = chr(65 + rem) + name
    return name


def build_xlsx(headers: list[str], rows: list[list[Any]], *, sheet_name: str = "analytics") -> bytes:
    """Minimal Office Open XML spreadsheet."""
    sheet_name = (sheet_name or "analytics")[:31] or "analytics"
    all_rows = [headers] + rows if headers else rows

    sheet_rows: list[str] = []
    for r_idx, row in enumerate(all_rows, start=1):
        cells: list[str] = []
        for c_idx, value in enumerate(row, start=1):
            ref = f"{_col_name(c_idx)}{r_idx}"
            text = "" if value is None else str(value)
            cells.append(
                f'<c r="{ref}" t="inlineStr"><is><t>{escape(text)}</t></is></c>'
            )
        sheet_rows.append(f'<row r="{r_idx}">{"".join(cells)}</row>')

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData>'
        "</worksheet>"
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{escape(sheet_name)}" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return buf.getvalue()


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_pdf(headers: list[str], rows: list[list[Any]], *, title: str = "Analytics Export") -> bytes:
    """Minimal single-page-ish PDF with monospace text lines (ASCII-safe)."""
    lines: list[str] = [title, ""]
    if headers:
        lines.append(" | ".join(str(h) for h in headers))
        lines.append("-" * min(100, max(10, len(lines[-1]))))
    for row in rows[:200]:
        lines.append(" | ".join("" if v is None else str(v) for v in row))

    # Use Helvetica; non-ascii replaced for glyph safety in core PDF fonts
    safe_lines = []
    for line in lines:
        safe_lines.append("".join(ch if ord(ch) < 128 else "?" for ch in line)[:120])

    content_parts = ["BT", "/F1 9 Tf", "40 800 Td", "12 TL"]
    if safe_lines:
        content_parts.append(f"({_pdf_escape(safe_lines[0])}) Tj")
        for line in safe_lines[1:]:
            content_parts.append("T*")
            content_parts.append(f"({_pdf_escape(line)}) Tj")
    content_parts.append("ET")
    stream = "\n".join(content_parts).encode("latin-1", errors="replace")

    objects: list[bytes] = []
    objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objects.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
    )
    objects.append(
        f"4 0 obj<< /Length {len(stream)} >>stream\n".encode("ascii")
        + stream
        + b"\nendstream\nendobj\n"
    )
    objects.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(out.tell())
        out.write(obj)
    xref_pos = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.write(f"{off:010d} 00000 n \n".encode("ascii"))
    out.write(
        f"trailer<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return out.getvalue()


def content_type_for(fmt: str) -> str:
    if fmt == "csv":
        return "text/csv; charset=utf-8"
    if fmt == "xlsx":
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if fmt == "pdf":
        return "application/pdf"
    raise ValueError(f"Unsupported format: {fmt}")


def filename_for(domain: str, fmt: str) -> str:
    return f"phase3-7-analytics-{domain}.{fmt}"


def record_export(
    db: Session,
    *,
    actor_admin_user_id: Optional[int],
    domain: str,
    export_format: str,
    row_count: int,
    filters: Optional[dict[str, Any]] = None,
) -> models_analytics.AnalyticsExportLog:
    row = models_analytics.AnalyticsExportLog(
        actor_admin_user_id=actor_admin_user_id,
        domain=domain,
        export_format=export_format,
        row_count=int(row_count or 0),
        filters_json=json.dumps(filters or {}, ensure_ascii=False, default=str),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
