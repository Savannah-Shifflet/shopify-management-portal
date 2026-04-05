# Backend Reference

## Database Models

### Product (`products`)
```
id (UUID PK) | user_id (FK) | supplier_id (FK, nullable)
shopify_product_id (BigInt, unique)

-- Status (mirrors Shopify)
status: draft | active | archived

-- Main fields (user-edited / accepted from AI)
title, body_html, vendor, product_type, handle, tags (array)

-- Raw source data (NEVER overwritten after import)
raw_title, raw_description, source_url
source_type: manual | csv | pdf | scrape | image

-- AI staging (separate from main — user must explicitly accept)
ai_title, ai_description, ai_tags (array), ai_attributes (JSONB)
seo_title, seo_description

-- AI enrichment status
enrichment_status: not_started | pending | running | done | failed
enrichment_model, enrichment_at
applied_template_id (FK → description_templates, SET NULL on delete)

-- Pricing
cost_price, map_price, base_price, compare_at_price
shipping_cost            -- per-product shipping baked into retail
supplier_price, supplier_price_at, use_supplier_price (bool)

-- Shopify sync
sync_status: never_synced | pending | synced | failed | out_of_sync
synced_at, shopify_hash (SHA256 of last synced payload)

-- Other
options (JSONB), metafields (JSONB), created_at, updated_at
```

**enrichment_status lifecycle**: `not_started` (model default — never set explicitly) → `pending` (queued) → `running` (worker picked up) → `done` / `failed`

**AI field rule**: Enrichment always writes to `ai_*` columns. `apply_ai_acceptance()` in `services/ai_acceptance.py` is the only place that copies them to main fields. See `ACCEPTANCE_MAP` in that file.

### ProductVariant (`product_variants`)
```
id, product_id (FK CASCADE), shopify_variant_id (BigInt unique)
title, sku (indexed), barcode
option1, option2, option3   -- maps to product.options names
price, compare_at_price, cost (Decimal)
inventory_quantity, inventory_policy (deny|continue), inventory_management
weight, weight_unit (kg), requires_shipping (bool), taxable (bool)
image_id (FK → product_images), position
```

### Supplier (`suppliers`)
```
id, user_id (FK), name, website_url
scrape_config (JSONB), pricing_config (JSONB), enrichment_config (JSONB)
monitor_enabled (bool), monitor_interval (min, default 1440)
last_scraped_at, auto_approve_threshold
contacts (JSONB array), crm_notes (JSONB array)

-- SRM pipeline
status: LEAD | CONTACTED | NEGOTIATING | APPROVED | REJECTED | INACTIVE
company_email, contact_name, phone, product_categories (array)
follow_up_date, approved_at, payment_terms, min_order_qty, lead_time_days
return_policy, map_enforced (bool), warranty_info

-- Fulfillment
free_shipping (bool), avg_fulfillment_days, google_listings_approved (bool)
```

### Other Models
| Model | Table | Key Fields |
|---|---|---|
| User | `users` | email, hashed_password, shopify_store, shopify_token |
| ProductImage | `product_images` | product_id, src, alt, position, shopify_image_id |
| PriceHistory | `price_history` | product_id, old_price, new_price, change_pct, source, price_type |
| PricingAlert | `pricing_alerts` | product_id, old_price, new_price, status (pending\|approved\|rejected\|auto_applied) |
| PricingSchedule | `pricing_schedules` | product_id, price_action, starts_at, ends_at, status, original_price |
| PricingRule | `pricing_rules` | supplier_id, condition_type, markup_type, markup_value, priority |
| StoreSettings | `store_settings` | user_id (unique), map_hard_block, low_stock_threshold, default_markup_pct, default_shipping_cost, SMTP/IMAP config |
| ImportJob | `import_jobs` | job_type (csv\|pdf\|scrape\|image_batch), status, total_rows, error_details |
| ScrapeSession | `scrape_sessions` | supplier_id, status, pages_scraped, raw_data (JSONB) |
| DescriptionTemplate | `description_templates` | user_id, name, sections (JSONB array) |
| SupplierEmail | `supplier_emails` | supplier_id, direction (INBOUND\|OUTBOUND), subject, body, message_id |
| SupplierDocument | `supplier_documents` | supplier_id, name, category, file_path, expires_at |
| ReorderLog | `reorder_logs` | supplier_id, user_id, po_number, status, line_items (JSONB) |
| EmailTemplate | `email_templates` | user_id, name, subject, body |
| ShopifySyncLog | `shopify_sync_log` | product_id, operation, status, error_message |
| AuditLog | `audit_logs` | user_id, action_type, entity_type, entity_id, description |

---

## API Routes (all prefixed `/api/v1`)

### Products — `routers/products.py`
```
GET    /products                    List + filters (status, sync_status, enrichment_status, supplier_id, search)
POST   /products                    Create
GET    /products/{id}               Full detail
PATCH  /products/{id}               Update — AI acceptance, MAP enforcement, sync flag, price history
DELETE /products/{id}               Archive
GET    /products/duplicate-skus     Products sharing a SKU
POST   /products/bulk               Bulk: approve | archive | tag | enrich | sync | rescrape | delete
POST   /products/merge              Merge secondaries into primary
GET    /products/{id}/variants
POST   /products/{id}/variants
PATCH  /products/{id}/variants/{vid}
DELETE /products/{id}/variants/{vid}
GET    /products/{id}/images
POST   /products/{id}/images
DELETE /products/{id}/images/{iid}
GET    /products/{id}/price-history
POST   /products/{id}/rescrape
POST   /products/sync-supplier-prices
```

**ProductUpdate special fields:**
- `accept_ai_title/description/tags/attributes` (bool) → copies staging field to main field via `apply_ai_acceptance()`
- `ai_title / ai_description` (str|null) → directly sets/clears a staging suggestion
- `applied_template_id` (UUID|null) → sets/clears template association
- `enrichment_status` (str) → directly sets status (used by reject flow)

### Enrichment — `routers/enrichment.py`
```
POST /enrichment/product/{id}     Queue single enrichment (fields, template_id)
POST /enrichment/bulk             Queue batch enrichment (product_ids, fields, template_id)
GET  /enrichment/status/{task_id} Celery task status
```

### Suppliers — `routers/suppliers.py`
```
GET/POST/PATCH/DELETE  /suppliers, /suppliers/{id}
GET                    /suppliers/{id}/stats
POST                   /suppliers/{id}/scrape-now
GET                    /suppliers/{id}/scrape-status
GET/POST               /suppliers/{id}/scrape-sessions/{sid}/status|items|approve
POST                   /suppliers/{id}/test-scrape
POST                   /suppliers/{id}/suggest-selectors
POST                   /suppliers/{id}/bulk-apply-supplier-price
POST                   /suppliers/{id}/rescrape-products
GET                    /suppliers/{id}/scrape-history
PATCH                  /suppliers/{id}/status
GET/POST               /suppliers/{id}/emails
POST                   /suppliers/{id}/emails/send
GET/POST/DELETE        /suppliers/{id}/documents, /documents/{did}
GET/POST/PATCH/DELETE  /suppliers/{id}/checklist, /checklist/{iid}
GET/POST/PATCH         /suppliers/{id}/reorders, /reorders/{rid}
POST                   /suppliers/{id}/generate-letter
POST                   /suppliers/import-csv
POST                   /suppliers/bulk-email
POST                   /suppliers/sync-inbox
```

### Other Routers
```
POST /auth/register | POST /auth/login | GET /auth/me
GET/PATCH /store-settings/ | POST /store-settings/test-email
GET/POST /settings/shopify | POST /settings/shopify/disconnect
GET /sync/status | POST /sync/product/{id} | POST /sync/products | POST /sync/all
GET /sync/log | GET /sync/shopify/connection | POST /sync/shopify/pull
GET /pricing/alerts | POST /pricing/alerts/{id}/approve | POST /pricing/alerts/{id}/reject
POST /pricing/alerts/bulk-approve
GET/POST/PATCH/DELETE /pricing/rules | /pricing/schedules
POST /pricing/calculate | POST /pricing/bulk-update
GET/POST/PATCH/DELETE /email-templates/
GET /reorders/ | GET /audit/ | GET /analytics/orders
POST /imports/csv | /imports/pdf | /imports/scrape | /imports/images
GET /imports/jobs | GET /imports/jobs/{id} | POST /imports/csv/column-map
POST /webhooks/shopify/products/update | /delete | /orders/create
POST /webhooks/shopify/gdpr/customers/data_request
POST /webhooks/shopify/gdpr/customers/redact
POST /webhooks/shopify/gdpr/shop/redact
```

### Templates — `routers/templates.py`
```
GET/POST/PATCH/DELETE /templates, /templates/{id}
POST /templates/ai-fill    Reorganize description into template structure (returns HTML, not saved)
```
Template section schema: `{ tag, title, hint, required, indent }` — see `.claude/architecture.md`.

---

## Alembic Migrations

| Revision | What it does |
|---|---|
| 001 | Initial schema: all core tables |
| 002 | Add `shopify_token_expires_at` to users |
| 003 | Add `use_supplier_price` to products |
| 004 | Add supplier fulfillment fields |
| 005 | Replace flat contact fields with `contacts` JSONB array on suppliers |
| 006 | Add `detail_scrape_logs` table |
| 007 | Add `description_templates` table |
| 008 | Add `options` JSONB to products |
| 009 | SRM core: supplier CRM/pipeline fields; supplier_emails, documents, checklist, reorder_logs, email_templates, audit_logs, store_settings |
| 010 | Add IMAP config to store_settings; `message_id` to supplier_emails |
| 011 | Add `applied_template_id` FK to products |
| 012 | Fix `enrichment_status` default → `"not_started"` |
| 013 | Simplify product status: `draft \| active \| archived` |
| 014 | Add `shipping_cost` to products; `default_shipping_cost` + `default_markup_pct` to store_settings |
| 015 | Add `ai_title` to products |

---

## Environment Variables

```bash
# backend/.env
DATABASE_URL=postgresql://postgres:admin@localhost:5432/shopify_products
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
ANTHROPIC_API_KEY=...
SECRET_KEY=...                  # JWT signing — must change in production
CORS_ORIGINS=http://localhost:3000
STORAGE_PATH=./storage
SHOPIFY_CLIENT_ID=...
SHOPIFY_CLIENT_SECRET=...
APP_URL=http://localhost:8000   # Backend — Shopify OAuth callback base
FRONTEND_URL=http://localhost:3000

# frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```
