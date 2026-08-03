"""Buyback admin permission helpers — KYC / payout separation from card-shop admin."""

from __future__ import annotations

from services.admin_auth import AdminContext

# New permission codes may satisfy legacy buyback.* codes during migration.
_PERMISSION_ALIASES: dict[str, set[str]] = {
    "kyc.view": {"buyback.identity.read"},
    "kyc.review": {"buyback.identity.write"},
    "kyc.document.view": {"buyback.identity.read"},
    "kyc.document.print": {"buyback.identity.read"},
    "guardian_consent.view": {"buyback.identity.read"},
    "payout.view": {"buyback.payout.complete"},
    "payout.bank_account.view": {"buyback.payout.complete"},
    "payout.execute": {"buyback.payout.complete"},
    "payout.complete": {"buyback.payout.complete"},
    "audit_log.view": {"buyback.logs.read"},
}


def has_buyback_perm(ctx: AdminContext, code: str) -> bool:
    perms = set(ctx.permissions or [])
    if code in perms:
        return True
    return bool(perms.intersection(_PERMISSION_ALIASES.get(code, set())))


def has_any_buyback_perm(ctx: AdminContext, *codes: str) -> bool:
    return any(has_buyback_perm(ctx, code) for code in codes)


def can_view_kyc(ctx: AdminContext) -> bool:
    return has_any_buyback_perm(ctx, "kyc.view")


def can_review_kyc(ctx: AdminContext) -> bool:
    return has_any_buyback_perm(ctx, "kyc.review")


def can_view_kyc_documents(ctx: AdminContext) -> bool:
    return has_any_buyback_perm(ctx, "kyc.document.view")


def can_view_payout_queue(ctx: AdminContext) -> bool:
    return has_any_buyback_perm(ctx, "payout.view")


def can_view_bank_account(ctx: AdminContext) -> bool:
    return has_any_buyback_perm(ctx, "payout.bank_account.view")


def can_complete_payout(ctx: AdminContext) -> bool:
    return has_any_buyback_perm(ctx, "payout.complete", "payout.execute")
