"""Phase 3-7: Admin analytics export audit (additive only)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, Index

from database import Base


class AnalyticsExportLog(Base):
    __tablename__ = "analytics_export_logs"
    __table_args__ = (Index("ix_analytics_export_logs_created", "created_at"),)

    id = Column(Integer, primary_key=True, index=True)
    actor_admin_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    domain = Column(String(32), nullable=False, index=True)
    export_format = Column(String(16), nullable=False)
    row_count = Column(Integer, default=0, nullable=False)
    filters_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
