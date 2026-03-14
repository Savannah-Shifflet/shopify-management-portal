import uuid as uuid_module
from datetime import datetime
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
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


# ── SRM inline schemas ────────────────────────────────────────────────────────

from datetime import datetime as dt_type

class StatusUpdate(BaseModel):
    status: str

class EmailIn(BaseModel):
    direction: str  # INBOUND | OUTBOUND
    subject: Optional[str] = None
    body: Optional[str] = None
    sent_at: Optional[dt_type] = None
    attachments: Optional[list] = None

class SendEmailIn(BaseModel):
    to_email: str
    subject: str
    body: str

class ChecklistItemIn(BaseModel):
    label: str

class ChecklistItemUpdate(BaseModel):
    completed: Optional[bool] = None
    notes: Optional[str] = None

class ReorderIn(BaseModel):
    po_number: Optional[str] = None
    order_date: Optional[str] = None
    expected_delivery: Optional[str] = None
    status: str = "Pending"
    line_items: Optional[list] = None
    notes: Optional[str] = None

class ReorderUpdate(BaseModel):
    po_number: Optional[str] = None
    status: Optional[str] = None
    expected_delivery: Optional[str] = None
    notes: Optional[str] = None


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


# ── Pipeline / status ─────────────────────────────────────────────────────────

@router.patch("/{supplier_id}/status")
def update_status(
    supplier_id: UUID,
    payload: StatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    supplier = _get_or_404(supplier_id, current_user.id, db)
    old_status = supplier.status
    supplier.status = payload.status
    if payload.status == "APPROVED" and not supplier.approved_at:
        supplier.approved_at = datetime.utcnow()
    db.commit()
    _audit(db, current_user.id, "SUPPLIER_STATUS_CHANGE", "Supplier", str(supplier_id),
           f"{supplier.name}: {old_status} → {payload.status}")
    return {"status": supplier.status}

# ── Emails ────────────────────────────────────────────────────────────────────

@router.get("/{supplier_id}/emails")
def list_emails(supplier_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _get_or_404(supplier_id, current_user.id, db)
    from app.models.supplier_email import SupplierEmail
    emails = db.query(SupplierEmail).filter(SupplierEmail.supplier_id == supplier_id).order_by(SupplierEmail.sent_at).all()
    return [{"id": str(e.id), "direction": e.direction, "subject": e.subject, "body": e.body,
             "sent_at": e.sent_at.isoformat(), "attachments": e.attachments or []} for e in emails]

@router.post("/{supplier_id}/emails")
def log_email(supplier_id: UUID, payload: EmailIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    supplier = _get_or_404(supplier_id, current_user.id, db)
    from app.models.supplier_email import SupplierEmail
    from datetime import datetime as _dt
    email = SupplierEmail(
        supplier_id=supplier_id,
        direction=payload.direction,
        subject=payload.subject,
        body=payload.body,
        sent_at=payload.sent_at or _dt.utcnow(),
        attachments=payload.attachments or [],
    )
    db.add(email)
    if payload.direction == "OUTBOUND" and supplier.status == "LEAD":
        supplier.status = "CONTACTED"
    db.commit()
    _audit(db, current_user.id, "EMAIL_LOGGED", "Supplier", str(supplier_id),
           f"{'Sent to' if payload.direction == 'OUTBOUND' else 'Received from'} {supplier.name}: {payload.subject}")
    return {"id": str(email.id)}

@router.post("/{supplier_id}/emails/send")
def send_email(supplier_id: UUID, payload: SendEmailIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Send an email via SMTP and log it."""
    supplier = _get_or_404(supplier_id, current_user.id, db)
    from app.models.store_settings import StoreSettings
    from app.models.supplier_email import SupplierEmail
    from datetime import datetime as _dt
    settings = db.query(StoreSettings).filter(StoreSettings.user_id == current_user.id).first()
    if not settings or not settings.smtp_host:
        raise HTTPException(status_code=400, detail="SMTP not configured. Go to Settings to configure email.")
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        msg = MIMEMultipart("alternative")
        msg["Subject"] = payload.subject
        msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
        msg["To"] = payload.to_email
        msg.attach(MIMEText(payload.body, "html"))
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port or 587) as server:
            server.starttls()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_from_email, payload.to_email, msg.as_string())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")
    email = SupplierEmail(supplier_id=supplier_id, direction="OUTBOUND",
                          subject=payload.subject, body=payload.body, sent_at=_dt.utcnow())
    db.add(email)
    if supplier.status == "LEAD":
        supplier.status = "CONTACTED"
    db.commit()
    _audit(db, current_user.id, "EMAIL_SENT", "Supplier", str(supplier_id),
           f"Email sent to {supplier.name}: {payload.subject}")
    return {"sent": True}

# ── Documents ─────────────────────────────────────────────────────────────────

@router.get("/{supplier_id}/documents")
def list_documents(supplier_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _get_or_404(supplier_id, current_user.id, db)
    from app.models.supplier_document import SupplierDocument
    docs = db.query(SupplierDocument).filter(SupplierDocument.supplier_id == supplier_id).order_by(SupplierDocument.uploaded_at.desc()).all()
    return [{"id": str(d.id), "name": d.name, "category": d.category, "file_name": d.file_name,
             "mime_type": d.mime_type, "expires_at": d.expires_at.isoformat() if d.expires_at else None,
             "uploaded_at": d.uploaded_at.isoformat()} for d in docs]

@router.post("/{supplier_id}/documents")
async def upload_document(
    supplier_id: UUID,
    name: str,
    category: str = "Other",
    expires_at: Optional[str] = None,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_or_404(supplier_id, current_user.id, db)
    from app.models.supplier_document import SupplierDocument
    import os, shutil
    from datetime import datetime as dt
    upload_dir = f"uploads/supplier_docs/{supplier_id}"
    os.makedirs(upload_dir, exist_ok=True)
    safe_name = f"{uuid_module.uuid4()}_{file.filename}"
    file_path = f"{upload_dir}/{safe_name}"
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    exp = dt.fromisoformat(expires_at) if expires_at else None
    doc = SupplierDocument(supplier_id=supplier_id, name=name, category=category,
                           file_path=file_path, file_name=file.filename,
                           mime_type=file.content_type, expires_at=exp,
                           uploaded_at=dt.utcnow())
    db.add(doc)
    db.commit()
    return {"id": str(doc.id)}

@router.delete("/{supplier_id}/documents/{doc_id}", status_code=204)
def delete_document(supplier_id: UUID, doc_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _get_or_404(supplier_id, current_user.id, db)
    from app.models.supplier_document import SupplierDocument
    doc = db.query(SupplierDocument).filter(SupplierDocument.id == doc_id, SupplierDocument.supplier_id == supplier_id).first()
    if doc:
        db.delete(doc)
        db.commit()

# ── Checklist ─────────────────────────────────────────────────────────────────

@router.get("/{supplier_id}/checklist")
def get_checklist(supplier_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _get_or_404(supplier_id, current_user.id, db)
    from app.models.checklist import SupplierChecklistItem
    items = db.query(SupplierChecklistItem).filter(SupplierChecklistItem.supplier_id == supplier_id).all()
    return [{"id": str(i.id), "label": i.label, "completed": i.completed, "notes": i.notes, "file_name": i.file_name} for i in items]

@router.post("/{supplier_id}/checklist")
def add_checklist_item(supplier_id: UUID, payload: ChecklistItemIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _get_or_404(supplier_id, current_user.id, db)
    from app.models.checklist import SupplierChecklistItem
    item = SupplierChecklistItem(supplier_id=supplier_id, label=payload.label)
    db.add(item)
    db.commit()
    return {"id": str(item.id)}

@router.patch("/{supplier_id}/checklist/{item_id}")
def update_checklist_item(supplier_id: UUID, item_id: UUID, payload: ChecklistItemUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _get_or_404(supplier_id, current_user.id, db)
    from app.models.checklist import SupplierChecklistItem
    item = db.query(SupplierChecklistItem).filter(SupplierChecklistItem.id == item_id, SupplierChecklistItem.supplier_id == supplier_id).first()
    if not item:
        raise HTTPException(404, "Item not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(item, k, v)
    db.commit()
    return {"id": str(item.id), "completed": item.completed}

@router.delete("/{supplier_id}/checklist/{item_id}", status_code=204)
def delete_checklist_item(supplier_id: UUID, item_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _get_or_404(supplier_id, current_user.id, db)
    from app.models.checklist import SupplierChecklistItem
    item = db.query(SupplierChecklistItem).filter(SupplierChecklistItem.id == item_id, SupplierChecklistItem.supplier_id == supplier_id).first()
    if item:
        db.delete(item)
        db.commit()

# ── Reorders ──────────────────────────────────────────────────────────────────

@router.get("/{supplier_id}/reorders")
def list_reorders(supplier_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _get_or_404(supplier_id, current_user.id, db)
    from app.models.reorder import ReorderLog
    rows = db.query(ReorderLog).filter(ReorderLog.supplier_id == supplier_id).order_by(ReorderLog.created_at.desc()).all()
    return [{"id": str(r.id), "po_number": r.po_number, "order_date": r.order_date.isoformat() if r.order_date else None,
             "expected_delivery": r.expected_delivery.isoformat() if r.expected_delivery else None,
             "status": r.status, "line_items": r.line_items, "notes": r.notes,
             "created_at": r.created_at.isoformat()} for r in rows]

@router.post("/{supplier_id}/reorders", status_code=201)
def create_reorder(supplier_id: UUID, payload: ReorderIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _get_or_404(supplier_id, current_user.id, db)
    from app.models.reorder import ReorderLog
    r = ReorderLog(supplier_id=supplier_id, user_id=current_user.id, **payload.model_dump())
    db.add(r)
    db.commit()
    _audit(db, current_user.id, "REORDER_CREATED", "ReorderLog", str(r.id), f"PO {r.po_number}")
    return {"id": str(r.id)}

@router.patch("/{supplier_id}/reorders/{reorder_id}")
def update_reorder(supplier_id: UUID, reorder_id: UUID, payload: ReorderUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _get_or_404(supplier_id, current_user.id, db)
    from app.models.reorder import ReorderLog
    r = db.query(ReorderLog).filter(ReorderLog.id == reorder_id, ReorderLog.supplier_id == supplier_id).first()
    if not r:
        raise HTTPException(404, "Reorder not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(r, k, v)
    db.commit()
    return {"id": str(r.id), "status": r.status}


def _get_or_404(supplier_id: UUID, user_id, db: Session) -> Supplier:
    s = db.query(Supplier).filter(
        Supplier.id == supplier_id, Supplier.user_id == user_id
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return s


def _audit(db, user_id, action_type: str, entity_type: str, entity_id: str, description: str):
    try:
        from app.models.audit_log import AuditLog
        from datetime import datetime as _dt
        log = AuditLog(user_id=user_id, action_type=action_type, entity_type=entity_type,
                       entity_id=entity_id, description=description, timestamp=_dt.utcnow())
        db.add(log)
        db.commit()
    except Exception:
        pass
