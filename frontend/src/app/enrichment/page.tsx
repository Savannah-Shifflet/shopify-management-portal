"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { productsApi } from "@/lib/api";
import { PageShell } from "@/components/layout/PageShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { BulkEnrichDialog } from "@/components/products/BulkEnrichDialog";
import { Sparkles, Package, Loader2, Search, ChevronLeft, ChevronRight } from "lucide-react";
import { cn, statusColor } from "@/lib/utils";
import Link from "next/link";

const STATUS_FILTERS = ["all", "draft", "enriched", "approved", "synced", "archived"];

export default function EnrichmentPage() {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [enrichTarget, setEnrichTarget] = useState<string[] | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["products-enrichment", { page, search, status: statusFilter === "all" ? undefined : statusFilter }],
    queryFn: () =>
      productsApi.list({
        page,
        page_size: 50,
        search: search || undefined,
        status: statusFilter === "all" ? undefined : statusFilter,
      }).then((r) => r.data),
  });

  const items: any[] = data?.items ?? [];
  const total: number = data?.total ?? 0;
  const totalPages: number = data?.pages ?? 1;

  const visibleIds = items.map((p: any) => p.id);
  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((id) => selected.has(id));

  const toggleAll = () => {
    if (allVisibleSelected) {
      setSelected((prev) => {
        const next = new Set(prev);
        visibleIds.forEach((id) => next.delete(id));
        return next;
      });
    } else {
      setSelected((prev) => {
        const next = new Set(prev);
        visibleIds.forEach((id) => next.add(id));
        return next;
      });
    }
  };

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const openEnrichDialog = (ids: string[]) => setEnrichTarget(ids);
  const closeEnrichDialog = () => setEnrichTarget(null);

  return (
    <PageShell
      title="AI Enrichment"
      description="Enhance product content with AI-generated descriptions, tags, and SEO"
      actions={
        <div className="flex gap-2">
          {selected.size > 0 && (
            <Button size="sm" variant="outline" onClick={() => openEnrichDialog([...selected])}>
              <Sparkles className="h-4 w-4 mr-1" />
              Enrich {selected.size} Selected
            </Button>
          )}
          <Button
            size="sm"
            onClick={() => openEnrichDialog(items.map((p: any) => p.id))}
            disabled={items.length === 0}
          >
            <Sparkles className="h-4 w-4 mr-1" />
            Enrich All ({items.length})
          </Button>
        </div>
      }
    >
      {/* Info banner */}
      <div className="flex items-start gap-3 p-4 bg-blue-50 border border-blue-100 rounded-lg mb-5">
        <Sparkles className="h-5 w-5 text-blue-600 mt-0.5 flex-shrink-0" />
        <p className="text-sm text-blue-700">
          AI analyzes raw product data and generates improved titles, rich descriptions, SEO metadata, tags, and attributes.
          You review and accept suggestions before they&apos;re applied.
        </p>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            placeholder="Search products..."
            className="pl-9"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); setSelected(new Set()); }}
          />
        </div>
        <div className="flex gap-1 flex-wrap">
          {STATUS_FILTERS.map((s) => (
            <button
              key={s}
              onClick={() => { setStatusFilter(s); setPage(1); setSelected(new Set()); }}
              className={cn(
                "px-3 py-1.5 rounded-md text-sm font-medium capitalize transition-colors",
                statusFilter === s
                  ? "bg-blue-600 text-white"
                  : "bg-white border text-gray-600 hover:bg-gray-50"
              )}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Selected bar */}
      {selected.size > 0 && (
        <div className="mb-3 flex items-center gap-3 px-3 py-2 bg-blue-50 border border-blue-200 rounded-lg">
          <span className="text-sm font-medium text-blue-700">{selected.size} selected</span>
          <Button size="sm" variant="outline" onClick={() => openEnrichDialog([...selected])}>
            <Sparkles className="h-3.5 w-3.5 mr-1" /> Enrich Selected
          </Button>
          <button className="text-xs text-gray-400 hover:text-gray-600 ml-auto" onClick={() => setSelected(new Set())}>
            Clear selection
          </button>
        </div>
      )}

      {/* Product list */}
      {isLoading ? (
        <div className="flex justify-center p-12"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>
      ) : items.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center">
            <Package className="h-10 w-10 mx-auto text-gray-300 mb-3" />
            <p className="text-gray-500 font-medium">No products found</p>
            <p className="text-sm text-gray-400 mt-1">Try adjusting your search or filter</p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="w-10 px-4 py-3">
                    <input
                      type="checkbox"
                      checked={allVisibleSelected}
                      onChange={toggleAll}
                      className="rounded"
                    />
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Product</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Vendor</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Enrichment</th>
                  <th className="w-20"></th>
                </tr>
              </thead>
              <tbody>
                {items.map((p: any) => (
                  <tr
                    key={p.id}
                    className={cn("border-b last:border-0 hover:bg-gray-50 cursor-pointer", selected.has(p.id) && "bg-blue-50")}
                    onClick={() => toggle(p.id)}
                  >
                    <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={selected.has(p.id)}
                        onChange={() => toggle(p.id)}
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
                    <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                      <Link href={`/products/${p.id}`}>
                        <Button size="sm" variant="outline">View</Button>
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-gray-500">{total} product{total !== 1 ? "s" : ""}</p>
          <div className="flex items-center gap-2">
            <Button size="sm" variant="outline" onClick={() => setPage((p) => p - 1)} disabled={page === 1}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm text-gray-600">Page {page} of {totalPages}</span>
            <Button size="sm" variant="outline" onClick={() => setPage((p) => p + 1)} disabled={page === totalPages}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {enrichTarget && (
        <BulkEnrichDialog
          productIds={enrichTarget}
          onClose={closeEnrichDialog}
          onQueued={() => {
            closeEnrichDialog();
            setSelected(new Set());
            qc.invalidateQueries({ queryKey: ["products-enrichment"] });
          }}
        />
      )}
    </PageShell>
  );
}
