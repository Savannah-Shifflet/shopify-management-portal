"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { syncApi } from "@/lib/api";
import { PageShell } from "@/components/layout/PageShell";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Loader2, Tag, Layers, Search, ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";

type CollectionRule = {
  column: string;
  relation: string;
  condition: string;
};

type Collection = {
  id: number;
  title: string;
  handle: string;
  automated: boolean;
  disjunctive: boolean;
  rules: CollectionRule[];
};

const COLUMN_LABELS: Record<string, string> = {
  TAG: "Tag",
  TITLE: "Title",
  TYPE: "Product type",
  VENDOR: "Vendor",
  PRICE: "Price",
  COMPARE_AT_PRICE: "Compare-at price",
  WEIGHT: "Weight",
  INVENTORY_STOCK: "Inventory stock",
  IS_PRICE_REDUCED: "Price reduced",
};

const RELATION_LABELS: Record<string, string> = {
  EQUALS: "is equal to",
  NOT_EQUALS: "is not equal to",
  GREATER_THAN: "is greater than",
  LESS_THAN: "is less than",
  STARTS_WITH: "starts with",
  ENDS_WITH: "ends with",
  CONTAINS: "contains",
  NOT_CONTAINS: "does not contain",
};

export default function CollectionsPage() {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<"all" | "automated" | "manual">("all");
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const { data: collections, isLoading, error, refetch, isFetching } = useQuery<Collection[]>({
    queryKey: ["shopify-collections"],
    queryFn: () => syncApi.collections().then((r) => r.data),
    staleTime: 5 * 60 * 1000, // cache for 5 min — Shopify collections don't change often
  });

  const toggleExpand = (id: number) =>
    setExpanded((prev) => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });

  const filtered = (collections ?? []).filter((c) => {
    if (filter === "automated" && !c.automated) return false;
    if (filter === "manual" && c.automated) return false;
    if (search && !c.title.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const tagCollections = filtered.filter((c) => c.rules.some((r) => r.column === "TAG"));

  return (
    <PageShell
      title="Shopify Collections"
      description="View collection rules to understand what tags products need for automated collections"
      actions={
        <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
          {isFetching ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
          Refresh
        </Button>
      }
    >
      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            className="pl-8 h-9"
            placeholder="Search collections..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="flex gap-1">
          {(["all", "automated", "manual"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                "px-3 py-1.5 rounded-md text-sm font-medium capitalize transition-colors",
                filter === f ? "bg-blue-600 text-white" : "bg-white text-gray-600 border hover:bg-gray-50"
              )}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center p-12"><Loader2 className="h-6 w-6 animate-spin text-blue-500" /></div>
      ) : error ? (
        <Card>
          <CardContent className="p-8 text-center text-red-500 text-sm">
            Failed to load collections — make sure Shopify is connected in Settings.
          </CardContent>
        </Card>
      ) : filtered.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center text-gray-400 text-sm">No collections found.</CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {/* Tag-rule summary banner */}
          {filter !== "manual" && tagCollections.length > 0 && (
            <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg mb-4 text-sm text-blue-700 flex items-center gap-2">
              <Tag className="h-4 w-4 flex-shrink-0" />
              <span>
                <strong>{tagCollections.length}</strong> automated collection{tagCollections.length !== 1 ? "s" : ""} use tag rules — expand them to see required tags.
              </span>
            </div>
          )}

          {filtered.map((c) => {
            const isExpanded = expanded.has(c.id);
            const tagRules = c.rules.filter((r) => r.column === "TAG");
            const otherRules = c.rules.filter((r) => r.column !== "TAG");

            return (
              <Card key={c.id} className="overflow-hidden">
                <button
                  className="w-full text-left"
                  onClick={() => toggleExpand(c.id)}
                >
                  <CardContent className="p-4">
                    <div className="flex items-center gap-3">
                      <div className={cn(
                        "p-1.5 rounded",
                        c.automated ? "bg-purple-100" : "bg-gray-100"
                      )}>
                        {c.automated
                          ? <Tag className="h-4 w-4 text-purple-600" />
                          : <Layers className="h-4 w-4 text-gray-500" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm">{c.title}</p>
                        <p className="text-xs text-gray-400">/{c.handle}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={cn(
                          "px-2 py-0.5 rounded-full text-xs font-medium",
                          c.automated ? "bg-purple-100 text-purple-700" : "bg-gray-100 text-gray-600"
                        )}>
                          {c.automated ? "Automated" : "Manual"}
                        </span>
                        {c.automated && tagRules.length > 0 && (
                          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
                            {tagRules.length} tag rule{tagRules.length !== 1 ? "s" : ""}
                          </span>
                        )}
                        {isExpanded
                          ? <ChevronUp className="h-4 w-4 text-gray-400" />
                          : <ChevronDown className="h-4 w-4 text-gray-400" />}
                      </div>
                    </div>
                  </CardContent>
                </button>

                {isExpanded && (
                  <div className="border-t px-4 pb-4 pt-3 bg-gray-50 space-y-3">
                    {!c.automated ? (
                      <p className="text-sm text-gray-500 italic">Manual collection — products are added individually, no rules.</p>
                    ) : (
                      <>
                        <p className="text-xs text-gray-500">
                          Products must match{" "}
                          <strong>{c.disjunctive ? "any" : "all"}</strong> of these conditions:
                        </p>

                        {/* Tag rules highlighted */}
                        {tagRules.length > 0 && (
                          <div>
                            <p className="text-xs font-medium text-blue-600 uppercase mb-1.5">Tag Conditions</p>
                            <div className="flex flex-wrap gap-2">
                              {tagRules.map((r, i) => (
                                <div key={i} className="flex items-center gap-1.5 bg-blue-50 border border-blue-200 rounded px-2.5 py-1.5">
                                  <Tag className="h-3 w-3 text-blue-500 flex-shrink-0" />
                                  <span className="text-xs text-blue-800">
                                    {RELATION_LABELS[r.relation] ?? r.relation}{" "}
                                    <strong>"{r.condition}"</strong>
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Other rules */}
                        {otherRules.length > 0 && (
                          <div>
                            <p className="text-xs font-medium text-gray-500 uppercase mb-1.5">Other Conditions</p>
                            <div className="space-y-1">
                              {otherRules.map((r, i) => (
                                <p key={i} className="text-xs text-gray-600">
                                  {COLUMN_LABELS[r.column] ?? r.column}{" "}
                                  {RELATION_LABELS[r.relation] ?? r.relation}{" "}
                                  <strong>"{r.condition}"</strong>
                                </p>
                              ))}
                            </div>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </PageShell>
  );
}
