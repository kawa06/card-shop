"""Buyback request status definitions, flows, and transition rules."""

from __future__ import annotations

from typing import Optional

import models_buyback

# Color categories for admin / customer UI
STATUS_COLOR_RECEPTION = "reception"  # blue
STATUS_COLOR_WAITING = "waiting"  # yellow
STATUS_COLOR_ASSESSING = "assessing"  # orange
STATUS_COLOR_COMPLETE = "complete"  # green
STATUS_COLOR_NEGATIVE = "negative"  # red

STATUS_LABELS: dict[str, str] = {
    "draft": "下書き",
    "submitted": "申請受付",
    "identity_pending": "本人確認待ち",
    "awaiting_shipment": "発送待ち",
    "awaiting_visit": "来店待ち",
    "shipped": "発送済み",
    "received": "到着済み",
    "store_visited": "来店済み",
    "assessing": "査定中",
    "assessed": "査定完了",
    "awaiting_customer": "承認待ち",
    "accepted": "承認済み",
    "rejected": "買取不可",
    "payout_pending": "支払準備中",
    "paid": "支払完了",
    "return_preparing": "返送待ち",
    "returned": "返送済み",
    "completed": "完了",
    "cancelled": "キャンセル",
    "sent_back": "差戻し",
    "on_hold": "保留",
}

STATUS_DESCRIPTIONS: dict[str, str] = {
    "submitted": "申請が完了した状態",
    "identity_pending": "身分証などの確認待ち",
    "awaiting_shipment": "ユーザーが発送する状態（郵送買取）",
    "awaiting_visit": "店舗へ持ち込み予定（店舗買取）",
    "shipped": "ユーザーが発送済み",
    "received": "店舗へ到着",
    "store_visited": "来店・持ち込み済み",
    "assessing": "カードを査定中",
    "assessed": "査定金額が確定",
    "awaiting_customer": "ユーザーが査定結果を確認中",
    "accepted": "ユーザーが承認",
    "rejected": "買取不可",
    "payout_pending": "振込・支払い処理中",
    "paid": "振込完了",
    "return_preparing": "キャンセル品を返送準備",
    "returned": "商品返送済み",
    "completed": "全て終了",
    "cancelled": "申請キャンセル",
    "sent_back": "不備があり修正依頼",
    "on_hold": "問い合わせ・確認事項あり",
}

STATUS_COLORS: dict[str, str] = {
    "draft": STATUS_COLOR_RECEPTION,
    "submitted": STATUS_COLOR_RECEPTION,
    "identity_pending": STATUS_COLOR_WAITING,
    "awaiting_shipment": STATUS_COLOR_WAITING,
    "awaiting_visit": STATUS_COLOR_WAITING,
    "shipped": STATUS_COLOR_WAITING,
    "received": STATUS_COLOR_WAITING,
    "store_visited": STATUS_COLOR_WAITING,
    "assessing": STATUS_COLOR_ASSESSING,
    "assessed": STATUS_COLOR_ASSESSING,
    "awaiting_customer": STATUS_COLOR_WAITING,
    "accepted": STATUS_COLOR_COMPLETE,
    "payout_pending": STATUS_COLOR_WAITING,
    "paid": STATUS_COLOR_COMPLETE,
    "return_preparing": STATUS_COLOR_WAITING,
    "returned": STATUS_COLOR_WAITING,
    "completed": STATUS_COLOR_COMPLETE,
    "cancelled": STATUS_COLOR_NEGATIVE,
    "sent_back": STATUS_COLOR_NEGATIVE,
    "on_hold": STATUS_COLOR_WAITING,
    "rejected": STATUS_COLOR_NEGATIVE,
}

MAIL_PROGRESS_STEPS: list[str] = [
    "submitted",
    "awaiting_shipment",
    "shipped",
    "received",
    "assessing",
    "assessed",
    "awaiting_customer",
    "accepted",
    "payout_pending",
    "paid",
    "completed",
]

STORE_PROGRESS_STEPS: list[str] = [
    "submitted",
    "awaiting_visit",
    "store_visited",
    "assessing",
    "awaiting_customer",
    "accepted",
    "paid",
    "completed",
]

COMMON_TRANSITIONS: dict[str, set[str]] = {
    "submitted": {"identity_pending", "on_hold", "sent_back", "cancelled"},
    "identity_pending": {"on_hold", "sent_back", "cancelled"},
    "assessing": {"assessed", "on_hold", "cancelled"},
    "assessed": {"awaiting_customer", "rejected", "on_hold", "cancelled"},
    "awaiting_customer": {"accepted", "rejected", "on_hold", "cancelled"},
    "accepted": {"cancelled"},
    "payout_pending": {"paid"},  # paid は専用エンドポイント経由（手動ドロップダウンからは除外）
    "paid": {"completed"},
    "return_preparing": {"returned"},
    "returned": {"completed"},
    "rejected": {"return_preparing", "returned"},
    "on_hold": {
        "submitted",
        "identity_pending",
        "awaiting_shipment",
        "awaiting_visit",
        "shipped",
        "received",
        "store_visited",
        "assessing",
        "assessed",
        "awaiting_customer",
    },
    "sent_back": {"submitted", "cancelled"},
    "completed": set(),
    "cancelled": set(),
    "draft": set(),
}

MAIL_TRANSITIONS: dict[str, set[str]] = {
    **COMMON_TRANSITIONS,
    "submitted": COMMON_TRANSITIONS["submitted"] | {"awaiting_shipment", "assessing"},
    "identity_pending": COMMON_TRANSITIONS["identity_pending"] | {"awaiting_shipment"},
    "awaiting_shipment": {"shipped", "cancelled", "on_hold"},
    "shipped": {"received", "assessing", "cancelled", "on_hold"},
    "received": {"assessing", "cancelled", "on_hold"},
    "accepted": {"payout_pending", "cancelled"},
}

STORE_TRANSITIONS: dict[str, set[str]] = {
    **COMMON_TRANSITIONS,
    "submitted": COMMON_TRANSITIONS["submitted"] | {"awaiting_visit", "assessing"},
    "identity_pending": COMMON_TRANSITIONS["identity_pending"] | {"awaiting_visit"},
    "awaiting_visit": {"store_visited", "cancelled", "on_hold"},
    "store_visited": {"assessing", "cancelled", "on_hold"},
    "accepted": {"paid", "payout_pending", "cancelled"},
}

# Statuses that must use barcode / dedicated ops (excluded from manual dropdown)
BARCODE_ONLY_STATUSES = frozenset({"received", "returned"})

# Statuses that require dedicated payout endpoint
DEDICATED_PAYOUT_STATUS = models_buyback.BuybackRequestStatus.paid.value


def status_label(code: str | None) -> str:
    if not code:
        return "—"
    return STATUS_LABELS.get(code, code)


def status_description(code: str | None) -> str | None:
    if not code:
        return None
    return STATUS_DESCRIPTIONS.get(code)


def status_color(code: str | None) -> str:
    if not code:
        return STATUS_COLOR_WAITING
    return STATUS_COLORS.get(code, STATUS_COLOR_WAITING)


def _normalized_method(buyback_method: str | None) -> str:
    from services.buyback_method import normalize_buyback_method

    return normalize_buyback_method(buyback_method)


def progress_steps_for_method(buyback_method: str | None) -> list[str]:
    if _normalized_method(buyback_method) == "store":
        return list(STORE_PROGRESS_STEPS)
    return list(MAIL_PROGRESS_STEPS)


def progress_index(status: str, buyback_method: str | None) -> int:
    method = _normalized_method(buyback_method)
    steps = progress_steps_for_method(method)
    normalized_status = status
    if method == "store" and status == "assessed":
        normalized_status = "awaiting_customer"
    if normalized_status in steps:
        return steps.index(normalized_status)
    fallback = {
        "identity_pending": 0,
        "assessed": steps.index("awaiting_customer") if "awaiting_customer" in steps else 0,
        "return_preparing": max(len(steps) - 2, 0),
        "returned": max(len(steps) - 2, 0),
        "sent_back": 0,
        "on_hold": max(0, len(steps) - 1),
        "rejected": steps.index("assessed") if "assessed" in steps else 0,
        "cancelled": -1,
        "draft": -1,
    }
    return fallback.get(status, 0)


def build_progress_payload(status: str, buyback_method: str | None) -> list[dict[str, object]]:
    steps = progress_steps_for_method(buyback_method)
    current = progress_index(status, buyback_method)
    result: list[dict[str, object]] = []
    for idx, code in enumerate(steps):
        result.append(
            {
                "code": code,
                "label": status_label(code),
                "description": status_description(code),
                "state": (
                    "done"
                    if idx < current
                    else "current"
                    if idx == current
                    else "upcoming"
                ),
            }
        )
    return result


def transitions_for_request(
    status: str,
    buyback_method: str | None,
) -> set[str]:
    if _normalized_method(buyback_method) == "store":
        base = STORE_TRANSITIONS.get(status, set())
    else:
        base = MAIL_TRANSITIONS.get(status, set())
    return set(base)


def allowed_next_statuses(
    request: models_buyback.BuybackRequest,
    *,
    permissions: set[str] | None = None,
) -> list[str]:
    permissions = permissions or set()
    current = request.status or ""
    method = _normalized_method(request.buyback_method)
    next_statuses = transitions_for_request(current, method)
    next_statuses -= BARCODE_ONLY_STATUSES
    next_statuses.discard(DEDICATED_PAYOUT_STATUS)

    if "buyback.request.status.write" not in permissions:
        if "buyback.assessment.write" in permissions:
            next_statuses &= {
                models_buyback.BuybackRequestStatus.assessing.value,
                models_buyback.BuybackRequestStatus.assessed.value,
            }
        else:
            next_statuses.clear()

    return sorted(next_statuses)


def validate_transition(
    current: str,
    new_status: str,
    buyback_method: str | None,
) -> bool:
    allowed = transitions_for_request(current, buyback_method)
    return new_status in allowed
