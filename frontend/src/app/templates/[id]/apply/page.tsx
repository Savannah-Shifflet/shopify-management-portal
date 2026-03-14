"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation } from "@tanstack/react-query";
import { templatesApi, productsApi, enrichmentApi } from "@/lib/api";
import { PageShell } from "@/components/layout/PageShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Sparkles, Package, Search, Loader2, ArrowLeft, X, Check } from "lucide-react";
import Link from "next/link";
import { cn, statusColor } from "@/lib/utils";

export default function ApplyTemplatePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [search, setSearch] = useState("");
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
    queryKey: ["products-for-template"],
    queryFn: () => productsApi.list({ page: 1, page_size: 10000 }).then((r) => r.data),
  });

  const applyMutation = useMutation({
    mutationFn: () =>
      enrichmentApi.bulkEnrich([...selected], ["body_html"], id),
    onSuccess: () => {
      router.push(`/templates/${id}/review`);
    },
  });

  const allItems = productsData?.items ?? [];
  const filtered = search.trim()
    ? allItems.filter((p: any) =>
        p.title.toLowerCase().includes(search.toLowerCase()) ||
        (p.vendor ?? "").toLowerCase().includes(search.toLowerCase())
      )
    : allItems;

  const toggleAll = () => {
    if (selected.size === filtered.length) setSelected(new Set());
    else setSelected(new Set(filtered.map((p: any) => p.id)));
  };

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  if (templateLoading) return <div className="flex justify-center p-12"><Loader2 className="h-6 w-6 animate-spin" /></div>;
  if (!template) return <div className="p-8 text-center text-gray-500">Template not found.</div>;

  return (
    <PageShell
      title={`Apply: ${template.name}`}
      description="Select products to regenerate descriptions using this template"
      actions={
        <Link href="/templates">
          <Button variant="outline" size="sm"><ArrowLeft className="h-4 w-4 mr-1" />Back to Templates</Button>
        </Link>
      }
    >
      {/* Template preview */}
      <div className="mb-5 p-4 bg-blue-50 border border-blue-100 rounded-lg">
        <p className="text-sm font-medium text-blue-800 mb-2">Template structure:</p>
        <div className="flex flex-wrap gap-1.5">
          {template.sections.map((s: any, i: number) => (
            <span key={i} className={`px-2 py-0.5 rounded text-xs font-medium ${s.level === "h2" ? "bg-blue-200 text-blue-800" : "bg-blue-100 text-blue-700"}`}>
              {s.level.toUpperCase()}: {s.title}
            </span>
          ))}
        </div>
        <p className="text-xs text-blue-600 mt-2">AI will only use information already present in each product — no invented content.</p>
      </div>

      {/* Search + select-all */}
      <div className="flex items-center gap-3 mb-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            placeholder="Search products..."
            className="pl-9"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <button className="text-sm text-blue-600 hover:underline whitespace-nowrap" onClick={toggleAll}>
          {selected.size === filtered.length && filtered.length > 0 ? "Deselect all" : `Select all ${filtered.length}`}
        </button>
        <span className="text-sm text-gray-500">{selected.size} selected</span>
      </div>

      {/* Product list */}
      {productsLoading ? (
        <div className="flex justify-center p-8"><Loader2 className="h-6 w-6 animate-spin text-blue-500" /></div>
      ) : (
        <div className="space-y-1.5 mb-6">
          {filtered.map((p: any) => (
            <Card
              key={p.id}
              className={cn("cursor-pointer hover:border-blue-200 transition-colors", selected.has(p.id) && "border-blue-300 bg-blue-50")}
              onClick={() => toggle(p.id)}
            >
              <CardContent className="p-3">
                <div className="flex items-center gap-3">
                  <input type="checkbox" checked={selected.has(p.id)} onChange={() => {}} className="rounded" />
                  <div className="w-8 h-8 bg-gray-100 rounded flex items-center justify-center flex-shrink-0">
                    {p.thumbnail
                      ? <img src={p.thumbnail} alt="" className="w-full h-full object-cover rounded" />
                      : <Package className="h-3.5 w-3.5 text-gray-400" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{p.title}</p>
                    {p.vendor && <p className="text-xs text-gray-400">{p.vendor}</p>}
                  </div>
                  <span className={cn("px-1.5 py-0.5 rounded text-xs font-medium flex-shrink-0", statusColor(p.status))}>{p.status}</span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Sticky footer */}
      <div className="sticky bottom-0 bg-white border-t pt-4 pb-2 flex items-center gap-3">
        <Button
          disabled={selected.size === 0}
          onClick={() => setShowConfirm(true)}
        >
          <Sparkles className="h-4 w-4 mr-1" />
          Apply to {selected.size} Product{selected.size !== 1 ? "s" : ""}
        </Button>
        <p className="text-sm text-gray-400">AI will generate body_html only — you review before anything is saved</p>
      </div>

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
                <Button
                  onClick={() => applyMutation.mutate()}
                  disabled={applyMutation.isPending}
                >
                  {applyMutation.isPending
                    ? <><Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />Queuing...</>
                    : <><Check className="h-3.5 w-3.5 mr-1" />Yes, Apply with AI</>}
                </Button>
                <Button variant="outline" onClick={() => setShowConfirm(false)}>Cancel</Button>
              </div>
            </div>
          </div>
        </>
      )}
    </PageShell>
  );
}
