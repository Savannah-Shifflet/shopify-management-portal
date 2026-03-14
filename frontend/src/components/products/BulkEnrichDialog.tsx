"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { enrichmentApi, templatesApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Sparkles, X, Loader2 } from "lucide-react";

const ENRICHABLE_FIELDS = [
  { key: "body_html", label: "Description (body_html)" },
  { key: "tags", label: "Tags" },
  { key: "title", label: "Title" },
  { key: "seo_title", label: "SEO Title" },
  { key: "seo_description", label: "SEO Description" },
];

interface BulkEnrichDialogProps {
  productIds: string[];
  onClose: () => void;
  onQueued: (count: number) => void;
}

export function BulkEnrichDialog({ productIds, onClose, onQueued }: BulkEnrichDialogProps) {
  const [selectedFields, setSelectedFields] = useState<Set<string>>(
    new Set(ENRICHABLE_FIELDS.map((f) => f.key))
  );
  const [templateId, setTemplateId] = useState<string>("");

  const { data: templatesData } = useQuery({
    queryKey: ["templates"],
    queryFn: () => templatesApi.list().then((r) => r.data as { id: string; name: string }[]),
  });
  const templates = templatesData ?? [];

  const enrichMutation = useMutation({
    mutationFn: () =>
      enrichmentApi.bulkEnrich(
        productIds,
        selectedFields.size === ENRICHABLE_FIELDS.length ? undefined : [...selectedFields],
        templateId || undefined,
      ),
    onSuccess: (res) => {
      onQueued(res.data.queued);
      onClose();
    },
  });

  const toggleField = (key: string) => {
    setSelectedFields((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  const bodyHtmlSelected = selectedFields.has("body_html");

  return (
    <>
      <div className="fixed inset-0 bg-black/40 z-50" onClick={onClose} />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-xl shadow-xl w-full max-w-md" onClick={(e) => e.stopPropagation()}>
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b">
            <div className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-blue-500" />
              <div>
                <h2 className="font-semibold">Bulk AI Enrichment</h2>
                <p className="text-xs text-gray-500">{productIds.length} product{productIds.length !== 1 ? "s" : ""} selected</p>
              </div>
            </div>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Fields */}
          <div className="px-6 py-4 space-y-4">
            <div>
              <p className="text-sm font-medium text-gray-700 mb-2">Fields to enrich</p>
              <div className="space-y-2">
                {ENRICHABLE_FIELDS.map((f) => (
                  <label key={f.key} className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedFields.has(f.key)}
                      onChange={() => toggleField(f.key)}
                      className="rounded"
                    />
                    <span className="text-sm text-gray-700">{f.label}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Template selector — only relevant when body_html is selected */}
            {bodyHtmlSelected && (
              <div>
                <p className="text-sm font-medium text-gray-700 mb-1">Description template <span className="font-normal text-gray-400">(optional)</span></p>
                <p className="text-xs text-gray-400 mb-2">If selected, AI will format the description using this template&apos;s section structure.</p>
                {templates.length === 0 ? (
                  <p className="text-xs text-gray-400 italic">
                    No templates yet.{" "}
                    <a href="/settings/templates" className="text-blue-500 hover:underline">Create one in Settings</a>{" "}
                    to use structured descriptions.
                  </p>
                ) : (
                  <select
                    value={templateId}
                    onChange={(e) => setTemplateId(e.target.value)}
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">No template (free-form)</option>
                    {templates.map((t) => (
                      <option key={t.id} value={t.id}>{t.name}</option>
                    ))}
                  </select>
                )}
              </div>
            )}

            {selectedFields.size === 0 && (
              <p className="text-xs text-amber-600">Select at least one field to enrich.</p>
            )}
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t bg-gray-50 flex gap-3">
            <Button
              onClick={() => enrichMutation.mutate()}
              disabled={selectedFields.size === 0 || enrichMutation.isPending}
            >
              {enrichMutation.isPending ? (
                <><Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />Queuing...</>
              ) : (
                <><Sparkles className="h-3.5 w-3.5 mr-1" />Enrich {productIds.length} Product{productIds.length !== 1 ? "s" : ""}</>
              )}
            </Button>
            <Button variant="outline" onClick={onClose}>Cancel</Button>
          </div>
        </div>
      </div>
    </>
  );
}
