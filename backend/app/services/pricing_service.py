from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.pricing import PricingRule, PricingAlert, PriceHistory
from app.models.product import Product
from app.models.variant import ProductVariant


def calculate_retail_price(
    cost: Decimal,
    supplier_id: UUID,
    product_type: Optional[str],
    tags: list[str],
    db: Session,
) -> dict:
    """Apply the highest-priority matching rule to compute the retail price."""
    rules = (
        db.query(PricingRule)
        .filter(PricingRule.supplier_id == supplier_id)
        .order_by(PricingRule.priority.desc())
        .all()
    )

    for rule in rules:
        if _rule_matches(rule, cost, product_type, tags):
            price = _apply_markup(cost, rule)
            if rule.round_to:
                price = _apply_rounding(price, rule.round_to)
            if rule.min_price and price < rule.min_price:
                price = rule.min_price
            if rule.max_price and price > rule.max_price:
                price = rule.max_price
            return {"price": price, "rule_name": rule.rule_name or f"Rule {rule.id}"}

    # Fallback: no markup, return cost
    return {"price": cost, "rule_name": None}


def _rule_matches(rule: PricingRule, cost: Decimal, product_type: Optional[str], tags: list[str]) -> bool:
    if rule.condition_type == "always":
        return True
    if rule.condition_type == "cost_range":
        cv = rule.condition_value or {}
        min_v = Decimal(str(cv.get("min", 0)))
        max_v = Decimal(str(cv.get("max", 999999)))
        return min_v <= cost <= max_v
    if rule.condition_type == "product_type":
        return product_type == rule.condition_value.get("type")
    if rule.condition_type == "tag":
        return rule.condition_value.get("tag") in tags
    return False


def _apply_markup(cost: Decimal, rule: PricingRule) -> Decimal:
    if rule.markup_type == "percent":
        return cost * (1 + Decimal(str(rule.markup_value)) / 100)
    if rule.markup_type == "fixed":
        return cost + Decimal(str(rule.markup_value))
    return cost


def _apply_rounding(price: Decimal, round_to: Decimal) -> Decimal:
    """Round price to nearest round_to increment, then set cents to round_to's cents.
    e.g. price=23.45, round_to=0.99 → 22.99 or 23.99 depending on proximity
    """
    cents = round_to % 1
    base = (price - cents).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return base + cents


def apply_price_change(alert: PricingAlert, db: Session):
    """Apply a pricing alert's new price to the product and its variants."""
    product = db.query(Product).filter(Product.id == alert.product_id).first()
    if not product:
        return

    # Record history
    history = PriceHistory(
        product_id=product.id,
        supplier_id=alert.supplier_id,
        price_type="supplier",
        old_price=alert.old_price,
        new_price=alert.new_price,
        change_pct=alert.change_pct,
        source="alert_approval",
    )
    db.add(history)

    # Update supplier price on product
    product.supplier_price = alert.new_price

    # Recalculate retail prices for all variants if we have pricing rules
    if product.supplier_id and alert.new_price:
        result = calculate_retail_price(
            cost=alert.new_price,
            supplier_id=product.supplier_id,
            product_type=product.product_type,
            tags=product.tags or [],
            db=db,
        )
        new_retail = result["price"]
        for variant in product.variants:
            variant.price = new_retail

    db.flush()
