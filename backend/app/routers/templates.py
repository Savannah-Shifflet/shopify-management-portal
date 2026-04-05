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
    tag: str = "h2"        # "h2" | "h3" | "p" | "ul" | "ol" | "table"
    title: str             # heading text for h2/h3; descriptive label for content elements
    hint: Optional[str] = ""
    required: bool = True  # True = always generate; False = only if product data is sufficient
    indent: int = 0        # 0 = top-level, 1 = nested, 2 = deeply nested


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

    TAG_GUIDANCE = {
        "h2":    "H2 heading (becomes a tab in the store)",
        "h3":    "H3 heading (becomes a sub-section accordion)",
        "p":     "prose paragraph(s) — use <p> tags",
        "ul":    "unordered bullet list — use <ul><li>",
        "ol":    "numbered list — use <ol><li>",
        "table": "two-column specs table — use <table><thead><tbody><tr><th><td>",
    }

    # Build an indented outline for the prompt showing the nested structure
    section_lines_parts = []
    for s in sections:
        tag = s.get("tag") or ("h3" if s.get("level") == "h3" else "h2")  # back-compat
        indent = s.get("indent", 0)
        required = s.get("required", True)
        req_label = "REQUIRED" if required else "OPTIONAL"
        guidance = TAG_GUIDANCE.get(tag, tag)
        hint_part = f" — {s['hint']}" if s.get("hint") else ""
        prefix = "  " * indent
        section_lines_parts.append(
            f"{prefix}[{req_label}] <{tag}> {s['title']} ({guidance}){hint_part}"
        )
    section_lines = "\n".join(section_lines_parts)

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

TEMPLATE STRUCTURE:
{section_lines}

EXISTING CONTENT TO REORGANIZE:
{existing_description or "(no existing description)"}

AI-GENERATED DESCRIPTION (additional context):
{ai_description or "(none)"}

RULES:
- Use ONLY these HTML tags: h2, h3, p, ul, ol, li, strong, em, br, table, thead, tbody, tr, th, td
- Each row in the outline maps to an HTML element of that exact tag type
- For h2/h3 rows: emit the heading with the exact title shown — e.g. <h2>Features</h2>
- For p rows: emit one or more <p> paragraphs with relevant prose
- For ul rows: emit <ul><li>…</li></ul> with relevant bullet points
- For ol rows: emit <ol><li>…</li></ol> with numbered steps or points
- For table rows: emit a two-column <table> with spec name and value pairs
- Indentation in the outline shows nesting — emit nested elements directly inside their parent heading's section (no extra wrapper div)
- REQUIRED rows: always include, even if you must write reasonable copy from the product title and type alone
- OPTIONAL rows: only include if the product data above contains sufficient concrete information; omit the element entirely if not
- Do not output section hints or the [REQUIRED]/[OPTIONAL] labels
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
