"""Build carrier-specific package tracking URLs for Japan domestic shipping."""

from __future__ import annotations

CARRIER_JAPAN_POST = "japan_post"
CARRIER_YAMATO = "yamato"
CARRIER_SAGAWA = "sagawa"

METHOD_CARRIER_MAP: dict[str, str] = {
    "click_post": CARRIER_JAPAN_POST,
    "teikei_post": CARRIER_JAPAN_POST,
    "teigai_post": CARRIER_JAPAN_POST,
    "letter_pack_light": CARRIER_JAPAN_POST,
    "letter_pack_plus": CARRIER_JAPAN_POST,
    "yu_pack_60": CARRIER_JAPAN_POST,
    "yu_pack_80": CARRIER_JAPAN_POST,
    "yu_pack_100": CARRIER_JAPAN_POST,
    "ems": CARRIER_JAPAN_POST,
    "takkyubin_compact": CARRIER_YAMATO,
    "takkyubin_60": CARRIER_YAMATO,
    "takkyubin_80": CARRIER_YAMATO,
    "yamato_global": CARRIER_YAMATO,
}

NON_TRACKABLE_METHODS = frozenset({"teikei_post", "teigai_post"})


def _carrier_from_text(text: str) -> str | None:
    normalized = text.strip().lower()
    if not normalized:
        return None
    if any(k in text for k in ("ヤマト", "宅急便", "kuroneko", "yamato")):
        return CARRIER_YAMATO
    if any(k in text for k in ("佐川", "sagawa")):
        return CARRIER_SAGAWA
    if any(k in text for k in ("日本郵便", "郵便", "ゆうパック", "EMS", "Japan Post")):
        return CARRIER_JAPAN_POST
    if "japan" in normalized and "post" in normalized:
        return CARRIER_JAPAN_POST
    return None


def resolve_carrier(
    shipping_method: str | None,
    shipping_carrier: str | None,
) -> str | None:
    if shipping_carrier:
        from_text = _carrier_from_text(shipping_carrier)
        if from_text:
            return from_text
    if shipping_method:
        return METHOD_CARRIER_MAP.get(shipping_method)
    return None


def build_tracking_url(
    tracking_number: str,
    *,
    shipping_method: str | None = None,
    shipping_carrier: str | None = None,
) -> str | None:
    num = (tracking_number or "").strip()
    if not num:
        return None

    carrier = resolve_carrier(shipping_method, shipping_carrier)
    if carrier == CARRIER_YAMATO:
        return (
            "https://track.kuronekoyamato.co.jp/english/tracking/inquiry"
            f"?number={num}"
        )
    if carrier == CARRIER_SAGAWA:
        return f"https://k2k.sagawa-exp.co.jp/p/web/okurijoinput.do?okurijoNo={num}"
    if carrier == CARRIER_JAPAN_POST:
        return (
            "https://trackings.post.japanpost.jp/services/srv/search/direct"
            f"?reqCodeNo1={num}&locale=ja"
        )
    return None


def is_trackable_shipping_method(shipping_method: str | None) -> bool:
    if not shipping_method:
        return True
    return shipping_method not in NON_TRACKABLE_METHODS


def carrier_display_name(
    shipping_method: str | None,
    shipping_carrier: str | None,
) -> str:
    if shipping_carrier and shipping_carrier.strip():
        return shipping_carrier.strip()
    carrier = resolve_carrier(shipping_method, shipping_carrier)
    if carrier == CARRIER_YAMATO:
        return "ヤマト運輸"
    if carrier == CARRIER_SAGAWA:
        return "佐川急便"
    if carrier == CARRIER_JAPAN_POST:
        return "日本郵便"
    return shipping_method or "配送業者"
