"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { X, Check, Sparkles, ChevronDown, ChevronUp, Eye, Pencil } from "lucide-react";
import { cn } from "@/lib/utils";
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
  isHtml: boolean;
}

export function EnrichmentPanel({ product, onClose, onAccept }: EnrichmentPanelProps) {
  const suggestions: FieldSuggestion[] = [
    {
      key: "body_html",
      label: "Description",
      current: product.body_html || null,
      suggested: product.ai_description || null,
      isHtml: true,
    },
    {
      key: "tags",
      label: "Tags",
      current: (product.tags || []).join(", ") || null,
      suggested: (product.ai_tags || []).join(", ") || null,
      isHtml: false,
    },
  ].filter((s) => s.suggested);

  const [accepted, setAccepted] = useState<Set<keyof Product>>(new Set());
  const [expanded, setExpanded] = useState<Set<string>>(new Set(["body_html"]));
  const [editMode, setEditMode] = useState<Set<string>>(new Set());
  const [editedContent, setEditedContent] = useState<Record<string, string>>({});

  const getContent = (key: string, original: string | null): string =>
    editedContent[key] !== undefined ? editedContent[key] : original ?? "";

  const isEdited = (key: string, original: string | null) =>
    editedContent[key] !== undefined && editedContent[key] !== (original ?? "");

  const toggleAccept = (key: keyof Product) => {
    setAccepted((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  const acceptAll = () => setAccepted(new Set(suggestions.map((s) => s.key)));

  const handleApply = () => {
    const fields: Partial<Product> = {
      ai_description: null,  // always clear the suggestion on accept
    };
    if (accepted.has("body_html")) {
      fields.body_html = getContent("body_html", product.ai_description);
    }
    if (accepted.has("tags")) {
      const raw = getContent("tags", (product.ai_tags || []).join(", "));
      fields.tags = raw.split(",").map((t) => t.trim()).filter(Boolean) as any;
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
              <p className="text-xs text-gray-500">Review, edit, and accept AI-generated content</p>
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
            const key = s.key as string;
            const isExpandedField = expanded.has(key);
            const isAccepted = accepted.has(s.key);
            const isEditingField = editMode.has(key);
            const currentContent = getContent(key, s.suggested);
            const edited = isEdited(key, s.suggested);

            return (
              <div
                key={key}
                className={cn(
                  "border rounded-lg overflow-hidden transition-colors",
                  isAccepted ? "border-green-300 bg-green-50" : "border-gray-200"
                )}
              >
                {/* Field header */}
                <div className="flex items-center gap-3 px-4 py-3">
                  <button
                    className="flex-1 flex items-center gap-2 text-left"
                    onClick={() =>
                      setExpanded((prev) => {
                        const next = new Set(prev);
                        next.has(key) ? next.delete(key) : next.add(key);
                        return next;
                      })
                    }
                  >
                    <span className="font-medium text-sm">{s.label}</span>
                    {edited && (
                      <span className="text-xs bg-blue-100 text-blue-600 px-1.5 py-0.5 rounded font-medium">Edited</span>
                    )}
                    {isExpandedField ? (
                      <ChevronUp className="h-4 w-4 text-gray-400 ml-auto" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-gray-400 ml-auto" />
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
                {isExpandedField && (
                  <div className="border-t grid grid-cols-2 gap-0">
                    {/* Current */}
                    <div className="p-4 border-r overflow-y-auto max-h-96">
                      <p className="text-xs font-medium text-gray-400 uppercase mb-2">Current</p>
                      {s.current ? (
                        s.isHtml ? (
                          <div
                            className="text-sm text-gray-700 prose prose-sm max-w-none"
                            dangerouslySetInnerHTML={{ __html: s.current }}
                          />
                        ) : (
                          <p className="text-sm text-gray-700">{s.current}</p>
                        )
                      ) : (
                        <p className="text-sm text-gray-400 italic">Empty</p>
                      )}
                    </div>

                    {/* AI Suggestion (editable) */}
                    <div className="p-4 bg-blue-50/50 overflow-y-auto max-h-96">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <p className="text-xs font-medium text-blue-500 uppercase">AI Suggestion</p>
                          {edited && (
                            <span className="text-xs bg-blue-100 text-blue-600 px-1.5 py-0.5 rounded font-medium">Edited</span>
                          )}
                        </div>
                        {s.isHtml && (
                          <button
                            onClick={() =>
                              setEditMode((prev) => {
                                const next = new Set(prev);
                                next.has(key) ? next.delete(key) : next.add(key);
                                // Seed on first edit
                                if (!next.has(key)) return next;
                                if (editedContent[key] === undefined) {
                                  setEditedContent((p) => ({ ...p, [key]: s.suggested ?? "" }));
                                }
                                return next;
                              })
                            }
                            className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-700"
                          >
                            {isEditingField
                              ? <><Eye className="h-3 w-3" />Preview</>
                              : <><Pencil className="h-3 w-3" />Edit HTML</>}
                          </button>
                        )}
                      </div>

                      {isEditingField ? (
                        <>
                          <textarea
                            className="w-full text-xs font-mono bg-gray-900 text-green-300 rounded p-2 min-h-[200px] resize-y border-0 outline-none focus:ring-1 focus:ring-blue-400"
                            value={currentContent}
                            onChange={(e) =>
                              setEditedContent((prev) => ({ ...prev, [key]: e.target.value }))
                            }
                            spellCheck={false}
                          />
                          {edited && (
                            <button
                              className="mt-1.5 text-xs text-gray-400 hover:text-gray-600 underline"
                              onClick={() =>
                                setEditedContent((prev) => ({ ...prev, [key]: s.suggested ?? "" }))
                              }
                            >
                              Reset to original
                            </button>
                          )}
                        </>
                      ) : s.isHtml ? (
                        <div
                          className="text-sm text-gray-700 prose prose-sm max-w-none"
                          dangerouslySetInnerHTML={{ __html: currentContent }}
                        />
                      ) : (
                        <p className="text-sm text-gray-700">{currentContent}</p>
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
