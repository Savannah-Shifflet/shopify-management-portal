"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { templatesApi, productsApi } from "@/lib/api";
import { PageShell } from "@/components/layout/PageShell";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Save, X, Loader2, ArrowLeft, CheckCircle, Package, Eye, Pencil } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

export default function ReviewTemplatePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const [accepted, setAccepted] = useState<Set<string>>(new Set());
  const [rejected, setRejected] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [editMode, setEditMode] = useState<Set<string>>(new Set());
  // Stores per-product edited HTML; seeded from ai_description on first expand
  const [editedContent, setEditedContent] = useState<Record<string, string>>({});

  const { data: template } = useQuery({
    queryKey: ["template", id],
    queryFn: () => templatesApi.list().then((r) => {
      const templates = r.data as { id: string; name: string }[];
      return templates.find((t) => t.id === id) ?? null;
    }),
  });

  const { data: productsData, isLoading, isFetching } = useQuery({
    queryKey: ["products-review", id],
    queryFn: () => productsApi.list({ page: 1, page_size: 10000 }).then((r) => r.data),
    refetchInterval: (query) => {
      const items: any[] = query.state.data?.items ?? [];
      const anyActive = items.some(
        (p: any) => p.applied_template_id === id &&
          (p.enrichment_status === "pending" || p.enrichment_status === "running")
      );
      return anyActive ? 3000 : 5000;
    },
  });

  const allProducts = productsData?.items ?? [];

  const reviewItems = allProducts.filter((p: any) => {
    const isThisTemplate = p.applied_template_id === id;
    const isProcessing = p.enrichment_status === "running" || p.enrichment_status === "pending";
    const isFailed = p.enrichment_status === "failed";
    const hasAiContent = !!p.ai_description;
    // Exclude products that were previously accepted (done but ai_description already cleared)
    return isThisTemplate && (isProcessing || isFailed || hasAiContent);
  });

  // Returns the effective save content for a product (edited version or original ai_description)
  const getContent = (productId: string): string => {
    if (editedContent[productId] !== undefined) return editedContent[productId];
    return allProducts.find((p: any) => p.id === productId)?.ai_description ?? "";
  };

  const acceptMutation = useMutation({
    mutationFn: (productId: string) =>
      productsApi.update(productId, {
        body_html: getContent(productId),
        ai_description: null,
      } as any),
    onSuccess: (_, productId) => {
      setAccepted((prev) => new Set(prev).add(productId));
      qc.invalidateQueries({ queryKey: ["products-review", id] });
      qc.invalidateQueries({ queryKey: ["products-apply-template-all"] });
      qc.invalidateQueries({ queryKey: ["products-for-template-progress"] });
    },
  });

  const rejectMutation = useMutation({
    mutationFn: (productId: string) =>
      productsApi.update(productId, {
        ai_description: null,
        applied_template_id: null,
        enrichment_status: "not_started",
      } as any),
    onSuccess: (_, productId) => {
      setRejected((prev) => new Set(prev).add(productId));
      qc.invalidateQueries({ queryKey: ["products-review", id] });
      qc.invalidateQueries({ queryKey: ["products-apply-template-all"] });
      qc.invalidateQueries({ queryKey: ["products-for-template-progress"] });
    },
  });

  const acceptAll = async () => {
    setSaving(true);
    const pending = reviewItems.filter((p: any) => p.ai_description && !accepted.has(p.id) && !rejected.has(p.id));
    for (const p of pending) {
      await productsApi.update(p.id, {
        body_html: getContent(p.id),
        ai_description: null,
      } as any);
      setAccepted((prev) => new Set(prev).add(p.id));
    }
    setSaving(false);
    qc.invalidateQueries({ queryKey: ["products-review", id] });
    qc.invalidateQueries({ queryKey: ["products-apply-template-all"] });
    qc.invalidateQueries({ queryKey: ["products-for-template-progress"] });
    router.push("/templates");
  };

  const toggleExpand = (pid: string, aiDescription?: string) => {
    setExpanded((prev) => {
      const n = new Set(prev);
      if (n.has(pid)) {
        n.delete(pid);
      } else {
        n.add(pid);
        // Seed edit content from ai_description on first expand (don't overwrite user edits)
        if (aiDescription && editedContent[pid] === undefined) {
          setEditedContent((prev) => ({ ...prev, [pid]: aiDescription }));
        }
      }
      return n;
    });
  };

  const toggleEditMode = (pid: string) =>
    setEditMode((prev) => { const n = new Set(prev); n.has(pid) ? n.delete(pid) : n.add(pid); return n; });

  const doneCount = reviewItems.filter((p: any) => p.enrichment_status === "done" && p.ai_description && !accepted.has(p.id) && !rejected.has(p.id)).length;
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
              {saving ? <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> : <Save className="h-3.5 w-3.5 mr-1" />}
              Save All ({doneCount})
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

      {isLoading || (isFetching && reviewItems.length === 0) ? (
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
            const isProcessing = p.enrichment_status === "pending" || p.enrichment_status === "running";
            const isFailed = p.enrichment_status === "failed";
            const isReady = p.enrichment_status === "done" && !!p.ai_description;
            const isExpanded = expanded.has(p.id);
            const isEditing = editMode.has(p.id);
            const currentContent = editedContent[p.id] ?? p.ai_description ?? "";
            const isEdited = editedContent[p.id] !== undefined && editedContent[p.id] !== p.ai_description;

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
                    {isProcessing ? (
                      <span className="text-xs text-blue-600 flex items-center gap-1"><Loader2 className="h-3 w-3 animate-spin" />Processing...</span>
                    ) : isFailed ? (
                      <span className="text-xs text-red-500">Enrichment failed</span>
                    ) : isAccepted ? (
                      <span className="text-xs text-green-600 flex items-center gap-1"><CheckCircle className="h-3.5 w-3.5" />Saved</span>
                    ) : isRejected ? (
                      <span className="text-xs text-gray-400">Skipped</span>
                    ) : (
                      <div className="flex items-center gap-2">
                        {isEdited && (
                          <span className="text-xs text-blue-600 font-medium">Edited</span>
                        )}
                        <Button size="sm" variant="outline" onClick={() => toggleExpand(p.id, p.ai_description)}>
                          {isExpanded ? "Hide" : "Preview"}
                        </Button>
                        <Button
                          size="sm"
                          className="bg-green-600 hover:bg-green-700"
                          onClick={() => acceptMutation.mutate(p.id)}
                          disabled={acceptMutation.isPending}
                        >
                          <Save className="h-3.5 w-3.5 mr-1" />Save
                        </Button>
                        <Button
                          size="sm" variant="outline"
                          className="text-gray-400 hover:text-red-500"
                          onClick={() => rejectMutation.mutate(p.id)}
                          disabled={rejectMutation.isPending}
                        >
                          <X className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    )}
                  </div>

                  {/* Expanded panel */}
                  {isReady && isExpanded && (
                    <div className="mt-3 border-t pt-3 grid grid-cols-2 gap-4">
                      {/* Left: current description */}
                      <div>
                        <p className="text-xs font-medium text-gray-400 uppercase mb-2">Current</p>
                        {p.body_html ? (
                          <div className="text-sm text-gray-600 prose prose-sm max-w-none line-clamp-10"
                            dangerouslySetInnerHTML={{ __html: p.body_html }} />
                        ) : (
                          <p className="text-sm text-gray-400 italic">No description</p>
                        )}
                      </div>

                      {/* Right: AI suggestion (editable) */}
                      <div className="bg-blue-50/50 rounded p-2">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <p className="text-xs font-medium text-blue-500 uppercase">AI Suggestion</p>
                            {isEdited && (
                              <span className="text-xs bg-blue-100 text-blue-600 px-1.5 py-0.5 rounded font-medium">Edited</span>
                            )}
                          </div>
                          <button
                            onClick={() => toggleEditMode(p.id)}
                            className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-700"
                          >
                            {isEditing
                              ? <><Eye className="h-3 w-3" />Preview</>
                              : <><Pencil className="h-3 w-3" />Edit HTML</>}
                          </button>
                        </div>

                        {isEditing ? (
                          <textarea
                            className="w-full text-xs font-mono bg-gray-900 text-green-300 rounded p-2 min-h-[200px] resize-y border-0 outline-none focus:ring-1 focus:ring-blue-400"
                            value={currentContent}
                            onChange={(e) => setEditedContent((prev) => ({ ...prev, [p.id]: e.target.value }))}
                            spellCheck={false}
                          />
                        ) : (
                          <div
                            className="text-sm text-gray-700 prose prose-sm max-w-none line-clamp-10"
                            dangerouslySetInnerHTML={{ __html: currentContent }}
                          />
                        )}

                        {isEditing && isEdited && (
                          <button
                            className="mt-1.5 text-xs text-gray-400 hover:text-gray-600 underline"
                            onClick={() => setEditedContent((prev) => ({ ...prev, [p.id]: p.ai_description }))}
                          >
                            Reset to original
                          </button>
                        )}
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
