import json
import base64
from typing import Optional
from pathlib import Path

from app.utils.claude_client import ClaudeClient

PRODUCT_FIELDS = ["title", "sku", "description", "price", "cost", "vendor",
                  "product_type", "barcode", "weight", "tags", "option1", "option2", "option3"]


async def enrich_product_with_ai(
    raw_title: Optional[str],
    raw_description: Optional[str],
    source_url: Optional[str],
    product_type: Optional[str],
    vendor: Optional[str],
    supplier_name: Optional[str],
    cost_price: Optional[float],
    existing_tags: Optional[list],
    image_paths: list[str] = None,
    fields: list | None = None,
    template_sections: list | None = None,
) -> dict:
    """Call Claude to enrich product data. Returns dict of enriched fields."""
    client = ClaudeClient()

    all_fields = ["body_html", "tags", "title", "seo_title", "seo_description"]
    active_fields = set(fields) if fields else set(all_fields)

    context_parts = []
    if raw_title:
        context_parts.append(f"Product title: {raw_title}")
    if raw_description:
        context_parts.append(f"Raw description: {raw_description[:2000]}")
    if vendor:
        context_parts.append(f"Brand/Vendor: {vendor}")
    if supplier_name:
        context_parts.append(f"Supplier: {supplier_name}")
    if product_type:
        context_parts.append(f"Product type: {product_type}")
    if cost_price:
        context_parts.append(f"Cost price: ${cost_price}")
    if source_url:
        context_parts.append(f"Source URL: {source_url}")
    if existing_tags:
        context_parts.append(f"Existing tags: {', '.join(existing_tags)}")

    context = "\n".join(context_parts)

    output_schema = {}
    if "title" in active_fields:
        output_schema["title"] = "Improved, SEO-friendly product title (max 255 chars)"
    if "body_html" in active_fields:
        if template_sections:
            output_schema["body_html"] = "Rich HTML product description using the template structure below"
        else:
            output_schema["body_html"] = "Rich HTML product description (2-4 paragraphs, use <p>, <ul>, <strong>)"
    if "tags" in active_fields:
        output_schema["tags"] = ["array", "of", "relevant", "tags"]
    # Always include attributes — small, useful for context
    output_schema["attributes"] = {"material": "...", "color": "...", "dimensions": "..."}
    if "seo_title" in active_fields:
        output_schema["seo_title"] = "SEO meta title (max 70 chars)"
    if "seo_description" in active_fields:
        output_schema["seo_description"] = "SEO meta description (max 160 chars)"

    system_prompt = (
        "You are a professional e-commerce product description writer for an authorized dealer. "
        "Your ONLY job is to organize and present the product information you are given — "
        "you must NEVER invent, assume, or add any product specifications, features, dimensions, "
        "materials, compatibility claims, or benefits that are not explicitly stated in the product data provided. "
        "Accuracy is more important than completeness. If information is missing for a section, write a brief "
        "factual statement based only on what is known, or use a minimal placeholder like "
        "'Contact us for more details.' "
        "Respond ONLY with valid JSON matching the schema provided. No markdown, no explanation."
    )

    user_prompt = (
        f"STRICT ACCURACY RULE: Only include information explicitly present in the product data below.\n"
        f"Do not add specifications, dimensions, materials, features, compatibility claims, or benefits\n"
        f"that are not directly mentioned in the product data. Do not invent content.\n\n"
        f"Enrich this product for an e-commerce store:\n\n"
        f"{context}\n\n"
        f"Return JSON with this exact structure:\n{json.dumps(output_schema, indent=2)}\n\n"
        f"Guidelines:\n"
        f"- Title: capitalize properly, include brand + key feature + product type\n"
        f"- Description: highlight key features, benefits, specs; write for the buyer\n"
        f"- Tags: 5-15 relevant tags for search and filtering\n"
        f"- Attributes: only include attributes you are confident about\n"
        f"- SEO: natural language, include primary keyword"
    )

    if template_sections and "body_html" in active_fields:
        section_lines = "\n".join(
            f"  <{s['level']}>{s['title']}</{s['level']}>" + (f"  <!-- hint: {s['hint']} -->" if s.get("hint") else "")
            for s in template_sections
        )
        user_prompt += (
            f"\n\nFor body_html, you MUST use this EXACT template structure. "
            f"Do not add, remove, rename, or reorder any headings. "
            f"Only use these HTML tags within section content: p, ul, ol, li, strong, em, table, thead, tbody, tr, th, td. "
            f"The output must start with the first heading and contain ONLY the headings listed below:\n"
            f"{section_lines}\n"
            f"Section hints (in HTML comments) guide what content belongs there — do not output the hints."
        )

    # Build content blocks (text + optional images)
    content = [{"type": "text", "text": user_prompt}]
    if image_paths:
        for path in image_paths[:3]:  # max 3 images
            try:
                data = Path(path).read_bytes()
                b64 = base64.standard_b64encode(data).decode()
                content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
                })
            except Exception:
                pass

    response = client.message(
        system=system_prompt,
        content=content,
        max_tokens=2000,
    )

    raw = response.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


async def suggest_csv_column_mapping(headers: list[str], sample_rows: list[list]) -> dict:
    """Use Claude to suggest CSV column → product field mapping."""
    client = ClaudeClient()

    sample_text = "\n".join([",".join(map(str, row)) for row in sample_rows[:3]])
    available_fields = ", ".join(PRODUCT_FIELDS)

    prompt = (
        f"I have a CSV file with these headers:\n{headers}\n\n"
        f"Here are the first 3 rows of data:\n{sample_text}\n\n"
        f"Map each header to one of these product fields: {available_fields}\n"
        f"If a header doesn't match any field, set it to null.\n\n"
        f"Return ONLY valid JSON like: {{\"Header Name\": \"field_name\", ...}}"
    )

    response = client.message(
        system="You are a data mapping assistant. Respond only with valid JSON.",
        content=[{"type": "text", "text": prompt}],
        max_tokens=500,
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    mapping = json.loads(raw)
    return {"mapping": mapping, "confidence": 0.9}


async def extract_products_from_pdf_page(page_text: str, page_image_b64: Optional[str] = None) -> list[dict]:
    """Extract structured product data from a PDF page."""
    client = ClaudeClient()

    content = []
    if page_image_b64:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": page_image_b64},
        })
    content.append({
        "type": "text",
        "text": (
            f"Extract all products from this catalog page.\n"
            f"Page text content:\n{page_text[:3000]}\n\n"
            f"Return a JSON array of products with fields: "
            f"title, sku, description, price, cost, vendor, product_type, attributes. "
            f"If no products found, return empty array []."
        ),
    })

    response = client.message(
        system="Extract product data from catalog pages. Return only valid JSON arrays.",
        content=content,
        max_tokens=3000,
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    return json.loads(raw)
