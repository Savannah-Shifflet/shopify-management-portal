"""Audit log — read-only."""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.audit_log import AuditLog
from app.models.user import User

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("/")
def list_audit_log(
    action_type: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(AuditLog).filter(AuditLog.user_id == current_user.id)
    if action_type:
        q = q.filter(AuditLog.action_type == action_type)
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    total = q.count()
    rows = q.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "items": [
            {"id": str(r.id), "timestamp": r.timestamp.isoformat(), "action_type": r.action_type,
             "entity_type": r.entity_type, "entity_id": r.entity_id, "description": r.description}
            for r in rows
        ],
    }
