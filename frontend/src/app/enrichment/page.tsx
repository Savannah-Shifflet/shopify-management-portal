"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { productsApi } from "@/lib/api";
import { PageShell } from "@/components/layout/PageShell";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { BulkEnrichDialog } from "@/components/products/BulkEnrichDialog";
import { Sparkles, Package, Loader2, CheckCircle } from "lucide-react";
import { cn, statusColor } from "@/lib/utils";
import Link from "next/link";

export default function EnrichmentPage() {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [enrichTarget, setEnrichTarget] = useState<string[] | null>(null);

  const { data: products, isLoading } = useQuery({
    queryKey: ["products-enrichment"],
    queryFn: () =>
      productsApi.list({ page: 1, page_size: 10000 }).then((r) => r.data),
  });

  const items = products?.items ?? [];

  const openEnrichDialog = (ids: string[]) => setEnrichTarget(ids);
  const closeEnrichDialog = () => setEnrichTarget(null);

  return (
    <PageShell
      title="AI Enrichment"
      description="Enhance product content with AI-generated descriptions, tags, and SEO"
      actions={
        <div className="flex gap-2">
          {selected.size > 0 && (
            <Button
              size="sm" variant="outline"
              onClick={() => openEnrichDialog([...selected])}
            >
              <Sparkles className="h-4 w-4 mr-1" />
              Enrich Selected ({selected.size})
            </Button>
          )}
          <Button
            size="sm"
            onClick={() => openEnrichDialog(items.map((p: any) => p.id))}
            disabled={items.length === 0}
          >
            <Sparkles className="h-4 w-4 mr-1" />
            Enrich All Pending
          </Button>
        </div>
      }
    >
      {/* Info banner */}
      <div className="flex items-start gap-3 p-4 bg-blue-50 border border-blue-100 rounded-lg mb-6">
        <Sparkles className="h-5 w-5 text-blue-600 mt-0.5 flex-shrink-0" />
        <div>
          <p className="font-medium text-blue-800">How AI Enrichment Works</p>
          <p className="text-sm text-blue-600 mt-0.5">
            AI analyzes your raw product data and generates improved titles, rich descriptions,
            SEO metadata, relevant tags, and product attributes. You review and accept suggestions
            before they&apos;re applied.
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center p-12"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>
      ) : items.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center">
            <CheckCircle className="h-10 w-10 mx-auto text-green-400 mb-3" />
            <p className="text-gray-500 font-medium">No products found</p>
            <p className="text-sm text-gray-400 mt-1">Import products to get started</p>
            <Link href="/import" className="mt-4 inline-block">
              <Button size="sm" variant="outline">Import Products</Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm text-gray-500">{items.length} product{items.length !== 1 ? "s" : ""}</p>
            <button
              className="text-sm text-blue-600 hover:underline"
              onClick={() => {
                if (selected.size === items.length) setSelected(new Set());
                else setSelected(new Set(items.map((p: any) => p.id)));
              }}
            >
              {selected.size === items.length ? "Deselect all" : "Select all"}
            </button>
          </div>
          <div className="space-y-2">
            {items.map((p: any) => (
              <Card
                key={p.id}
                className={cn(
                  "cursor-pointer hover:border-blue-200 transition-colors",
                  selected.has(p.id) && "border-blue-300 bg-blue-50"
                )}
                onClick={() => {
                  setSelected((prev) => {
                    const next = new Set(prev);
                    next.has(p.id) ? next.delete(p.id) : next.add(p.id);
                    return next;
                  });
                }}
              >
                <CardContent className="p-4">
                  <div className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      checked={selected.has(p.id)}
                      onChange={() => {}}
                      className="rounded"
                    />
                    <div className="w-10 h-10 bg-gray-100 rounded flex items-center justify-center flex-shrink-0">
                      {p.thumbnail
                        ? <img src={p.thumbnail} alt="" className="w-full h-full object-cover rounded" />
                        : <Package className="h-4 w-4 text-gray-400" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate">{p.title}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-xs text-gray-400">{p.source_type || "manual"}</span>
                        <span className={cn("px-1.5 py-0.5 rounded text-xs font-medium", statusColor(p.enrichment_status))}>
                          {p.enrichment_status}
                        </span>
                      </div>
                    </div>
                    <Link
                      href={`/products/${p.id}`}
                      className="text-xs text-blue-600 hover:underline flex-shrink-0"
                      onClick={(e) => e.stopPropagation()}
                    >
                      View
                    </Link>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </>
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
