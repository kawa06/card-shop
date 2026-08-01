"""Transactional admin operations for the buyback catalog."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

import models_buyback
import schemas_buyback


class CatalogConflictError(Exception):
    """The requested catalog identity already exists."""


class CatalogNotFoundError(Exception):
    """The requested catalog product does not exist."""


class CatalogPersistenceError(Exception):
    """The catalog mutation could not be persisted safely."""


class CatalogValidationError(Exception):
    """A caller bypassed request validation with invalid catalog data."""


def _normalized(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip().casefold() or None


def _duplicate_query(
    db: Session,
    *,
    name: str,
    card_number: str | None,
    rarity: str | None,
    pack_name: str | None,
    exclude_product_id: int | None = None,
):
    normalized_pack = _normalized(pack_name)
    normalized_number = _normalized(card_number)
    query = db.query(models_buyback.BuybackProduct)
    if normalized_number is not None:
        query = query.filter(
            func.lower(models_buyback.BuybackProduct.card_number)
            == normalized_number
        )
        if normalized_pack is None:
            query = query.filter(models_buyback.BuybackProduct.pack_name.is_(None))
        else:
            query = query.filter(
                func.lower(models_buyback.BuybackProduct.pack_name) == normalized_pack
            )
    else:
        query = query.filter(
            func.lower(models_buyback.BuybackProduct.name) == name.casefold(),
            models_buyback.BuybackProduct.card_number.is_(None),
        )
        normalized_rarity = _normalized(rarity)
        if normalized_rarity is None:
            query = query.filter(models_buyback.BuybackProduct.rarity.is_(None))
        else:
            query = query.filter(
                func.lower(models_buyback.BuybackProduct.rarity) == normalized_rarity
            )
        if normalized_pack is None:
            query = query.filter(models_buyback.BuybackProduct.pack_name.is_(None))
        else:
            query = query.filter(
                func.lower(models_buyback.BuybackProduct.pack_name) == normalized_pack
            )
    if exclude_product_id is not None:
        query = query.filter(models_buyback.BuybackProduct.id != exclude_product_id)
    return query.order_by(models_buyback.BuybackProduct.id.asc())


def _assert_valid_input(body: schemas_buyback.AdminBuybackCatalogProductIn) -> None:
    """Defend the service boundary when callers use Pydantic model_construct."""
    if not isinstance(body.name, str) or not body.name.strip():
        raise CatalogValidationError("invalid catalog input")
    if not isinstance(body.category, str) or not body.category.strip():
        raise CatalogValidationError("invalid catalog input")
    if type(body.is_active) is not bool or type(body.sort_order) is not int:
        raise CatalogValidationError("invalid catalog input")
    if not isinstance(body.prices, list) or not body.prices:
        raise CatalogValidationError("invalid catalog input")

    seen: set[str] = set()
    for price in body.prices:
        code = getattr(price, "condition_code", None)
        if not isinstance(code, str) or not code.strip():
            raise CatalogValidationError("invalid catalog input")
        normalized_code = code.strip().casefold()
        if normalized_code in seen:
            raise CatalogValidationError("invalid catalog input")
        seen.add(normalized_code)
        for field in (
            "price_normal",
            "price_high",
            "purchase_limit",
            "tier_overflow_price",
        ):
            value = getattr(price, field, None)
            if field == "price_normal" and value is None:
                raise CatalogValidationError("invalid catalog input")
            if value is not None and (type(value) is not int or value < 0):
                raise CatalogValidationError("invalid catalog input")


def list_products(
    db: Session,
    *,
    include_inactive: bool = False,
) -> list[models_buyback.BuybackProduct]:
    query = db.query(models_buyback.BuybackProduct).options(
        selectinload(models_buyback.BuybackProduct.prices)
    )
    if not include_inactive:
        query = query.filter(models_buyback.BuybackProduct.is_active.is_(True))
    rows = query.order_by(
        models_buyback.BuybackProduct.sort_order.asc(),
        models_buyback.BuybackProduct.id.asc(),
    ).all()
    for row in rows:
        row.prices.sort(key=lambda price: (price.condition_code.casefold(), price.id))
    return rows


def _add_history(
    db: Session,
    *,
    product_id: int,
    price: schemas_buyback.AdminBuybackCatalogPriceIn,
    actor_user_id: int,
    source: str,
) -> None:
    db.add(
        models_buyback.BuybackPriceHistory(
            product_id=product_id,
            condition_code=price.condition_code,
            price_normal=price.price_normal,
            price_high=price.price_high,
            changed_by_user_id=actor_user_id,
            source=source,
        )
    )


def create_product(
    db: Session,
    *,
    body: schemas_buyback.AdminBuybackCatalogProductIn,
    actor_user_id: int,
) -> models_buyback.BuybackProduct:
    """Stage one atomic create; the route owns the single commit."""
    try:
        _assert_valid_input(body)
        if _duplicate_query(
            db,
            name=body.name,
            card_number=body.card_number,
            rarity=body.rarity,
            pack_name=body.pack_name,
        ).first():
            raise CatalogConflictError

        product = models_buyback.BuybackProduct(
            name=body.name,
            category=body.category,
            card_number=body.card_number,
            rarity=body.rarity,
            pack_name=body.pack_name,
            image_url=body.image_url,
            notes=body.notes,
            is_active=body.is_active,
            sort_order=body.sort_order,
        )
        db.add(product)
        db.flush()

        for price in body.prices:
            db.add(
                models_buyback.BuybackProductPrice(
                    product_id=product.id,
                    condition_code=price.condition_code,
                    price_normal=price.price_normal,
                    price_high=price.price_high,
                    purchase_limit=price.purchase_limit,
                    tier_overflow_price=price.tier_overflow_price,
                )
            )
            _add_history(
                db,
                product_id=product.id,
                price=price,
                actor_user_id=actor_user_id,
                source="admin_catalog_create",
            )
        db.flush()
        return product
    except CatalogConflictError:
        db.rollback()
        raise
    except CatalogValidationError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise CatalogConflictError from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise CatalogPersistenceError from exc


def update_product(
    db: Session,
    *,
    product_id: int,
    body: schemas_buyback.AdminBuybackCatalogProductIn,
    actor_user_id: int,
) -> models_buyback.BuybackProduct:
    """Stage one atomic update; omitted condition rows remain for snapshots."""
    try:
        _assert_valid_input(body)
        product = (
            db.query(models_buyback.BuybackProduct)
            .options(selectinload(models_buyback.BuybackProduct.prices))
            .filter(models_buyback.BuybackProduct.id == product_id)
            .first()
        )
        if product is None:
            raise CatalogNotFoundError
        if _duplicate_query(
            db,
            name=body.name,
            card_number=body.card_number,
            rarity=body.rarity,
            pack_name=body.pack_name,
            exclude_product_id=product_id,
        ).first():
            raise CatalogConflictError

        product.name = body.name
        product.category = body.category
        product.card_number = body.card_number
        product.rarity = body.rarity
        product.pack_name = body.pack_name
        product.image_url = body.image_url
        product.notes = body.notes
        product.is_active = body.is_active
        product.sort_order = body.sort_order
        product.updated_at = datetime.utcnow()

        existing = {price.condition_code.casefold(): price for price in product.prices}
        for price_in in body.prices:
            price = existing.get(price_in.condition_code.casefold())
            changed = price is None or any(
                (
                    price.price_normal != price_in.price_normal,
                    price.price_high != price_in.price_high,
                    price.purchase_limit != price_in.purchase_limit,
                    price.tier_overflow_price != price_in.tier_overflow_price,
                )
            )
            if price is None:
                price = models_buyback.BuybackProductPrice(product_id=product.id)
                db.add(price)
            price.condition_code = price_in.condition_code
            price.price_normal = price_in.price_normal
            price.price_high = price_in.price_high
            price.purchase_limit = price_in.purchase_limit
            price.tier_overflow_price = price_in.tier_overflow_price
            if changed:
                price.effective_from = datetime.utcnow()
                _add_history(
                    db,
                    product_id=product.id,
                    price=price_in,
                    actor_user_id=actor_user_id,
                    source="admin_catalog_update",
                )
        db.flush()
        return product
    except (CatalogConflictError, CatalogNotFoundError, CatalogValidationError):
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise CatalogConflictError from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise CatalogPersistenceError from exc


def soft_delete_product(
    db: Session,
    *,
    product_id: int,
) -> models_buyback.BuybackProduct:
    """Stage a soft delete without touching request or cart snapshots."""
    try:
        product = (
            db.query(models_buyback.BuybackProduct)
            .filter(models_buyback.BuybackProduct.id == product_id)
            .first()
        )
        if product is None:
            raise CatalogNotFoundError
        product.is_active = False
        product.updated_at = datetime.utcnow()
        db.flush()
        return product
    except CatalogNotFoundError:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise CatalogPersistenceError from exc
