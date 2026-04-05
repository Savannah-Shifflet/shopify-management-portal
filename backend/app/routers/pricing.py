from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.dependencies import get_current_user
from app.models.pricing import PricingAlert, PricingRule, PricingSchedule
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User
from app.schemas.pricing import (
    PricingAlertOut, AlertReviewRequest,
    PricingRuleCreate, PricingRuleUpdate, PricingRuleOut,
    PricingScheduleCreate, PricingScheduleUpdate, PricingScheduleOut,
    PriceCalculateRequest, PriceCalculateResponse,
    BulkPriceUpdateRequest, BulkPriceUpdateResponse,
)

router = APIRouter(prefix="/api/v1/pricing", tags=["pricing"])


# ── Alerts ─────────────────────────────────────────────────────────────────────

@router.get("/alerts", response_model=list[PricingAlertOut])
def list_alerts(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(PricingAlert).filter(PricingAlert.user_id == current_user.id)
    if status_filter:
        q = q.filter(PricingAlert.status == status_filter)
    else:
        q = q.filter(PricingAlert.status == "pending")
    alerts = q.order_by(PricingAlert.created_at.desc()).all()

    result = []
    for a in alerts:
        product = db.query(Product).filter(Product.id == a.product_id).first()
        supplier = db.query(Supplier).filter(Supplier.id == a.supplier_id).first() if a.supplier_id else None
        out = PricingAlertOut.model_validate(a)
        out.product_title = product.title if product else None
        out.supplier_name = supplier.name if supplier else None
        result.append(out)
    return result


@router.post("/alerts/{alert_id}/approve")
def approve_alert(
    alert_id: UUID,
    payload: AlertReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = _get_alert_or_404(alert_id, current_user.id, db)
    if alert.status != "pending":
        raise HTTPException(status_code=400, detail="Alert is not pending")

    from app.services.pricing_service import apply_price_change
    apply_price_change(alert, db)

    alert.status = "approved"
    alert.reviewed_at = datetime.utcnow()
    alert.notes = payload.notes
    db.commit()

    from app.workers.sync_tasks import sync_price_update_only
    sync_price_update_only.delay(str(alert.product_id))

    return {"status": "approved"}


@router.post("/alerts/{alert_id}/reject")
def reject_alert(
    alert_id: UUID,
    payload: AlertReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = _get_alert_or_404(alert_id, current_user.id, db)
    if alert.status != "pending":
        raise HTTPException(status_code=400, detail="Alert is not pending")
    alert.status = "rejected"
    alert.reviewed_at = datetime.utcnow()
    alert.notes = payload.notes
    db.commit()
    return {"status": "rejected"}


@router.post("/alerts/bulk-approve")
def bulk_approve_alerts(
    alert_ids: list[UUID],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.pricing_service import apply_price_change
    from app.workers.sync_tasks import sync_price_update_only

    alerts = db.query(PricingAlert).filter(
        PricingAlert.id.in_(alert_ids),
        PricingAlert.user_id == current_user.id,
        PricingAlert.status == "pending",
    ).all()

    for alert in alerts:
        apply_price_change(alert, db)
        alert.status = "approved"
        alert.reviewed_at = datetime.utcnow()
        sync_price_update_only.delay(str(alert.product_id))

    db.commit()
    return {"approved": len(alerts)}


# ── Pricing Rules ──────────────────────────────────────────────────────────────

@router.get("/rules", response_model=list[PricingRuleOut])
def list_rules(
    supplier_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Scope to suppliers owned by the current user — PricingRule has no user_id column
    owned_supplier_ids = (
        db.query(Supplier.id).filter(Supplier.user_id == current_user.id).subquery()
    )
    q = db.query(PricingRule).filter(PricingRule.supplier_id.in_(owned_supplier_ids))
    if supplier_id:
        q = q.filter(PricingRule.supplier_id == supplier_id)
    return q.order_by(PricingRule.priority.desc()).all()


@router.post("/rules", response_model=PricingRuleOut, status_code=status.HTTP_201_CREATED)
def create_rule(
    payload: PricingRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify the target supplier belongs to the current user
    supplier = db.query(Supplier).filter(
        Supplier.id == payload.supplier_id,
        Supplier.user_id == current_user.id,
    ).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    rule = PricingRule(**payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.patch("/rules/{rule_id}", response_model=PricingRuleOut)
def update_rule(
    rule_id: UUID,
    payload: PricingRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rule = _get_rule_or_404(rule_id, current_user.id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(
    rule_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rule = _get_rule_or_404(rule_id, current_user.id, db)
    db.delete(rule)
    db.commit()


# ── Pricing Schedules ──────────────────────────────────────────────────────────

@router.get("/schedules", response_model=list[PricingScheduleOut])
def list_schedules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(PricingSchedule).filter(
        PricingSchedule.user_id == current_user.id
    ).order_by(PricingSchedule.starts_at).all()


@router.post("/schedules", response_model=PricingScheduleOut, status_code=status.HTTP_201_CREATED)
def create_schedule(
    payload: PricingScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    schedule = PricingSchedule(user_id=current_user.id, **payload.model_dump())
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


@router.patch("/schedules/{schedule_id}", response_model=PricingScheduleOut)
def update_schedule(
    schedule_id: UUID,
    payload: PricingScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    schedule = db.query(PricingSchedule).filter(
        PricingSchedule.id == schedule_id,
        PricingSchedule.user_id == current_user.id,
    ).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(schedule, field, value)
    db.commit()
    db.refresh(schedule)
    return schedule


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_schedule(
    schedule_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    schedule = db.query(PricingSchedule).filter(
        PricingSchedule.id == schedule_id,
        PricingSchedule.user_id == current_user.id,
    ).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    schedule.status = "cancelled"
    db.commit()


# ── Price calculation preview ──────────────────────────────────────────────────

@router.post("/calculate", response_model=PriceCalculateResponse)
def calculate_price(
    payload: PriceCalculateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.pricing_service import calculate_retail_price
    from app.models.store_settings import StoreSettings
    from decimal import Decimal

    store = db.query(StoreSettings).filter(StoreSettings.user_id == current_user.id).first()
    default_markup_pct = Decimal(str(store.default_markup_pct)) if store and store.default_markup_pct else None
    global_shipping = Decimal(str(store.default_shipping_cost)) if store and store.default_shipping_cost else None

    shipping = payload.shipping_cost if payload.shipping_cost is not None else global_shipping
    effective_cost = payload.cost_price + (shipping or Decimal("0"))

    result = calculate_retail_price(
        cost=payload.cost_price,
        supplier_id=payload.supplier_id,
        product_type=payload.product_type,
        tags=payload.tags or [],
        db=db,
        shipping_cost=shipping,
        default_markup_pct=default_markup_pct,
    )
    margin = None
    if effective_cost and result["price"] and result["price"] > 0:
        margin = float((result["price"] - effective_cost) / result["price"] * 100)
    return PriceCalculateResponse(
        cost_price=payload.cost_price,
        shipping_cost=shipping,
        effective_cost=effective_cost,
        calculated_price=result["price"],
        rule_applied=result["rule_name"],
        margin_pct=margin,
    )


@router.post("/bulk-update", response_model=BulkPriceUpdateResponse)
def bulk_price_update(
    payload: BulkPriceUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a price field on multiple products at once.

    action values:
      set          — set the field to exactly `value`
      percent_markup — new_price = current * (1 + value/100)  [for base_price only]
      percent_off  — new_price = current * (1 - value/100)
      fixed_off    — new_price = max(current - value, 0)
    """
    from decimal import Decimal
    from app.services.pricing_service import record_price_history

    ALLOWED_FIELDS = {"base_price", "cost_price", "map_price", "shipping_cost"}
    if payload.price_type not in ALLOWED_FIELDS:
        raise HTTPException(status_code=400, detail=f"price_type must be one of {sorted(ALLOWED_FIELDS)}")
    ALLOWED_ACTIONS = {"set", "percent_markup", "percent_off", "fixed_off"}
    if payload.action not in ALLOWED_ACTIONS:
        raise HTTPException(status_code=400, detail=f"action must be one of {sorted(ALLOWED_ACTIONS)}")

    products = db.query(Product).filter(
        Product.id.in_(payload.product_ids),
        Product.user_id == current_user.id,
    ).all()

    updated = 0
    skipped = 0
    for product in products:
        old_val = getattr(product, payload.price_type)
        if payload.action == "set":
            new_val = payload.value
        else:
            if old_val is None:
                skipped += 1
                continue
            old_dec = Decimal(str(old_val))
            if payload.action == "percent_markup":
                new_val = old_dec * (1 + payload.value / 100)
            elif payload.action == "percent_off":
                new_val = old_dec * (1 - payload.value / 100)
            else:  # fixed_off
                new_val = max(old_dec - payload.value, Decimal("0"))

        setattr(product, payload.price_type, new_val)

        # Record price history for base_price and cost_price changes
        if payload.price_type in ("base_price", "cost_price") and old_val != new_val:
            price_type_map = {"base_price": "retail", "cost_price": "cost"}
            record_price_history(
                db, product.id, old_val, new_val,
                source="manual",
                price_type=price_type_map[payload.price_type],
            )
        # Flag for re-sync if retail price changed
        if payload.price_type == "base_price" and product.sync_status == "synced":
            product.sync_status = "out_of_sync"
            product.shopify_hash = None

        updated += 1

    db.commit()
    return BulkPriceUpdateResponse(updated=updated, skipped=skipped)


# ── Helper ─────────────────────────────────────────────────────────────────────

def _get_alert_or_404(alert_id: UUID, user_id, db: Session) -> PricingAlert:
    alert = db.query(PricingAlert).filter(
        PricingAlert.id == alert_id,
        PricingAlert.user_id == user_id,
    ).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


def _get_rule_or_404(rule_id: UUID, user_id, db: Session) -> PricingRule:
    """Verify ownership via the supplier FK — PricingRule has no user_id column."""
    rule = (
        db.query(PricingRule)
        .join(Supplier, Supplier.id == PricingRule.supplier_id)
        .filter(PricingRule.id == rule_id, Supplier.user_id == user_id)
        .first()
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule
