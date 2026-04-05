"use client";

import { useState, useMemo, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { templatesApi, productsApi, enrichmentApi } from "@/lib/api";
import { PageShell } from "@/components/layout/PageShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Sparkles, Package, Search, Loader2, ArrowLeft, Check, X, CheckCircle2, AlertCircle } from "lucide-react";
import Link from "next/link";
import { cn, statusColor } from "@/lib/utils";

const STATUS_OPTIONS = ["draft", "active", "archived"];
const ENRICHMENT_OPTIONS = ["not_started", "pending", "running", "done", "failed"];
// template filter virtual values: "applied" | "other" | "none"

function toggleSet(prev: Set<string>, value: string): Set<string> {
  const next = new Set(prev);
  next.has(value) ? next.delete(value) : next.add(value);
  return next;
}

export default function ApplyTemplatePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilters, setStatusFilters] = useState<Set<string>>(new Set());
  const [enrichmentFilters, setEnrichmentFilters] = useState<Set<string>>(new Set());
  const [templateFilters, setTemplateFilters] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [showConfirm, setShowConfirm] = useState(false);

  const { data: template, isLoading: templateLoading } = useQuery({
    queryKey: ["template", id],
    queryFn: () => templatesApi.list().then((r) => {
      const templates = r.data as { id: string; name: string; sections: any[] }[];
      return templates.find((t) => t.id === id) ?? null;
    }),
  });

  const { data: productsData, isLoading: productsLoading } = useQuery({
    queryKey: ["products-apply-template-all"],
    queryFn: () => productsApi.list({ page: 1, page_size: 10000 }).then((r) => r.data),
    refetchOnMount: "always",
    refetchInterval: (query) => {
      const items: any[] = query.state.data?.items ?? [];
      const anyProcessing = items.some(
        (p: any) => p.applied_template_id === id && (p.enrichment_status === "pending" || p.enrichment_status === "running")
      );
      return anyProcessing ? 3000 : false;
    },
  });

  const applyMutation = useMutation({
    mutationFn: () => enrichmentApi.bulkEnrich([...selected], ["body_html"], id),
    onSuccess: () => {
      // Remove stale cache so the review page always starts with a fresh fetch
      qc.removeQueries({ queryKey: ["products-review", id] });
      router.push(`/templates/${id}/review`);
    },
  });

  const allItems: any[] = productsData?.items ?? [];

  // Counts (unfiltered so chips always show real numbers)
  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const p of allItems) counts[p.status] = (counts[p.status] ?? 0) + 1;
    return counts;
  }, [allItems]);

  const enrichmentCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const p of allItems) counts[p.enrichment_status] = (counts[p.enrichment_status] ?? 0) + 1;
    return counts;
  }, [allItems]);

  const templateCounts = useMemo(() => {
    const isProcessing = (p: any) => p.applied_template_id === id && (p.enrichment_status === "pending" || p.enrichment_status === "running");
    const isPending = (p: any) => p.applied_template_id === id && p.enrichment_status === "done" && !!p.ai_description;
    const isApplied = (p: any) => p.applied_template_id === id && p.enrichment_status === "done" && !p.ai_description;
    const isFailed = (p: any) => p.applied_template_id === id && p.enrichment_status === "failed";
    return {
      processing: allItems.filter(isProcessing).length,
      pending: allItems.filter(isPending).length,
      applied: allItems.filter(isApplied).length,
      failed: allItems.filter(isFailed).length,
      other: allItems.filter((p: any) => p.applied_template_id && p.applied_template_id !== id).length,
      none: allItems.filter((p: any) => !p.applied_template_id).length,
    };
  }, [allItems, id]);

  const filtered = useMemo(() => {
    return allItems.filter((p: any) => {
      const matchSearch = !search.trim() ||
        p.title.toLowerCase().includes(search.toLowerCase()) ||
        (p.vendor ?? "").toLowerCase().includes(search.toLowerCase());
      const matchStatus = statusFilters.size === 0 || statusFilters.has(p.status);
      const matchEnrichment = enrichmentFilters.size === 0 || enrichmentFilters.has(p.enrichment_status);
      const matchTemplate =
        templateFilters.size === 0 || (
          (templateFilters.has("processing") && p.applied_template_id === id && (p.enrichment_status === "pending" || p.enrichment_status === "running")) ||
          (templateFilters.has("pending") && p.applied_template_id === id && p.enrichment_status === "done" && !!p.ai_description) ||
          (templateFilters.has("applied") && p.applied_template_id === id && p.enrichment_status === "done" && !p.ai_description) ||
          (templateFilters.has("failed") && p.applied_template_id === id && p.enrichment_status === "failed") ||
          (templateFilters.has("other") && p.applied_template_id && p.applied_template_id !== id) ||
          (templateFilters.has("none") && !p.applied_template_id)
        );
      return matchSearch && matchStatus && matchEnrichment && matchTemplate;
    });
  }, [allItems, search, statusFilters, enrichmentFilters, templateFilters, id]);

  const visibleIds = filtered.map((p: any) => p.id);
  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((vid) => selected.has(vid));

  const toggleAll = () => {
    if (allVisibleSelected) {
      setSelected((prev) => { const next = new Set(prev); visibleIds.forEach((vid) => next.delete(vid)); return next; });
    } else {
      setSelected((prev) => { const next = new Set(prev); visibleIds.forEach((vid) => next.add(vid)); return next; });
    }
  };

  const lastClickedId = useRef<string | null>(null);

  const toggle = (pid: string) =>
    setSelected((prev) => { const next = new Set(prev); next.has(pid) ? next.delete(pid) : next.add(pid); return next; });

  const handleRowClick = (e: React.MouseEvent, pid: string) => {
    if (e.shiftKey && lastClickedId.current !== null) {
      const anchorIndex = filtered.findIndex((p: any) => p.id === lastClickedId.current);
      const currentIndex = filtered.findIndex((p: any) => p.id === pid);
      if (anchorIndex !== -1 && currentIndex !== -1) {
        const start = Math.min(anchorIndex, currentIndex);
        const end = Math.max(anchorIndex, currentIndex);
        setSelected((prev) => {
          const next = new Set(prev);
          for (let i = start; i <= end; i++) next.add(filtered[i].id);
          return next;
        });
        return; // don't update anchor on shift+click
      }
    }
    toggle(pid);
    lastClickedId.current = pid;
  };

  const hasActiveFilters = statusFilters.size > 0 || enrichmentFilters.size > 0 || templateFilters.size > 0 || search.trim().length > 0;

  const clearFilters = () => {
    setStatusFilters(new Set());
    setEnrichmentFilters(new Set());
    setTemplateFilters(new Set());
    setSearch("");
    setSelected(new Set());
  };

  const chipClass = (active: boolean, disabled: boolean) => cn(
    "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors border",
    active
      ? "bg-blue-600 text-white border-blue-600"
      : disabled
      ? "bg-gray-50 text-gray-300 border-gray-200 cursor-not-allowed"
      : "bg-white text-gray-600 border-gray-300 hover:border-blue-400 hover:text-blue-600"
  );

  const countBadgeClass = (active: boolean) => cn(
    "px-1 py-0.5 rounded text-[10px] leading-none font-semibold",
    active ? "bg-white/20 text-white" : "bg-gray-100 text-gray-500"
  );

  if (templateLoading) return <div className="flex justify-center p-12"><Loader2 className="h-6 w-6 animate-spin" /></div>;
  if (!template) return <div className="p-8 text-center text-gray-500">Template not found.</div>;

  return (
    <PageShell
      title={`Apply: ${template.name}`}
      description="Select products to regenerate descriptions using this template"
      actions={
        <div className="flex gap-2">
          <Link href="/templates">
            <Button variant="outline" size="sm"><ArrowLeft className="h-4 w-4 mr-1" />Back</Button>
          </Link>
          {selected.size > 0 && (
            <Button size="sm" onClick={() => setShowConfirm(true)}>
              <Sparkles className="h-4 w-4 mr-1" />
              Apply to {selected.size} Product{selected.size !== 1 ? "s" : ""}
            </Button>
          )}
        </div>
      }
    >
      {/* Template structure preview */}
      <div className="mb-5 p-4 bg-blue-50 border border-blue-100 rounded-lg">
        <p className="text-sm font-medium text-blue-800 mb-2">Template structure:</p>
        <div className="flex flex-wrap gap-1.5 mb-2">
          {template.sections.map((s: any, i: number) => {
            const tag: string = s.tag ?? s.level ?? "h2";
            return (
              <span
                key={i}
                style={{ marginLeft: (s.indent ?? 0) * 8 }}
                className={`px-2 py-0.5 rounded text-xs font-medium ${tag === "h2" ? "bg-blue-200 text-blue-800" : "bg-blue-100 text-blue-700"}`}
              >
                {tag.toUpperCase()}: {s.title}
              </span>
            );
          })}
        </div>
        <p className="text-xs text-blue-600">AI uses only existing product information — no invented content.</p>
      </div>

      {/* Filters */}
      <div className="space-y-3 mb-4">
        {/* Search */}
        <div className="relative max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            placeholder="Search products..."
            className="pl-9"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setSelected(new Set()); }}
          />
        </div>

        {/* All chips in one section */}
        <div className="flex gap-1.5 flex-wrap items-center">
          {/* Status chips */}
          {STATUS_OPTIONS.map((s) => {
            const count = statusCounts[s] ?? 0;
            const active = statusFilters.has(s);
            return (
              <button
                key={`status-${s}`}
                onClick={() => { setStatusFilters((prev) => toggleSet(prev, s)); setSelected(new Set()); }}
                disabled={count === 0}
                className={chipClass(active, count === 0)}
              >
                <span className="capitalize">{s}</span>
                <span className={countBadgeClass(active)}>{count}</span>
              </button>
            );
          })}

          {/* Divider */}
          <div className="w-px h-5 bg-gray-200 mx-0.5 self-center" />

          {/* Enrichment status chips — only show options that have products */}
          {ENRICHMENT_OPTIONS.filter((s) => (enrichmentCounts[s] ?? 0) > 0).map((s) => {
            const count = enrichmentCounts[s] ?? 0;
            const active = enrichmentFilters.has(s);
            return (
              <button
                key={`enr-${s}`}
                onClick={() => { setEnrichmentFilters((prev) => toggleSet(prev, s)); setSelected(new Set()); }}
                className={chipClass(active, false)}
              >
                <span className="capitalize">{s.replace("_", " ")}</span>
                <span className={countBadgeClass(active)}>{count}</span>
              </button>
            );
          })}

          {/* Divider */}
          <div className="w-px h-5 bg-gray-200 mx-0.5 self-center" />

          {/* Template chips */}
          {(["processing", "pending", "applied", "failed", "none", "other"] as const).map((f) => {
            const count = templateCounts[f];
            const active = templateFilters.has(f);
            const label =
              f === "processing" ? "Processing" :
              f === "pending" ? "Pending review" :
              f === "applied" ? "Applied" :
              f === "failed" ? "Failed" :
              f === "none" ? "No template" : "Other template";
            return (
              <button
                key={`tmpl-${f}`}
                onClick={() => { setTemplateFilters((prev) => toggleSet(prev, f)); setSelected(new Set()); }}
                disabled={count === 0}
                className={chipClass(active, count === 0)}
              >
                {f === "applied" && <CheckCircle2 className="h-3 w-3" />}
                <span>{label}</span>
                <span className={countBadgeClass(active)}>{count}</span>
              </button>
            );
          })}

          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="text-xs text-gray-400 hover:text-gray-700 underline px-1 ml-1"
            >
              Clear all
            </button>
          )}
        </div>

        {/* Active filter summary */}
        {hasActiveFilters && (
          <div className="text-xs text-gray-500">
            Showing <strong>{filtered.length}</strong> of <strong>{allItems.length}</strong> products
          </div>
        )}
      </div>

      {/* Stats row */}
      {!productsLoading && !hasActiveFilters && (
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm text-gray-500">
            {allItems.length} product{allItems.length !== 1 ? "s" : ""}
            {templateCounts.processing > 0 && (
              <span className="ml-2 text-blue-600 font-medium">· {templateCounts.processing} processing</span>
            )}
            {templateCounts.pending > 0 && (
              <span className="ml-2 text-amber-600 font-medium">· {templateCounts.pending} pending review</span>
            )}
            {templateCounts.applied > 0 && (
              <span className="ml-2 text-green-600 font-medium">· {templateCounts.applied} applied</span>
            )}
            {templateCounts.failed > 0 && (
              <span className="ml-2 text-red-600 font-medium">· {templateCounts.failed} failed</span>
            )}
          </p>
          {selected.size > 0 && (
            <button className="text-xs text-gray-400 hover:text-gray-600" onClick={() => setSelected(new Set())}>
              Clear selection ({selected.size})
            </button>
          )}
        </div>
      )}

      {/* Selection bar */}
      {selected.size > 0 && (
        <div className="mb-3 flex items-center gap-3 px-3 py-2 bg-blue-50 border border-blue-200 rounded-lg">
          <span className="text-sm font-medium text-blue-700">{selected.size} selected</span>
          <Button size="sm" onClick={() => setShowConfirm(true)}>
            <Sparkles className="h-3.5 w-3.5 mr-1" /> Apply Template
          </Button>
          <button className="text-xs text-gray-400 hover:text-gray-600 ml-auto" onClick={() => setSelected(new Set())}>
            Clear
          </button>
        </div>
      )}

      {/* Product table */}
      {productsLoading ? (
        <div className="flex justify-center p-12"><Loader2 className="h-6 w-6 animate-spin text-blue-500" /></div>
      ) : filtered.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center">
            <Package className="h-10 w-10 mx-auto text-gray-300 mb-3" />
            <p className="text-gray-500 font-medium">No products match these filters</p>
            {hasActiveFilters && (
              <button onClick={clearFilters} className="mt-2 text-sm text-blue-500 hover:text-blue-700 underline">
                Clear all filters
              </button>
            )}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="w-10 px-4 py-3">
                    <input type="checkbox" checked={allVisibleSelected} onChange={toggleAll} className="rounded" />
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Product</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Vendor</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Enrichment</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Template</th>
                  <th className="w-20"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((p: any) => {
                  const isThisTemplate = p.applied_template_id === id;
                  const hasThisTemplateProcessing = isThisTemplate && (p.enrichment_status === "pending" || p.enrichment_status === "running");
                  const hasThisTemplateFailed = isThisTemplate && p.enrichment_status === "failed";
                  const hasThisTemplatePending = isThisTemplate && p.enrichment_status === "done" && !!p.ai_description;
                  const hasThisTemplateApplied = isThisTemplate && p.enrichment_status === "done" && !p.ai_description;
                  return (
                    <tr
                      key={p.id}
                      className={cn("border-b last:border-0 hover:bg-gray-50 cursor-pointer select-none", selected.has(p.id) && "bg-blue-50")}
                      onClick={(e) => handleRowClick(e, p.id)}
                    >
                      <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={selected.has(p.id)}
                          onChange={() => { toggle(p.id); lastClickedId.current = p.id; }}
                          className="rounded"
                        />
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="w-8 h-8 bg-gray-100 rounded flex items-center justify-center flex-shrink-0">
                            {p.thumbnail
                              ? <img src={p.thumbnail} alt="" className="w-full h-full object-cover rounded" />
                              : <Package className="h-3.5 w-3.5 text-gray-400" />}
                          </div>
                          <span className="font-medium truncate max-w-xs">{p.title}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-gray-500 text-xs">{p.vendor || "—"}</td>
                      <td className="px-4 py-3">
                        <span className={cn("px-1.5 py-0.5 rounded text-xs font-medium capitalize", statusColor(p.status))}>
                          {p.status}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={cn("px-1.5 py-0.5 rounded text-xs font-medium", statusColor(p.enrichment_status))}>
                          {p.enrichment_status}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {hasThisTemplateApplied ? (
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700">
                            <CheckCircle2 className="h-3 w-3" /> Applied
                          </span>
                        ) : hasThisTemplatePending ? (
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-700">
                            Pending review
                          </span>
                        ) : hasThisTemplateProcessing ? (
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-700">
                            <Loader2 className="h-3 w-3 animate-spin" /> Processing
                          </span>
                        ) : hasThisTemplateFailed ? (
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-red-100 text-red-700">
                            Failed
                          </span>
                        ) : p.applied_template_id ? (
                          <span className="text-xs text-gray-400">Other template</span>
                        ) : (
                          <span className="text-xs text-gray-300">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                        <Link href={`/products/${p.id}?back=/templates/${id}/apply`}>
                          <Button size="sm" variant="outline">View</Button>
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {/* Confirm dialog */}
      {showConfirm && (
        <>
          <div className="fixed inset-0 bg-black/40 z-50" onClick={() => setShowConfirm(false)} />
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-xl shadow-xl w-full max-w-sm p-6" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center gap-2 mb-3">
                <Sparkles className="h-5 w-5 text-blue-500" />
                <h2 className="font-semibold">Apply AI Template?</h2>
              </div>
              <p className="text-sm text-gray-600 mb-4">
                AI will generate new <strong>body_html</strong> for <strong>{selected.size} product{selected.size !== 1 ? "s" : ""}</strong> using the <strong>"{template.name}"</strong> template.
              </p>
              <ul className="text-sm text-gray-500 space-y-1 mb-5 list-disc list-inside">
                <li>Only existing product data will be used — no invented content</li>
                <li>Results go to a review page before anything is saved</li>
                <li>Current descriptions are not changed until you accept</li>
              </ul>
              <div className="flex gap-2">
                <Button onClick={() => applyMutation.mutate()} disabled={applyMutation.isPending}>
                  {applyMutation.isPending
                    ? <><Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />Queuing...</>
                    : <><Check className="h-3.5 w-3.5 mr-1" />Yes, Apply with AI</>}
                </Button>
                <Button variant="outline" onClick={() => setShowConfirm(false)}>
                  <X className="h-3.5 w-3.5 mr-1" />Cancel
                </Button>
              </div>
            </div>
          </div>
        </>
      )}
    </PageShell>
  );
}
