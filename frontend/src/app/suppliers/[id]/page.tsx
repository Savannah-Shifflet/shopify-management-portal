"use client";

import { useState, useEffect, useRef } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { suppliersApi, productsApi } from "@/lib/api";
import { PageShell } from "@/components/layout/PageShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Save, Play, Loader2, ArrowLeft, CheckCircle, AlertCircle, Sparkles,
  Check, X, PackageCheck, Package, DollarSign, TrendingUp, Truck,
  ShoppingBag, Phone, Mail, User, Plus, Trash2, RefreshCw, ExternalLink,
} from "lucide-react";
import Link from "next/link";
import { cn, formatPrice, statusColor } from "@/lib/utils";

const SELECTOR_FIELDS = [
  { key: "product_selector", label: "Product Container", placeholder: "article, .product" },
  { key: "title_selector", label: "Title", placeholder: "h2, .product-title" },
  { key: "price_selector", label: "Price", placeholder: ".price, [data-price]" },
  { key: "sku_selector", label: "SKU", placeholder: "[data-sku], .sku" },
  { key: "next_page_selector", label: "Next Page", placeholder: "a[rel='next']" },
  { key: "max_pages", label: "Max Pages", placeholder: "10" },
] as const;

const CATALOG_URL_KEY = "catalog_url";

const REVIEW_FIELDS: { key: string; label: string; sampleKey?: keyof typeof EMPTY_SAMPLE }[] = [
  { key: "product_selector", label: "Product Container" },
  { key: "title_selector",   label: "Title",    sampleKey: "title" },
  { key: "price_selector",   label: "Price",    sampleKey: "price" },
  { key: "sku_selector",     label: "SKU",      sampleKey: "sku" },
  { key: "next_page_selector", label: "Next Page" },
];

const EMPTY_SAMPLE = { title: null as string | null, price: null as string | null, sku: null as string | null };

type Tab = "overview" | "pricing" | "scraping" | "crm" | "products";

type Tone = "neutral" | "green" | "yellow" | "red";

const TONE_STYLES: Record<Tone, { card: string; icon: string; value: string }> = {
  neutral: { card: "bg-white border-gray-200",        icon: "bg-gray-50 text-gray-500",         value: "text-gray-900" },
  green:   { card: "bg-green-50 border-green-200",    icon: "bg-green-100 text-green-600",      value: "text-green-700" },
  yellow:  { card: "bg-amber-50 border-amber-200",    icon: "bg-amber-100 text-amber-600",      value: "text-amber-700" },
  red:     { card: "bg-red-50 border-red-200",        icon: "bg-red-100 text-red-600",          value: "text-red-700" },
};

function StatCard({ icon, label, value, sub, tone = "neutral" }: {
  icon: React.ReactNode; label: string; value: React.ReactNode; sub?: React.ReactNode; tone?: Tone;
}) {
  const s = TONE_STYLES[tone];
  return (
    <div className={`rounded-lg border p-4 flex items-start gap-3 ${s.card}`}>
      <div className={`p-2 rounded-md shrink-0 ${s.icon}`}>{icon}</div>
      <div className="min-w-0">
        <p className="text-xs text-gray-500 mb-0.5">{label}</p>
        <p className={`text-lg font-semibold leading-tight ${s.value}`}>{value}</p>
        {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus-visible:outline-none ${checked ? "bg-blue-600" : "bg-gray-200"}`}
    >
      <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${checked ? "translate-x-4" : "translate-x-0.5"}`} />
      <span className="sr-only">{label}</span>
    </button>
  );
}

export default function SupplierDetailPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("overview");
  const [testResult, setTestResult] = useState<any>(null);
  const [form, setForm] = useState<any>(null);
  const [isDirty, setIsDirty] = useState(false);
  const savedFormRef = useRef<string | null>(null);
  const [pendingReview, setPendingReview] = useState<{ suggestions: any; samples: any[]; notes: string; containerHtml: string; isShopifyJson?: boolean } | null>(null);
  const [showDom, setShowDom] = useState(false);
  const [scrapeActive, setScrapeActive] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [reviewSelected, setReviewSelected] = useState<Set<number>>(new Set());
  const [filterText, setFilterText] = useState("");
  const [createdCount, setCreatedCount] = useState<number | null>(null);
  const [newNoteText, setNewNoteText] = useState("");

  const { data: supplier } = useQuery({
    queryKey: ["supplier", id],
    queryFn: () => suppliersApi.get(id).then((r) => r.data),
  });

  const { data: stats } = useQuery({
    queryKey: ["supplier-stats", id],
    queryFn: () => suppliersApi.stats(id).then((r) => r.data),
    enabled: !!id,
  });

  const { data: scrapeHistory } = useQuery({
    queryKey: ["supplier-scrape-history", id],
    queryFn: () => suppliersApi.scrapeHistory(id).then((r) => r.data),
    enabled: tab === "scraping",
  });

  const [productSearch, setProductSearch] = useState("");
  const { data: supplierProductsData, isLoading: productsLoading } = useQuery({
    queryKey: ["supplier-products", id],
    queryFn: () => productsApi.list({ supplier_id: id, page_size: 200 }).then((r) => r.data),
    enabled: tab === "products",
  });

  useEffect(() => {
    if (supplier && !form) {
      setForm(supplier);
      savedFormRef.current = JSON.stringify(supplier);
    }
  }, [supplier]);

  useEffect(() => {
    if (!form || !savedFormRef.current) return;
    setIsDirty(JSON.stringify(form) !== savedFormRef.current);
  }, [form]);

  const saveMutation = useMutation({
    mutationFn: () => suppliersApi.update(id, form),
    onSuccess: () => {
      savedFormRef.current = JSON.stringify(form);
      setIsDirty(false);
      qc.invalidateQueries({ queryKey: ["supplier", id] });
      qc.invalidateQueries({ queryKey: ["supplier-stats", id] });
    },
  });

  const testMutation = useMutation({
    mutationFn: () => suppliersApi.testScrape(id),
    onSuccess: (res) => setTestResult(res.data),
  });

  const scrapeMutation = useMutation({
    mutationFn: () => suppliersApi.scrapeNow(id),
    onSuccess: (res) => {
      const newSessionId: string = res.data.session_id;
      setActiveSessionId(newSessionId);
      setScrapeActive(true);
    },
  });

  const [rescrapeProductsDone, setRescrapeProductsDone] = useState(false);
  const rescrapeProductsMutation = useMutation({
    mutationFn: () => suppliersApi.rescrapeProducts(id),
    onSuccess: () => {
      setRescrapeProductsDone(true);
      setTimeout(() => setRescrapeProductsDone(false), 3000);
    },
  });

  const { data: currentScrapeData } = useQuery({
    queryKey: ["scrape-session", activeSessionId],
    queryFn: () => suppliersApi.scrapeSessionStatus(id, activeSessionId!).then((r) => r.data),
    enabled: scrapeActive && !!activeSessionId,
    refetchOnWindowFocus: false,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "needs_review" || status === "done" || status === "failed") return false;
      return 2000;
    },
  });

  const sessionId = currentScrapeData?.session_id;

  const { data: reviewData, isFetching: reviewLoading } = useQuery({
    queryKey: ["scrape-items", sessionId],
    queryFn: () => suppliersApi.scrapeSessionItems(id, sessionId!).then((r) => r.data),
    enabled: !!sessionId && reviewOpen,
  });

  const approveMutation = useMutation({
    mutationFn: () => suppliersApi.scrapeApprove(id, sessionId!, Array.from(reviewSelected)),
    onSuccess: (res) => {
      setReviewOpen(false);
      setScrapeActive(false);
      setCreatedCount(res.data.created);
      qc.invalidateQueries({ queryKey: ["scrape-session", activeSessionId] });
      qc.invalidateQueries({ queryKey: ["supplier-stats", id] });
    },
  });

  const [syncPricesDone, setSyncPricesDone] = useState(false);
  const syncPricesMutation = useMutation({
    mutationFn: () => productsApi.syncSupplierPrices(id),
    onSuccess: () => { setSyncPricesDone(true); setTimeout(() => setSyncPricesDone(false), 4000); },
  });

  const [bulkApplyTracking, setBulkApplyTracking] = useState(true);
  const [bulkApplyResult, setBulkApplyResult] = useState<{ updated: number; skipped: number; total: number } | null>(null);
  const bulkApplyMutation = useMutation({
    mutationFn: () => suppliersApi.bulkApplySupplierPrice(id, bulkApplyTracking),
    onSuccess: (res) => {
      setBulkApplyResult(res.data);
      qc.invalidateQueries({ queryKey: ["products"] });
      qc.invalidateQueries({ queryKey: ["supplier-products", id] });
      setTimeout(() => setBulkApplyResult(null), 6000);
    },
  });

  const suggestMutation = useMutation({
    mutationFn: () => suppliersApi.suggestSelectors(id, form.scrape_config?.catalog_url || undefined),
    onSuccess: (res) => {
      const { suggestions, samples, container_html, shopify_json } = res.data;
      if (!suggestions) return;
      setShowDom(false);
      setPendingReview({ suggestions, samples: samples ?? [], notes: suggestions.notes ?? "", containerHtml: container_html ?? "", isShopifyJson: shopify_json === true });
    },
  });

  function applyReview() {
    if (!pendingReview) return;
    if (pendingReview.isShopifyJson) {
      setForm((prev: any) => ({
        ...prev,
        scrape_config: { ...prev.scrape_config, scrape_mode: "shopify_json" },
      }));
    } else {
      const s = pendingReview.suggestions;
      setForm((prev: any) => ({
        ...prev,
        scrape_config: {
          ...prev.scrape_config,
          scrape_mode: "html",
          ...(s.product_selector   && { product_selector: s.product_selector }),
          ...(s.title_selector     && { title_selector: s.title_selector }),
          ...(s.price_selector     && { price_selector: s.price_selector }),
          ...(s.sku_selector       && { sku_selector: s.sku_selector }),
          ...(s.next_page_selector && { next_page_selector: s.next_page_selector }),
        },
      }));
    }
    setPendingReview(null);
  }

  function addCrmNote() {
    const text = newNoteText.trim();
    if (!text) return;
    const note = { text, created_at: new Date().toISOString() };
    const updated = [note, ...(form.crm_notes || [])];
    setForm((prev: any) => ({ ...prev, crm_notes: updated }));
    setNewNoteText("");
  }

  function deleteCrmNote(idx: number) {
    const updated = (form.crm_notes || []).filter((_: any, i: number) => i !== idx);
    setForm((prev: any) => ({ ...prev, crm_notes: updated }));
  }

  if (!form) {
    return <PageShell title="Loading..."><Loader2 className="animate-spin" /></PageShell>;
  }

  const productCount = stats?.product_count ?? supplier?.product_count ?? 0;
  const TABS: { key: Tab; label: string }[] = [
    { key: "overview", label: "Overview" },
    { key: "products", label: `Products${productCount > 0 ? ` (${productCount})` : ""}` },
    { key: "pricing",  label: "Pricing" },
    { key: "scraping", label: "Scraping" },
    { key: "crm",      label: "CRM" },
  ];

  return (
    <PageShell
      title={form.name || "Supplier"}
      description={form.website_url ? (
        <a href={form.website_url} target="_blank" rel="noopener noreferrer" className="text-sm text-blue-600 hover:underline">
          {form.website_url}
        </a>
      ) : undefined}
      actions={
        <div className="flex gap-2">
          <Link href="/suppliers">
            <Button variant="ghost" size="sm"><ArrowLeft className="h-4 w-4 mr-1" />Back</Button>
          </Link>
          <Button size="sm" onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending || !isDirty}>
            {saveMutation.isPending ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Save className="h-4 w-4 mr-1" />}
            {isDirty ? "Save" : "Saved"}
          </Button>
        </div>
      }
    >
      {/* Tab nav */}
      <div className="flex gap-1 border-b border-gray-200 mb-6">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t.key
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ── OVERVIEW TAB ── */}
      {tab === "overview" && (
        <div className="space-y-6">
          {/* KPI cards */}
          {(() => {
            const margin = stats?.avg_margin_pct;
            const marginTone: Tone = margin == null ? "neutral" : margin >= 30 ? "green" : margin >= 15 ? "yellow" : "red";
            const fulfillDays = form.avg_fulfillment_days;
            const fulfillTone: Tone = fulfillDays == null ? "neutral" : fulfillDays <= 3 ? "green" : fulfillDays <= 7 ? "yellow" : "red";
            const fulfillSub = fulfillDays == null ? "not set" : fulfillDays <= 3 ? "fast" : fulfillDays <= 7 ? "standard" : "slow";
            return (
              <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3">
                <StatCard
                  icon={<Package className="h-4 w-4" />}
                  label="Products"
                  value={productCount}
                  sub={<Link href={`/products?supplier=${id}`} className="text-blue-500 hover:underline">View all</Link>}
                  tone={productCount > 0 ? "neutral" : "neutral"}
                />
                <StatCard
                  icon={<DollarSign className="h-4 w-4" />}
                  label="Avg Supplier Price"
                  value={stats?.avg_supplier_price != null ? formatPrice(stats.avg_supplier_price) : "—"}
                  tone="neutral"
                />
                <StatCard
                  icon={<TrendingUp className="h-4 w-4" />}
                  label="Avg Margin"
                  value={margin != null ? `${margin.toFixed(1)}%` : "—"}
                  sub="(retail − cost) ÷ retail"
                  tone={marginTone}
                />
                <StatCard
                  icon={<Truck className="h-4 w-4" />}
                  label="Fulfillment"
                  value={fulfillDays != null ? `${fulfillDays}d` : "—"}
                  sub={fulfillSub}
                  tone={fulfillTone}
                />
                <StatCard
                  icon={<Truck className="h-4 w-4" />}
                  label="Free Shipping"
                  value={form.free_shipping ? "Yes" : "No"}
                  tone={form.free_shipping ? "green" : "red"}
                />
                <StatCard
                  icon={<ShoppingBag className="h-4 w-4" />}
                  label="Google Listings"
                  value={form.google_listings_approved ? "Approved" : "Not approved"}
                  tone={form.google_listings_approved ? "green" : "red"}
                />
              </div>
            );
          })()}

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            {/* Basic info */}
            <Card>
              <CardHeader className="pb-4"><CardTitle className="text-base">Supplier Information</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label>Name</Label>
                  <Input className="mt-1" value={form.name || ""} onChange={(e) => setForm({ ...form, name: e.target.value })} />
                </div>
                <div>
                  <Label>Website URL</Label>
                  <Input className="mt-1" value={form.website_url || ""} onChange={(e) => setForm({ ...form, website_url: e.target.value })} placeholder="https://supplier.com" />
                </div>
                <div>
                  <Label>Notes</Label>
                  <Textarea className="mt-1" rows={3} value={form.notes || ""} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="General notes about this supplier…" />
                </div>
              </CardContent>
            </Card>

            {/* Shipping & listings settings */}
            <Card>
              <CardHeader className="pb-4"><CardTitle className="text-base">Shipping & Listings</CardTitle></CardHeader>
              <CardContent className="space-y-5">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-gray-700">Free Shipping</p>
                      <span className={`text-[11px] font-medium px-1.5 py-0.5 rounded-full ${form.free_shipping ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`}>
                        {form.free_shipping ? "Yes" : "No"}
                      </span>
                    </div>
                    <p className="text-xs text-gray-400">Supplier offers free shipping to you</p>
                  </div>
                  <Toggle checked={!!form.free_shipping} onChange={(v) => setForm({ ...form, free_shipping: v })} label="Free shipping" />
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-gray-700">Google Listings Approved</p>
                      <span className={`text-[11px] font-medium px-1.5 py-0.5 rounded-full ${form.google_listings_approved ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`}>
                        {form.google_listings_approved ? "Approved" : "Not approved"}
                      </span>
                    </div>
                    <p className="text-xs text-gray-400">Supplier permits Google Shopping listings</p>
                  </div>
                  <Toggle checked={!!form.google_listings_approved} onChange={(v) => setForm({ ...form, google_listings_approved: v })} label="Google listings" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <Label>Avg Fulfillment Window (days)</Label>
                    {form.avg_fulfillment_days != null && (
                      <span className={`text-[11px] font-medium px-1.5 py-0.5 rounded-full ${
                        form.avg_fulfillment_days <= 3 ? "bg-green-100 text-green-700"
                        : form.avg_fulfillment_days <= 7 ? "bg-amber-100 text-amber-700"
                        : "bg-red-100 text-red-600"
                      }`}>
                        {form.avg_fulfillment_days <= 3 ? "Fast" : form.avg_fulfillment_days <= 7 ? "Standard" : "Slow"}
                      </span>
                    )}
                  </div>
                  <Input
                    className="mt-1 w-32"
                    type="number"
                    min={0}
                    value={form.avg_fulfillment_days ?? ""}
                    onChange={(e) => setForm({ ...form, avg_fulfillment_days: e.target.value ? Number(e.target.value) : null })}
                    placeholder="e.g. 3"
                  />
                  <p className="text-xs text-gray-400 mt-1">Typical days from order to shipment</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* ── PRICING TAB ── */}
      {tab === "pricing" && (
        <div className="max-w-xl space-y-6">
          <Card>
            <CardHeader className="pb-4"><CardTitle className="text-base">Price Monitoring</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  id="monitor_enabled"
                  checked={form.monitor_enabled}
                  onChange={(e) => setForm({ ...form, monitor_enabled: e.target.checked })}
                  className="rounded"
                />
                <Label htmlFor="monitor_enabled">Enable price monitoring</Label>
              </div>
              <div>
                <Label>Check interval (minutes)</Label>
                <Input
                  className="mt-1 w-32"
                  type="number"
                  value={form.monitor_interval}
                  onChange={(e) => setForm({ ...form, monitor_interval: Number(e.target.value) })}
                />
              </div>
              <div>
                <Label>Auto-approve threshold (%)</Label>
                <Input
                  className="mt-1 w-32"
                  value={form.auto_approve_threshold}
                  onChange={(e) => setForm({ ...form, auto_approve_threshold: e.target.value })}
                  placeholder="0"
                />
                <p className="text-xs text-gray-400 mt-1">
                  Changes below this % are applied automatically. Set to 0 to always require approval.
                </p>
              </div>
              <div className="pt-2 border-t">
                <p className="text-xs text-gray-500 mb-2">
                  Products with "Track supplier price" enabled will auto-sync daily. You can also trigger it manually:
                </p>
                <Button
                  size="sm" variant="outline"
                  onClick={() => syncPricesMutation.mutate()}
                  disabled={syncPricesMutation.isPending || syncPricesDone}
                >
                  {syncPricesMutation.isPending
                    ? <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                    : syncPricesDone
                    ? <CheckCircle className="h-4 w-4 mr-1 text-green-600" />
                    : <Play className="h-4 w-4 mr-1" />}
                  {syncPricesDone ? "Queued!" : "Sync prices with supplier"}
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Bulk price sync card */}
          <Card>
            <CardHeader className="pb-4"><CardTitle className="text-base">Bulk Price Sync</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-gray-600">
                Set the retail price for <strong>all products from this supplier</strong> to match
                their current scraped supplier price in one click.
              </p>
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={bulkApplyTracking}
                  onChange={(e) => setBulkApplyTracking(e.target.checked)}
                  className="rounded"
                />
                <span className="text-sm text-gray-700">
                  Also enable <strong>auto-sync</strong> — future price changes will automatically update retail price
                </span>
              </label>

              <div className="flex items-center gap-3 pt-1">
                <Button
                  size="sm"
                  onClick={() => bulkApplyMutation.mutate()}
                  disabled={bulkApplyMutation.isPending}
                >
                  {bulkApplyMutation.isPending
                    ? <><Loader2 className="h-4 w-4 mr-1 animate-spin" /> Applying…</>
                    : <><DollarSign className="h-4 w-4 mr-1" /> Apply supplier prices to all products</>}
                </Button>
              </div>

              {bulkApplyResult && (
                <div className="flex items-start gap-2 p-3 rounded-lg bg-green-50 border border-green-200 text-sm text-green-800">
                  <CheckCircle className="h-4 w-4 shrink-0 mt-0.5 text-green-600" />
                  <span>
                    Updated <strong>{bulkApplyResult.updated}</strong> of{" "}
                    <strong>{bulkApplyResult.total}</strong> products.
                    {bulkApplyResult.skipped > 0 && (
                      <> {bulkApplyResult.skipped} skipped (no supplier price recorded).</>
                    )}
                    {bulkApplyTracking && <> Auto-sync enabled for updated products.</>}
                  </span>
                </div>
              )}

              {bulkApplyMutation.isError && (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  {(bulkApplyMutation.error as any)?.response?.data?.detail ?? "Failed to apply prices."}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* ── SCRAPING TAB ── */}
      {tab === "scraping" && (
        <div className="space-y-6">
          <Card>
            <CardHeader className="pb-4">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">Scrape Configuration</CardTitle>
                <div className="flex gap-2">
                  <Button
                    size="sm" variant="outline"
                    onClick={() => { setPendingReview(null); suggestMutation.mutate(); }}
                    disabled={suggestMutation.isPending || !form.website_url}
                    title={!form.website_url ? "Set a Website URL first" : undefined}
                  >
                    {suggestMutation.isPending ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Sparkles className="h-4 w-4 mr-1" />}
                    {suggestMutation.isPending ? "Detecting…" : "Auto-Detect Selectors"}
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => testMutation.mutate()} disabled={testMutation.isPending}>
                    {testMutation.isPending ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Play className="h-4 w-4 mr-1" />}
                    Test Scrape
                  </Button>
                  <Button
                    size="sm" variant="outline"
                    onClick={() => { setScrapeActive(false); setActiveSessionId(null); scrapeMutation.mutate(); }}
                    disabled={scrapeMutation.isPending}
                  >
                    {scrapeMutation.isPending ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Play className="h-4 w-4 mr-1" />}
                    Scrape Now
                  </Button>
                  <Button
                    size="sm" variant="outline"
                    onClick={() => rescrapeProductsMutation.mutate()}
                    disabled={rescrapeProductsMutation.isPending || rescrapeProductsDone}
                    title="Re-fetch description and images for all existing products from this supplier"
                  >
                    {rescrapeProductsMutation.isPending
                      ? <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                      : <RefreshCw className="h-4 w-4 mr-1" />}
                    {rescrapeProductsDone ? "Queued!" : "Re-scrape Products"}
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {scrapeMutation.isError && (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  {(scrapeMutation.error as any)?.response?.data?.detail ?? "Failed to queue scrape"}
                </div>
              )}
              {createdCount !== null && (
                <div className="flex items-start gap-3 p-4 rounded-lg bg-green-50 border border-green-200">
                  <PackageCheck className="h-4 w-4 text-green-600 shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-green-800">
                      {createdCount} product{createdCount !== 1 ? "s" : ""} created
                    </p>
                    <p className="text-xs text-green-700 mt-0.5">
                      Descriptions and images are being fetched in the background.
                    </p>
                    <Link href={`/products?supplier=${id}`} className="text-xs text-green-700 underline underline-offset-2 hover:text-green-900 mt-1 inline-block">
                      View products →
                    </Link>
                  </div>
                  <button type="button" className="text-green-400 hover:text-green-600 shrink-0" onClick={() => setCreatedCount(null)}>
                    <X className="h-4 w-4" />
                  </button>
                </div>
              )}
              {(scrapeMutation.isPending || (scrapeActive && !currentScrapeData)) && (
                <div className="flex items-center gap-2 p-4 rounded-lg bg-blue-50 border border-blue-200">
                  <Loader2 className="h-4 w-4 text-blue-500 animate-spin shrink-0" />
                  <p className="text-sm text-blue-800 font-medium">Starting scrape…</p>
                </div>
              )}
              {scrapeActive && currentScrapeData && (() => {
                const s = currentScrapeData;
                const running = s.status === "running" || s.status === "queued";
                const needsReview = s.status === "needs_review";
                const done = s.status === "done";
                const failed = s.status === "failed";
                const items: any[] = reviewData?.items ?? [];
                const filtered = filterText
                  ? items.filter((it) => it.title?.toLowerCase().includes(filterText.toLowerCase()))
                  : items;
                return (
                  <div className={`rounded-lg border ${done ? "bg-green-50 border-green-200" : failed ? "bg-red-50 border-red-200" : needsReview ? "bg-amber-50 border-amber-200" : "bg-blue-50 border-blue-200"}`}>
                    <div className="flex items-center gap-2 p-4">
                      {running && <Loader2 className="h-4 w-4 text-blue-500 animate-spin shrink-0" />}
                      {needsReview && <AlertCircle className="h-4 w-4 text-amber-500 shrink-0" />}
                      {done && <CheckCircle className="h-4 w-4 text-green-600 shrink-0" />}
                      {failed && <AlertCircle className="h-4 w-4 text-red-600 shrink-0" />}
                      <div className="flex-1">
                        <p className={`font-medium text-sm ${done ? "text-green-700" : failed ? "text-red-700" : needsReview ? "text-amber-800" : "text-blue-800"}`}>
                          {running && (s.status === "queued" ? "Scrape queued — waiting for worker…" : "Scraping in progress…")}
                          {needsReview && `Ready to review — ${s.products_found} items found after filtering`}
                          {done && `Done — ${s.products_found} products created`}
                          {failed && `Scrape failed: ${s.error ?? "unknown error"}`}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 ml-auto shrink-0">
                        {needsReview && (
                          <Button size="sm" className="h-7 text-xs bg-amber-600 hover:bg-amber-700 text-white"
                            onClick={() => {
                              setReviewOpen((v) => !v);
                              if (!reviewOpen) {
                                const all = new Set(Array.from({ length: s.products_found }, (_, i) => i));
                                setReviewSelected(all);
                              }
                            }}>
                            {reviewOpen ? "Hide Review" : `Review ${s.products_found} Items`}
                          </Button>
                        )}
                        {(done || failed) && (
                          <button type="button" className="text-xs text-gray-400 hover:text-gray-600" onClick={() => setScrapeActive(false)}>Dismiss</button>
                        )}
                      </div>
                    </div>
                    {running && (
                      <div className="flex gap-6 px-4 pb-4">
                        <div>
                          <p className="text-xs text-gray-500 mb-0.5">Pages scraped</p>
                          <p className="text-2xl font-bold tabular-nums text-blue-700">{s.pages_scraped}</p>
                        </div>
                        <div>
                          <p className="text-xs text-gray-500 mb-0.5">Items found</p>
                          <p className="text-2xl font-bold tabular-nums text-blue-700">{s.products_found}</p>
                        </div>
                      </div>
                    )}
                    {needsReview && reviewOpen && (
                      <div className="border-t border-amber-200 px-4 pb-4 pt-3 space-y-3">
                        <div className="flex items-center gap-2">
                          <Input className="h-7 text-xs flex-1" placeholder="Filter by title…" value={filterText} onChange={(e) => setFilterText(e.target.value)} />
                          <button type="button" className="text-xs text-blue-600 hover:underline whitespace-nowrap"
                            onClick={() => setReviewSelected(new Set(filtered.map((_: any, i: number) => items.indexOf(_))))}>
                            Select all ({filtered.length})
                          </button>
                          <button type="button" className="text-xs text-gray-500 hover:underline whitespace-nowrap"
                            onClick={() => setReviewSelected(new Set())}>None</button>
                        </div>
                        {reviewLoading ? (
                          <div className="flex items-center gap-2 text-sm text-gray-500 py-4">
                            <Loader2 className="h-4 w-4 animate-spin" /> Loading items…
                          </div>
                        ) : (
                          <div className="rounded border border-amber-200 overflow-auto max-h-96 bg-white">
                            <table className="w-full text-xs">
                              <thead className="bg-amber-50 sticky top-0">
                                <tr>
                                  <th className="w-8 px-2 py-2"></th>
                                  <th className="text-left px-3 py-2 font-medium text-gray-700">Title</th>
                                  <th className="text-left px-3 py-2 font-medium text-gray-700 w-28">Price</th>
                                  <th className="text-left px-3 py-2 font-medium text-gray-700 w-24">SKU</th>
                                </tr>
                              </thead>
                              <tbody>
                                {filtered.map((item: any) => {
                                  const realIdx = items.indexOf(item);
                                  const checked = reviewSelected.has(realIdx);
                                  return (
                                    <tr key={realIdx} className={`border-t border-amber-50 cursor-pointer ${checked ? "bg-blue-50" : "hover:bg-gray-50"}`}
                                      onClick={() => setReviewSelected((prev) => {
                                        const next = new Set(prev);
                                        checked ? next.delete(realIdx) : next.add(realIdx);
                                        return next;
                                      })}>
                                      <td className="px-2 py-1.5 text-center"><input type="checkbox" readOnly checked={checked} className="pointer-events-none" /></td>
                                      <td className="px-3 py-1.5 text-gray-800 font-medium max-w-xs truncate">{item.title}</td>
                                      <td className="px-3 py-1.5 text-green-700">{item.price || <span className="text-gray-300 italic">—</span>}</td>
                                      <td className="px-3 py-1.5 text-gray-500">{item.sku || <span className="text-gray-300 italic">—</span>}</td>
                                    </tr>
                                  );
                                })}
                                {filtered.length === 0 && (
                                  <tr><td colSpan={4} className="px-3 py-4 text-center text-gray-400 italic">No items match the filter</td></tr>
                                )}
                              </tbody>
                            </table>
                          </div>
                        )}
                        <div className="flex items-center justify-between pt-1">
                          <p className="text-xs text-gray-500">{reviewSelected.size} of {items.length} selected</p>
                          <Button size="sm" className="h-7 text-xs bg-green-600 hover:bg-green-700 text-white"
                            disabled={reviewSelected.size === 0 || approveMutation.isPending}
                            onClick={() => approveMutation.mutate()}>
                            {approveMutation.isPending ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <CheckCircle className="h-3 w-3 mr-1" />}
                            Create {reviewSelected.size} Product{reviewSelected.size !== 1 ? "s" : ""}
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })()}

              <div>
                <Label className="text-xs">Catalog / Product Listing URL</Label>
                <Input
                  className="mt-1"
                  value={form.scrape_config?.[CATALOG_URL_KEY] || ""}
                  onChange={(e) => setForm({ ...form, scrape_config: { ...form.scrape_config, [CATALOG_URL_KEY]: e.target.value } })}
                  placeholder={form.website_url ? `${form.website_url}/products` : "https://supplier.com/products"}
                />
                <p className="text-xs text-gray-400 mt-1">
                  URL listing multiple products (e.g. <code className="bg-gray-100 px-1 rounded">/shop</code>). Falls back to Website URL if blank.
                </p>
              </div>

              {suggestMutation.isError && (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  {(suggestMutation.error as any)?.response?.data?.detail ?? "Auto-detect failed"}
                </div>
              )}

              {pendingReview && (
                <div className="rounded-lg border border-blue-200 bg-blue-50 overflow-hidden">
                  <div className="flex items-center justify-between px-4 py-3 border-b border-blue-200">
                    <div className="flex items-center gap-2">
                      <Sparkles className="h-4 w-4 text-blue-500" />
                      <p className="font-medium text-sm text-blue-900">
                        {pendingReview.isShopifyJson ? "Shopify Store Detected" : "Review Detected Selectors"}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline" className="h-7 text-xs border-blue-300 text-blue-700 hover:bg-blue-100" onClick={() => setPendingReview(null)}>
                        <X className="h-3 w-3 mr-1" />Dismiss
                      </Button>
                      <Button size="sm" className="h-7 text-xs bg-blue-600 hover:bg-blue-700 text-white" onClick={applyReview}>
                        <Check className="h-3 w-3 mr-1" />
                        {pendingReview.isShopifyJson ? "Use Shopify JSON API" : "Apply Selectors"}
                      </Button>
                    </div>
                  </div>
                  <div className="px-4 py-3">
                    <p className="text-xs text-blue-700 mb-3">{pendingReview.notes}</p>
                    {!pendingReview.isShopifyJson && (
                      <div className="rounded border border-blue-200 overflow-hidden text-xs mb-3">
                        <table className="w-full">
                          <thead>
                            <tr className="bg-blue-100 text-blue-800">
                              <th className="text-left px-3 py-2 font-medium w-36">Field</th>
                              <th className="text-left px-3 py-2 font-medium">Detected Selector</th>
                            </tr>
                          </thead>
                          <tbody>
                            {REVIEW_FIELDS.map(({ key, label }) => {
                              const val = pendingReview.suggestions[key];
                              return (
                                <tr key={key} className="border-t border-blue-100 bg-white">
                                  <td className="px-3 py-2 text-gray-500 font-medium">{label}</td>
                                  <td className="px-3 py-2">
                                    {val ? <code className="bg-gray-100 px-1.5 py-0.5 rounded text-gray-800">{val}</code> : <span className="text-gray-400 italic">not detected</span>}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    )}
                    {pendingReview.samples.length > 0 && (
                      <>
                        <p className="text-xs font-medium text-blue-800 mb-2">Sample products from JSON API:</p>
                        <div className="space-y-1.5">
                          {pendingReview.samples.map((s: any, i: number) => (
                            <div key={i} className="bg-white rounded border border-blue-100 px-3 py-2 text-xs">
                              <span className="text-gray-400 font-medium mr-2">#{i + 1}</span>
                              {s.title && <span className="mr-3"><span className="text-gray-400">Title:</span> <span className="text-gray-800">{s.title}</span></span>}
                              {s.price && <span className="mr-3"><span className="text-gray-400">Price:</span> <span className="text-green-700 font-medium">{s.price}</span></span>}
                              {s.sku && <span><span className="text-gray-400">SKU:</span> <span className="text-gray-800">{s.sku}</span></span>}
                              {!s.title && !s.price && !s.sku && <span className="text-gray-400 italic">No data extracted</span>}
                            </div>
                          ))}
                        </div>
                      </>
                    )}
                    {pendingReview.containerHtml && (
                      <div className="mt-3">
                        <button type="button" className="text-xs text-blue-700 underline underline-offset-2 hover:text-blue-900" onClick={() => setShowDom((v) => !v)}>
                          {showDom ? "Hide" : "Show"} first container DOM
                        </button>
                        {showDom && (
                          <pre className="mt-2 bg-gray-900 text-gray-100 text-[11px] leading-relaxed rounded p-3 overflow-auto max-h-80 whitespace-pre-wrap break-all">
                            {pendingReview.containerHtml}
                          </pre>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {form.scrape_config?.scrape_mode === "shopify_json" ? (
                <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-green-800 bg-green-100 border border-green-200 rounded-full px-2.5 py-1">
                      <span className="h-1.5 w-1.5 rounded-full bg-green-500 inline-block" />
                      Shopify JSON API
                    </span>
                    <p className="text-xs text-green-700">Products are fetched directly via the Shopify API — no HTML selectors needed.</p>
                  </div>
                  <Button
                    size="sm" variant="outline"
                    className="h-7 text-xs border-gray-300 text-gray-500 hover:bg-gray-100 shrink-0 ml-4"
                    onClick={() => setForm((prev: any) => ({ ...prev, scrape_config: { ...prev.scrape_config, scrape_mode: "html" } }))}
                  >
                    Switch to HTML mode
                  </Button>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-4">
                  {SELECTOR_FIELDS.map(({ key, label, placeholder }) => (
                    <div key={key}>
                      <Label className="text-xs">{label}</Label>
                      <Input
                        className="mt-1 font-mono text-xs"
                        value={form.scrape_config?.[key] || ""}
                        onChange={(e) => setForm({ ...form, scrape_config: { ...form.scrape_config, [key]: e.target.value } })}
                        placeholder={placeholder}
                      />
                    </div>
                  ))}
                </div>
              )}

              {testResult && (
                <div className={`p-4 rounded-lg border mt-2 ${testResult.success ? "bg-green-50 border-green-200" : "bg-red-50 border-red-200"}`}>
                  <div className="flex items-center gap-2 mb-3">
                    {testResult.success ? <CheckCircle className="h-4 w-4 text-green-600" /> : <AlertCircle className="h-4 w-4 text-red-600" />}
                    <p className={`font-medium text-sm ${testResult.success ? "text-green-700" : "text-red-700"}`}>
                      {testResult.success ? `Found ${testResult.products?.length} products` : `Error: ${testResult.error}`}
                    </p>
                  </div>
                  {testResult.products?.map((p: any, i: number) => (
                    <div key={i} className="text-xs bg-white rounded p-2 mb-1 border">
                      <p className="font-medium">{p.title || "No title"}</p>
                      <p className="text-gray-500">{p.price || "No price"}</p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* ── Scrape History ── */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Scrape History</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6 pt-0">
              {/* Catalog pulls */}
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Catalog Pulls (product list)</p>
                {!scrapeHistory || scrapeHistory.catalog_scrapes.length === 0 ? (
                  <p className="text-sm text-gray-400 italic">No catalog scrapes yet.</p>
                ) : (
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-gray-50 text-xs text-gray-500">
                        <th className="text-left px-3 py-2 font-medium">Date</th>
                        <th className="text-left px-3 py-2 font-medium">URL</th>
                        <th className="text-right px-3 py-2 font-medium">Items</th>
                        <th className="text-right px-3 py-2 font-medium">Pages</th>
                        <th className="text-left px-3 py-2 font-medium">Status</th>
                        <th className="text-right px-3 py-2 font-medium">Duration</th>
                      </tr>
                    </thead>
                    <tbody>
                      {scrapeHistory.catalog_scrapes.map((s: any) => {
                        const started = s.started_at ? new Date(s.started_at) : null;
                        const completed = s.completed_at ? new Date(s.completed_at) : null;
                        const durationSec = started && completed
                          ? Math.round((completed.getTime() - started.getTime()) / 1000)
                          : null;
                        const statusStyle =
                          s.status === "done" || s.status === "needs_review" ? "text-green-700 bg-green-50"
                          : s.status === "running" || s.status === "queued" ? "text-blue-700 bg-blue-50"
                          : "text-red-700 bg-red-50";
                        return (
                          <tr key={s.id} className="border-b last:border-0 hover:bg-gray-50">
                            <td className="px-3 py-2 text-gray-600 whitespace-nowrap">
                              {started ? started.toLocaleString() : "—"}
                            </td>
                            <td className="px-3 py-2 text-gray-500 max-w-[200px] truncate" title={s.url}>
                              {s.url ? s.url.replace(/^https?:\/\//, "").slice(0, 40) : "—"}
                            </td>
                            <td className="px-3 py-2 text-right font-medium tabular-nums">
                              {s.products_found ?? 0}
                            </td>
                            <td className="px-3 py-2 text-right tabular-nums text-gray-500">
                              {s.pages_scraped ?? 0}
                            </td>
                            <td className="px-3 py-2">
                              <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusStyle}`}>
                                {s.status}
                              </span>
                              {s.error && (
                                <span className="ml-2 text-xs text-red-500 truncate" title={s.error}>
                                  {s.error.slice(0, 40)}
                                </span>
                              )}
                            </td>
                            <td className="px-3 py-2 text-right text-gray-500 tabular-nums whitespace-nowrap">
                              {durationSec != null ? `${durationSec}s` : "—"}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>

              {/* Detail pulls */}
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Detail Pulls (descriptions &amp; images)</p>
                {!scrapeHistory || scrapeHistory.detail_scrapes.length === 0 ? (
                  <p className="text-sm text-gray-400 italic">No detail scrapes yet.</p>
                ) : (
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-gray-50 text-xs text-gray-500">
                        <th className="text-left px-3 py-2 font-medium">Date</th>
                        <th className="text-left px-3 py-2 font-medium">Triggered by</th>
                        <th className="text-right px-3 py-2 font-medium">Items</th>
                      </tr>
                    </thead>
                    <tbody>
                      {scrapeHistory.detail_scrapes.map((d: any) => (
                        <tr key={d.id} className="border-b last:border-0 hover:bg-gray-50">
                          <td className="px-3 py-2 text-gray-600 whitespace-nowrap">
                            {d.created_at ? new Date(d.created_at).toLocaleString() : "—"}
                          </td>
                          <td className="px-3 py-2">
                            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${d.triggered_by === "approval" ? "bg-purple-50 text-purple-700" : "bg-blue-50 text-blue-700"}`}>
                              {d.triggered_by === "approval" ? "Catalog approval" : "Manual re-scrape"}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-right font-medium tabular-nums">{d.item_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* ── CRM TAB ── */}
      {/* ── PRODUCTS TAB ── */}
      {tab === "products" && (
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between gap-3">
                <CardTitle className="text-base">Products</CardTitle>
                <div className="flex items-center gap-2">
                  <div className="relative">
                    <input
                      type="text"
                      placeholder="Search products…"
                      value={productSearch}
                      onChange={(e) => setProductSearch(e.target.value)}
                      className="h-8 pl-3 pr-3 text-xs rounded-md border border-gray-200 bg-white focus:outline-none focus:ring-1 focus:ring-blue-400 w-48"
                    />
                  </div>
                  <Link href={`/products?supplier=${id}`}>
                    <Button size="sm" variant="outline" className="h-8 text-xs">Open in Products</Button>
                  </Link>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {productsLoading ? (
                <div className="p-8 text-center text-gray-400"><Loader2 className="h-5 w-5 animate-spin mx-auto" /></div>
              ) : (() => {
                const allItems: any[] = supplierProductsData?.items ?? [];
                const items = productSearch.trim()
                  ? allItems.filter((p: any) => p.title?.toLowerCase().includes(productSearch.toLowerCase()))
                  : allItems;
                if (allItems.length === 0) {
                  return (
                    <div className="p-12 text-center">
                      <Package className="h-10 w-10 mx-auto text-gray-300 mb-3" />
                      <p className="text-gray-500 font-medium">No products yet</p>
                      <p className="text-sm text-gray-400 mt-1">Scrape the catalog or import products to get started</p>
                    </div>
                  );
                }
                return (
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-gray-50">
                        <th className="text-left px-4 py-3 font-medium text-gray-600">Product</th>
                        <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
                        <th className="text-left px-4 py-3 font-medium text-gray-600">Enrichment</th>
                        <th className="text-left px-4 py-3 font-medium text-gray-600">Supplier Price</th>
                        <th className="text-left px-4 py-3 font-medium text-gray-600">Retail Price</th>
                        <th className="text-left px-4 py-3 font-medium text-gray-600">Sync</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((p: any) => (
                        <tr key={p.id} className="border-b last:border-0 hover:bg-gray-50">
                          <td className="px-4 py-3 max-w-xs">
                            <Link href={`/products/${p.id}`} className="font-medium text-gray-900 hover:text-blue-600 truncate block">
                              {p.title}
                            </Link>
                            {p.source_url && (
                              <a href={p.source_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-xs text-gray-400 hover:text-blue-500 mt-0.5 truncate">
                                <ExternalLink className="h-3 w-3 flex-shrink-0" />{p.source_url.replace(/^https?:\/\//, "").slice(0, 50)}
                              </a>
                            )}
                          </td>
                          <td className="px-4 py-3">
                            <span className={cn("px-2 py-0.5 rounded-full text-xs font-medium capitalize", statusColor(p.status))}>
                              {p.status}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className={cn("px-2 py-0.5 rounded-full text-xs font-medium", statusColor(p.enrichment_status))}>
                              {p.enrichment_status}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-gray-700">{p.supplier_price != null ? formatPrice(p.supplier_price) : <span className="text-gray-300">—</span>}</td>
                          <td className="px-4 py-3 text-gray-700">{p.base_price != null ? formatPrice(p.base_price) : <span className="text-gray-300">—</span>}</td>
                          <td className="px-4 py-3">
                            <span className={cn("px-2 py-0.5 rounded-full text-xs font-medium", statusColor(p.sync_status))}>
                              {p.sync_status?.replace(/_/g, " ")}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                );
              })()}
            </CardContent>
          </Card>
        </div>
      )}

      {tab === "crm" && (
        <div className="space-y-6">
          {/* Contacts */}
          <Card>
            <CardHeader className="pb-4">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">Contacts</CardTitle>
                <Button
                  size="sm" variant="outline"
                  onClick={() => setForm((prev: any) => ({
                    ...prev,
                    contacts: [...(prev.contacts || []), { name: "", email: "", phone: "", role: "" }],
                  }))}
                >
                  <Plus className="h-3.5 w-3.5 mr-1" />Add Contact
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {(form.contacts || []).length === 0 && (
                <p className="text-sm text-gray-400 italic py-4 text-center">No contacts yet. Click "Add Contact" to add one.</p>
              )}
              <div className="space-y-4">
                {(form.contacts || []).map((c: any, i: number) => {
                  function setContact(field: string, value: string) {
                    setForm((prev: any) => {
                      const updated = [...(prev.contacts || [])];
                      updated[i] = { ...updated[i], [field]: value };
                      return { ...prev, contacts: updated };
                    });
                  }
                  function removeContact() {
                    setForm((prev: any) => ({
                      ...prev,
                      contacts: (prev.contacts || []).filter((_: any, idx: number) => idx !== i),
                    }));
                  }
                  return (
                    <div key={i} className="rounded-lg border border-gray-200 p-4 space-y-3 relative">
                      <button
                        type="button"
                        className="absolute top-3 right-3 text-gray-300 hover:text-red-500 transition-colors"
                        onClick={removeContact}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pr-6">
                        <div>
                          <Label className="flex items-center gap-1.5 text-xs"><User className="h-3 w-3 text-gray-400" />Name</Label>
                          <Input className="mt-1 h-8 text-sm" value={c.name || ""} onChange={(e) => setContact("name", e.target.value)} placeholder="Jane Smith" />
                        </div>
                        <div>
                          <Label className="text-xs">Role / Title</Label>
                          <Input className="mt-1 h-8 text-sm" value={c.role || ""} onChange={(e) => setContact("role", e.target.value)} placeholder="Account Manager" />
                        </div>
                        <div>
                          <Label className="flex items-center gap-1.5 text-xs"><Mail className="h-3 w-3 text-gray-400" />Email</Label>
                          <Input className="mt-1 h-8 text-sm" type="email" value={c.email || ""} onChange={(e) => setContact("email", e.target.value)} placeholder="jane@supplier.com" />
                        </div>
                        <div>
                          <Label className="flex items-center gap-1.5 text-xs"><Phone className="h-3 w-3 text-gray-400" />Phone</Label>
                          <Input className="mt-1 h-8 text-sm" type="tel" value={c.phone || ""} onChange={(e) => setContact("phone", e.target.value)} placeholder="+1 555 000 0000" />
                        </div>
                      </div>
                      {(c.email || c.phone) && (
                        <div className="flex gap-3 pt-1 border-t border-gray-100">
                          {c.email && (
                            <a href={`mailto:${c.email}`} className="text-xs text-blue-600 hover:underline flex items-center gap-1">
                              <Mail className="h-3 w-3" /> Email
                            </a>
                          )}
                          {c.phone && (
                            <a href={`tel:${c.phone}`} className="text-xs text-blue-600 hover:underline flex items-center gap-1">
                              <Phone className="h-3 w-3" /> Call
                            </a>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          {/* Notes log */}
          <Card>
            <CardHeader className="pb-4"><CardTitle className="text-base">Activity & Notes</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Textarea
                  rows={2}
                  className="flex-1 resize-none"
                  placeholder="Log a call, note, or update…"
                  value={newNoteText}
                  onChange={(e) => setNewNoteText(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); addCrmNote(); } }}
                />
                <Button size="sm" className="self-end" onClick={addCrmNote} disabled={!newNoteText.trim()}>
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              <p className="text-xs text-gray-400">Press Ctrl+Enter to add quickly. Notes are saved when you click Save.</p>
              <div className="space-y-2 max-h-96 overflow-auto pr-1">
                {(form.crm_notes || []).length === 0 && (
                  <p className="text-xs text-gray-400 italic py-4 text-center">No notes yet. Log your first interaction above.</p>
                )}
                {(form.crm_notes || []).map((note: any, i: number) => (
                  <div key={i} className="group flex gap-2 p-3 rounded-lg border border-gray-100 bg-gray-50 text-sm">
                    <div className="flex-1 min-w-0">
                      <p className="text-gray-800 whitespace-pre-wrap">{note.text}</p>
                      <p className="text-xs text-gray-400 mt-1">{new Date(note.created_at).toLocaleString()}</p>
                    </div>
                    <button
                      type="button"
                      className="text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity shrink-0 mt-0.5"
                      onClick={() => deleteCrmNote(i)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </PageShell>
  );
}
