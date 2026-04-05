import json
import base64
from typing import Optional
from pathlib import Path

from app.utils.claude_client import ClaudeClient

PRODUCT_FIELDS = ["title", "sku", "description", "price", "cost", "vendor",
                  "product_type", "barcode", "weight", "tags", "option1", "option2", "option3"]


def _strip_code_fence(text: str) -> str:
    """Remove markdown code fences Claude sometimes wraps HTML output in."""
    text = text.strip()
    if text.startswith("```"):
        # Drop the opening fence line (e.g. ```html or just ```)
        text = text[3:]
        if text.startswith("html"):
            text = text[4:]
        # Drop the closing fence
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


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

    result = {}

    # When a template is provided, generate body_html with a dedicated HTML-only call.
    # Embedding complex structured HTML inside a JSON value is fragile and the AI tends
    # to ignore the template structure. A dedicated call (matching the ai_fill approach)
    # is far more reliable.
    if template_sections and "body_html" in active_fields:
        result["body_html"] = await _generate_html_with_template(
            context=context,
            template_sections=template_sections,
            client=client,
            image_paths=image_paths,
        )
        active_fields = active_fields - {"body_html"}

    # Generate remaining fields as JSON (title, tags, seo_*, attributes).
    # active_fields has body_html removed if it was already handled by the template call above.
    # Always fetch attributes for context; skip the JSON call only if nothing is needed.
    output_schema = {}
    if "title" in active_fields:
        output_schema["title"] = "Improved, SEO-friendly product title (max 255 chars)"
    if "body_html" in active_fields:
        output_schema["body_html"] = "Rich HTML product description (2-4 paragraphs, use <p>, <ul>, <strong>)"
    if "tags" in active_fields:
        output_schema["tags"] = ["array", "of", "relevant", "tags"]
    if "seo_title" in active_fields:
        output_schema["seo_title"] = "SEO meta title (max 70 chars)"
    if "seo_description" in active_fields:
        output_schema["seo_description"] = "SEO meta description (max 160 chars)"
    # Always include attributes — useful context, small output cost
    output_schema["attributes"] = {"material": "...", "color": "...", "dimensions": "..."}

    if active_fields:  # skip JSON call when template handled the only requested field
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

        content = [{"type": "text", "text": user_prompt}]
        if image_paths and "body_html" in active_fields:
            for path in image_paths[:3]:
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
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result.update(json.loads(raw))

    return result


async def _generate_html_with_template(
    context: str,
    template_sections: list,
    client,
    image_paths: list[str] = None,
) -> str:
    """Generate body_html using a template with a dedicated HTML-only Claude call."""
    TAG_GUIDANCE = {
        "h2":    "H2 heading (becomes a tab in the store)",
        "h3":    "H3 heading (becomes a sub-section accordion)",
        "p":     "prose paragraph(s) — use <p> tags",
        "ul":    "unordered bullet list — use <ul><li>",
        "ol":    "numbered list — use <ol><li>",
        "table": "two-column specs table — use <table><tbody><tr><td>",
    }

    section_lines_parts = []
    for s in template_sections:
        tag = s.get("tag") or ("h3" if s.get("level") == "h3" else "h2")
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

    system = (
        "You are a professional product description writer for an e-commerce store. "
        "You write accurate, engaging product copy using ONLY the information provided. "
        "Never invent specifications, dimensions, features, or claims not present in the product data."
    )

    user_content = (
        f"Write a product description for this product using the exact template structure below.\n\n"
        f"PRODUCT DATA:\n{context}\n\n"
        f"TEMPLATE STRUCTURE (follow exactly, in order):\n{section_lines}\n\n"
        f"RULES:\n"
        f"- Use ONLY these HTML tags: h2, h3, p, ul, ol, li, strong, em, br, table, tbody, tr, th, td\n"
        f"- For h2/h3 rows: emit the heading with that exact title — e.g. <h2>Features</h2>\n"
        f"- For p rows: emit one or more <p> paragraphs with relevant prose\n"
        f"- For ul rows: emit <ul><li>…</li></ul> with relevant bullet points\n"
        f"- For ol rows: emit <ol><li>…</li></ol> with numbered steps\n"
        f"- For table rows: emit a two-column <table> with property name and value pairs\n"
        f"- Indented rows belong inside the section directly above them\n"
        f"- REQUIRED rows: always include, write factual copy from available data\n"
        f"- OPTIONAL rows: include only if product data has sufficient detail; omit entirely if not\n"
        f"- Do NOT output hints or [REQUIRED]/[OPTIONAL] labels in the HTML\n"
        f"- Output ONLY the raw HTML — no explanations, no JSON\n"
        f"- Do NOT wrap the output in markdown code fences (no ```html, no ```) — just the HTML tags directly"
    )

    content: list = [{"type": "text", "text": user_content}]
    if image_paths:
        for path in image_paths[:3]:
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
        system=system,
        content=content,
        max_tokens=4000,
    )
    return _strip_code_fence(response.content[0].text.strip())


async def enrich_product_with_ai_async(
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
    client=None,  # AsyncClaudeClient — shared across concurrent calls
) -> dict:
    """
    Async version of enrich_product_with_ai for concurrent batch processing.
    Awaits Claude API calls so asyncio.gather() gives true parallelism.
    Pass a shared AsyncClaudeClient instance to reuse the connection pool.
    """
    from app.utils.claude_client import AsyncClaudeClient
    if client is None:
        client = AsyncClaudeClient()

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

    result = {}

    if template_sections and "body_html" in active_fields:
        result["body_html"] = await _generate_html_with_template_async(
            context=context,
            template_sections=template_sections,
            client=client,
            image_paths=image_paths,
        )
        active_fields = active_fields - {"body_html"}

    output_schema = {}
    if "title" in active_fields:
        output_schema["title"] = "Improved, SEO-friendly product title (max 255 chars)"
    if "body_html" in active_fields:
        output_schema["body_html"] = "Rich HTML product description (2-4 paragraphs, use <p>, <ul>, <strong>)"
    if "tags" in active_fields:
        output_schema["tags"] = ["array", "of", "relevant", "tags"]
    if "seo_title" in active_fields:
        output_schema["seo_title"] = "SEO meta title (max 70 chars)"
    if "seo_description" in active_fields:
        output_schema["seo_description"] = "SEO meta description (max 160 chars)"
    output_schema["attributes"] = {"material": "...", "color": "...", "dimensions": "..."}

    if active_fields:
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
        content = [{"type": "text", "text": user_prompt}]
        if image_paths and "body_html" in active_fields:
            for path in image_paths[:3]:
                try:
                    data = Path(path).read_bytes()
                    b64 = base64.standard_b64encode(data).decode()
                    content.append({
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
                    })
                except Exception:
                    pass

        response = await client.message(system=system_prompt, content=content, max_tokens=2000)
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result.update(json.loads(raw))

    return result


async def _generate_html_with_template_async(
    context: str,
    template_sections: list,
    client,
    image_paths: list[str] = None,
) -> str:
    """Async version of _generate_html_with_template."""
    TAG_GUIDANCE = {
        "h2":    "H2 heading (becomes a tab in the store)",
        "h3":    "H3 heading (becomes a sub-section accordion)",
        "p":     "prose paragraph(s) — use <p> tags",
        "ul":    "unordered bullet list — use <ul><li>",
        "ol":    "numbered list — use <ol><li>",
        "table": "two-column specs table — use <table><tbody><tr><td>",
    }
    section_lines_parts = []
    for s in template_sections:
        tag = s.get("tag") or ("h3" if s.get("level") == "h3" else "h2")
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

    system = (
        "You are a professional product description writer for an e-commerce store. "
        "You write accurate, engaging product copy using ONLY the information provided. "
        "Never invent specifications, dimensions, features, or claims not present in the product data."
    )
    user_content = (
        f"Write a product description for this product using the exact template structure below.\n\n"
        f"PRODUCT DATA:\n{context}\n\n"
        f"TEMPLATE STRUCTURE (follow exactly, in order):\n{section_lines}\n\n"
        f"RULES:\n"
        f"- Use ONLY these HTML tags: h2, h3, p, ul, ol, li, strong, em, br, table, tbody, tr, th, td\n"
        f"- For h2/h3 rows: emit the heading with that exact title — e.g. <h2>Features</h2>\n"
        f"- For p rows: emit one or more <p> paragraphs with relevant prose\n"
        f"- For ul rows: emit <ul><li>…</li></ul> with relevant bullet points\n"
        f"- For ol rows: emit <ol><li>…</li></ol> with numbered steps\n"
        f"- For table rows: emit a two-column <table> with property name and value pairs\n"
        f"- Indented rows belong inside the section directly above them\n"
        f"- REQUIRED rows: always include, write factual copy from available data\n"
        f"- OPTIONAL rows: include only if product data has sufficient detail; omit entirely if not\n"
        f"- Do NOT output hints or [REQUIRED]/[OPTIONAL] labels in the HTML\n"
        f"- Output ONLY the HTML — no explanations, no JSON, no markdown fences"
    )
    content: list = [{"type": "text", "text": user_content}]
    if image_paths:
        for path in image_paths[:3]:
            try:
                data = Path(path).read_bytes()
                b64 = base64.standard_b64encode(data).decode()
                content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
                })
            except Exception:
                pass

    response = await client.message(system=system, content=content, max_tokens=4000)
    return _strip_code_fence(response.content[0].text.strip())


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
