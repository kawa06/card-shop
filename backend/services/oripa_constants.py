"""Phase 3-9 Oripa constants (single source of truth)."""

from __future__ import annotations

ORIPA_STATUS_DRAFT = "draft"
ORIPA_STATUS_SCHEDULED = "scheduled"
ORIPA_STATUS_ON_SALE = "on_sale"
ORIPA_STATUS_SOLD_OUT = "sold_out"
ORIPA_STATUS_ENDED = "ended"

ORIPA_PURCHASE_PENDING = "pending"
ORIPA_PURCHASE_COMPLETED = "completed"
ORIPA_PURCHASE_FAILED = "failed"
ORIPA_PURCHASE_CANCELLED = "cancelled"

ORIPA_STATUSES = {
    ORIPA_STATUS_DRAFT,
    ORIPA_STATUS_SCHEDULED,
    ORIPA_STATUS_ON_SALE,
    ORIPA_STATUS_SOLD_OUT,
    ORIPA_STATUS_ENDED,
}

# Publish / end transitions used by admin status updates (Step 1).
ORIPA_STATUS_TRANSITIONS: dict[str, set[str]] = {
    ORIPA_STATUS_DRAFT: {ORIPA_STATUS_SCHEDULED, ORIPA_STATUS_ON_SALE, ORIPA_STATUS_ENDED},
    ORIPA_STATUS_SCHEDULED: {ORIPA_STATUS_ON_SALE, ORIPA_STATUS_DRAFT, ORIPA_STATUS_ENDED},
    ORIPA_STATUS_ON_SALE: {ORIPA_STATUS_SOLD_OUT, ORIPA_STATUS_ENDED},
    ORIPA_STATUS_SOLD_OUT: {ORIPA_STATUS_ENDED},
    ORIPA_STATUS_ENDED: set(),
}

ENTRY_ASSIGNMENT_AVAILABLE = "available"
ENTRY_ASSIGNMENT_ASSIGNED = "assigned"
ENTRY_ASSIGNMENT_RETIRED = "retired"  # assigned then cancelled; not resold (Step 8)

ENTRY_SHIPMENT_HELD = "held"
ENTRY_SHIPMENT_PENDING = "pending_ship"
ENTRY_SHIPMENT_SHIPPED = "shipped"
ENTRY_SHIPMENT_CANCELLED = "cancelled"


def format_entry_number(n: int) -> str:
    return f"No.{int(n):03d}"
