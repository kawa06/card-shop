from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas
from services.shipping_rates import refresh_all_rates, calculate_shipping_fee
from auth import get_current_user
from typing import Optional

router = APIRouter(prefix="/shipping-rates", tags=["shipping"])

@router.get("", response_model=list[schemas.ShippingRateOut])
def get_shipping_rates(db: Session = Depends(get_db)):
    rates = db.query(models.ShippingRate).all()
    if not rates:
        # If empty, try to refresh once synchronously (or wait for first background task)
        return []
    return rates

@router.get("/calculate")
def get_calculated_shipping(
    method_code: str,
    region: Optional[str] = None,
    country: str = "Japan",
    db: Session = Depends(get_db)
):
    fee = calculate_shipping_fee(method_code, region, country)
    return {"method_code": method_code, "fee_jpy": fee}

@router.post("/refresh", status_code=status.HTTP_200_OK)
async def manual_refresh_rates(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can refresh rates")
    
    await refresh_all_rates(db)
    return {"message": "Shipping rates refreshed"}
