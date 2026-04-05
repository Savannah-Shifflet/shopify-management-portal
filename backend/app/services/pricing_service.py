from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.pricing import PricingRule, PricingAlert, PriceHistory
from app.models.product import Product
from app.models.variant import ProductVariant


def record_price_history(
    db: Session,
    product_id,
    old_price: Optional[Decimal],
    new_price: Decimal,
    source: str,
    price_type: str = "retail",
    supplier_id=None,
    variant_id=None,
) -> Optional[PriceHistory]:
    """
    Record a price change. No-op if old_price is None or unchanged.

    source values: 'manual' | 'scrape' | 'scheduled' | 'scheduled_revert' |
                   'alert_approval' | 'csv_import' | 'api'
    price_type:    'retail' | 'supplier' | 'cost' | 'promo'
    """
    if old_price is None or old_price == new_price:
        return None
    change_pct = (
        abs((new_price - old_price) / old_price * 100)
        if old_price != 0
        else Decimal("100")
    )
    entry = PriceHistory(
        product_id=product_id,
        variant_id=variant_id,
        supplier_id=supplier_id,
        price_type=price_type,
        old_price=old_price,
        new_price=new_price,
        change_pct=change_pct,
        source=source,
    )
    db.add(entry)
    return entry


def calculate_retail_price(
    cost: Decimal,
    supplier_id: Optional[UUID],
    product_type: Optional[str],
    tags: list[str],
    db: Session,
    shipping_cost: Optional[Decimal] = None,
    default_markup_pct: Optional[Decimal] = None,
) -> dict:
    """Apply the highest-priority matching rule to compute the retail price.

    shipping_cost is added to cost before markup so the reseller can offer
    free shipping while still covering the actual shipping expense.

    default_markup_pct is used as a fallback when no supplier rule matches.
    """
    effective_cost = cost + (shipping_cost or Decimal("0"))

    if supplier_id:
        rules = (
            db.query(PricingRule)
            .filter(PricingRule.supplier_id == supplier_id)
            .order_by(PricingRule.priority.desc())
            .all()
        )

        for rule in rules:
            if _rule_matches(rule, effective_cost, product_type, tags):
                price = _apply_markup(effective_cost, rule)
                if rule.round_to:
                    price = _apply_rounding(price, rule.round_to)
                if rule.min_price and price < rule.min_price:
                    price = rule.min_price
                if rule.max_price and price > rule.max_price:
                    price = rule.max_price
                return {"price": price, "rule_name": rule.rule_name or f"Rule {rule.id}"}

    # Fallback: global default markup if configured
    if default_markup_pct:
        price = effective_cost * (1 + Decimal(str(default_markup_pct)) / 100)
        return {"price": price, "rule_name": f"Default {default_markup_pct}% markup"}

    # No rule and no default — return effective cost (shipping baked in, no margin)
    return {"price": effective_cost, "rule_name": None}


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
    if alert.new_price:
        from app.models.store_settings import StoreSettings
        from decimal import Decimal as _Decimal
        store = db.query(StoreSettings).filter(StoreSettings.user_id == product.user_id).first()
        default_markup_pct = _Decimal(str(store.default_markup_pct)) if store and store.default_markup_pct else None
        shipping = product.shipping_cost or (
            _Decimal(str(store.default_shipping_cost)) if store and store.default_shipping_cost else None
        )
        result = calculate_retail_price(
            cost=alert.new_price,
            supplier_id=product.supplier_id,
            product_type=product.product_type,
            tags=product.tags or [],
            db=db,
            shipping_cost=shipping,
            default_markup_pct=default_markup_pct,
        )
        new_retail = result["price"]
        for variant in product.variants:
            variant.price = new_retail

    db.flush()
