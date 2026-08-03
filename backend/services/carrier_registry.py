"""Extensible carrier registry — add carriers and tracking URL patterns without code changes elsewhere."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class CarrierDef:
    carrier_id: str
    display_name: str
    tracking_url_template: str
    method_keys: frozenset[str] = frozenset()
    name_keywords: frozenset[str] = frozenset()


# Add new carriers here; tracking_urls.build_tracking_url() reads this registry.
CARRIER_REGISTRY: dict[str, CarrierDef] = {
    "japan_post": CarrierDef(
        carrier_id="japan_post",
        display_name="日本郵便",
        tracking_url_template=(
            "https://trackings.post.japanpost.jp/services/srv/search/direct"
            "?reqCodeNo1={tracking_number}&locale=ja"
        ),
        method_keys=frozenset({
            "click_post", "teikei_post", "teigai_post", "letter_pack_light",
            "letter_pack_plus", "yu_pack_60", "yu_pack_80", "yu_pack_100", "ems",
        }),
        name_keywords=frozenset({"日本郵便", "郵便", "ゆうパック", "EMS", "Japan Post", "japan post"}),
    ),
    "yamato": CarrierDef(
        carrier_id="yamato",
        display_name="ヤマト運輸",
        tracking_url_template=(
            "https://track.kuronekoyamato.co.jp/english/tracking/inquiry?number={tracking_number}"
        ),
        method_keys=frozenset({
            "takkyubin_compact", "takkyubin_60", "takkyubin_80", "yamato_global",
        }),
        name_keywords=frozenset({"ヤマト", "宅急便", "kuroneko", "yamato", "Yamato"}),
    ),
    "sagawa": CarrierDef(
        carrier_id="sagawa",
        display_name="佐川急便",
        tracking_url_template=(
            "https://k2k.sagawa-exp.co.jp/p/web/okurijoinput.do?okurijoNo={tracking_number}"
        ),
        method_keys=frozenset(),
        name_keywords=frozenset({"佐川", "sagawa", "Sagawa"}),
    ),
}


def resolve_carrier_id(
    shipping_method: str | None,
    shipping_carrier: str | None,
) -> str | None:
    carrier_text = (shipping_carrier or "").strip()
    if carrier_text:
        lower = carrier_text.lower()
        for cid, cdef in CARRIER_REGISTRY.items():
            if any(kw.lower() in lower or kw in carrier_text for kw in cdef.name_keywords):
                return cid
    if shipping_method:
        for cid, cdef in CARRIER_REGISTRY.items():
            if shipping_method in cdef.method_keys:
                return cid
    return None


def build_carrier_tracking_url(
    tracking_number: str,
    *,
    shipping_method: str | None = None,
    shipping_carrier: str | None = None,
    carrier_id: str | None = None,
) -> str | None:
    num = (tracking_number or "").strip()
    if not num:
        return None
    cid = carrier_id or resolve_carrier_id(shipping_method, shipping_carrier)
    if not cid or cid not in CARRIER_REGISTRY:
        return None
    tpl = CARRIER_REGISTRY[cid].tracking_url_template
    return tpl.replace("{tracking_number}", num)


def carrier_display_name(
    shipping_method: str | None,
    shipping_carrier: str | None,
) -> str:
    if shipping_carrier and shipping_carrier.strip():
        return shipping_carrier.strip()
    cid = resolve_carrier_id(shipping_method, shipping_carrier)
    if cid and cid in CARRIER_REGISTRY:
        return CARRIER_REGISTRY[cid].display_name
    return shipping_method or "配送業者"
