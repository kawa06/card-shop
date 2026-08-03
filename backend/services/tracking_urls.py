"""Build carrier tracking URLs — delegates to extensible carrier_registry."""

from __future__ import annotations

from services.carrier_registry import (
    build_carrier_tracking_url,
    carrier_display_name as _registry_carrier_display_name,
    resolve_carrier_id,
)

# Backward-compatible constants
CARRIER_JAPAN_POST = "japan_post"
CARRIER_YAMATO = "yamato"
CARRIER_SAGAWA = "sagawa"

NON_TRACKABLE_METHODS = frozenset({"teikei_post", "teigai_post"})


def resolve_carrier(
    shipping_method: str | None,
    shipping_carrier: str | None,
) -> str | None:
    return resolve_carrier_id(shipping_method, shipping_carrier)


def build_tracking_url(
    tracking_number: str,
    *,
    shipping_method: str | None = None,
    shipping_carrier: str | None = None,
) -> str | None:
    return build_carrier_tracking_url(
        tracking_number,
        shipping_method=shipping_method,
        shipping_carrier=shipping_carrier,
    )


def is_trackable_shipping_method(shipping_method: str | None) -> bool:
    if not shipping_method:
        return True
    return shipping_method not in NON_TRACKABLE_METHODS


def carrier_display_name(
    shipping_method: str | None,
    shipping_carrier: str | None,
) -> str:
    return _registry_carrier_display_name(shipping_method, shipping_carrier)
