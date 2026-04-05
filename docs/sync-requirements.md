# Bi-Directional Shopify Sync — Requirements Document

**Scope**: Define every rule governing how data moves between ProductHub and Shopify, which system owns each field, how conflicts are resolved, and what implementation steps produce a fully automatic, real-time sync without data loss.

---

## 1. Core Principles

1. **One owner per field.** Every field has exactly one authoritative source. The owner's value always wins on conflict. No negotiation — deterministic, no timestamp comparison needed.
2. **Non-destructive by default.** AI fields (`ai_description`, `ai_tags`, `ai_attributes`) are never touched by sync in either direction.
3. **Webhooks are the real-time channel Shopify → App.** The manual pull (`POST /sync/shopify/pull`) is a recovery tool only; normal operation never requires it.
4. **Push is the real-time channel App → Shopify.** Every user edit that changes an app-owned field must mark the product `out_of_sync` and queue a push immediately.
5. **Idempotent operations.** Every sync operation can be retried safely. Hashes prevent redundant API calls.
6. **Deletions must propagate.** An image deleted in Shopify must disappear from the app. An image deleted in the app must disappear from Shopify. A product deleted in Shopify must be marked archived (not deleted) in the app.

---

## 2. Field Ownership Model

This is the definitive table. "Owner" determines who writes; the other side reads.

### 2a. Product-Level Fields

| Field | Owner | On App→Shopify Push | On Shopify→App Webhook | Notes |
|---|---|---|---|---|
| `title` | **App** | Always pushed | Ignored | Edited in app only |
| `body_html` | **App** | Always pushed | Ignored | Accepted AI or manual edit |
| `vendor` | **App** | Always pushed | Ignored | |
| `product_type` | **App** | Always pushed | Ignored | |
| `tags` | **App** | Always pushed | Ignored | `product.tags` preferred; `ai_tags` if null |
| `options` | **App** | Pushed on create; immutable after | Ignored | Shopify enforces immutability on existing variants |
| `handle` | **Shopify** | Never pushed (Shopify auto-generates) | Update local | Shopify enforces uniqueness |
| `status` | **Shopify** | Push local status on explicit user action | **Update local immediately** | Active/Draft/Archived — Shopify is the publication record |
| `shopify_product_id` | **Shopify** | Written from create response | Read-only | Never modified by app |
| `raw_title` | **App** | Never pushed | Never touched | Preserved from import forever |
| `raw_description` | **App** | Never pushed | Never touched | Preserved from import forever |
| `source_url` | **App** | Never pushed | Never touched | |
| `ai_description` | **App (AI)** | Never pushed directly | Never touched | Staging field only |
| `ai_tags` | **App (AI)** | Never pushed directly | Never touched | Staging field only |
| `ai_attributes` | **App (AI)** | Never pushed directly | Never touched | |
| `cost_price` | **App** | Never pushed | Never touched | Internal cost data |
| `supplier_price` | **App** | Never pushed | Never touched | |
| `map_price` | **App** | Never pushed | Never touched | |
| `base_price` | **App** | Pushed via variant price | Never touched | Source of truth for selling price |
| `compare_at_price` | **App** | Pushed via variant | Never touched | |
| `enrichment_status` | **App** | Never pushed | Never touched | |
| `sync_status` | **System** | Set to `synced` on success | Set to `out_of_sync` on relevant webhook | |
| `shopify_hash` | **System** | Written after successful push | Cleared on `out_of_sync` | Change detection |

### 2b. Variant-Level Fields

| Field | Owner | On Push | On Webhook | Notes |
|---|---|---|---|---|
| `price` | **App** | Always pushed | Ignored | If `use_supplier_price=true`, `supplier_price` → `price` before push |
| `compare_at_price` | **App** | Always pushed | Ignored | |
| `sku` | **App** | Always pushed | Ignored | |
| `barcode` | **App** | Always pushed | Ignored | |
| `weight` / `weight_unit` | **App** | Always pushed | Ignored | |
| `inventory_policy` | **App** | Always pushed | Ignored | deny/continue |
| `taxable` | **App** | Always pushed | Ignored | |
| `requires_shipping` | **App** | Always pushed | Ignored | |
| `option1/2/3` | **App** | Pushed on create only | Ignored | Shopify immutable after create |
| `inventory_quantity` | **Shopify** | **Never pushed** | **Update local immediately** | Shopify manages inventory; app is read-only |
| `shopify_variant_id` | **Shopify** | Written from create/update response | Read-only | |

### 2c. Images

| Scenario | Action |
|---|---|
| Image added locally (no `shopify_image_id`) | Push to Shopify on next sync; write `shopify_image_id` back |
| Image deleted locally | Delete from Shopify via `fileDelete` mutation on next sync |
| Image added in Shopify (webhook) | Create local `ProductImage` record |
| Image deleted in Shopify (webhook) | Delete local `ProductImage` record |
| CDN URL changed (same image, new query string) | Update local `src` only |

---

## 3. Sync Status State Machine

```
never_synced ──────────────────────────────► pending ──► [push task runs]
                                                               │
                                              ┌────────────────┼──────────────────┐
                                              ▼                ▼                  ▼
                                           synced           failed          out_of_sync
                                              │                │                  │
                          webhook arrives ────┤         retry beat ──► pending    │
                          or local edit       │                                   │
                                             ▼                              user/auto ──► pending
                                        out_of_sync
```

**Transitions**:

| Event | From | To |
|---|---|---|
| User queues sync | any | `pending` |
| `sync_product_to_shopify` task starts | `pending` | `pending` (stays; hash checked inside task) |
| Push succeeds, hash matches (no-op) | `pending` | `synced` |
| Push succeeds, Shopify updated | `pending` | `synced` |
| Push fails (all retries exhausted) | `pending` | `failed` |
| User edits an app-owned field via `PATCH /products/{id}` | `synced` | `out_of_sync` |
| Webhook arrives with relevant change (status, inventory, images) | `synced` | stays `synced` (local updated, hash invalidated) |
| Webhook arrives but nothing actually changed | `synced` | stays `synced` |
| Hourly beat picks up `failed` | `failed` | `pending` |
| Product deleted in Shopify webhook | any | `archived` (status) + `sync_status = synced` |

**Rule**: `sync_status = out_of_sync` must be set atomically with the field edit in the same DB transaction. Never let a field update commit without also flagging out_of_sync.

---

## 4. App → Shopify (Push) — Full Specification

### 4a. Trigger Points

Every one of these must queue `sync_product_to_shopify`:

| Trigger | Condition |
|---|---|
| `PATCH /products/{id}` edits any app-owned field | Product already has `shopify_product_id` |
| `POST /products/{id}/variants` adds a variant | Has `shopify_product_id` |
| `PATCH /products/{id}/variants/{vid}` | Has `shopify_product_id` |
| `DELETE /products/{id}/variants/{vid}` | Has `shopify_product_id` |
| `POST /products/{id}/images` | Has `shopify_product_id` |
| `DELETE /products/{id}/images/{iid}` | Has `shopify_product_id` |
| Accept AI description (`accept_ai_description=true`) | Has `shopify_product_id` |
| Accept AI tags (`accept_ai_tags=true`) | Has `shopify_product_id` |
| Bulk action: approve/sync/enrich | Any product in set with `shopify_product_id` |
| Pricing alert approved (price change) | Use `sync_price_update_only` for speed |
| Supplier price sync updates `base_price` | Use `sync_price_update_only` for speed |
| Manual: `POST /sync/product/{id}` | Always |
| Manual: `POST /sync/products` | Always |
| Manual: `POST /sync/all` | Always |
| Hourly retry beat | `sync_status = failed` |

### 4b. Push Task Logic (revised `sync_product_to_shopify`)

```
1. Load product + user + variants + images from DB
2. If no Shopify connection → mark failed, stop
3. If shopify_product_id exists:
   a. Pre-fetch current Shopify product (get_product)
   b. Reconcile variant IDs (sku/position matching)
   c. Check image deletions: local images with shopify_image_id NOT in Shopify response
      → delete those local DB records (they were deleted directly in Shopify before we could track)
4. Build payload (app fields only — no Shopify fallbacks for app-owned fields)
5. Compute hash
6. If hash == shopify_hash AND sync_status == 'synced' → skip (no-op), return
7. If shopify_product_id exists → update_product()
   Else → create_product()
8. Handle image deletions: any ProductImage with is_deleted=True → call fileDelete mutation
9. Write shopify_image_id for newly uploaded images
10. Update product: shopify_product_id, sync_status='synced', synced_at, shopify_hash
11. Write ShopifySyncLog
12. On any exception: set sync_status='failed', log, retry with backoff
```

### 4c. Payload Build Rules (no fallbacks for app-owned fields)

Current code uses Shopify values as fallbacks for empty app fields (e.g., `product.title or sc.get("title")`). This must change for app-owned fields:

- **App-owned fields**: send the local value directly, even if empty. An empty `body_html` should push an empty description to Shopify — the user cleared it intentionally.
- **The only exception**: if the product has never been pushed before (create), and a local field is empty, it's acceptable to leave it empty in Shopify rather than pulling from nowhere.
- **Variant price exception**: if `v.price == 0` AND `use_supplier_price=False`, that's a data problem — log a warning and skip that variant rather than sending $0.

### 4d. Image Deletion Tracking

Add a column `is_pending_delete BOOLEAN DEFAULT FALSE` to `product_images` table (new migration).

- When `DELETE /products/{id}/images/{iid}` is called:
  - If image has a `shopify_image_id`: set `is_pending_delete = True` (do NOT delete the DB row yet)
  - If image has no `shopify_image_id`: delete the DB row immediately (never existed in Shopify)
- During push task: collect all `is_pending_delete = True` images → call `fileDelete` mutation → delete DB rows on success
- If `fileDelete` fails: leave `is_pending_delete = True` for retry on next push

---

## 5. Shopify → App (Webhooks) — Full Specification

### 5a. `products/update` Webhook

**Must implement** — currently a stub that does nothing.

**Payload fields received** (Shopify REST format):

```json
{
  "id": 123456789,
  "title": "...",
  "body_html": "...",
  "vendor": "...",
  "product_type": "...",
  "handle": "...",
  "status": "active",
  "tags": "tag1, tag2",
  "variants": [{ "id": 111, "sku": "...", "price": "...", "inventory_quantity": 5, ... }],
  "images": [{ "id": 222, "src": "...", "alt": "..." }]
}
```

**Processing logic**:

```
1. Verify HMAC (shopify_webhook_secret)
2. Respond 200 immediately (async processing — Shopify requires response within 5s)
3. Queue Celery task: handle_shopify_product_update(shopify_id, payload)
```

**`handle_shopify_product_update` task logic**:

```
1. Look up local product by shopify_product_id
2. If not found: log warning, stop (product not imported yet — manual pull needed)
3. Apply Shopify-owned field updates (ONLY these fields):
   a. status → map ACTIVE/DRAFT/ARCHIVED to local values, update product.status
   b. handle → update product.handle
4. Do NOT overwrite app-owned fields (title, body_html, vendor, product_type, tags)
5. For each variant in webhook payload:
   a. Match local variant by shopify_variant_id (primary) or sku (fallback)
   b. Update inventory_quantity (Shopify-owned)
   c. Do NOT overwrite price, compare_at, sku, barcode, weight (app-owned)
6. Reconcile images:
   a. Build set of shopify_image_ids present in webhook payload
   b. Query local ProductImage records for this product
   c. For each local image with shopify_image_id NOT in payload set:
      → delete local DB record (image was deleted in Shopify)
   d. For each image in payload NOT matching any local record (by shopify_image_id or base src):
      → create new local ProductImage record
   e. For each image in payload matching an existing local record:
      → update src (CDN URL may change) and alt
7. Invalidate sync hash: set product.shopify_hash = NULL
   (hash will be recomputed on next push — ensures next push detects real delta)
8. Update product.sync_status:
   - If only inventory/status/images changed: keep 'synced' (these are Shopify-owned, no push needed)
   - Record the webhook event in ShopifySyncLog (operation='webhook_update')
9. Commit
```

**Critical rules**:
- Step 4 is non-negotiable: webhook must never overwrite `title`, `body_html`, `tags`, `vendor`, `product_type`. If a merchant edits these in Shopify admin, the next app push will correct them back. The app is authoritative for content.
- Step 7 (hash invalidation) ensures that if the webhook changes status or images, the next push will include the correct hash and not skip.

### 5b. `products/delete` Webhook

**Must implement** — currently a stub.

**Processing logic**:

```
1. Verify HMAC
2. Respond 200 immediately
3. Queue Celery task: handle_shopify_product_delete(shopify_id)
```

**`handle_shopify_product_delete` task logic**:

```
1. Look up local product by shopify_product_id
2. If not found: log, stop
3. Set product.status = 'archived'
4. Set product.sync_status = 'synced' (it is in sync — just archived)
5. Set product.shopify_product_id = NULL (it no longer exists in Shopify)
   Note: keep shopify_product_id? Debatable. Setting NULL prevents accidental re-push to a dead ID.
   Preferred: keep the ID for audit purposes but set a new field deleted_in_shopify_at timestamp.
6. Log to ShopifySyncLog (operation='webhook_delete')
7. Commit
```

**Do NOT delete the local product record.** The app is a product database; Shopify deletion is a publication event, not a data deletion event.

### 5c. `orders/create` Webhook

Currently a stub. For now: log the order and update `inventory_quantity` on matching variants.

```
1. Verify HMAC
2. Queue Celery task: handle_shopify_order_created(payload)
3. For each line_item in order:
   a. Find local variant by shopify_variant_id
   b. Decrement inventory_quantity by line_item.quantity
   c. If quantity < store_settings.low_stock_threshold → create alert (future)
4. Log
```

### 5d. Webhook Registration Requirements

These webhooks must be registered in Shopify Partner Dashboard (or via API on OAuth install):

| Topic | Endpoint | Secret Used |
|---|---|---|
| `products/update` | `POST /api/v1/webhooks/shopify/products/update` | `SHOPIFY_WEBHOOK_SECRET` |
| `products/delete` | `POST /api/v1/webhooks/shopify/products/delete` | `SHOPIFY_WEBHOOK_SECRET` |
| `orders/create` | `POST /api/v1/webhooks/shopify/orders/create` | `SHOPIFY_WEBHOOK_SECRET` |
| `inventory_levels/update` | `POST /api/v1/webhooks/shopify/inventory/update` *(new)* | `SHOPIFY_WEBHOOK_SECRET` |
| `customers/data_request` | `POST /api/v1/webhooks/shopify/gdpr/customers/data_request` | `SHOPIFY_CLIENT_SECRET` |
| `customers/redact` | `POST /api/v1/webhooks/shopify/gdpr/customers/redact` | `SHOPIFY_CLIENT_SECRET` |
| `shop/redact` | `POST /api/v1/webhooks/shopify/gdpr/shop/redact` | `SHOPIFY_CLIENT_SECRET` |

**Auto-register on OAuth install**: During `shopify_callback`, after storing the access token, call Shopify's webhook API to register all non-GDPR webhooks. GDPR webhooks are registered once in Partner Dashboard.

### 5e. `inventory_levels/update` Webhook (new)

Shopify fires this independently of `products/update` when inventory changes. Required for accurate real-time inventory.

```
Payload: { inventory_item_id, location_id, available }
```

**Task logic**:

```
1. Look up ProductVariant by shopify_variant_id where inventoryItem.id matches
   (requires storing inventory_item_id on ProductVariant — new column needed)
2. Update variant.inventory_quantity = available
3. Commit
```

---

## 6. Manual Pull (`POST /sync/shopify/pull`) — Corrected Behavior

The pull endpoint is a **recovery/import tool** only. Its merge rules must respect field ownership:

### 6a. For existing products (matched by shopify_product_id or SKU)

| Field | Current (wrong) | Corrected |
|---|---|---|
| `title` | Always overwritten | **Skip** (app-owned) |
| `body_html` | Overwritten if Shopify non-empty | **Skip** (app-owned) |
| `vendor` | Overwritten if Shopify non-empty | **Skip** (app-owned) |
| `product_type` | Overwritten if Shopify non-empty | **Skip** (app-owned) |
| `tags` | Overwritten if Shopify non-empty | **Skip** (app-owned) |
| `options` | Overwritten if Shopify non-empty | **Skip** (immutable after create) |
| `status` | Overwritten | **Overwrite** (Shopify-owned) ✓ |
| `handle` | Overwritten if Shopify non-empty | **Overwrite** (Shopify-owned) ✓ |
| `shopify_product_id` | Updated | **Always update** ✓ |
| `base_price` | Only if null | **Only if null** ✓ (leave if already set) |
| `compare_at_price` | Only if null | **Only if null** ✓ |
| Variant `inventory_quantity` | Overwritten | **Always overwrite** ✓ (Shopify-owned) |
| Variant `price` | Overwritten | **Only if local is 0 or null** |
| Variant `sku/barcode` | Overwritten | **Only if local is empty** |
| Images | Adds new; never deletes | Adds new; **delete local images not in Shopify** |

### 6b. For new products (not in local DB)

Import fully from Shopify — all fields. Set `source_type = 'shopify_pull'`. This is correct as-is.

---

## 7. Auto-Queue on User Edits

`PATCH /products/{id}` must auto-flag `out_of_sync` and queue a push when any app-owned field changes AND the product has a `shopify_product_id`. Currently this does NOT happen — edits are silent to the sync system.

**Fields that trigger `out_of_sync` + auto-queue on PATCH**:

```
title, body_html, vendor, product_type, tags, status, options,
accept_ai_description (copies ai_description → body_html),
accept_ai_tags (copies ai_tags → tags)
```

**Fields that do NOT trigger a push** (internal app state only):

```
enrichment_status, ai_description, ai_tags, ai_attributes,
cost_price, map_price, applied_template_id, source_url
```

**Implementation in `PATCH /products/{id}`**:

```python
APP_OWNED_SYNC_FIELDS = {
    "title", "body_html", "vendor", "product_type", "tags", "status",
    "accept_ai_description", "accept_ai_tags"
}

if product.shopify_product_id and any(
    f in update_data for f in APP_OWNED_SYNC_FIELDS
):
    product.sync_status = "out_of_sync"
    # After commit:
    sync_product_to_shopify.delay(str(product.id))
```

Same pattern applies in variant and image routers.

---

## 8. Conflict Resolution — Exhaustive Scenario Table

| Scenario | Resolution | Rationale |
|---|---|---|
| App has description, Shopify empty | App wins (push sends it) | App is authoritative for content |
| Shopify has description, app has different description | App wins (push overwrites Shopify) | App is authoritative for content |
| User edits description in Shopify admin directly | Next push corrects it back to app value | App is authoritative; merchant should use the app |
| Status set to Active in Shopify | Webhook updates local status immediately | Shopify-owned field |
| Status set to Draft in app | Push sends DRAFT to Shopify | App triggers the push |
| Status changed in app AND Shopify before sync | App push fires last → app wins | Push is triggered immediately on app edit |
| Price changed in app | Push sends new price | App-owned |
| Price changed in Shopify admin | Ignored by webhook; corrected on next push | App-owned; Shopify admin price edits not respected |
| Supplier price updated (use_supplier_price=True) | `sync_price_update_only` fires automatically | Price feed → app → Shopify |
| Image added in app | Pushed on next sync, `shopify_image_id` written | App-initiated |
| Image deleted in app | `is_pending_delete=True`; deleted from Shopify on next push | Tracked deletion |
| Image added in Shopify admin | Webhook creates local `ProductImage` record | Shopify-initiated |
| Image deleted in Shopify admin | Webhook deletes local `ProductImage` record | Shopify-initiated |
| Same image deleted in both simultaneously | Webhook deletes local; push `fileDelete` gets 404 → treat as success | Idempotent |
| Product deleted in Shopify | Webhook sets local status=archived, clears shopify_product_id | Soft archive; preserve data |
| Inventory changed in Shopify | `inventory_levels/update` webhook updates local quantity | Shopify-owned |
| Inventory changed by order | `orders/create` webhook decrements local quantity | Shopify-owned |
| AI description accepted, push queued | Push sends `body_html` to Shopify | Normal flow |
| AI description accepted, then user edits in Shopify | Next push corrects back to app value | App-owned |

---

## 9. New Database Changes Required

### Migration 014: `product_images.is_pending_delete`

```sql
ALTER TABLE product_images ADD COLUMN is_pending_delete BOOLEAN NOT NULL DEFAULT FALSE;
```

### Migration 015: `product_variants.inventory_item_id`

Required for `inventory_levels/update` webhook matching:

```sql
ALTER TABLE product_variants ADD COLUMN inventory_item_id BIGINT;
CREATE INDEX ix_product_variants_inventory_item_id ON product_variants(inventory_item_id);
```

Populate on next sync: Shopify's variant response includes `inventoryItem.id` — write it back.

### Migration 016: `products.deleted_in_shopify_at` (optional but recommended)

```sql
ALTER TABLE products ADD COLUMN deleted_in_shopify_at TIMESTAMP;
```

Lets you distinguish "never synced" from "was synced but product was deleted in Shopify."

### Schema change: `ShopifySyncLog.operation` enum expansion

Add values: `webhook_update`, `webhook_delete`, `webhook_inventory`, `price_only`.

---

## 10. Celery Task Additions

| Task | Queue | Trigger |
|---|---|---|
| `handle_shopify_product_update(shopify_id, payload)` | `sync` | `products/update` webhook |
| `handle_shopify_product_delete(shopify_id)` | `sync` | `products/delete` webhook |
| `handle_shopify_order_created(payload)` | `default` | `orders/create` webhook |
| `handle_shopify_inventory_update(inventory_item_id, available)` | `sync` | `inventory_levels/update` webhook |

All four tasks must be added to `celery_app.autodiscover_tasks` and routed appropriately.

---

## 11. Implementation Steps (Ordered)

Execute in this order. Each step is independently testable.

### Step 1 — Database migrations
- Write migration 014: `product_images.is_pending_delete`
- Write migration 015: `product_variants.inventory_item_id`
- Write migration 016: `products.deleted_in_shopify_at`
- Run `alembic upgrade head`
- Verify columns exist

### Step 2 — Image deletion tracking in routers
- `DELETE /products/{id}/images/{iid}`: if `shopify_image_id` exists → set `is_pending_delete=True` instead of deleting; if no `shopify_image_id` → delete immediately
- `POST /products/{id}/images`: no change needed
- Test: delete a local image with `shopify_image_id`; confirm DB row remains with flag set

### Step 3 — Fix `update_product` to push pending image deletions
- In `sync_tasks.sync_product_to_shopify`: collect `is_pending_delete=True` images, call `client.delete_product_image()` for each, delete DB row on success
- Test: flag an image, run sync, confirm Shopify image gone and DB row deleted

### Step 4 — Remove Shopify fallbacks for app-owned fields in push payload
- In `ShopifyClient.update_product()` and `build_payload()`: remove `or sc.get("title")` etc. for title, body_html, vendor, product_type, tags
- Keep fallbacks only for: variant sku (empty sku is valid, but send what's local), variant barcode, variant weight
- Keep the variant price fallback ONLY if `v.price == 0` and add a warning log
- Test: push a product with empty vendor; confirm Shopify vendor is now blank (not kept from previous value)

### Step 5 — Fix `pull_from_shopify` field ownership
- Remove overwrites of app-owned fields (title, body_html, vendor, product_type, tags, options) for existing products
- Keep overwrites for: status, handle, shopify_product_id, sync_status
- Keep "only if null" logic for base_price, compare_at_price
- For variant price: update only if local is 0 or null
- Add image reconciliation: delete local images not present in Shopify pull response
- Test: pull with a product where app and Shopify have different titles; confirm app title preserved

### Step 6 — Auto-queue push on `PATCH /products/{id}`
- Add `APP_OWNED_SYNC_FIELDS` check after committing the PATCH
- Set `sync_status = 'out_of_sync'` in the same transaction as the field update
- After commit: if `shopify_product_id` exists → `sync_product_to_shopify.delay(str(product.id))`
- Test: PATCH a product's title; confirm `sync_status='out_of_sync'` and a Celery task is queued

### Step 7 — Auto-queue push on variant and image changes
- `PATCH /products/{id}/variants/{vid}`: same pattern as Step 6
- `POST /products/{id}/variants`: queue push
- `DELETE /products/{id}/variants/{vid}`: queue push
- `POST /products/{id}/images`: queue push (will upload new image)
- `DELETE /products/{id}/images/{iid}` (now sets flag): queue push (will delete from Shopify)
- Test each endpoint

### Step 8 — Implement `handle_shopify_product_update` Celery task
- New file `backend/app/workers/sync_tasks.py` additions (or new file `webhook_tasks.py`)
- Apply only Shopify-owned fields: status, handle, inventory_quantity (per variant), images (reconcile)
- Never touch app-owned fields
- Invalidate hash after applying changes
- Log to `ShopifySyncLog`
- Test: send a mock webhook payload; confirm status updated, title NOT updated

### Step 9 — Wire `products/update` webhook to task
- Replace stub in `webhooks.py` with: parse body, queue `handle_shopify_product_update.delay()`
- Return 200 immediately (before task runs)
- Test with ngrok + Shopify webhook delivery test

### Step 10 — Implement `handle_shopify_product_delete` Celery task
- Set status=archived, sync_status=synced, deleted_in_shopify_at=now
- Optionally clear shopify_product_id (see decision note in §5b)
- Log to ShopifySyncLog

### Step 11 — Wire `products/delete` webhook to task
- Same pattern as Step 9

### Step 12 — Implement `inventory_levels/update` webhook + task
- New route `POST /api/v1/webhooks/shopify/inventory/update`
- New task: look up variant by `inventory_item_id`, update `inventory_quantity`
- Requires `inventory_item_id` column from Step 1
- Populate `inventory_item_id` during push: add `inventoryItem { id }` to GraphQL variant response

### Step 13 — Implement `orders/create` webhook task
- Decrement `inventory_quantity` on matched variants
- Log

### Step 14 — Auto-register webhooks on OAuth install
- In `shopify_oauth.py` callback: after storing token, call Shopify webhook create API for all 4 non-GDPR topics
- Idempotent: check existing webhooks first; skip if already registered
- Store webhook IDs on User model (optional, for future management)

### Step 15 — `inventory_item_id` backfill
- During `sync_product_to_shopify`: when writing back `shopify_variant_id` from response, also write `inventory_item_id` from `inventoryItem.id` in the GraphQL response
- Update `_GQL_PRODUCT_CREATE` and `_GQL_VARIANTS_BULK_UPDATE` responses to include `inventoryItem { id }`
- Test: create/update a product; confirm `inventory_item_id` is stored on variants

### Step 16 — End-to-end integration tests
- Test: Create product in app → sync → verify Shopify
- Test: Edit title in app → verify auto-queued push → verify Shopify updated
- Test: Set product Active in Shopify → webhook fires → verify local status updated, title NOT changed
- Test: Delete image in Shopify → webhook fires → verify local DB record deleted
- Test: Add image in Shopify → webhook fires → verify local DB record created
- Test: Delete image in app → verify flag set → sync → verify Shopify image deleted
- Test: Delete product in Shopify → webhook fires → verify local status=archived
- Test: Order in Shopify → webhook fires → verify local inventory decremented
- Test: Pull from Shopify → verify app-owned fields preserved, Shopify-owned fields updated

---

## 12. What Is Explicitly Out of Scope

- **Metafields sync**: `metafields` JSONB is not pushed or pulled. Shopify metafields are managed separately.
- **Collections assignment**: Collections are read for display; the app does not assign products to collections.
- **Multi-location inventory**: `inventory_quantity` tracks a single aggregate. Multi-location tracking requires per-location inventory tables (future scope).
- **Variant option mutability**: Shopify makes variant options immutable after creation. The app enforces this by only sending `optionValues` on create, never on update.
- **Shopify draft orders**: Not tracked or synced.
- **Price edits made directly in Shopify admin**: Intentionally ignored by webhook. App owns price. If this policy changes, it requires a conflict resolution strategy (timestamp comparison) and is a separate feature.

---

## 13. Decision Log

| Decision | Rationale |
|---|---|
| App owns content fields (title, body_html, tags) | The app is the master product catalog; Shopify is a publishing channel |
| Shopify owns status | Merchants set Active/Draft/Archived in Shopify to control storefront visibility |
| Shopify owns inventory | Shopify tracks real inventory via orders and adjustments; app has no order system |
| Webhooks respond 200 immediately, queue async task | Shopify requires 5s response; DB work can take longer |
| Pull does not overwrite app-owned fields | Pull is a recovery tool; it must not clobber in-progress editorial work |
| Deleted products archived, not deleted | Product history and AI enrichment work must not be lost |
| `is_pending_delete` flag on images | Allows atomic "delete from Shopify on next sync" without a separate deletion queue |
| Hash cleared on webhook | Ensures next push re-evaluates actual delta against current Shopify state |
