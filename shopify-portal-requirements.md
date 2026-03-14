# Shopify Management Portal — Product Requirements
**Version 1.1 | Authorized High-Ticket Reseller Edition**
**Repo:** https://github.com/Savannah-Shifflet/shopify-management-portal

---

## Overview

This document extends the existing portal (Shopify sync, AI enrichment, multi-format product import) with a full **Supplier Relationship Management (SRM)** module and supporting features tailored to an authorized reseller selling high-ticket products. Requirements are organized by module and written as implementation-ready user stories for Claude Code.

**Existing stack:** React (TypeScript) frontend · Python backend · nginx · Docker Compose

---

## Module 1: Supplier Discovery & Outreach

### 1.1 Supplier Lead Tracking

**US-101 — Add a supplier lead**
> As a store owner, I want to manually add a potential supplier (brand/manufacturer) with fields for company name, contact name, email, phone, website, product categories, and notes, so I can start tracking them before any outreach.

**Acceptance Criteria:**
- Form with required fields: company name, primary contact email
- Optional fields: contact name, phone, website URL, product categories (multi-select tags), notes, estimated product price range
- Supplier saved with status = `LEAD` and `created_at` timestamp
- Duplicate email check with warning on save

---

**US-102 — View supplier pipeline**
> As a store owner, I want a Kanban-style or table view of all supplier leads organized by status (`LEAD → CONTACTED → NEGOTIATING → APPROVED → REJECTED → INACTIVE`), so I can see my pipeline at a glance.

**Acceptance Criteria:**
- Table view (default) with columns: Company, Contact, Status, Last Contact Date, # Emails Sent, # Emails Received, Next Follow-up Date
- Filter by status, product category, date added
- Sort by any column
- Inline status change via dropdown
- Bulk status update

---

**US-103 — Import supplier leads from CSV**
> As a store owner, I want to import a CSV of supplier leads with column mapping, so I can bulk-add prospects I've researched elsewhere.

**Acceptance Criteria:**
- Upload CSV, map columns to supplier fields
- Preview first 5 rows before import
- Skip duplicates (match on email), report how many were skipped
- Show import summary (added / skipped / errors)

---

### 1.2 Email Outreach

**US-104 — Compose and send outreach email**
> As a store owner, I want to compose and send an email to a supplier directly from the portal, so all communication is tracked in one place.

**Acceptance Criteria:**
- Email composer with To (pre-filled from supplier), Subject, Body (rich text)
- Send via configured SMTP or Gmail OAuth integration
- Email saved to supplier's communication log with timestamp, subject, body, direction = `OUTBOUND`
- Supplier status auto-updates to `CONTACTED` if currently `LEAD`

---

**US-105 — Email templates**
> As a store owner, I want to create and manage reusable email templates (e.g., "Initial Outreach", "Follow-Up", "Reseller Application"), so I can send consistent, professional messages quickly.

**Acceptance Criteria:**
- Template library: name, subject, body with `{{supplier_name}}`, `{{my_store_name}}`, `{{my_name}}` merge fields
- Apply template to email composer (populates subject + body, still editable)
- CRUD for templates
- At least 3 starter templates pre-seeded on first run

---

**US-106 — Scheduled follow-up reminders**
> As a store owner, I want to set a follow-up reminder date on any supplier, so I get an in-app notification when it's time to re-contact them.

**Acceptance Criteria:**
- Date picker on supplier detail page labeled "Follow-up Reminder"
- Dashboard badge/alert showing suppliers with overdue or due-today follow-ups
- Reminder dismissable; can set a new one after dismissal

---

**US-107 — Log inbound email response**
> As a store owner, I want to manually log a reply I received from a supplier (paste body or attach a file), so the full conversation history is in the portal even if I read it in my email client.

**Acceptance Criteria:**
- "Log Response" button on supplier detail page
- Fields: date received, subject, body (text area), optional file attachment (PDF/image)
- Saved with direction = `INBOUND`
- Supplier status can be manually updated at the same time

---

**US-108 — Email thread view per supplier**
> As a store owner, I want to see a chronological conversation thread for each supplier showing all sent and received emails, so I have full context before writing the next message.

**Acceptance Criteria:**
- Timeline view: sent (right-aligned/blue) vs received (left-aligned/gray)
- Shows date, subject, truncated body (expand to full)
- Attached files downloadable inline
- Total sent count and last contact date shown in header

---

### 1.3 Supplier Approval Workflow

**US-109 — Supplier application checklist**
> As a store owner, I want to track an approval checklist for each supplier (e.g., W9 received, reseller agreement signed, MAP policy reviewed, credit terms confirmed), so I know exactly what's needed before onboarding them.

**Acceptance Criteria:**
- Configurable checklist template (global settings)
- Per-supplier checklist with checkbox + optional notes per item
- File upload per checklist item (e.g., attach signed agreement PDF)
- Progress bar showing % complete
- Cannot mark supplier as `APPROVED` until checklist is 100% (with override option + reason)

---

**US-110 — Approve supplier**
> As a store owner, I want to formally approve a supplier once all requirements are met, so they become an active supplier in the system and I can associate their products with them.

**Acceptance Criteria:**
- "Approve Supplier" button (enabled when checklist complete OR override used)
- Confirmation modal: "This will mark [Company] as an approved supplier."
- Status changes to `APPROVED`, `approved_at` timestamp saved
- Supplier now appears in the Approved Suppliers dropdown when adding products

---

**US-111 — Supplier profile page**
> As a store owner, I want a dedicated profile page for each supplier showing all their info, communication history, approval status, associated products, and payment/terms details.

**Acceptance Criteria:**
- Sections: Contact Info · Communication History · Approval Checklist · Products Supplied · Commercial Terms
- Commercial Terms fields: payment terms (Net 30, etc.), minimum order quantity, lead time (days), return policy, MAP enforcement (yes/no), warranty info
- Edit in-place for all fields
- "View in Shopify" link for associated products

---

## Module 2: Product Management (Enhancements)

**US-201 — Link products to approved suppliers**
> As a store owner, I want to associate each product with its approved supplier, so I can filter products by supplier and track sourcing.

**Acceptance Criteria:**
- "Supplier" field on product form (dropdown of APPROVED suppliers only)
- Products filterable/searchable by supplier in the product list
- Supplier profile shows list of all their associated products with Shopify sync status

---

**US-202 — MAP (Minimum Advertised Price) enforcement alerts**
> As a store owner, I want the system to warn me if I set a product's sale price below the supplier's MAP, so I don't accidentally violate my reseller agreement.

**Acceptance Criteria:**
- MAP price field per product (auto-filled from supplier if set)
- Red warning banner if `sale_price < MAP` when saving a product
- Hard block option (configurable in settings): prevent save vs. warn only
- MAP violations log viewable in supplier profile

---

**US-203 — Cost and margin tracking**
> As a store owner, I want to enter my cost per product and see calculated gross margin, so I know profitability before publishing.

**Acceptance Criteria:**
- Cost field per product (not synced to Shopify)
- Auto-calculated: Gross Margin % = `(sale_price - cost) / sale_price * 100`
- Margin displayed inline in product list as color-coded badge (red < 10%, yellow 10–25%, green > 25%)
- Sortable column in product list

---

**US-204 — Bulk price adjustment tool**
> As a store owner, I want to bulk-adjust prices for a filtered set of products (e.g., increase all products from Supplier X by 5%), so I can respond quickly to cost changes.

**Acceptance Criteria:**
- Select products (multi-select with "select all filtered")
- Adjustment options: set fixed price, set % markup over cost, increase/decrease by % or fixed amount
- Preview table showing old price → new price before applying
- Respects MAP check before applying
- Syncs changes to Shopify

---

**US-205 — Product tags and collections management**
> As a store owner, I want to manage Shopify product tags and collections from the portal, so I can organize my storefront without going to Shopify admin.

**Acceptance Criteria:**
- Tag editor on product detail (add/remove tags, autocomplete existing tags)
- Collections panel: show which collections the product belongs to, add/remove
- Bulk tag: apply/remove tag from all selected products
- Syncs to Shopify

---

## Module 3: Inventory & Order Intelligence

**US-301 — Inventory sync and low-stock alerts**
> As a store owner, I want to see current Shopify inventory levels for each product and set low-stock thresholds, so I can reorder before running out.

**Acceptance Criteria:**
- Inventory quantity pulled from Shopify (refreshable on demand)
- Low-stock threshold configurable per product (or globally)
- Dashboard widget: "X products below threshold"
- Alert badge in product list for low-stock items
- One-click "Contact Supplier" button from low-stock alert → pre-fills email template "Reorder Request"

---

**US-302 — Reorder history log**
> As a store owner, I want to log reorders I've placed with suppliers (PO number, items, quantities, cost, expected delivery), so I can track outstanding orders.

**Acceptance Criteria:**
- "Log Reorder" form linked to approved supplier: PO number, line items (product + qty + unit cost), order date, expected delivery date, status (Pending / Shipped / Received / Cancelled)
- Reorders visible on supplier profile and in a global Reorders list
- Mark as Received updates notes; does NOT auto-update Shopify inventory (manual process, noted in UI)

---

**US-303 — Order analytics dashboard**
> As a store owner, I want a dashboard showing key metrics (revenue, orders, top-selling products, top suppliers by revenue), so I can make informed buying decisions.

**Acceptance Criteria:**
- Date range selector (last 7/30/90 days, custom)
- Metrics cards: Total Revenue, # Orders, Average Order Value, # Products Sold
- Charts: Revenue over time (line), Top 10 Products by Revenue (bar), Revenue by Supplier (pie/donut)
- Data pulled from Shopify Orders API
- Exportable to CSV

---

## Module 4: Reseller Compliance & Documents

**US-401 — Reseller certificate / document vault**
> As a store owner, I want to store reseller certificates, tax exemption forms, and brand authorization letters in a per-supplier document vault, so I can find them instantly during audits or disputes.

**Acceptance Criteria:**
- Document upload per supplier: name, category (Reseller Cert / Authorization Letter / W9 / MAP Agreement / Other), upload date, expiry date (optional)
- Expiry alerts: warn 60 days before expiry, show expired badge
- Download or preview (PDF preview in modal)
- Document count shown on supplier card in list view

---

**US-402 — Generate reseller inquiry letter (AI-assisted)**
> As a store owner, I want to generate a professional reseller inquiry or application letter using AI, based on the supplier's info and my store's details, so I can send polished outreach without writing from scratch.

**Acceptance Criteria:**
- "Generate Letter" button on supplier profile
- Sends supplier name, product category, and my store details to AI endpoint (existing AI integration)
- Returns editable draft in email composer
- Can save as new template

---

## Module 5: Settings & Integrations

**US-501 — Email integration setup**
> As a store owner, I want to configure my outbound email settings (SMTP credentials or Gmail OAuth), so emails sent from the portal come from my own address.

**Acceptance Criteria:**
- Settings page: choose SMTP (host, port, user, password) or Gmail OAuth
- Test connection button sends a test email to myself
- Credentials stored encrypted; never exposed in UI after save
- From name and from email configurable

---

**US-502 — Store settings**
> As a store owner, I want to configure global store settings (store name, owner name, logo, default currency, timezone), so these are used across templates and the dashboard.

**Acceptance Criteria:**
- Settings form with the above fields
- Logo upload (used in header of portal UI)
- Changes save immediately; no page reload required for name/logo

---

**US-503 — Shopify webhook for real-time product sync**
> As a store owner, I want the portal to receive Shopify webhooks for product and order updates, so my local data stays in sync without manual refresh.

**Acceptance Criteria:**
- Backend endpoint to receive `products/update`, `products/delete`, `orders/create` webhooks
- Webhook secret validated (HMAC)
- Portal UI shows "Last synced: X minutes ago" timestamp
- Conflict resolution: Shopify is source of truth for price/inventory; portal is source of truth for cost, supplier, and MAP fields

---

**US-504 — Activity audit log**
> As a store owner, I want a full audit log of actions taken in the portal (product edits, emails sent, supplier status changes, approvals), so I have a record for accountability and troubleshooting.

**Acceptance Criteria:**
- Log table: timestamp, user (if multi-user added later), action type, entity type + ID, description
- Filterable by action type, date range, entity
- Read-only; cannot delete log entries
- Accessible from Settings > Audit Log

---

## Module 6: Dashboard & Navigation

**US-601 — Home dashboard**
> As a store owner, I want a home dashboard that surfaces the most important things needing my attention, so I know exactly what to do when I open the portal.

**Acceptance Criteria:**
Dashboard widgets (collapsible, rearrangeable):
- 🔔 Action Items: overdue follow-ups, expiring documents, low stock alerts, MAP violations
- 📦 Product Health: total products, % synced to Shopify, # with missing cost/MAP
- 🤝 Supplier Pipeline: count by status (LEAD / CONTACTED / NEGOTIATING / APPROVED)
- 📈 Revenue snapshot (last 30 days, from Shopify)
- 📬 Recent Emails: last 5 outbound/inbound emails across all suppliers

---

**US-602 — Global search**
> As a store owner, I want a global search bar that searches across products, suppliers, and emails, so I can quickly find anything without knowing which section it's in.

**Acceptance Criteria:**
- Keyboard shortcut (Cmd/Ctrl+K) opens search modal
- Results grouped by type: Products / Suppliers / Emails
- Click result navigates to detail page
- Searches product title, SKU, supplier name, email subject

---

## Data Model Reference (for Claude Code)

```
Supplier
  id, company_name, contact_name, email, phone, website
  status: LEAD | CONTACTED | NEGOTIATING | APPROVED | REJECTED | INACTIVE
  product_categories: string[]
  payment_terms, min_order_qty, lead_time_days
  return_policy, map_enforced: bool, warranty_info
  follow_up_date, created_at, approved_at, updated_at

SupplierEmail
  id, supplier_id, direction: INBOUND | OUTBOUND
  subject, body, sent_at, attachments: FileRef[]

SupplierDocument
  id, supplier_id, name, category, file_ref
  uploaded_at, expires_at

ApprovalChecklistItem  (global template)
  id, label, order

SupplierChecklistItem  (per supplier)
  id, supplier_id, checklist_item_id
  completed: bool, notes, file_ref

ReorderLog
  id, supplier_id, po_number, order_date
  expected_delivery, status, line_items: JSON
  
Product (extend existing)
  + supplier_id (FK → Supplier)
  + cost_price, map_price

EmailTemplate
  id, name, subject, body

AuditLog
  id, timestamp, action_type, entity_type, entity_id, description
```

---

## Implementation Priority (Suggested Phases)

| Phase | Modules | Why First |
|-------|---------|-----------|
| **1** | Supplier CRUD + Pipeline view (US-101, 102, 111) | Foundation for everything else |
| **2** | Email outreach + threading (US-104–108) | Core requested feature |
| **3** | Approval workflow + document vault (US-109–110, US-401) | Enables product linking |
| **4** | Product enhancements: supplier link, MAP, margins (US-201–203) | Revenue protection |
| **5** | Inventory alerts + reorder log (US-301–302) | Operational efficiency |
| **6** | Dashboard + analytics (US-303, US-601–602) | Visibility layer |
| **7** | Settings, webhooks, audit log (US-501–504) | Polish & production-readiness |

---

## Technical Notes for Claude Code

- **Email sending:** Add `aiosmtplib` (Python) for SMTP; `google-auth-oauthlib` for Gmail OAuth. Store credentials in existing env config pattern.
- **File storage:** Use local filesystem with configurable path for MVP; abstract behind a `StorageService` interface so S3 can be swapped in later.
- **New DB tables:** Use Alembic migrations (add to existing backend). Assume PostgreSQL (from Docker Compose).
- **Frontend routes to add:** `/suppliers`, `/suppliers/:id`, `/suppliers/:id/email`, `/reorders`, `/settings/email`, `/audit-log`
- **AI letter generation:** Use the existing AI enrichment endpoint pattern; add a new prompt template for reseller inquiry letters.
- **Shopify webhooks:** Add a new FastAPI router `webhooks.py`; verify `X-Shopify-Hmac-Sha256` header before processing.
- **MAP enforcement:** Run check in the product save handler (both API and Shopify sync directions).
