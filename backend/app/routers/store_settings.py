"""Store settings and email configuration."""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.store_settings import StoreSettings
from app.models.user import User

router = APIRouter(prefix="/api/v1/store-settings", tags=["store-settings"])


class StoreSettingsUpdate(BaseModel):
    store_name: Optional[str] = None
    owner_name: Optional[str] = None
    currency: Optional[str] = None
    timezone: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from_name: Optional[str] = None
    smtp_from_email: Optional[str] = None
    map_hard_block: Optional[bool] = None
    low_stock_threshold: Optional[int] = None


def _get_or_create(user_id, db: Session) -> StoreSettings:
    s = db.query(StoreSettings).filter(StoreSettings.user_id == user_id).first()
    if not s:
        s = StoreSettings(user_id=user_id)
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


@router.get("/")
def get_settings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    s = _get_or_create(current_user.id, db)
    return {
        "store_name": s.store_name, "owner_name": s.owner_name,
        "currency": s.currency, "timezone": s.timezone,
        "smtp_host": s.smtp_host, "smtp_port": s.smtp_port,
        "smtp_user": s.smtp_user,
        "smtp_from_name": s.smtp_from_name, "smtp_from_email": s.smtp_from_email,
        "map_hard_block": s.map_hard_block, "low_stock_threshold": s.low_stock_threshold,
        "smtp_configured": bool(s.smtp_host and s.smtp_from_email),
    }


@router.patch("/")
def update_settings(payload: StoreSettingsUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    s = _get_or_create(current_user.id, db)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    db.commit()
    return {"saved": True}


@router.post("/test-email")
def test_email(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    s = _get_or_create(current_user.id, db)
    if not s.smtp_host or not s.smtp_from_email:
        from fastapi import HTTPException
        raise HTTPException(400, "SMTP not configured")
    try:
        import smtplib
        from email.mime.text import MIMEText
        msg = MIMEText("This is a test email from ProductHub.", "plain")
        msg["Subject"] = "ProductHub — Test Email"
        msg["From"] = f"{s.smtp_from_name or 'ProductHub'} <{s.smtp_from_email}>"
        msg["To"] = s.smtp_from_email
        with smtplib.SMTP(s.smtp_host, s.smtp_port or 587) as server:
            server.starttls()
            if s.smtp_user and s.smtp_password:
                server.login(s.smtp_user, s.smtp_password)
            server.sendmail(s.smtp_from_email, s.smtp_from_email, msg.as_string())
        return {"sent": True}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(500, f"Failed: {str(e)}")
