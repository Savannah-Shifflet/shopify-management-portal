from collections import defaultdict
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User
from app.utils.shopify_client import ShopifyClient

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/orders")
def get_order_analytics(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch order analytics from Shopify Orders REST API."""
    try:
        client = ShopifyClient.from_user(current_user, db)
    except RuntimeError:
        return {
            "connected": False,
            "total_revenue": 0,
            "order_count": 0,
            "avg_order_value": 0,
            "products_sold": 0,
            "revenue_by_date": [],
            "top_products": [],
            "top_suppliers": [],
        }

    since = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"
    all_orders = []
    page_info = None

    while True:
        params = {
            "status": "any",
            "created_at_min": since,
            "limit": 250,
            "financial_status": "paid",
        }
        if page_info:
            params = {"limit": 250, "page_info": page_info}

        resp = httpx.get(
            f"{client.base_url}/orders.json",
            headers=client.headers,
            params=params,
            timeout=30,
        )
        if not resp.is_success:
            break

        data = resp.json()
        orders = data.get("orders", [])
        all_orders.extend(orders)

        # Check for next page via Link header
        link_header = resp.headers.get("Link", "")
        if 'rel="next"' in link_header:
            import re
            match = re.search(r'page_info=([^&>]+).*rel="next"', link_header)
            page_info = match.group(1) if match else None
        else:
            break

        if not page_info:
            break

    # --- Aggregate ---
    total_revenue = 0.0
    order_count = len(all_orders)
    products_sold = 0
    revenue_by_date: dict[str, float] = defaultdict(float)
    sku_revenue: dict[str, dict] = defaultdict(lambda: {"revenue": 0.0, "quantity": 0, "title": ""})

    for order in all_orders:
        subtotal = float(order.get("subtotal_price") or 0)
        total_revenue += subtotal
        date_str = (order.get("created_at") or "")[:10]
        revenue_by_date[date_str] += subtotal

        for item in order.get("line_items", []):
            qty = item.get("quantity", 0)
            price = float(item.get("price") or 0)
            sku = item.get("sku") or item.get("name", "unknown")
            products_sold += qty
            sku_revenue[sku]["revenue"] += price * qty
            sku_revenue[sku]["quantity"] += qty
            sku_revenue[sku]["title"] = item.get("name") or sku

    avg_order_value = (total_revenue / order_count) if order_count > 0 else 0

    # Top 10 products by revenue
    top_products = sorted(
        [{"sku": k, "title": v["title"], "revenue": round(v["revenue"], 2), "quantity": v["quantity"]}
         for k, v in sku_revenue.items()],
        key=lambda x: x["revenue"],
        reverse=True,
    )[:10]

    # Revenue by supplier — join sku → ProductVariant → Product → Supplier
    from app.models.variant import ProductVariant
    supplier_revenue: dict[str, float] = defaultdict(float)
    for sku, data in sku_revenue.items():
        product = (
            db.query(Product)
            .join(Product.variants)
            .filter(
                Product.user_id == current_user.id,
                ProductVariant.sku == sku,
            )
            .first()
        )
        if product and product.supplier_id:
            supplier = db.query(Supplier).filter(
                Supplier.id == product.supplier_id,
                Supplier.user_id == current_user.id,
            ).first()
            supplier_name = supplier.name if supplier else "Unknown"
            supplier_revenue[supplier_name] += data["revenue"]
        else:
            supplier_revenue["Unassigned"] += data["revenue"]

    top_suppliers = sorted(
        [{"name": k, "revenue": round(v, 2)} for k, v in supplier_revenue.items()],
        key=lambda x: x["revenue"],
        reverse=True,
    )[:10]

    # Sort revenue_by_date
    sorted_dates = sorted(revenue_by_date.items())

    return {
        "connected": True,
        "days": days,
        "total_revenue": round(total_revenue, 2),
        "order_count": order_count,
        "avg_order_value": round(avg_order_value, 2),
        "products_sold": products_sold,
        "revenue_by_date": [{"date": d, "revenue": round(r, 2)} for d, r in sorted_dates],
        "top_products": top_products,
        "top_suppliers": top_suppliers,
    }
