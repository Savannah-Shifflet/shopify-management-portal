"""Synchronous scrape helpers used by the API (test-scrape endpoint)."""
from typing import Optional
from urllib.parse import urlparse

from app.models.supplier import Supplier


def _try_shopify_json(url: str, limit: int = 250) -> Optional[list]:
    """
    Probe for a Shopify JSON products endpoint and return raw product dicts.
    Handles /products, /collections/{handle}, and generic store roots.
    Returns None if the store is not Shopify or the request fails.
    """
    try:
        import httpx
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        path = parsed.path.rstrip("/")

        candidates = []
        if path.endswith("/products"):
            candidates.append(f"{base}/products.json")
        elif "/collections/" in path:
            # Correct Shopify endpoint: /collections/{handle}/products.json
            candidates.append(f"{base}{path}/products.json")
        candidates.append(f"{base}/products.json")

        headers = {"User-Agent": "Mozilla/5.0 (compatible; ProductBot/1.0)", "Accept": "application/json"}

        for json_url in candidates:
            try:
                resp = httpx.get(f"{json_url}?limit={limit}", headers=headers, timeout=10, follow_redirects=True)
                if resp.status_code == 200:
                    data = resp.json()
                    products = data.get("products")
                    if products and isinstance(products, list):
                        results = []
                        for p in products:
                            handle = p.get("handle", "")
                            product_url = f"{base}/products/{handle}" if handle else None
                            variants = p.get("variants", [])
                            price = None
                            if variants:
                                raw_price = variants[0].get("price")
                                price = f"${raw_price}" if raw_price else None
                            results.append({
                                "title": p.get("title"),
                                "price": price,
                                "sku": variants[0].get("sku") if variants else None,
                                "url": product_url,
                            })
                        if results:
                            return results
            except Exception:
                continue
    except Exception:
        pass
    return None


def test_scrape_supplier(supplier: Supplier) -> dict:
    """
    Quick test scrape that returns up to 3 products.
    Tries Shopify JSON first; falls back to Playwright for HTML sites.
    """
    config = supplier.scrape_config or {}
    url = config.get("catalog_url") or supplier.website_url

    # ── Shopify JSON fast path ──────────────────────────────────────────
    shopify_results = _try_shopify_json(url, limit=3)
    if shopify_results is not None:
        return {"success": True, "products": shopify_results[:3], "url": url, "source": "shopify_json"}

    # ── Playwright fallback ─────────────────────────────────────────────
    from playwright.sync_api import sync_playwright

    results = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent="Mozilla/5.0 (compatible; ProductBot/1.0)")
            page.goto(url, wait_until="load", timeout=25000)
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1500)
                page.evaluate("window.scrollTo(0, 0)")
            except Exception:
                pass

            product_selector = config.get("product_selector", "article, .product, [data-product]")
            price_selector = config.get("price_selector", ".price, [data-price], .product-price")
            title_selector = config.get("title_selector", "h2, h3, .product-title, .product-name")

            items = page.query_selector_all(product_selector)
            for item in items[:3]:
                title_el = item.query_selector(title_selector)
                price_el = item.query_selector(price_selector)
                results.append({
                    "title": title_el.inner_text().strip() if title_el else None,
                    "price": price_el.inner_text().strip() if price_el else None,
                    "raw_html": item.inner_html()[:500],
                })

            browser.close()
    except Exception as e:
        return {"success": False, "error": str(e), "products": []}

    return {"success": True, "products": results, "url": url}


def suggest_selectors_with_ai(supplier: Supplier, url: str = None) -> dict:
    """
    Analyze the supplier's page to suggest scrape configuration.
    Strategy:
      1. Try Shopify JSON API — if available, no CSS selectors needed.
      2. Fall back to Playwright DOM heuristics for HTML-only sites.
    """
    url = url or supplier.website_url

    # ── Shopify JSON fast path ──────────────────────────────────────────
    shopify_results = _try_shopify_json(url, limit=3)
    if shopify_results is not None:
        notes = (
            "Shopify store detected — products are fetched automatically via the Shopify JSON API. "
            "No CSS selectors are needed. The scraper will handle pagination automatically."
        )
        return {
            "success": True,
            "shopify_json": True,
            "suggestions": {"notes": notes},
            "samples": shopify_results,
            "url": url,
        }

    # ── Playwright DOM heuristics ───────────────────────────────────────
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent="Mozilla/5.0 (compatible; ProductBot/1.0)")
            page.goto(url, wait_until="load", timeout=25000)
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass  # Page is loaded enough; ignore ongoing background requests
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1500)
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(500)
            except Exception:
                pass

            result = page.evaluate("""() => {
                // Build a short, stable CSS selector for a single element
                function selectorFor(el) {
                    if (!el) return '';
                    if (el.id) return '#' + CSS.escape(el.id);
                    const tag = el.tagName.toLowerCase();
                    const skipPattern = /^(active|selected|hover|focus|open|visible|hidden|js-|is-|has-|ng-|v-)/;
                    const classes = [...el.classList]
                        .filter(c => !skipPattern.test(c) && c.length > 1)
                        .slice(0, 2);
                    if (classes.length) return tag + '.' + classes.map(c => CSS.escape(c)).join('.');
                    return tag;
                }

                // Does this element's text look like a price?
                const priceRe = /[\\$\\£\\€\\¥\\₹]\\s*[\\d,]+\\.?\\d{0,2}|[\\d,]+\\.?\\d{0,2}\\s*[\\$\\£\\€\\¥\\₹]/;
                function looksLikePrice(text) {
                    return priceRe.test(text) && text.trim().length < 25;
                }

                // Collect leaf elements whose text looks like a price
                const priceLeaves = [];
                const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
                let node;
                while ((node = walker.nextNode())) {
                    if (node.children.length === 0) {
                        const t = node.textContent.trim();
                        if (looksLikePrice(t)) priceLeaves.push(node);
                    }
                }
                if (priceLeaves.length === 0) {
                    return { error: 'No price-like text found on the page. Make sure the Website URL points to a product listing page.' };
                }

                // From each price leaf, walk up to find a repeating ancestor (>=3 matches)
                // that also contains non-price content — ensuring it is a full product card,
                // not just the price wrapper itself.
                let containerSel = null;
                let containerCount = 0;
                for (const leaf of priceLeaves.slice(0, 8)) {
                    let el = leaf.parentElement;
                    while (el && el !== document.body) {
                        const sel = selectorFor(el);
                        if (sel) {
                            try {
                                const matches = document.querySelectorAll(sel);
                                if (matches.length >= 3) {
                                    // Require the candidate container to have at least one
                                    // leaf element whose text is NOT a price (e.g. a title).
                                    const firstMatch = matches[0];
                                    const leaves = [...firstMatch.querySelectorAll('*')]
                                        .filter(e => e.children.length === 0 && e.textContent.trim().length > 2);
                                    const hasNonPrice = leaves.some(e => !looksLikePrice(e.textContent.trim()));
                                    if (hasNonPrice) {
                                        containerSel = sel;
                                        containerCount = matches.length;
                                        break;
                                    }
                                }
                            } catch (e) {}
                        }
                        el = el.parentElement;
                    }
                    if (containerSel) break;
                }
                if (!containerSel) {
                    return { error: 'Could not identify a repeating product container. The page may require login or use infinite scroll.' };
                }

                const firstContainer = document.querySelector(containerSel);

                // Title: first heading, then .title/.name class, then anchor with text
                const titleCandidates = [
                    ...firstContainer.querySelectorAll('h1,h2,h3,h4,h5,h6'),
                    ...firstContainer.querySelectorAll('.title,.name,.product-title,.product-name'),
                    ...firstContainer.querySelectorAll('a[href]'),
                ];
                let titleSel = '';
                for (const el of titleCandidates) {
                    const text = el.textContent.trim();
                    if (text.length > 3 && text.length < 200) {
                        titleSel = selectorFor(el);
                        break;
                    }
                }

                // Price: the price leaf inside the first container
                let priceSel = '';
                const priceInContainer = [...firstContainer.querySelectorAll('*')]
                    .filter(el => el.children.length === 0)
                    .find(el => looksLikePrice(el.textContent.trim()));
                if (priceInContainer) priceSel = selectorFor(priceInContainer);

                // SKU: short text matching a part-number pattern
                const skuRe = /^[A-Z0-9][A-Z0-9\\-\\/\\.]{2,}$/i;
                let skuSel = '';
                for (const el of firstContainer.querySelectorAll('*')) {
                    if (el.children.length === 0) {
                        const t = el.textContent.trim();
                        if (t.length >= 3 && t.length <= 30 && skuRe.test(t.replace(/\\s+/g, ''))) {
                            skuSel = selectorFor(el);
                            break;
                        }
                    }
                }

                // Next page: standard pagination patterns
                const nextPagePatterns = [
                    'a[rel="next"]',
                    '[aria-label="Next page"]',
                    '[aria-label="Next"]',
                    '.pagination .next a',
                    '.pagination a[href*="page"]',
                    'a.next',
                    '.next-page a',
                    'nav a[href*="page"]:last-child',
                ];
                let nextPageSel = '';
                for (const pat of nextPagePatterns) {
                    try {
                        if (document.querySelector(pat)) { nextPageSel = pat; break; }
                    } catch (e) {}
                }

                // Extract sample content from first 3 containers using detected selectors
                const allContainers = [...document.querySelectorAll(containerSel)];
                const samples = allContainers.slice(0, 3).map(c => ({
                    title: titleSel ? (c.querySelector(titleSel)?.textContent.trim() || null) : null,
                    price: priceSel ? (c.querySelector(priceSel)?.textContent.trim() || null) : null,
                    sku:   skuSel   ? (c.querySelector(skuSel)?.textContent.trim()   || null) : null,
                }));

                // Return a lightly-indented snippet of the first container's HTML so the
                // user can inspect the DOM structure and write selectors manually.
                const rawHtml = firstContainer.outerHTML;
                const container_html = rawHtml.length > 6000 ? rawHtml.slice(0, 6000) + ' [truncated]' : rawHtml;

                return {
                    product_selector: containerSel,
                    title_selector: titleSel,
                    price_selector: priceSel,
                    sku_selector: skuSel,
                    next_page_selector: nextPageSel,
                    container_count: containerCount,
                    container_html,
                    samples,
                };
            }""")

            browser.close()
    except Exception as e:
        return {"success": False, "error": f"Could not load page: {e}"}

    if result.get("error"):
        return {"success": False, "error": result["error"]}

    count = result.pop("container_count", 0)
    samples = result.pop("samples", [])
    container_html = result.pop("container_html", "")
    notes = f"Found {count} product containers matching '{result['product_selector']}'."
    if not result["title_selector"]:
        notes += " Could not detect a title selector — enter it manually."
    if not result["price_selector"]:
        notes += " Could not detect a price selector — enter it manually."

    return {"success": True, "suggestions": {**result, "notes": notes}, "samples": samples, "container_html": container_html, "url": url}
