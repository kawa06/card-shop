"""Role and permission definitions for KRX admin security."""

from __future__ import annotations

from typing import Iterable

# All admin roles (code -> display name)
ADMIN_ROLE_DEFINITIONS: dict[str, str] = {
    "owner": "オーナー",
    "admin": "管理者",
    "sales_manager": "販売マネージャー",
    "buyback_manager": "買取マネージャー",
    "appraiser": "査定担当",
    "identity_verifier": "本人確認担当",
    "inventory_manager": "在庫マネージャー",
    "shipping_manager": "発送マネージャー",
    "payment_manager": "決済マネージャー",
    "support_manager": "サポートマネージャー",
    "viewer": "閲覧専用",
}

# Permission codes used by admin security APIs and future modules.
ADMIN_PERMISSION_DEFINITIONS: list[tuple[str, str, str]] = [
    ("admin.users.read", "管理者一覧閲覧", "security"),
    ("admin.users.write", "管理者追加・編集", "security"),
    ("admin.roles.read", "役割閲覧", "security"),
    ("admin.roles.write", "役割・権限変更", "security"),
    ("admin.audit.read", "監査ログ閲覧", "security"),
    ("admin.settings.write", "重要設定変更", "settings"),
    ("admin.pii.read", "個人情報閲覧", "privacy"),
    ("admin.csv.export", "CSV出力", "export"),
    ("admin.reauth", "再認証", "security"),
    ("buyback.request.read", "買取申込閲覧", "buyback"),
    ("buyback.assessment.write", "買取査定変更", "buyback"),
    ("buyback.request.status.write", "買取申込状態変更", "buyback"),
    ("buyback.identity.read", "買取本人確認閲覧", "buyback"),
    ("buyback.identity.write", "買取本人確認審査", "buyback"),
    ("buyback.payout.complete", "買取振込完了", "buyback"),
    ("buyback.catalog.import", "買取カタログ取込", "buyback"),
    ("buyback.catalog.read", "買取カタログ閲覧", "buyback"),
    ("buyback.catalog.write", "買取カタログ変更", "buyback"),
    ("buyback.receive", "買取荷物受付", "buyback"),
    ("buyback.package.read", "梱包情報閲覧", "buyback"),
    ("buyback.package.write", "梱包作成・完了", "buyback"),
    ("buyback.ship.read", "発送先閲覧", "buyback"),
    ("buyback.ship.pii.read", "発送先個人情報閲覧", "buyback"),
    ("buyback.ship.confirm", "発送確定", "buyback"),
    ("buyback.print.internal", "内部ラベル印刷", "buyback"),
    ("buyback.print.pii", "住所付き印刷", "buyback"),
    ("buyback.logs.read", "買取物流ログ閲覧", "buyback"),
]

ROLE_PERMISSION_CODES: dict[str, set[str]] = {
    "owner": {code for code, _, _ in ADMIN_PERMISSION_DEFINITIONS},
    "admin": {
        "admin.users.read",
        "admin.users.write",
        "admin.roles.read",
        "admin.audit.read",
        "admin.settings.write",
        "admin.pii.read",
        "admin.csv.export",
        "admin.reauth",
        "buyback.request.read",
        "buyback.assessment.write",
        "buyback.request.status.write",
        "buyback.identity.read",
        "buyback.identity.write",
        "buyback.payout.complete",
        "buyback.catalog.import",
        "buyback.catalog.read",
        "buyback.catalog.write",
        "buyback.receive",
        "buyback.package.read",
        "buyback.package.write",
        "buyback.ship.read",
        "buyback.ship.pii.read",
        "buyback.ship.confirm",
        "buyback.print.internal",
        "buyback.print.pii",
        "buyback.logs.read",
    },
    "sales_manager": {
        "admin.audit.read",
        "admin.pii.read",
        "admin.csv.export",
        "admin.reauth",
    },
    "buyback_manager": {
        "admin.audit.read",
        "admin.pii.read",
        "admin.csv.export",
        "admin.reauth",
        "buyback.request.read",
        "buyback.assessment.write",
        "buyback.request.status.write",
        "buyback.identity.read",
        "buyback.identity.write",
        "buyback.payout.complete",
        "buyback.catalog.import",
        "buyback.catalog.read",
        "buyback.catalog.write",
        "buyback.receive",
        "buyback.package.read",
        "buyback.package.write",
        "buyback.ship.read",
        "buyback.ship.pii.read",
        "buyback.ship.confirm",
        "buyback.print.internal",
        "buyback.print.pii",
        "buyback.logs.read",
    },
    "appraiser": {
        "admin.reauth",
        "buyback.request.read",
        "buyback.assessment.write",
    },
    "identity_verifier": {
        "admin.audit.read",
        "admin.pii.read",
        "admin.reauth",
        "buyback.identity.read",
        "buyback.identity.write",
    },
    "inventory_manager": {
        "admin.audit.read",
        "admin.csv.export",
        "admin.reauth",
        "buyback.request.read",
        "buyback.receive",
        "buyback.package.read",
        "buyback.print.internal",
        "buyback.logs.read",
    },
    "shipping_manager": {
        "admin.audit.read",
        "admin.csv.export",
        "admin.reauth",
        "buyback.request.read",
        "buyback.package.read",
        "buyback.package.write",
        "buyback.ship.read",
        "buyback.ship.pii.read",
        "buyback.ship.confirm",
        "buyback.print.internal",
        "buyback.print.pii",
        "buyback.logs.read",
    },
    "payment_manager": {
        "admin.audit.read",
        "admin.pii.read",
        "admin.reauth",
        "buyback.request.read",
        "buyback.payout.complete",
    },
    "support_manager": {
        "admin.audit.read",
        "admin.pii.read",
        "admin.reauth",
        "buyback.request.read",
        "buyback.logs.read",
    },
    "viewer": {
        "admin.users.read",
        "admin.roles.read",
        "admin.audit.read",
        "buyback.request.read",
        "buyback.catalog.read",
        "buyback.logs.read",
    },
}

OWNER_ROLE_CODE = "owner"
VIEWER_ROLE_CODE = "viewer"

# Roles that cannot be assigned through normal admin UI/API (owner only via bootstrap).
PROTECTED_ASSIGNMENT_ROLES = {OWNER_ROLE_CODE}

MAX_FAILED_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 30
REAUTH_VALID_MINUTES = 15


def permission_codes_for_role(role_code: str) -> set[str]:
    return set(ROLE_PERMISSION_CODES.get(role_code, set()))


def all_permission_codes() -> Iterable[str]:
    for code, _, _ in ADMIN_PERMISSION_DEFINITIONS:
        yield code
