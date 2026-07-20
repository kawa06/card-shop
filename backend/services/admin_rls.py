"""PostgreSQL RLS policies for admin security tables (defense in depth)."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

from config import settings
from database import engine

logger = logging.getLogger(__name__)

ADMIN_SECURITY_TABLES = (
    "admin_roles",
    "admin_permissions",
    "admin_role_permissions",
    "admin_users",
    "admin_audit_logs",
)


def apply_admin_rls_policies() -> None:
    url = settings.DATABASE_URL
    if not (url.startswith("postgresql") or url.startswith("postgres")):
        logger.info("Skipping admin RLS (non-PostgreSQL database)")
        return

    inspector = inspect(engine)
    existing = set(inspector.get_table_names())

    with engine.connect() as conn:
        for table in ADMIN_SECURITY_TABLES:
            if table not in existing:
                continue
            conn.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
            conn.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))

            conn.execute(
                text(f"DROP POLICY IF EXISTS {table}_backend_only ON {table}")
            )
            conn.execute(
                text(
                    f"""
                    CREATE POLICY {table}_backend_only ON {table}
                    FOR ALL
                    USING (current_setting('krx.is_backend', true) = 'true')
                    WITH CHECK (current_setting('krx.is_backend', true) = 'true')
                    """
                )
            )
        conn.commit()
    logger.info("Applied admin RLS policies on PostgreSQL")


def set_backend_rls_context(conn) -> None:
    """Mark connection as trusted backend service (equivalent to service_role)."""
    url = settings.DATABASE_URL
    if url.startswith("postgresql") or url.startswith("postgres"):
        conn.execute(text("SET LOCAL krx.is_backend = 'true'"))
