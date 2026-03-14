"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { X, Check, Sparkles, ChevronDown, ChevronUp } from "lucide-react";
import type { Product } from "@/types/product";

interface EnrichmentPanelProps {
  product: Product;
  onClose: () => void;
  onAccept: (fields: Partial<Product>) => void;
}

interface FieldSuggestion {
  key: keyof Product;
  label: string;
  current: string | null;
  suggested: string | null;
}

export function EnrichmentPanel({ product, onClose, onAccept }: EnrichmentPanelProps) {
  const suggestions: FieldSuggestion[] = [
    {
      key: "body_html",
      label: "Description",
      current: product.body_html || null,
      suggested: product.ai_description || null,
    },
    {
      key: "tags",
      label: "Tags",
      current: (product.tags || []).join(", ") || null,
      suggested: (product.ai_tags || []).join(", ") || null,
    },
    // SEO fields are auto-applied directly by the enrichment task (no separate ai_seo_* columns).
    // They appear pre-filled in the product form's SEO section — no review step needed here.
  ].filter((s) => s.suggested);

  const [accepted, setAccepted] = useState<Set<keyof Product>>(new Set());
  const [expanded, setExpanded] = useState<Set<string>>(new Set(["body_html"]));

  const toggleAccept = (key: keyof Product) => {
    setAccepted((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  const acceptAll = () => {
    setAccepted(new Set(suggestions.map((s) => s.key)));
  };

  const handleApply = () => {
    const fields: Partial<Product> = {};
    if (accepted.has("body_html") && product.ai_description) {
      fields.body_html = product.ai_description;
    }
    if (accepted.has("tags") && product.ai_tags) {
      fields.tags = product.ai_tags;
    }
    onAccept(fields);
  };

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/30 z-40" onClick={onClose} />

      {/* Drawer */}
      <div className="fixed right-0 top-0 h-full w-full max-w-2xl bg-white shadow-xl z-50 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-blue-500" />
            <div>
              <h2 className="font-semibold">AI Enrichment Suggestions</h2>
              <p className="text-xs text-gray-500">Review and accept AI-generated content</p>
            </div>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 px-6 py-3 border-b bg-gray-50">
          <Button size="sm" variant="outline" onClick={acceptAll}>
            <Check className="h-3.5 w-3.5 mr-1" /> Accept All
          </Button>
          <span className="text-xs text-gray-400 ml-auto">
            {accepted.size} of {suggestions.length} accepted
          </span>
        </div>

        {/* Suggestions */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {suggestions.map((s) => {
            const isExpanded = expanded.has(s.key as string);
            const isAccepted = accepted.has(s.key);

            return (
              <div
                key={s.key as string}
                className={`border rounded-lg overflow-hidden transition-colors ${
                  isAccepted ? "border-green-300 bg-green-50" : "border-gray-200"
                }`}
              >
                {/* Field header */}
                <div className="flex items-center gap-3 px-4 py-3">
                  <button
                    className="flex-1 flex items-center gap-2 text-left"
                    onClick={() =>
                      setExpanded((prev) => {
                        const next = new Set(prev);
                        next.has(s.key as string) ? next.delete(s.key as string) : next.add(s.key as string);
                        return next;
                      })
                    }
                  >
                    <span className="font-medium text-sm">{s.label}</span>
                    {isExpanded ? (
                      <ChevronUp className="h-4 w-4 text-gray-400" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-gray-400" />
                    )}
                  </button>
                  <Button
                    size="sm"
                    variant={isAccepted ? "default" : "outline"}
                    className={isAccepted ? "bg-green-600 hover:bg-green-700" : ""}
                    onClick={() => toggleAccept(s.key)}
                  >
                    {isAccepted ? (
                      <><Check className="h-3.5 w-3.5 mr-1" />Accepted</>
                    ) : (
                      "Accept"
                    )}
                  </Button>
                </div>

                {/* Diff content */}
                {isExpanded && (
                  <div className="border-t grid grid-cols-2 gap-0">
                    <div className="p-4 border-r">
                      <p className="text-xs font-medium text-gray-400 uppercase mb-2">Current</p>
                      {s.current ? (
                        <p className="text-sm text-gray-700 whitespace-pre-wrap line-clamp-6"
                           dangerouslySetInnerHTML={{ __html: s.current }} />
                      ) : (
                        <p className="text-sm text-gray-400 italic">Empty</p>
                      )}
                    </div>
                    <div className="p-4 bg-blue-50/50">
                      <p className="text-xs font-medium text-blue-500 uppercase mb-2">AI Suggestion</p>
                      {s.suggested ? (
                        <p className="text-sm text-gray-700 whitespace-pre-wrap line-clamp-6"
                           dangerouslySetInnerHTML={{ __html: s.suggested }} />
                      ) : (
                        <p className="text-sm text-gray-400 italic">No suggestion</p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}

          {/* AI Attributes preview */}
          {product.ai_attributes && Object.keys(product.ai_attributes).length > 0 && (
            <div className="border rounded-lg p-4">
              <p className="font-medium text-sm mb-3 flex items-center gap-1.5">
                <Sparkles className="h-4 w-4 text-blue-500" /> Extracted Attributes
              </p>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
                {Object.entries(product.ai_attributes).map(([k, v]) => (
                  <div key={k} className="text-xs">
                    <dt className="font-medium text-gray-500 capitalize">{k}</dt>
                    <dd className="text-gray-700">{String(v)}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t bg-gray-50 flex gap-3">
          <Button onClick={handleApply} disabled={accepted.size === 0}>
            Apply {accepted.size} Change{accepted.size !== 1 ? "s" : ""}
          </Button>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
        </div>
      </div>
    </>
  );
}
