# Workers Reference

## Celery Task Registry

| Task | File | Queue | Trigger |
|---|---|---|---|
| `enrich_product` | enrichment_tasks.py | enrichment | API call (single product) |
| `enrich_products_batch` | enrichment_tasks.py | enrichment | API call (bulk) |
| `process_csv_import` | import_tasks.py | imports | API call |
| `process_pdf_import` | import_tasks.py | imports | API call |
| `process_image_batch` | import_tasks.py | imports | API call |
| `scrape_supplier_catalog` | scrape_tasks.py | scraping | API call / beat |
| `scrape_product_details` | scrape_tasks.py | scraping | API call |
| `check_all_supplier_prices` | pricing_tasks.py | pricing | Beat: every 15 min |
| `check_supplier_price_changes` | pricing_tasks.py | pricing | Queued by above |
| `apply_due_schedules` | pricing_tasks.py | pricing | Beat: every 1 min |
| `sync_use_supplier_prices` | pricing_tasks.py | pricing | Beat: daily 02:00 UTC |
| `sync_single_supplier_price` | pricing_tasks.py | pricing | Queued by sync_use_supplier_prices |
| `sync_product_to_shopify` | sync_tasks.py | sync | API call / beat |
| `sync_price_update_only` | sync_tasks.py | sync | After alert/schedule auto-apply |
| `retry_failed_syncs` | sync_tasks.py | sync | Beat: every 1 hr |
| `sync_all_inboxes` | email_tasks.py | default | Beat: every 15 min |
| `redact_shop_data` | gdpr_tasks.py | default | GDPR shop/redact webhook |

---

## Worker Pool

- **Dev (Windows)**: `threads` pool, `concurrency=4` — set in `celery_app.py`
- **Production (Linux)**: switch to `gevent --concurrency=50` for I/O-heavy workloads (enrichment, scraping)
- **Horizontal scaling**: add more worker processes pointing at the same Redis broker

---

## Batch Enrichment Pattern

`enrich_products_batch` uses a 3-phase pattern to avoid DB connection pool exhaustion:

```
Phase 1: open DB → read product data → CLOSE DB
Phase 2: wait at asyncio.Semaphore → call Claude API (no DB connection held)
Phase 3: open DB → write results → CLOSE DB
```

Max live DB connections = semaphore limit (`DEFAULT_CONCURRENCY = 15`), not N products.

`asyncio.gather()` launches all coroutines immediately — holding connections during semaphore wait would exhaust the pool. The 3-phase design prevents this.

One shared `AsyncClaudeClient` per batch task reuses the httpx connection pool across all concurrent coroutines.

---

## Pricing Tasks

`_detect_price_change(product, new_price, supplier_id, db)`:
- Compares `new_price` against `product.supplier_price`
- If `change_pct <= supplier.auto_approve_threshold`: auto-apply, sync to Shopify, create `auto_applied` alert
- Otherwise: create `pending` alert for manual review
- Always calls `record_price_history()` on change

`_calculate_schedule_price(original, schedule)` handles: `set | percent_off | fixed_off | compare_at`

---

## Enrichment Status Flow

Worker sets status directly — do not set `enrichment_status` anywhere else except:
- `"pending"` — enrichment router, at queue time
- `"running"` — worker, at task start
- `"done"` / `"failed"` — worker, on completion

On failure, worker opens a **fresh DB session** to mark `failed` — the original session may be rolled back.

---

## Price History Sources

Always call `record_price_history()` from `services/pricing_service.py` — it's a no-op if price is unchanged. Sources:
`manual | scrape | scheduled | scheduled_revert | alert_approval | csv_import | api`
