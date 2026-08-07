"""Shop-wide point settings access."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

import models_points


def get_point_settings(db: Session) -> models_points.PointSettings:
    row = db.query(models_points.PointSettings).filter(models_points.PointSettings.shop_id == 1).first()
    if row is None:
        row = models_points.PointSettings(shop_id=1)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def update_point_settings(db: Session, **fields) -> models_points.PointSettings:
    settings = get_point_settings(db)
    for key, value in fields.items():
        if value is not None and hasattr(settings, key):
            setattr(settings, key, value)
    settings.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(settings)
    return settings
