import logging
import re
from datetime import datetime
from decimal import Decimal
from typing import Optional
from urllib.parse import urljoin, urlparse
from uuid import UUID

import httpx

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Short nav/UI strings that are never product titles
_NON_PRODUCT_RE = re.compile(
    r"^(home|shop|all|sale|new|featured|about|contact|cart|login|register|search|"
    r"menu|navigation|breadcrumb|back|next|previous|more|view|see|load|continue|"
    r"add to cart|buy now|sold out|out of stock|unavailable|\d+|"
    r"public service & government|education & research|construction site|"
    r"open box sale|clearance|today's offer|secure payments|warranty protection|"
    r"installment plans|fast & free shipping|reliable support|eco-friendly power|"
    # Seel / third-party protection / warranty upsell products injected into Shopify catalogs
    r"worry[- ]free purchase|seel|seel protection|purchase protection|"
    r"shipping protection|route protection|extend protection|assurance|"
    r"[0-9]+[- ]year (warranty|protection|plan)|warranty plan|protection plan)$",
    re.IGNORECASE,
)


def _is_product_title(title: str) -> bool:
    t = title.strip()
    if not t or len(t) < 4 or len(t) > 400:
        return False
    return not _NON_PRODUCT_RE.match(t)


def _resolve_url(href: Optional[str], base_url: str) -> Optional[str]:
    if not href:
        return None
    if href.startswith("http"):
        return href
    return urljoin(base_url, href)


def _qa_filter(raw: list, base_url: str) -> list:
    """Resolve URLs, remove non-products, deduplicate by title and URL."""
    seen_titles: set = set()
    seen_urls: set = set()
    result = []
    for item in raw:
        title = (item.get("title") or "").strip()
        if not _is_product_title(title):
            continue
        url = _resolve_url(item.get("url"), base_url)
        title_key = title.lower()
        if title_key in seen_titles:
            continue
        if url and url in seen_urls:
            continue
        seen_titles.add(title_key)
        if url:
            seen_urls.add(url)
        result.append({**item, "title": title, "url": url})
    return result


def _try_shopify_json(url: str) -> Optional[list]:
    """
    Try to fetch products from a Shopify JSON endpoint.
    Shopify exposes /products.json and /collections/{handle}.json with full product data.
    Returns a list of raw product dicts or None if not a Shopify store / request failed.
    """
    try:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        path = parsed.path.rstrip("/")

        # Build candidate JSON URLs to try
        candidates = []
        # If URL is /products or /collections/X, use the correct Shopify JSON endpoints
        if path.endswith("/products"):
            candidates.append(f"{base}/products.json")
        elif "/collections/" in path:
            # Shopify collection products: /collections/{handle}/products.json (NOT /collections/{handle}.json)
            coll_path = path.split("?")[0].rstrip("/")
            candidates.append(f"{base}{coll_path}/products.json")
        # Always try the generic /products.json as a fallback
        candidates.append(f"{base}/products.json")

        headers = {"User-Agent": "Mozilla/5.0 (compatible; ProductBot/1.0)", "Accept": "application/json"}

        for json_url in candidates:
            try:
                # Paginate through all pages (Shopify max 250 per page)
                all_products = []
                page_num = 1
                base_url_no_qs = json_url.split("?")[0]
                while True:
                    paged_url = f"{base_url_no_qs}?limit=250&page={page_num}"
                    resp = httpx.get(paged_url, headers=headers, timeout=10, follow_redirects=True)
                    if resp.status_code != 200:
                        break
                    data = resp.json()
                    products = data.get("products") or data.get("collection", {}).get("products", [])
                    if not products or not isinstance(products, list):
                        break
                    all_products.extend(products)
                    if len(products) < 250:
                        break  # Last page
                    page_num += 1
                    if page_num > 40:
                        break  # Safety cap at 10,000 products
                if all_products:
                    results = []
                    for p in all_products:
                        handle = p.get("handle", "")
                        product_url = f"{base}/products/{handle}" if handle else None
                        price = None
                        variants = p.get("variants", [])
                        if variants:
                            raw_price = variants[0].get("price")
                            price = f"${raw_price}" if raw_price else None
                        results.append({
                            "title": p.get("title"),
                            "price": price,
                            "sku": variants[0].get("sku") if variants else None,
                            "url": product_url,
                            # Rich data from Shopify JSON — used at approval to skip Playwright detail scrape
                            "body_html": p.get("body_html") or "",
                            "images": [img["src"] for img in p.get("images", []) if img.get("src")][:10],
                            "vendor": p.get("vendor") or "",
                            "product_type": p.get("product_type") or "",
                            "tags": p.get("tags") or "",
                        })
                    logger.info(f"Shopify JSON API returned {len(results)} products from {base_url_no_qs} ({page_num} pages)")
                    return results
            except Exception:
                continue
    except Exception as e:
        logger.debug(f"Shopify JSON probe failed: {e}")
    return None


@celery_app.task(name="app.workers.scrape_tasks.scrape_supplier_catalog", bind=True, max_retries=0)
def scrape_supplier_catalog(self, supplier_id: Optional[str], url: Optional[str] = None, job_id: Optional[str] = None, session_id: Optional[str] = None):
    """Full catalog scrape for a supplier using Playwright.

    Products are NOT auto-created. Raw items are stored in ScrapeSession.raw_data
    with status="needs_review". The user approves selected items via the /approve endpoint.
    """
    from playwright.sync_api import sync_playwright
    from app.database import SessionLocal
    from app.models.supplier import Supplier
    from app.models.import_job import ImportJob
    from app.models.scrape_session import ScrapeSession

    db = SessionLocal()
    try:
        supplier = None
        scrape_url = url
        config = {}

        if supplier_id:
            supplier = db.query(Supplier).filter(Supplier.id == UUID(supplier_id)).first()
            if supplier:
                config = supplier.scrape_config or {}
                scrape_url = scrape_url or config.get("catalog_url") or supplier.website_url

        if not scrape_url:
            return {"error": "No URL to scrape"}

        if session_id:
            session = db.query(ScrapeSession).filter(ScrapeSession.id == UUID(session_id)).first()
            session.status = "running"
            session.url = scrape_url
            session.started_at = datetime.utcnow()
        else:
            session = ScrapeSession(
                supplier_id=UUID(supplier_id) if supplier_id else None,
                import_job_id=UUID(job_id) if job_id else None,
                url=scrape_url,
                status="running",
                started_at=datetime.utcnow(),
            )
            db.add(session)
        db.commit()

        raw_products = []
        product_selector = config.get("product_selector", "article, .product, [data-product], .product-item")
        title_selector = config.get("title_selector", "h2, h3, .product-title, .product-name")
        price_selector = config.get("price_selector", ".price, [data-price], .product-price")
        sku_selector = config.get("sku_selector", "[data-sku], .sku")
        next_page_selector = config.get("next_page_selector", "a[rel='next'], .next-page, [aria-label='Next page']")
        max_pages = config.get("max_pages", 10)
        # Whether the user has customised selectors (vs defaults)
        has_custom_selectors = bool(config.get("product_selector"))

        # ── Shopify JSON fast path ──────────────────────────────────────────
        # If the supplier runs on Shopify we can pull structured product data
        # directly from their JSON API — no Playwright needed.
        shopify_products = _try_shopify_json(scrape_url)
        if shopify_products is not None:
            filtered = _qa_filter(shopify_products, scrape_url)
            session.raw_data = filtered
            session.products_found = len(filtered)
            session.pages_scraped = 1
            session.status = "needs_review"
            session.completed_at = datetime.utcnow()
            if supplier:
                supplier.last_scraped_at = datetime.utcnow()
            db.commit()
            return {"pages_scraped": 1, "products_found": len(filtered), "session_id": str(session.id)}

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent="Mozilla/5.0 (compatible; ProductBot/1.0)")

            current_url = scrape_url
            pages_scraped = 0

            while current_url and pages_scraped < max_pages:
                try:
                    page.goto(current_url, wait_until="load", timeout=25000)
                    try:
                        page.wait_for_load_state("networkidle", timeout=8000)
                    except Exception:
                        pass

                    # Scroll to the bottom to trigger lazy-loaded product grids,
                    # then back to top so pagination links are visible.
                    try:
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        page.wait_for_timeout(1500)
                        page.evaluate("window.scrollTo(0, 0)")
                    except Exception:
                        pass

                    # If the user provided a specific product selector, wait for it.
                    if has_custom_selectors:
                        try:
                            page.wait_for_selector(product_selector, timeout=5000)
                        except Exception:
                            pass

                    # Increment and commit BEFORE processing items so the
                    # progress counter updates immediately on first page load.
                    pages_scraped += 1
                    session.pages_scraped = pages_scraped
                    db.commit()

                    items = page.query_selector_all(product_selector)
                    for idx, item in enumerate(items):
                        title_el = item.query_selector(title_selector)
                        price_el = item.query_selector(price_selector)
                        sku_el = item.query_selector(sku_selector)
                        link_el = item.query_selector("a")

                        raw_products.append({
                            "title": title_el.inner_text().strip() if title_el else None,
                            "price": price_el.inner_text().strip() if price_el else None,
                            "sku": sku_el.inner_text().strip() if sku_el else None,
                            "url": link_el.get_attribute("href") if link_el else None,
                        })

                        # Commit running count every 10 items so the UI reflects
                        # progress without hammering the DB on every item.
                        if idx % 10 == 9:
                            session.products_found = len(raw_products)
                            db.commit()

                    session.products_found = len(raw_products)

                    next_el = page.query_selector(next_page_selector)
                    if next_el:
                        next_href = next_el.get_attribute("href")
                        if next_href and next_href != current_url:
                            current_url = _resolve_url(next_href, scrape_url)
                        else:
                            break
                    else:
                        break

                    db.commit()

                except Exception as e:
                    logger.warning(f"Error on page {pages_scraped}: {e}")
                    break

            browser.close()

        # QA filter: resolve URLs, dedupe, remove non-products
        filtered = _qa_filter(raw_products, scrape_url)

        session.raw_data = filtered
        session.products_found = len(filtered)
        session.status = "needs_review"
        session.completed_at = datetime.utcnow()

        if supplier:
            supplier.last_scraped_at = datetime.utcnow()

        if job_id:
            job = db.query(ImportJob).filter(ImportJob.id == UUID(job_id)).first()
            if job:
                job.total_rows = len(filtered)

        db.commit()
        return {"pages_scraped": pages_scraped, "products_found": len(filtered), "session_id": str(session.id)}

    except Exception as exc:
        db.rollback()
        logger.error(f"Scrape task failed: {exc}")
        try:
            session.status = "failed"
            session.error_details = str(exc)
            db.commit()
        except Exception:
            pass
        raise
    finally:
        db.close()


def _apply_scraped_price(product, price_str: Optional[str], db) -> None:
    """Parse a scraped price string and apply it directly to the product.

    Always updates supplier_price — this is called from a manual re-scrape so the
    user explicitly requested a price refresh. Unlike the scheduled price checker
    (_detect_price_change), we never block on a pending alert here.
    """
    if not price_str:
        return
    try:
        cleaned = price_str.replace("$", "").replace(",", "").strip().split()[0]
        new_price = Decimal(cleaned)
    except Exception:
        return

    if product.supplier_price == new_price:
        return  # no change

    product.supplier_price = new_price
    product.supplier_price_at = datetime.utcnow()

    if product.use_supplier_price:
        product.base_price = new_price
        # Apply pricing rules for variant prices if a supplier is linked
        if product.supplier_id:
            try:
                from app.services.pricing_service import calculate_retail_price
                result = calculate_retail_price(
                    new_price, product.supplier_id,
                    product.product_type, product.tags or [], db,
                )
                for variant in product.variants:
                    variant.price = result["price"]
            except Exception:
                for variant in product.variants:
                    variant.price = new_price
        else:
            for variant in product.variants:
                variant.price = new_price

    # Mark out-of-sync so the new price is pushed to Shopify on next sync
    if product.sync_status == "synced":
        product.sync_status = "out_of_sync"


@celery_app.task(name="app.workers.scrape_tasks.scrape_product_details", bind=True, max_retries=2)
def scrape_product_details(self, product_id: str):
    """Scrape description and images from a product's source_url after approval."""
    from playwright.sync_api import sync_playwright
    from app.database import SessionLocal
    from app.models.product import Product
    from app.models.image import ProductImage

    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == UUID(product_id)).first()
        if not product or not product.source_url:
            return {"skipped": True, "reason": "no source_url"}

        description = None
        image_urls = []
        scraped_price: Optional[str] = None

        # ── Shopify product JSON fast path ──────────────────────────────
        # For Shopify stores: /products/{handle}.json returns description + images instantly
        parsed_src = urlparse(product.source_url)
        if "/products/" in parsed_src.path:
            handle = parsed_src.path.split("/products/")[-1].rstrip("/").split("?")[0]
            if handle and "." not in handle:
                json_url = f"{parsed_src.scheme}://{parsed_src.netloc}/products/{handle}.json"
                try:
                    resp = httpx.get(json_url, timeout=10, follow_redirects=True,
                                      headers={"User-Agent": "Mozilla/5.0 (compatible; ProductBot/1.0)"})
                    if resp.status_code == 200:
                        p_data = resp.json().get("product", {})
                        description = p_data.get("body_html") or None
                        image_urls = [img["src"] for img in p_data.get("images", []) if img.get("src")][:10]
                        variants = p_data.get("variants", [])
                        if variants and variants[0].get("price"):
                            scraped_price = str(variants[0]["price"])
                        logger.info(f"Shopify product JSON used for {product.source_url}: desc={bool(description)}, images={len(image_urls)}, price={scraped_price}")
                except Exception as e:
                    logger.debug(f"Shopify product JSON fast path failed: {e}")

        if description or image_urls or scraped_price:
            # Got everything from JSON — skip Playwright
            if description and not product.body_html:
                product.body_html = description
                product.raw_description = description
            existing_srcs = {img.src for img in product.images}
            for i, url in enumerate(image_urls):
                if url not in existing_srcs:
                    db.add(ProductImage(product_id=product.id, src=url, alt=product.title, position=len(existing_srcs) + i + 1))
            _apply_scraped_price(product, scraped_price, db)
            db.commit()
            return {"description_found": bool(description), "images_found": len(image_urls), "price_found": bool(scraped_price), "source": "shopify_json"}

        # Get supplier price selector for Playwright scrape
        price_selector = ".price, [data-price], .product-price"
        if product.supplier_id:
            from app.models.supplier import Supplier
            supplier = db.query(Supplier).filter(Supplier.id == product.supplier_id).first()
            if supplier and supplier.scrape_config and supplier.scrape_config.get("price_selector"):
                price_selector = supplier.scrape_config["price_selector"]

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent="Mozilla/5.0 (compatible; ProductBot/1.0)")
            page.goto(product.source_url, wait_until="domcontentloaded", timeout=20000)
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass

            # Extract description — try common product page selectors
            desc_selectors = [
                "[itemprop='description']",
                ".product-description",
                ".product__description",
                ".product-single__description",
                ".product-details__description",
                "#product-description",
                ".pdp-description",
                ".description",
            ]
            for sel in desc_selectors:
                el = page.query_selector(sel)
                if el:
                    text = el.inner_text().strip()
                    if len(text) > 20:
                        description = el.inner_html().strip()
                        break

            # Extract price
            price_el = page.query_selector(price_selector)
            if price_el:
                scraped_price = price_el.inner_text().strip()

            # Extract images — try common product image selectors, stop at first hit
            img_selectors = [
                "[itemprop='image']",
                ".product__media img",
                ".product__image img",
                ".product-image img",
                ".product-single__image img",
                ".product-images img",
                ".product-gallery img",
                ".gallery img",
            ]
            seen: set = set()
            for sel in img_selectors:
                els = page.query_selector_all(sel)
                for el in els[:10]:
                    src = (el.get_attribute("src") or el.get_attribute("data-src") or "").strip()
                    if src and not src.startswith("data:") and src not in seen:
                        src = _resolve_url(src, product.source_url) or src
                        seen.add(src)
                        image_urls.append(src)
                if image_urls:
                    break

            browser.close()

        # Persist description only if the product has none yet
        if description and not product.body_html:
            product.body_html = description
            product.raw_description = description

        # Persist images that are not already stored
        existing_srcs = {img.src for img in product.images}
        for i, url in enumerate(image_urls[:10]):
            if url not in existing_srcs:
                db.add(ProductImage(
                    product_id=product.id,
                    src=url,
                    alt=product.title,
                    position=len(existing_srcs) + i + 1,
                ))

        _apply_scraped_price(product, scraped_price, db)
        db.commit()
        return {"description_found": bool(description), "images_found": len(image_urls), "price_found": bool(scraped_price)}

    except Exception as exc:
        db.rollback()
        logger.error(f"Detail scrape failed for {product_id}: {exc}")
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()


def create_products_from_session(session_id: str, indices: list, db) -> int:
    """Create Product rows from the user-selected raw_data indices."""
    from app.models.scrape_session import ScrapeSession
    from app.models.product import Product
    from app.models.variant import ProductVariant
    from app.models.supplier import Supplier

    session = db.query(ScrapeSession).filter(ScrapeSession.id == UUID(session_id)).first()
    if not session or not session.raw_data:
        return 0

    supplier = None
    if session.supplier_id:
        supplier = db.query(Supplier).filter(Supplier.id == session.supplier_id).first()

    raw = session.raw_data
    success = 0
    product_ids_to_detail_scrape: list = []
    for i in indices:
        if i < 0 or i >= len(raw):
            continue
        prod_data = raw[i]
        if not prod_data.get("title"):
            continue
        try:
            existing = None
            if prod_data.get("url") and session.supplier_id:
                existing = db.query(Product).filter(
                    Product.source_url == prod_data["url"],
                    Product.supplier_id == session.supplier_id,
                ).first()

            if existing:
                if prod_data.get("price"):
                    price_str = prod_data["price"].replace("$", "").replace(",", "").strip()
                    try:
                        new_price = Decimal(price_str.split()[0])
                        if existing.supplier_price != new_price:
                            from app.workers.pricing_tasks import _detect_price_change
                            _detect_price_change(existing, new_price, session.supplier_id, db)
                    except Exception:
                        pass
            else:
                # Prefer vendor from JSON data, fall back to supplier name
                vendor = prod_data.get("vendor") or (supplier.name if supplier else None)
                product = Product(
                    user_id=supplier.user_id if supplier else UUID("00000000-0000-0000-0000-000000000001"),
                    supplier_id=session.supplier_id,
                    title=prod_data["title"],
                    raw_title=prod_data["title"],
                    vendor=vendor,
                    source_url=prod_data.get("url"),
                    source_type="scrape",
                    status="draft",
                    sync_status="never_synced",
                )
                if prod_data.get("price"):
                    price_str = prod_data["price"].replace("$", "").replace(",", "").strip()
                    try:
                        product.supplier_price = Decimal(price_str.split()[0])
                        product.supplier_price_at = datetime.utcnow()
                    except Exception:
                        pass
                # Use description from Shopify JSON if available
                if prod_data.get("body_html"):
                    product.body_html = prod_data["body_html"]
                    product.raw_description = prod_data["body_html"]

                db.add(product)
                db.flush()

                variant = ProductVariant(
                    product_id=product.id,
                    sku=prod_data.get("sku"),
                    price=product.supplier_price or Decimal("0"),
                    position=1,
                )
                db.add(variant)

                # Store images from Shopify JSON if available
                json_images = prod_data.get("images", [])
                for idx, src in enumerate(json_images[:10]):
                    from app.models.image import ProductImage
                    db.add(ProductImage(
                        product_id=product.id,
                        src=src,
                        alt=product.title,
                        position=idx + 1,
                    ))

                success += 1

                # Only queue Playwright detail scrape if JSON didn't provide description + images
                if not prod_data.get("body_html") or not json_images:
                    product_ids_to_detail_scrape.append(str(product.id))

        except Exception as e:
            logger.warning(f"Failed to create product for index {i}: {e}")

    session.status = "done"
    db.commit()

    # Fire detail-scrape tasks after commit so product IDs are stable
    for pid in product_ids_to_detail_scrape:
        scrape_product_details.delay(pid)

    return success
