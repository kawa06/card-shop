from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas
from services.shipping_rates import refresh_all_rates, calculate_shipping_fee, calculate_shipping_quote
from services.countries import is_domestic_japan, is_supported_checkout_country
from services.countries import get_all_countries
from auth import get_current_user
from typing import Optional

router = APIRouter(prefix="/api", tags=["shipping"])

@router.get("/shipping-rates")
def get_shipping_rates(
    method: Optional[str] = None,
    prefecture: Optional[str] = None,
    db: Session = Depends(get_db)
):
    if method and prefecture:
        fee = calculate_shipping_fee(method, prefecture, db=db)
        return {"fee": fee, "method": method, "prefecture": prefecture}
        
    rates = db.query(models.ShippingRate).all()
    if not rates:
        return []
    return [r for r in rates if r.method_code != "international"]

@router.get("/shipping-rates/calculate")
def get_calculated_shipping(
    method_code: str,
    region: Optional[str] = None,
    country: str = "Japan",
    db: Session = Depends(get_db)
):
    if not is_domestic_japan(country) and not is_supported_checkout_country(country):
        raise HTTPException(status_code=400, detail="Unsupported destination country")
    return calculate_shipping_quote(method_code, region, country, db=db)

@router.post("/shipping-rates/international")
def post_calculate_international_shipping(
    data: dict, # {country_code, postal_code, weight, shipping_method}
    db: Session = Depends(get_db)
):
    country = data.get("country_code", "Other")
    method = data.get("shipping_method", "ems")
    fee = calculate_shipping_fee(method, country=country, db=db)
    return {"country_code": country, "fee_jpy": fee, "shipping_method": method}

@router.get("/countries")
def get_countries():
    return get_all_countries()

@router.patch("/shipping-rates/{method_code}", response_model=schemas.ShippingRateOut)
def update_shipping_rate(
    method_code: str,
    rate_update: schemas.ShippingRateUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can update rates")
    
    db_rate = db.query(models.ShippingRate).filter(models.ShippingRate.method_code == method_code).first()
    if not db_rate:
        raise HTTPException(status_code=404, detail="Shipping rate not found")
    
    update_data = rate_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_rate, key, value)
    
    db.commit()
    db.refresh(db_rate)
    return db_rate

@router.get("/shipping-rates/debug")
def debug_shipping():
    return {"status": "shipping routes loaded", "prefix": "/api/shipping-rates"}

@router.post("/shipping-rates/refresh", status_code=status.HTTP_200_OK)
async def manual_refresh_rates(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can refresh rates")
    
    await refresh_all_rates(db)
    return {"message": "Shipping rates refreshed"}
