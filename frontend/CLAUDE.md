# Frontend Reference

## Pages

| Route | File | Purpose |
|---|---|---|
| `/login` | app/login/page.tsx | Auth — **remove dev credentials before production** |
| `/register` | app/register/page.tsx | Auth |
| `/` | app/page.tsx | Redirect → /products |
| `/products` | app/products/page.tsx | List, filters, pagination, bulk actions, duplicate SKU detection |
| `/products/new` | app/products/new/page.tsx | Manual create |
| `/products/[id]` | app/products/[id]/page.tsx | Detail editor — fields, variants, images, AI suggestions |
| `/products/merge` | app/products/merge/page.tsx | Field-by-field merge UI |
| `/import` | app/import/page.tsx | CSV/PDF/scrape/image upload, job tracking |
| `/enrichment` | app/enrichment/page.tsx | Bulk enrichment — select products, queue, track |
| `/suppliers` | app/suppliers/page.tsx | Supplier list, SRM pipeline filter |
| `/suppliers/[id]` | app/suppliers/[id]/page.tsx | Supplier detail — SRM, scrape config, pricing rules |
| `/suppliers/[id]/emails` | app/suppliers/[id]/emails/page.tsx | Email threads, compose, template insertion |
| `/pricing` | app/pricing/page.tsx | Price alerts + rules + schedules |
| `/sync` | app/sync/page.tsx | Shopify sync status + logs |
| `/templates` | app/templates/page.tsx | Template CRUD — section editor |
| `/templates/[id]/apply` | app/templates/[id]/apply/page.tsx | Select products → apply template |
| `/templates/[id]/review` | app/templates/[id]/review/page.tsx | Review AI output, accept/reject per-product |
| `/reorders` | app/reorders/page.tsx | Global reorder log |
| `/audit-log` | app/audit-log/page.tsx | Audit trail |
| `/settings` | app/settings/page.tsx | Shopify connection, SMTP/IMAP, store settings |

---

## API Client (`src/lib/api.ts`)

```typescript
authApi           — register, login, me
productsApi       — list, get, create, update, delete, bulk, merge,
                    variants.{list,create,update,delete},
                    images.{list,delete,addByUrl,upload},
                    priceHistory, rescrape, syncSupplierPrices, duplicateSkus
enrichmentApi     — enrich(productId, options), bulkEnrich(ids, fields, templateId), status(taskId)
suppliersApi      — list, get, create, update, delete, testScrape, scrapeNow,
                    scrapeStatus, scrapeSessionStatus, scrapeSessionItems,
                    scrapeApprove, suggestSelectors, rescrapeProducts,
                    bulkApplySupplierPrice, scrapeHistory, stats
supplierSrmApi    — updateStatus, listEmails, logEmail, sendEmail,
                    listDocuments, uploadDocument, deleteDocument,
                    getChecklist, addChecklistItem, updateChecklistItem, deleteChecklistItem,
                    listReorders, createReorder, updateReorder, bulkEmail, syncInbox
importsApi        — uploadCsv, uploadPdf, startScrape, uploadImages, jobs, job, suggestColumnMap
pricingApi        — alerts, approveAlert, rejectAlert, bulkApproveAlerts,
                    rules, createRule, updateRule, deleteRule,
                    schedules, createSchedule, updateSchedule, cancelSchedule,
                    calculatePrice, bulkPriceUpdate
templatesApi      — list, create, update, delete, aiFill
emailTemplatesApi — list, create, update, delete
syncApi           — status, syncProduct, syncSelected, syncAll, log, testConnection, pullFromShopify
settingsApi       — getShopify, connectShopify, disconnectShopify
storeSettingsApi  — get, update, testEmail
auditApi          — list
reordersApi       — list
analyticsApi      — orders(days)
supplierImportApi — importCsv
supplierLetterApi — generate(supplierId)
```

---

## Patterns & Constraints

**Node version**: 18.17.0 — `npx shadcn@latest` requires Node 20+. All shadcn/ui components are installed manually into `src/components/ui/`. Never run the CLI.

**shadcn/ui components**: `Button, Card, Input, Label, Select, Badge, Dialog, Tabs, Table, Textarea, Switch, Checkbox, Popover, Command, Separator, Skeleton, Toast` — check `src/components/ui/` before assuming a component exists or needs to be created.

**Data fetching**: TanStack Query v5. Job progress polling uses `refetchInterval` callbacks:
- 3s while a job is active (`status === "running"`)
- 5s when idle

**Auth**: JWT stored in localStorage via `src/lib/auth.ts`. `getToken()` / `isAuthenticated()` — no server-side session.

**Layout**: Wrap pages in `<PageShell title="..." description="..." actions={...}>` from `src/components/layout/PageShell.tsx`.

**AI suggestion review state machine** (template apply/review pages):
- `applied_template_id === id` + status `pending|running` → Processing (blue spinner)
- `applied_template_id === id` + status `done` + `!!ai_description` → Pending review (amber)
- `applied_template_id === id` + status `done` + `!ai_description` → Applied (green — user accepted)
- `applied_template_id === id` + status `failed` → Failed (red)
