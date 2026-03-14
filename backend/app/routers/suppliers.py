from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.dependencies import get_current_user
from app.models.supplier import Supplier
from app.models.product import Product
from app.models.user import User
from app.schemas.supplier import SupplierCreate, SupplierUpdate, SupplierOut, SupplierStats

router = APIRouter(prefix="/api/v1/suppliers", tags=["suppliers"])


@router.get("/", response_model=list[SupplierOut])
def list_suppliers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    suppliers = db.query(Supplier).filter(Supplier.user_id == current_user.id).all()
    result = []
    for s in suppliers:
        count = db.query(func.count(Product.id)).filter(Product.supplier_id == s.id).scalar()
        out = SupplierOut.model_validate(s)
        out.product_count = count
        result.append(out)
    return result


@router.post("/", response_model=SupplierOut, status_code=status.HTTP_201_CREATED)
def create_supplier(
    payload: SupplierCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    supplier = Supplier(user_id=current_user.id, **payload.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    out = SupplierOut.model_validate(supplier)
    out.product_count = 0
    return out


@router.get("/{supplier_id}", response_model=SupplierOut)
def get_supplier(
    supplier_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    supplier = _get_or_404(supplier_id, current_user.id, db)
    count = db.query(func.count(Product.id)).filter(Product.supplier_id == supplier_id).scalar()
    out = SupplierOut.model_validate(supplier)
    out.product_count = count
    return out


@router.patch("/{supplier_id}", response_model=SupplierOut)
def update_supplier(
    supplier_id: UUID,
    payload: SupplierUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    supplier = _get_or_404(supplier_id, current_user.id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(supplier, field, value)
    db.commit()
    db.refresh(supplier)
    count = db.query(func.count(Product.id)).filter(Product.supplier_id == supplier_id).scalar()
    out = SupplierOut.model_validate(supplier)
    out.product_count = count
    return out


@router.get("/{supplier_id}/stats", response_model=SupplierStats)
def supplier_stats(
    supplier_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate stats for the supplier overview dashboard."""
    _get_or_404(supplier_id, current_user.id, db)
    from app.models.product import Product
    from decimal import Decimal

    products = db.query(Product).filter(
        Product.supplier_id == supplier_id,
        Product.status != "archived",
    ).all()

    count = len(products)
    prices = [float(p.supplier_price) for p in products if p.supplier_price]
    base_prices = [float(p.base_price) for p in products if p.base_price]
    supplier_prices = [float(p.supplier_price) for p in products if p.supplier_price]

    avg_supplier = sum(supplier_prices) / len(supplier_prices) if supplier_prices else None
    avg_base = sum(base_prices) / len(base_prices) if base_prices else None

    margins = []
    for p in products:
        if p.base_price and p.supplier_price and p.base_price > 0:
            margin = (float(p.base_price) - float(p.supplier_price)) / float(p.base_price) * 100
            margins.append(margin)
    avg_margin = sum(margins) / len(margins) if margins else None

    return SupplierStats(
        product_count=count,
        avg_supplier_price=avg_supplier,
        avg_base_price=avg_base,
        avg_margin_pct=avg_margin,
    )


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier(
    supplier_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    supplier = _get_or_404(supplier_id, current_user.id, db)
    db.delete(supplier)
    db.commit()


@router.post("/{supplier_id}/scrape-now")
def scrape_now(
    supplier_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    supplier = _get_or_404(supplier_id, current_user.id, db)
    from app.models.scrape_session import ScrapeSession
    # Mark any stale queued/running sessions as failed (e.g. worker was killed on restart).
    stale = db.query(ScrapeSession).filter(
        ScrapeSession.supplier_id == supplier_id,
        ScrapeSession.status.in_(["queued", "running"]),
    ).all()
    for s in stale:
        s.status = "failed"
        s.error_details = "Interrupted — server restarted or worker was killed"
    if stale:
        db.commit()
    # Create the session now so the frontend has an ID before the Celery task starts.
    config = supplier.scrape_config or {}
    scrape_url = config.get("catalog_url") or supplier.website_url or ""
    session = ScrapeSession(
        supplier_id=supplier_id,
        url=scrape_url,
        status="queued",
    )
    db.add(session)
    db.commit()
    from app.workers.scrape_tasks import scrape_supplier_catalog
    task = scrape_supplier_catalog.delay(str(supplier_id), session_id=str(session.id))
    return {"task_id": task.id, "status": "queued", "session_id": str(session.id)}


@router.get("/{supplier_id}/scrape-status")
def scrape_status(
    supplier_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the most recent scrape session for this supplier."""
    _get_or_404(supplier_id, current_user.id, db)
    from app.models.scrape_session import ScrapeSession
    session = (
        db.query(ScrapeSession)
        .filter(ScrapeSession.supplier_id == supplier_id)
        .order_by(ScrapeSession.started_at.desc())
        .first()
    )
    if not session:
        return {"status": "none"}
    return {
        "session_id": str(session.id),
        "status": session.status,
        "pages_scraped": session.pages_scraped or 0,
        "products_found": session.products_found or 0,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        "error": session.error_details,
    }


class ApproveItemsRequest(BaseModel):
    indices: list[int]


@router.get("/{supplier_id}/scrape-sessions/{session_id}/status")
def scrape_session_status(
    supplier_id: UUID,
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return status for a specific scrape session."""
    _get_or_404(supplier_id, current_user.id, db)
    from app.models.scrape_session import ScrapeSession
    session = db.query(ScrapeSession).filter(
        ScrapeSession.id == session_id,
        ScrapeSession.supplier_id == supplier_id,
    ).first()
    if not session:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": str(session.id),
        "status": session.status,
        "pages_scraped": session.pages_scraped or 0,
        "products_found": session.products_found or 0,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        "error": session.error_details,
    }


@router.get("/{supplier_id}/scrape-sessions/{session_id}/items")
def scrape_session_items(
    supplier_id: UUID,
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the QA-filtered raw items stored in a scrape session."""
    _get_or_404(supplier_id, current_user.id, db)
    from app.models.scrape_session import ScrapeSession
    session = db.query(ScrapeSession).filter(
        ScrapeSession.id == session_id,
        ScrapeSession.supplier_id == supplier_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Scrape session not found")
    return {"items": session.raw_data or [], "total": len(session.raw_data or [])}


@router.post("/{supplier_id}/scrape-sessions/{session_id}/approve")
def approve_scrape_items(
    supplier_id: UUID,
    session_id: UUID,
    payload: ApproveItemsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create products from user-selected raw item indices."""
    _get_or_404(supplier_id, current_user.id, db)
    from app.models.scrape_session import ScrapeSession
    session = db.query(ScrapeSession).filter(
        ScrapeSession.id == session_id,
        ScrapeSession.supplier_id == supplier_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Scrape session not found")
    from app.workers.scrape_tasks import create_products_from_session
    created = create_products_from_session(str(session_id), payload.indices, db)
    # Log that detail scrapes were queued for the approved items
    if created > 0:
        from app.models.detail_scrape_log import DetailScrapeLog
        log = DetailScrapeLog(supplier_id=supplier_id, triggered_by="approval", item_count=created)
        db.add(log)
        db.commit()
    return {"created": created}


class BulkApplySupplierPriceRequest(BaseModel):
    enable_tracking: bool = True  # also set use_supplier_price=True on each product


@router.post("/{supplier_id}/bulk-apply-supplier-price")
def bulk_apply_supplier_price(
    supplier_id: UUID,
    payload: BulkApplySupplierPriceRequest = BulkApplySupplierPriceRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Set base_price = supplier_price for every product from this supplier that has a
    supplier_price recorded. Optionally also enables use_supplier_price tracking.
    """
    _get_or_404(supplier_id, current_user.id, db)
    from app.models.variant import ProductVariant

    products = db.query(Product).filter(
        Product.supplier_id == supplier_id,
        Product.user_id == current_user.id,
        Product.supplier_price.isnot(None),
    ).all()

    for p in products:
        p.base_price = p.supplier_price
        if payload.enable_tracking:
            p.use_supplier_price = True
        # Keep default variant price in sync too
        default_variant = (
            db.query(ProductVariant)
            .filter(ProductVariant.product_id == p.id)
            .order_by(ProductVariant.position)
            .first()
        )
        if default_variant:
            default_variant.price = p.supplier_price

    total = db.query(Product).filter(
        Product.supplier_id == supplier_id,
        Product.user_id == current_user.id,
    ).count()

    db.commit()
    return {
        "updated": len(products),
        "skipped": total - len(products),
        "total": total,
        "tracking_enabled": payload.enable_tracking,
    }


@router.post("/{supplier_id}/rescrape-products")
def rescrape_supplier_products(
    supplier_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Queue a detail re-scrape (description + images) for all existing products from this supplier."""
    from app.models.product import Product
    from app.workers.scrape_tasks import scrape_product_details
    _get_or_404(supplier_id, current_user.id, db)
    products = db.query(Product).filter(
        Product.supplier_id == supplier_id,
        Product.user_id == current_user.id,
        Product.source_url.isnot(None),
    ).all()
    task_ids = [scrape_product_details.delay(str(p.id)).id for p in products]
    if task_ids:
        from app.models.detail_scrape_log import DetailScrapeLog
        log = DetailScrapeLog(supplier_id=supplier_id, triggered_by="rescrape", item_count=len(task_ids))
        db.add(log)
        db.commit()
    return {"queued": len(task_ids), "task_ids": task_ids}


@router.get("/{supplier_id}/scrape-history")
def scrape_history(
    supplier_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the full scrape history for this supplier — catalog pulls and detail pulls."""
    _get_or_404(supplier_id, current_user.id, db)
    from app.models.scrape_session import ScrapeSession
    from app.models.detail_scrape_log import DetailScrapeLog

    sessions = (
        db.query(ScrapeSession)
        .filter(ScrapeSession.supplier_id == supplier_id)
        .order_by(ScrapeSession.started_at.desc())
        .limit(50)
        .all()
    )
    detail_logs = (
        db.query(DetailScrapeLog)
        .filter(DetailScrapeLog.supplier_id == supplier_id)
        .order_by(DetailScrapeLog.created_at.desc())
        .limit(50)
        .all()
    )

    return {
        "catalog_scrapes": [
            {
                "id": str(s.id),
                "url": s.url,
                "status": s.status,
                "pages_scraped": s.pages_scraped or 0,
                "products_found": s.products_found or 0,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "error": s.error_details,
            }
            for s in sessions
        ],
        "detail_scrapes": [
            {
                "id": str(d.id),
                "triggered_by": d.triggered_by,
                "item_count": d.item_count,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in detail_logs
        ],
    }


@router.post("/{supplier_id}/test-scrape")
def test_scrape(
    supplier_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    supplier = _get_or_404(supplier_id, current_user.id, db)
    if not supplier.website_url:
        raise HTTPException(status_code=400, detail="Supplier has no website URL configured")
    from app.services.scrape_service import test_scrape_supplier
    return test_scrape_supplier(supplier)


class SuggestSelectorsRequest(BaseModel):
    catalog_url: Optional[str] = None


@router.post("/{supplier_id}/suggest-selectors")
def suggest_selectors(
    supplier_id: UUID,
    payload: SuggestSelectorsRequest = SuggestSelectorsRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    supplier = _get_or_404(supplier_id, current_user.id, db)
    if not supplier.website_url and not payload.catalog_url:
        raise HTTPException(status_code=400, detail="Supplier has no website URL configured")
    from app.services.scrape_service import suggest_selectors_with_ai
    result = suggest_selectors_with_ai(supplier, url=payload.catalog_url or None)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Selector suggestion failed"))
    return result


def _get_or_404(supplier_id: UUID, user_id, db: Session) -> Supplier:
    s = db.query(Supplier).filter(
        Supplier.id == supplier_id, Supplier.user_id == user_id
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return s
