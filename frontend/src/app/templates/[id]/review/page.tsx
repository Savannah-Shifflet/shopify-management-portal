"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { templatesApi, productsApi } from "@/lib/api";
import { PageShell } from "@/components/layout/PageShell";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Check, X, Loader2, ArrowLeft, CheckCircle, Package } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

export default function ReviewTemplatePage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const [accepted, setAccepted] = useState<Set<string>>(new Set());
  const [rejected, setRejected] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const { data: template } = useQuery({
    queryKey: ["template", id],
    queryFn: () => templatesApi.list().then((r) => {
      const templates = r.data as { id: string; name: string }[];
      return templates.find((t) => t.id === id) ?? null;
    }),
  });

  // Load all products that have ai_description ready
  const { data: productsData, isLoading, refetch } = useQuery({
    queryKey: ["products-review", id],
    queryFn: () => productsApi.list({ page: 1, page_size: 10000 }).then((r) => r.data),
    refetchInterval: 5000, // poll while jobs may still be running
  });

  const allProducts = productsData?.items ?? [];
  // Show products that have ai_description (enrichment done) or are still running
  const reviewItems = allProducts.filter((p: any) => p.ai_description || p.enrichment_status === "running" || p.enrichment_status === "pending");

  const acceptMutation = useMutation({
    mutationFn: (productId: string) =>
      productsApi.update(productId, { body_html: allProducts.find((p: any) => p.id === productId)?.ai_description }),
    onSuccess: (_, productId) => {
      setAccepted((prev) => new Set(prev).add(productId));
      qc.invalidateQueries({ queryKey: ["products-review", id] });
    },
  });

  const acceptAll = async () => {
    setSaving(true);
    const pending = reviewItems.filter((p: any) => p.ai_description && !accepted.has(p.id) && !rejected.has(p.id));
    for (const p of pending) {
      await productsApi.update(p.id, { body_html: p.ai_description });
      setAccepted((prev) => new Set(prev).add(p.id));
    }
    setSaving(false);
    qc.invalidateQueries({ queryKey: ["products-review", id] });
  };

  const toggleExpand = (pid: string) =>
    setExpanded((prev) => { const n = new Set(prev); n.has(pid) ? n.delete(pid) : n.add(pid); return n; });

  const doneCount = reviewItems.filter((p: any) => p.ai_description).length;
  const pendingCount = reviewItems.filter((p: any) => p.enrichment_status === "running" || p.enrichment_status === "pending").length;

  return (
    <PageShell
      title="Review AI Descriptions"
      description={template ? `Template: ${template.name}` : "Review generated descriptions before saving"}
      actions={
        <div className="flex gap-2">
          <Link href={`/templates/${id}/apply`}>
            <Button variant="outline" size="sm"><ArrowLeft className="h-4 w-4 mr-1" />Back</Button>
          </Link>
          {doneCount > 0 && (
            <Button size="sm" onClick={acceptAll} disabled={saving}>
              {saving ? <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> : <CheckCircle className="h-3.5 w-3.5 mr-1" />}
              Accept All Ready ({doneCount})
            </Button>
          )}
        </div>
      }
    >
      {pendingCount > 0 && (
        <div className="flex items-center gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg mb-4 text-sm text-amber-700">
          <Loader2 className="h-4 w-4 animate-spin flex-shrink-0" />
          {pendingCount} product{pendingCount !== 1 ? "s" : ""} still being processed by AI — page refreshes automatically
        </div>
      )}

      {isLoading ? (
        <div className="flex justify-center p-12"><Loader2 className="h-6 w-6 animate-spin text-blue-500" /></div>
      ) : reviewItems.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center">
            <Package className="h-10 w-10 mx-auto text-gray-300 mb-3" />
            <p className="text-gray-500 font-medium">No results yet</p>
            <p className="text-sm text-gray-400 mt-1">Go back and apply the template to some products first</p>
            <Link href={`/templates/${id}/apply`} className="mt-4 inline-block">
              <Button size="sm" variant="outline"><ArrowLeft className="h-4 w-4 mr-1" />Apply Template</Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {reviewItems.map((p: any) => {
            const isAccepted = accepted.has(p.id);
            const isRejected = rejected.has(p.id);
            const isReady = !!p.ai_description;
            const isExpanded = expanded.has(p.id);

            return (
              <Card key={p.id} className={cn(
                "transition-colors",
                isAccepted && "border-green-300 bg-green-50",
                isRejected && "border-gray-200 opacity-50",
              )}>
                <CardContent className="p-4">
                  {/* Header row */}
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-gray-100 rounded flex items-center justify-center flex-shrink-0">
                      {p.thumbnail
                        ? <img src={p.thumbnail} alt="" className="w-full h-full object-cover rounded" />
                        : <Package className="h-3.5 w-3.5 text-gray-400" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm truncate">{p.title}</p>
                      {p.vendor && <p className="text-xs text-gray-400">{p.vendor}</p>}
                    </div>

                    {/* Status / actions */}
                    {!isReady ? (
                      <span className="text-xs text-amber-600 flex items-center gap-1"><Loader2 className="h-3 w-3 animate-spin" />Processing...</span>
                    ) : isAccepted ? (
                      <span className="text-xs text-green-600 flex items-center gap-1"><CheckCircle className="h-3.5 w-3.5" />Accepted</span>
                    ) : isRejected ? (
                      <span className="text-xs text-gray-400">Skipped</span>
                    ) : (
                      <div className="flex gap-2">
                        <Button size="sm" variant="outline" onClick={() => toggleExpand(p.id)}>
                          {isExpanded ? "Hide" : "Preview"}
                        </Button>
                        <Button
                          size="sm"
                          className="bg-green-600 hover:bg-green-700"
                          onClick={() => acceptMutation.mutate(p.id)}
                          disabled={acceptMutation.isPending}
                        >
                          <Check className="h-3.5 w-3.5 mr-1" />Accept
                        </Button>
                        <Button
                          size="sm" variant="outline"
                          className="text-gray-400 hover:text-red-500"
                          onClick={() => setRejected((prev) => new Set(prev).add(p.id))}
                        >
                          <X className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    )}
                  </div>

                  {/* Expanded diff */}
                  {isReady && isExpanded && (
                    <div className="mt-3 border-t pt-3 grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-xs font-medium text-gray-400 uppercase mb-2">Current</p>
                        {p.body_html ? (
                          <div className="text-sm text-gray-600 prose prose-sm max-w-none line-clamp-10"
                            dangerouslySetInnerHTML={{ __html: p.body_html }} />
                        ) : (
                          <p className="text-sm text-gray-400 italic">No description</p>
                        )}
                      </div>
                      <div className="bg-blue-50/50 rounded p-2">
                        <p className="text-xs font-medium text-blue-500 uppercase mb-2">AI Suggestion</p>
                        <div className="text-sm text-gray-700 prose prose-sm max-w-none line-clamp-10"
                          dangerouslySetInnerHTML={{ __html: p.ai_description }} />
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </PageShell>
  );
}
