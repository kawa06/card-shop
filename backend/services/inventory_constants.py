"""Phase 3-8 inventory alert / restock constants (single source of truth)."""

from __future__ import annotations

# Default low-stock threshold when product threshold is unset/null.
DEFAULT_LOW_STOCK_THRESHOLD = 3

ALERT_TYPE_LOW_STOCK = "low_stock"
ALERT_TYPE_OUT_OF_STOCK = "out_of_stock"

ALERT_STATUS_OPEN = "open"
ALERT_STATUS_RESOLVED = "resolved"

INVENTORY_STATUS_IN_STOCK = "in_stock"
INVENTORY_STATUS_LOW_STOCK = "low_stock"
INVENTORY_STATUS_OUT_OF_STOCK = "out_of_stock"

RESTOCK_STATUS_REQUESTED = "requested"
RESTOCK_STATUS_ORDERED = "ordered"
RESTOCK_STATUS_RECEIVED = "received"
RESTOCK_STATUS_CANCELLED = "cancelled"

RESTOCK_TRANSITIONS: dict[str, set[str]] = {
    RESTOCK_STATUS_REQUESTED: {
        RESTOCK_STATUS_ORDERED,
        RESTOCK_STATUS_RECEIVED,
        RESTOCK_STATUS_CANCELLED,
    },
    RESTOCK_STATUS_ORDERED: {
        RESTOCK_STATUS_RECEIVED,
        RESTOCK_STATUS_CANCELLED,
    },
    RESTOCK_STATUS_RECEIVED: set(),
    RESTOCK_STATUS_CANCELLED: set(),
}
