"""Global reorder log across all suppliers."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/v1/reorders", tags=["reorders"])


@router.get("/")
def list_all_reorders(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.models.reorder import ReorderLog
    from app.models.supplier import Supplier
    rows = (
        db.query(ReorderLog, Supplier.name)
        .join(Supplier, ReorderLog.supplier_id == Supplier.id)
        .filter(ReorderLog.user_id == current_user.id)
        .order_by(ReorderLog.created_at.desc())
        .all()
    )
    return [
        {
            "id": str(r.id), "supplier_id": str(r.supplier_id), "supplier_name": name,
            "po_number": r.po_number,
            "order_date": r.order_date.isoformat() if r.order_date else None,
            "expected_delivery": r.expected_delivery.isoformat() if r.expected_delivery else None,
            "status": r.status, "line_items": r.line_items, "notes": r.notes,
            "created_at": r.created_at.isoformat(),
        }
        for r, name in rows
    ]
