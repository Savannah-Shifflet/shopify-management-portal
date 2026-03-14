"""Description template CRUD and AI-fill endpoint."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.description_template import DescriptionTemplate
from app.models.user import User

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class SectionIn(BaseModel):
    level: str   # "h2" | "h3"
    title: str
    hint: Optional[str] = ""


class TemplateCreate(BaseModel):
    name: str
    sections: list[SectionIn] = []


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    sections: Optional[list[SectionIn]] = None


class TemplateOut(BaseModel):
    id: UUID
    name: str
    sections: list[dict]

    model_config = {"from_attributes": True}


# ── CRUD ───────────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[TemplateOut])
def list_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(DescriptionTemplate).filter(
        DescriptionTemplate.user_id == current_user.id
    ).order_by(DescriptionTemplate.created_at).all()


@router.post("/", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
def create_template(
    payload: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    t = DescriptionTemplate(
        user_id=current_user.id,
        name=payload.name,
        sections=[s.model_dump() for s in payload.sections],
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@router.patch("/{template_id}", response_model=TemplateOut)
def update_template(
    template_id: UUID,
    payload: TemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    t = _get_or_404(template_id, current_user.id, db)
    if payload.name is not None:
        t.name = payload.name
    if payload.sections is not None:
        t.sections = [s.model_dump() for s in payload.sections]
    db.commit()
    db.refresh(t)
    return t


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    t = _get_or_404(template_id, current_user.id, db)
    db.delete(t)
    db.commit()


# ── AI fill ────────────────────────────────────────────────────────────────────

class AiFillRequest(BaseModel):
    template_id: UUID
    product_id: UUID


@router.post("/ai-fill")
def ai_fill(
    payload: AiFillRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Use Claude to reorganize a product's existing description content into
    the structure defined by the chosen template and return the HTML.
    The result is NOT auto-saved — the client applies it to the editor.
    """
    from app.models.product import Product
    from app.utils.claude_client import ClaudeClient

    template = _get_or_404(payload.template_id, current_user.id, db)
    product = db.query(Product).filter(
        Product.id == payload.product_id,
        Product.user_id == current_user.id,
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    sections = template.sections or []
    if not sections:
        raise HTTPException(status_code=400, detail="Template has no sections defined")

    # Build source content from whatever we have
    existing_description = product.body_html or ""
    ai_description = product.ai_description or ""
    ai_attributes = product.ai_attributes or {}

    # Format template structure for the prompt
    section_lines = "\n".join(
        f"  <{s['level']}>{s['title']}</{s['level']}>"
        + (f"  <!-- {s['hint']} -->" if s.get("hint") else "")
        for s in sections
    )

    # Format AI attributes as context
    attrs_text = ""
    if ai_attributes:
        attrs_text = "\n\nProduct attributes:\n" + "\n".join(
            f"  {k}: {v}" for k, v in ai_attributes.items()
        )

    system = (
        "You are a product description formatter for a Shopify store. "
        "In this store, <h2> headings become navigation tabs and <h3> headings become "
        "accordion dropdowns within a tab. "
        "You write clean, professional product copy for an authorized dealer."
    )

    user_content = f"""Reformat the product description below into the following template structure.

Product: {product.title}
{attrs_text}

TEMPLATE STRUCTURE (preserve these exact headings and nesting):
{section_lines}

EXISTING CONTENT TO REORGANIZE:
{existing_description or "(no existing description)"}

AI-GENERATED DESCRIPTION (additional context):
{ai_description or "(none)"}

RULES:
- Use ONLY these HTML tags: h2, h3, p, ul, ol, li, strong, em, br, table, thead, tbody, tr, th, td
- Keep the exact heading titles from the template
- Distribute existing content into the most relevant sections
- For sections with no matching existing content, write concise appropriate copy based on the product title and type
- Section hints (in comments) guide what content belongs there — do not output the hints/comments
- Output ONLY the HTML, no explanations, no markdown code fences"""

    client = ClaudeClient()
    response = client.message(
        system=system,
        content=[{"type": "text", "text": user_content}],
        max_tokens=3000,
    )
    html = response.content[0].text.strip()

    return {"html": html, "template_name": template.name}


def _get_or_404(template_id: UUID, user_id, db: Session) -> DescriptionTemplate:
    t = db.query(DescriptionTemplate).filter(
        DescriptionTemplate.id == template_id,
        DescriptionTemplate.user_id == user_id,
    ).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    return t
