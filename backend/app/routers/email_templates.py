"""Email outreach template CRUD."""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.email_template import EmailTemplate
from app.models.user import User

router = APIRouter(prefix="/api/v1/email-templates", tags=["email-templates"])

STARTER_TEMPLATES = [
    {
        "name": "Initial Outreach",
        "subject": "Reseller Inquiry — {{my_store_name}}",
        "body": """<p>Hello {{supplier_name}},</p>
<p>My name is {{my_name}}, and I am the owner of {{my_store_name}}, an authorized online retailer specializing in high-quality products.</p>
<p>I came across your brand and am very interested in becoming an authorized reseller. I believe your products would resonate well with my customer base.</p>
<p>Could you please share information about your reseller program, pricing tiers, and minimum order requirements?</p>
<p>I look forward to hearing from you.</p>
<p>Best regards,<br>{{my_name}}<br>{{my_store_name}}</p>""",
    },
    {
        "name": "Follow-Up",
        "subject": "Following Up — Reseller Inquiry from {{my_store_name}}",
        "body": """<p>Hello {{supplier_name}},</p>
<p>I wanted to follow up on my previous email regarding a potential reseller partnership with {{my_store_name}}.</p>
<p>I remain very interested in carrying your products and would love to discuss the next steps.</p>
<p>Please let me know if you need any additional information from my end.</p>
<p>Best regards,<br>{{my_name}}<br>{{my_store_name}}</p>""",
    },
    {
        "name": "Reorder Request",
        "subject": "Purchase Order Request — {{my_store_name}}",
        "body": """<p>Hello {{supplier_name}},</p>
<p>I would like to place a reorder for the following items:</p>
<ul>
  <li>[Product Name] — Qty: [Quantity]</li>
</ul>
<p>Please confirm availability, pricing, and estimated lead time. I will send a formal PO upon your confirmation.</p>
<p>Thank you,<br>{{my_name}}<br>{{my_store_name}}</p>""",
    },
]


class TemplateCreate(BaseModel):
    name: str
    subject: Optional[str] = None
    body: Optional[str] = None


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None


@router.get("/")
def list_templates(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    templates = db.query(EmailTemplate).filter(EmailTemplate.user_id == current_user.id).order_by(EmailTemplate.created_at).all()
    # Seed starter templates on first call
    if not templates:
        for t in STARTER_TEMPLATES:
            tmpl = EmailTemplate(user_id=current_user.id, **t)
            db.add(tmpl)
        db.commit()
        templates = db.query(EmailTemplate).filter(EmailTemplate.user_id == current_user.id).all()
    return [{"id": str(t.id), "name": t.name, "subject": t.subject, "body": t.body} for t in templates]


@router.post("/", status_code=201)
def create_template(payload: TemplateCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    t = EmailTemplate(user_id=current_user.id, **payload.model_dump())
    db.add(t)
    db.commit()
    return {"id": str(t.id)}


@router.patch("/{template_id}")
def update_template(template_id: uuid.UUID, payload: TemplateUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    t = db.query(EmailTemplate).filter(EmailTemplate.id == template_id, EmailTemplate.user_id == current_user.id).first()
    if not t:
        raise HTTPException(404, "Not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    db.commit()
    return {"id": str(t.id)}


@router.delete("/{template_id}", status_code=204)
def delete_template(template_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    t = db.query(EmailTemplate).filter(EmailTemplate.id == template_id, EmailTemplate.user_id == current_user.id).first()
    if t:
        db.delete(t)
        db.commit()
