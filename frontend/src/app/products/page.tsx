"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { productsApi } from "@/lib/api";
import { PageShell } from "@/components/layout/PageShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { BulkEnrichDialog } from "@/components/products/BulkEnrichDialog";
import {
  Plus, Search, Sparkles, RefreshCw, CheckCircle, Archive,
  ChevronLeft, ChevronRight, Package, GitMerge, AlertTriangle, X,
} from "lucide-react";
import { cn, formatPrice, statusColor } from "@/lib/utils";
import type { ProductListItem } from "@/types/product";

const STATUS_FILTERS = ["all", "draft", "enriched", "approved", "synced", "archived"];

type DuplicateGroup = {
  sku: string;
  products: {
    id: string;
    title: string;
    status: string;
    sync_status: string;
    base_price: number | null;
    thumbnail: string | null;
  }[];
};

export default function ProductsPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [showDuplicatesDialog, setShowDuplicatesDialog] = useState(false);
  const [showEnrichDialog, setShowEnrichDialog] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["products", { page, search, status: statusFilter === "all" ? undefined : statusFilter }],
    queryFn: () =>
      productsApi.list({
        page,
        page_size: 50,
        search: search || undefined,
        status: statusFilter === "all" ? undefined : statusFilter,
      }).then((r) => r.data),
  });

  const { data: duplicateData } = useQuery({
    queryKey: ["products", "duplicate-skus"],
    queryFn: () => productsApi.duplicateSkus().then((r) => r.data as DuplicateGroup[]),
    staleTime: 60_000,
  });

  const duplicateGroups: DuplicateGroup[] = duplicateData ?? [];

  // Set of product IDs that appear in any duplicate group
  const duplicateProductIds = new Set<string>();
  const productGroupMap = new Map<string, DuplicateGroup>();
  for (const g of duplicateGroups) {
    for (const p of g.products) {
      duplicateProductIds.add(p.id);
      productGroupMap.set(p.id, g);
    }
  }

  const bulkMutation = useMutation({
    mutationFn: (action: string) =>
      productsApi.bulk({ product_ids: [...selected], action }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["products"] });
      setSelected(new Set());
    },
  });

  const openMergeFromSelected = () => {
    router.push(`/products/merge?ids=${[...selected].join(",")}`);
  };

  const openMergeFromGroup = (group: DuplicateGroup) => {
    const ids = group.products.map((p) => p.id).join(",");
    setShowDuplicatesDialog(false);
    router.push(`/products/merge?ids=${ids}`);
  };

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (!data) return;
    if (selected.size === data.items.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(data.items.map((p: ProductListItem) => p.id)));
    }
  };

  const items: ProductListItem[] = data?.items ?? [];
  const total: number = data?.total ?? 0;
  const pageCount = Math.ceil(total / 50);

  return (
    <PageShell
      title="Products"
      description={`${total} total products`}
      actions={
        <Link href="/products/new">
          <Button size="sm">
            <Plus className="h-4 w-4 mr-1" /> Add Product
          </Button>
        </Link>
      }
    >
      {/* Duplicate SKU banner */}
      {duplicateGroups.length > 0 && (
        <div className="mb-4 flex items-center gap-3 p-3 bg-amber-50 border border-amber-300 rounded-lg">
          <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
          <p className="text-sm text-amber-800 flex-1">
            <strong>{duplicateGroups.length} duplicate SKU {duplicateGroups.length === 1 ? "group" : "groups"}</strong> detected across your products.
          </p>
          <Button
            size="sm"
            variant="outline"
            className="border-amber-400 text-amber-800 hover:bg-amber-100"
            onClick={() => setShowDuplicatesDialog(true)}
          >
            Review &amp; Merge
          </Button>
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            placeholder="Search products..."
            className="pl-9"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          />
        </div>
        <div className="flex gap-1 flex-wrap">
          {STATUS_FILTERS.map((s) => (
            <button
              key={s}
              onClick={() => { setStatusFilter(s); setPage(1); }}
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

      {/* Bulk actions bar */}
      {selected.size > 0 && (
        <div className="mb-4 flex items-center gap-2 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <span className="text-sm font-medium text-blue-700">{selected.size} selected</span>
          <div className="flex gap-2 ml-auto">
            <Button
              size="sm" variant="outline"
              onClick={() => setShowEnrichDialog(true)}
            >
              <Sparkles className="h-3.5 w-3.5 mr-1" /> Enrich
            </Button>
            <Button
              size="sm" variant="outline"
              onClick={() => bulkMutation.mutate("approve")}
              disabled={bulkMutation.isPending}
            >
              <CheckCircle className="h-3.5 w-3.5 mr-1" /> Approve
            </Button>
            <Button
              size="sm" variant="outline"
              onClick={() => bulkMutation.mutate("rescrape")}
              disabled={bulkMutation.isPending}
            >
              <RefreshCw className="h-3.5 w-3.5 mr-1" /> Re-scrape
            </Button>
            <Button
              size="sm" variant="outline"
              onClick={() => bulkMutation.mutate("sync")}
              disabled={bulkMutation.isPending}
            >
              <RefreshCw className="h-3.5 w-3.5 mr-1" /> Sync
            </Button>
            <Button
              size="sm" variant="outline"
              onClick={() => bulkMutation.mutate("archive")}
              disabled={bulkMutation.isPending}
            >
              <Archive className="h-3.5 w-3.5 mr-1" /> Archive
            </Button>
            {selected.size >= 2 && (
              <Button
                size="sm" variant="outline"
                onClick={openMergeFromSelected}
                disabled={bulkMutation.isPending}
              >
                <GitMerge className="h-3.5 w-3.5 mr-1" /> Merge
              </Button>
            )}
          </div>
        </div>
      )}

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-8 text-center text-muted-foreground">Loading products...</div>
          ) : items.length === 0 ? (
            <div className="p-12 text-center">
              <Package className="h-10 w-10 mx-auto text-gray-300 mb-3" />
              <p className="text-gray-500 font-medium">No products found</p>
              <p className="text-sm text-gray-400 mt-1">Import products or add them manually</p>
              <Link href="/products/new" className="mt-4 inline-block">
                <Button size="sm"><Plus className="h-4 w-4 mr-1" />Add Product</Button>
              </Link>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="w-10 px-4 py-3">
                    <input
                      type="checkbox"
                      checked={selected.size === items.length && items.length > 0}
                      onChange={toggleAll}
                      className="rounded"
                    />
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Product</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Sync</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Enrichment</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Price</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Type</th>
                </tr>
              </thead>
              <tbody>
                {items.map((p) => (
                  <tr
                    key={p.id}
                    className={cn(
                      "border-b last:border-0 hover:bg-gray-50 cursor-pointer",
                      selected.has(p.id) && "bg-blue-50"
                    )}
                  >
                    <td className="px-4 py-3" onClick={(e) => { e.stopPropagation(); toggleSelect(p.id); }}>
                      <input
                        type="checkbox"
                        checked={selected.has(p.id)}
                        onChange={() => toggleSelect(p.id)}
                        className="rounded"
                      />
                    </td>
                    <td className="px-4 py-3" onClick={() => router.push(`/products/${p.id}`)}>
                      <div className="flex items-center gap-3">
                        {p.thumbnail ? (
                          <img src={p.thumbnail} alt="" className="w-10 h-10 object-cover rounded" />
                        ) : (
                          <div className="w-10 h-10 bg-gray-100 rounded flex items-center justify-center">
                            <Package className="h-4 w-4 text-gray-400" />
                          </div>
                        )}
                        <div>
                          <div className="flex items-center gap-2">
                            <p className="font-medium text-gray-900 hover:text-blue-600">{p.title}</p>
                            {duplicateProductIds.has(p.id) && (
                              <button
                                onClick={(e) => { e.stopPropagation(); openMergeFromGroup(productGroupMap.get(p.id)!); }}
                                className="flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-700 hover:bg-amber-200 shrink-0"
                                title="Duplicate SKU detected — click to merge"
                              >
                                <AlertTriangle className="h-3 w-3" /> Duplicate SKU
                              </button>
                            )}
                          </div>
                          {p.vendor && <p className="text-xs text-gray-400">{p.vendor}</p>}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={cn("px-2 py-0.5 rounded-full text-xs font-medium capitalize", statusColor(p.status))}>
                        {p.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={cn("px-2 py-0.5 rounded-full text-xs font-medium", statusColor(p.sync_status))}>
                        {p.sync_status.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={cn("px-2 py-0.5 rounded-full text-xs font-medium", statusColor(p.enrichment_status))}>
                        {p.enrichment_status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-700">
                      {p.base_price ? formatPrice(Number(p.base_price)) : "—"}
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">{p.product_type || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      {/* Pagination */}
      {pageCount > 1 && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-gray-500">
            Page {page} of {pageCount} ({total} products)
          </p>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(page - 1)}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="sm" disabled={page >= pageCount} onClick={() => setPage(page + 1)}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* ── Duplicate SKUs dialog ── */}
      {showDuplicatesDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setShowDuplicatesDialog(false)}>
          <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl mx-4 p-6 max-h-[80vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-lg font-semibold">Duplicate SKUs</h2>
                <p className="text-sm text-gray-500">{duplicateGroups.length} groups of products share the same SKU</p>
              </div>
              <button onClick={() => setShowDuplicatesDialog(false)} className="text-gray-400 hover:text-gray-600">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="overflow-y-auto flex-1 space-y-3">
              {duplicateGroups.map((group) => (
                <div key={group.sku} className="border rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <span className="text-xs text-gray-500 uppercase tracking-wide">SKU</span>
                      <p className="font-mono font-semibold text-gray-900">{group.sku}</p>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => openMergeFromGroup(group)}
                    >
                      <GitMerge className="h-3.5 w-3.5 mr-1" /> Merge {group.products.length} products
                    </Button>
                  </div>
                  <div className="space-y-2">
                    {group.products.map((p) => (
                      <div key={p.id} className="flex items-center gap-3 p-2 bg-gray-50 rounded-md">
                        {p.thumbnail ? (
                          <img src={p.thumbnail} alt="" className="w-8 h-8 object-cover rounded shrink-0" />
                        ) : (
                          <div className="w-8 h-8 bg-gray-200 rounded flex items-center justify-center shrink-0">
                            <Package className="h-3 w-3 text-gray-400" />
                          </div>
                        )}
                        <div className="flex-1 min-w-0">
                          <p
                            className="text-sm font-medium text-gray-900 truncate hover:text-blue-600 cursor-pointer"
                            onClick={() => { setShowDuplicatesDialog(false); router.push(`/products/${p.id}`); }}
                          >
                            {p.title}
                          </p>
                        </div>
                        <span className={cn("px-2 py-0.5 rounded-full text-xs font-medium capitalize shrink-0", statusColor(p.status))}>
                          {p.status}
                        </span>
                        {p.base_price !== null && (
                          <span className="text-xs text-gray-500 shrink-0">{formatPrice(p.base_price)}</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {showEnrichDialog && (
        <BulkEnrichDialog
          productIds={[...selected]}
          onClose={() => setShowEnrichDialog(false)}
          onQueued={(count) => {
            setShowEnrichDialog(false);
            setSelected(new Set());
          }}
        />
      )}

    </PageShell>
  );
}
