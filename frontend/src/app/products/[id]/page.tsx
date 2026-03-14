"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { productsApi, enrichmentApi, syncApi, suppliersApi, templatesApi } from "@/lib/api";
import { PageShell } from "@/components/layout/PageShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EnrichmentPanel } from "@/components/products/EnrichmentPanel";
import { VariantEditor } from "@/components/products/VariantEditor";
import { PriceHistoryChart } from "@/components/products/PriceHistoryChart";
import {
  Sparkles, RefreshCw, CheckCircle, Save, ArrowLeft,
  ExternalLink, Package, Loader2, LayoutTemplate, Plus, Trash2, ChevronDown, ChevronUp, X,
} from "lucide-react";
import Link from "next/link";
import { cn, formatPrice, statusColor } from "@/lib/utils";
import type { Product } from "@/types/product";

export default function ProductDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const [showEnrichment, setShowEnrichment] = useState(false);
  const [form, setForm] = useState<Partial<Product>>({});
  const [isDirty, setIsDirty] = useState(false);
  const [isEnriching, setIsEnriching] = useState(false);
  const [descTab, setDescTab] = useState<"edit" | "preview">("edit");
  const [tagInput, setTagInput] = useState("");

  const { data: suppliersData } = useQuery({
    queryKey: ["suppliers"],
    queryFn: () => suppliersApi.list().then((r) => r.data?.suppliers ?? r.data ?? []),
  });

  const { data: product, isLoading } = useQuery({
    queryKey: ["product", id],
    queryFn: () => productsApi.get(id).then((r) => r.data),
    // Poll every 2s while Celery enrichment task is running
    refetchInterval: isEnriching ? 2000 : false,
  });

  // Initialize form on first load; don't overwrite while user is editing
  useEffect(() => {
    if (product && !isDirty) setForm(product as Product);
  }, [product]);

  // Open enrichment panel once the task completes
  useEffect(() => {
    if (isEnriching && product?.enrichment_status === "done") {
      setIsEnriching(false);
      setShowEnrichment(true);
    }
  }, [product?.enrichment_status, isEnriching]);

  const saveMutation = useMutation({
    mutationFn: (data: Partial<Product>) => productsApi.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["product", id] });
      qc.invalidateQueries({ queryKey: ["products"] });
      setIsDirty(false);
    },
  });

  const enrichMutation = useMutation({
    mutationFn: () => enrichmentApi.enrich(id),
    onSuccess: () => {
      // Start polling — panel opens automatically when enrichment_status becomes "done"
      setIsEnriching(true);
    },
  });

  const syncMutation = useMutation({
    mutationFn: () => syncApi.syncProduct(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["product", id] }),
  });

  const approveMutation = useMutation({
    mutationFn: () => productsApi.update(id, { status: "approved" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["product", id] }),
  });

  const [rescrapeDone, setRescrapesDone] = useState(false);
  const rescrapeMutation = useMutation({
    mutationFn: () => productsApi.rescrape(id),
    onSuccess: () => {
      setRescrapesDone(true);
      setTimeout(() => {
        setRescrapesDone(false);
        qc.invalidateQueries({ queryKey: ["product", id] });
      }, 3000);
    },
  });

  // ── Image management ─────────────────────────────────────────────────────
  const [imageUrlInput, setImageUrlInput] = useState("");

  const deleteImageMutation = useMutation({
    mutationFn: (imageId: string) => productsApi.images.delete(id, imageId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["product", id] }),
  });

  const addImageMutation = useMutation({
    mutationFn: (src: string) => productsApi.images.addByUrl(id, src),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["product", id] });
      setImageUrlInput("");
    },
  });

  // ── Template panel state ──────────────────────────────────────────────────
  type Section = { level: "h2" | "h3"; title: string; hint: string };
  type Template = { id: string; name: string; sections: Section[] };
  const EMPTY_SECTION = (): Section => ({ level: "h2", title: "", hint: "" });

  const [showTemplatePanel, setShowTemplatePanel] = useState(false);
  const [templateView, setTemplateView] = useState<"apply" | "manage">("apply");
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>("");
  const [aiFillMode, setAiFillMode] = useState(true);
  // Editor state for creating/editing a template
  const [editingTemplate, setEditingTemplate] = useState<Partial<Template> & { sections: Section[] } | null>(null);

  const { data: templatesData, refetch: refetchTemplates } = useQuery({
    queryKey: ["description-templates"],
    queryFn: () => templatesApi.list().then((r) => r.data as Template[]),
  });
  const templates: Template[] = templatesData ?? [];

  const aiFillMutation = useMutation({
    mutationFn: () => templatesApi.aiFill(selectedTemplateId, id),
    onSuccess: (res) => {
      setField("body_html", res.data.html);
      setShowTemplatePanel(false);
      setDescTab("preview");
    },
  });

  const saveTemplateMutation = useMutation({
    mutationFn: () => {
      if (!editingTemplate) return Promise.reject();
      if (editingTemplate.id) {
        return templatesApi.update(editingTemplate.id, { name: editingTemplate.name, sections: editingTemplate.sections });
      }
      return templatesApi.create({ name: editingTemplate.name ?? "New Template", sections: editingTemplate.sections });
    },
    onSuccess: () => { refetchTemplates(); setEditingTemplate(null); setTemplateView("apply"); },
  });

  const deleteTemplateMutation = useMutation({
    mutationFn: (tid: string) => templatesApi.delete(tid),
    onSuccess: () => { refetchTemplates(); if (editingTemplate) setEditingTemplate(null); setTemplateView("apply"); },
  });

  function applyEmptyStructure() {
    const t = templates.find((t) => t.id === selectedTemplateId);
    if (!t) return;
    const html = t.sections
      .map((s) => `<${s.level}>${s.title}</${s.level}>\n<p></p>`)
      .join("\n");
    setField("body_html", html);
    setShowTemplatePanel(false);
    setDescTab("edit");
  }

  const selectedTemplate = templates.find((t) => t.id === selectedTemplateId) ?? null;

  const setField = (field: keyof Product, value: unknown) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setIsDirty(true);
  };

  if (isLoading) {
    return (
      <PageShell title="Loading...">
        <div className="flex items-center justify-center h-48">
          <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
        </div>
      </PageShell>
    );
  }

  if (!product) {
    return <PageShell title="Not found"><p>Product not found.</p></PageShell>;
  }

  const p = product as Product;

  return (
    <PageShell
      title={p.title}
      description={
        <span className="flex items-center gap-2">
          <span className={cn("px-2 py-0.5 rounded-full text-xs font-medium capitalize", statusColor(p.status))}>
            {p.status}
          </span>
          <span className={cn("px-2 py-0.5 rounded-full text-xs font-medium", statusColor(p.sync_status))}>
            {p.sync_status.replace(/_/g, " ")}
          </span>
        </span>
      }
      actions={
        <div className="flex items-center gap-2">
          <Link href="/products">
            <Button variant="ghost" size="sm"><ArrowLeft className="h-4 w-4 mr-1" />Back</Button>
          </Link>
          {p.source_url && (
            <Button
              variant="outline" size="sm"
              onClick={() => rescrapeMutation.mutate()}
              disabled={rescrapeMutation.isPending || rescrapeDone}
            >
              {rescrapeMutation.isPending
                ? <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                : <RefreshCw className="h-4 w-4 mr-1" />}
              {rescrapeDone ? "Queued" : "Re-scrape"}
            </Button>
          )}
          <Button
            variant="outline" size="sm"
            onClick={() => enrichMutation.mutate()}
            disabled={enrichMutation.isPending || isEnriching}
          >
            {(enrichMutation.isPending || isEnriching)
              ? <Loader2 className="h-4 w-4 mr-1 animate-spin" />
              : <Sparkles className="h-4 w-4 mr-1" />}
            {isEnriching ? "Enriching..." : "AI Enrich"}
          </Button>
          {p.status !== "approved" && p.status !== "synced" && (
            <Button
              variant="outline" size="sm"
              onClick={() => approveMutation.mutate()}
              disabled={approveMutation.isPending}
            >
              <CheckCircle className="h-4 w-4 mr-1" /> Approve
            </Button>
          )}
          <Button
            variant="outline" size="sm"
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
          >
            {syncMutation.isPending
              ? <Loader2 className="h-4 w-4 mr-1 animate-spin" />
              : <RefreshCw className="h-4 w-4 mr-1" />}
            Sync to Shopify
          </Button>
          <Button
            size="sm"
            onClick={() => saveMutation.mutate(form)}
            disabled={saveMutation.isPending || !isDirty}
          >
            {saveMutation.isPending
              ? <Loader2 className="h-4 w-4 mr-1 animate-spin" />
              : <Save className="h-4 w-4 mr-1" />}
            Save
          </Button>
        </div>
      }
    >
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Main content — 2/3 width */}
        <div className="xl:col-span-2 space-y-6">
          {/* AI enrichment notification */}
          {isEnriching && (
            <div className="flex items-center gap-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <Loader2 className="h-4 w-4 text-blue-600 flex-shrink-0 animate-spin" />
              <p className="text-sm text-blue-700">AI enrichment in progress — this takes 10–30 seconds...</p>
            </div>
          )}
          {!isEnriching && p.ai_description && p.enrichment_status === "done" && (
            <div className="flex items-center gap-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <Sparkles className="h-4 w-4 text-blue-600 flex-shrink-0" />
              <p className="text-sm text-blue-700">AI suggestions are ready.</p>
              <Button
                size="sm" variant="outline" className="ml-auto border-blue-300 text-blue-700"
                onClick={() => setShowEnrichment(true)}
              >
                Review suggestions
              </Button>
            </div>
          )}

          {/* Basic info */}
          <Card>
            <CardHeader className="pb-4">
              <CardTitle className="text-base">Product Information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>Title</Label>
                <Input
                  className="mt-1"
                  value={form.title ?? ""}
                  onChange={(e) => setField("title", e.target.value)}
                />
              </div>
              <div>
                {/* Description header row */}
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-3">
                    <Label>Description</Label>
                    <div className="flex rounded border border-gray-200 overflow-hidden text-xs">
                      <button type="button" className={`px-2 py-0.5 ${descTab === "edit" ? "bg-gray-100 font-medium text-gray-800" : "text-gray-500 hover:bg-gray-50"}`} onClick={() => setDescTab("edit")}>Edit</button>
                      <button type="button" className={`px-2 py-0.5 border-l border-gray-200 ${descTab === "preview" ? "bg-gray-100 font-medium text-gray-800" : "text-gray-500 hover:bg-gray-50"}`} onClick={() => setDescTab("preview")}>Preview</button>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {p.ai_description && (
                      <button className="text-xs text-blue-600 hover:underline" onClick={() => setField("body_html", p.ai_description)}>
                        Use AI suggestion
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => { setShowTemplatePanel((v) => !v); setTemplateView("apply"); setEditingTemplate(null); }}
                      className={cn(
                        "flex items-center gap-1 text-xs px-2 py-0.5 rounded border transition-colors",
                        showTemplatePanel ? "bg-purple-50 border-purple-300 text-purple-700" : "border-gray-200 text-gray-500 hover:bg-gray-50"
                      )}
                    >
                      <LayoutTemplate className="h-3 w-3" />
                      Templates
                      {showTemplatePanel ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                    </button>
                  </div>
                </div>

                {/* ── Template panel ── */}
                {showTemplatePanel && (
                  <div className="mb-2 rounded-lg border border-purple-200 bg-purple-50 p-3 space-y-3">
                    {/* Panel tabs */}
                    <div className="flex items-center justify-between">
                      <div className="flex rounded border border-purple-200 overflow-hidden text-xs">
                        <button type="button" onClick={() => { setTemplateView("apply"); setEditingTemplate(null); }} className={`px-2.5 py-1 ${templateView === "apply" ? "bg-purple-600 text-white" : "text-purple-600 hover:bg-purple-100"}`}>Apply</button>
                        <button type="button" onClick={() => { setTemplateView("manage"); setEditingTemplate(null); }} className={`px-2.5 py-1 border-l border-purple-200 ${templateView === "manage" ? "bg-purple-600 text-white" : "text-purple-600 hover:bg-purple-100"}`}>Manage</button>
                      </div>
                      <button type="button" onClick={() => setShowTemplatePanel(false)} className="text-purple-400 hover:text-purple-600"><X className="h-4 w-4" /></button>
                    </div>

                    {/* ── APPLY VIEW ── */}
                    {templateView === "apply" && (
                      <>
                        {templates.length === 0 ? (
                          <p className="text-xs text-purple-600 italic">No templates yet — create one in the Manage tab.</p>
                        ) : (
                          <>
                            <div className="flex items-center gap-2">
                              <select
                                value={selectedTemplateId}
                                onChange={(e) => setSelectedTemplateId(e.target.value)}
                                className="flex-1 text-xs rounded border border-purple-200 bg-white px-2 py-1.5 text-gray-700 focus:outline-none focus:ring-1 focus:ring-purple-400"
                              >
                                <option value="">— select a template —</option>
                                {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                              </select>
                            </div>

                            {/* Section preview */}
                            {selectedTemplate && (
                              <div className="flex flex-wrap gap-1">
                                {selectedTemplate.sections.map((s, i) => (
                                  <span key={i} className={cn(
                                    "px-2 py-0.5 rounded text-xs font-medium",
                                    s.level === "h2" ? "bg-purple-200 text-purple-800" : "bg-purple-100 text-purple-600 ml-2"
                                  )}>
                                    {s.level === "h2" ? "▣" : "▷"} {s.title}
                                  </span>
                                ))}
                              </div>
                            )}

                            {/* Mode toggle */}
                            <div className="flex items-center gap-3 pt-1">
                              <label className="flex items-center gap-1.5 text-xs text-purple-700 cursor-pointer">
                                <input type="radio" name="tpl-mode" checked={!aiFillMode} onChange={() => setAiFillMode(false)} />
                                Insert empty structure
                              </label>
                              <label className="flex items-center gap-1.5 text-xs text-purple-700 cursor-pointer">
                                <input type="radio" name="tpl-mode" checked={aiFillMode} onChange={() => setAiFillMode(true)} />
                                <Sparkles className="h-3 w-3" /> AI-fill from existing content
                              </label>
                            </div>
                            {aiFillMode && (
                              <p className="text-xs text-purple-500">
                                Claude will read the current description and AI data, then rewrite it into the template sections.
                              </p>
                            )}

                            <div className="flex gap-2 pt-1">
                              <Button
                                size="sm"
                                disabled={!selectedTemplateId || aiFillMutation.isPending}
                                onClick={() => aiFillMode ? aiFillMutation.mutate() : applyEmptyStructure()}
                                className="bg-purple-600 hover:bg-purple-700 text-white h-7 text-xs"
                              >
                                {aiFillMutation.isPending
                                  ? <><Loader2 className="h-3 w-3 mr-1 animate-spin" /> Generating…</>
                                  : <><LayoutTemplate className="h-3 w-3 mr-1" /> Apply template</>}
                              </Button>
                              {aiFillMutation.isError && (
                                <span className="text-xs text-red-600 self-center">
                                  {(aiFillMutation.error as any)?.response?.data?.detail ?? "Failed"}
                                </span>
                              )}
                            </div>
                          </>
                        )}
                      </>
                    )}

                    {/* ── MANAGE VIEW ── */}
                    {templateView === "manage" && !editingTemplate && (
                      <div className="space-y-2">
                        {templates.length === 0 && (
                          <p className="text-xs text-purple-500 italic">No templates yet.</p>
                        )}
                        {templates.map((t) => (
                          <div key={t.id} className="flex items-center justify-between bg-white rounded border border-purple-100 px-3 py-2">
                            <div>
                              <p className="text-xs font-medium text-gray-800">{t.name}</p>
                              <p className="text-xs text-gray-400">{t.sections.length} sections</p>
                            </div>
                            <div className="flex gap-1">
                              <button type="button" onClick={() => setEditingTemplate({ ...t, sections: t.sections.map((s) => ({ ...s })) })} className="text-xs text-purple-600 hover:underline px-1">Edit</button>
                              <button type="button" onClick={() => deleteTemplateMutation.mutate(t.id)} className="text-xs text-red-500 hover:text-red-700 px-1">Delete</button>
                            </div>
                          </div>
                        ))}
                        <button
                          type="button"
                          onClick={() => setEditingTemplate({ name: "", sections: [{ level: "h2", title: "", hint: "" }] })}
                          className="flex items-center gap-1 text-xs text-purple-700 hover:text-purple-900 pt-1"
                        >
                          <Plus className="h-3 w-3" /> New template
                        </button>
                      </div>
                    )}

                    {/* ── TEMPLATE EDITOR ── */}
                    {templateView === "manage" && editingTemplate && (
                      <div className="space-y-2">
                        <div className="flex items-center gap-2">
                          <button type="button" onClick={() => setEditingTemplate(null)} className="text-xs text-purple-500 hover:text-purple-700">← Back</button>
                          <input
                            type="text"
                            placeholder="Template name"
                            value={editingTemplate.name ?? ""}
                            onChange={(e) => setEditingTemplate({ ...editingTemplate, name: e.target.value })}
                            className="flex-1 text-xs rounded border border-purple-200 bg-white px-2 py-1 focus:outline-none focus:ring-1 focus:ring-purple-400"
                          />
                        </div>

                        <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                          {editingTemplate.sections.map((s, i) => (
                            <div key={i} className="flex items-center gap-1.5 bg-white rounded border border-purple-100 px-2 py-1.5">
                              <select
                                value={s.level}
                                onChange={(e) => {
                                  const secs = [...editingTemplate.sections];
                                  secs[i] = { ...secs[i], level: e.target.value as "h2" | "h3" };
                                  setEditingTemplate({ ...editingTemplate, sections: secs });
                                }}
                                className="text-xs rounded border border-purple-200 bg-purple-50 px-1 py-0.5 text-purple-700 font-medium w-14"
                              >
                                <option value="h2">H2 tab</option>
                                <option value="h3">H3 drop</option>
                              </select>
                              <input
                                type="text"
                                placeholder="Section title"
                                value={s.title}
                                onChange={(e) => {
                                  const secs = [...editingTemplate.sections];
                                  secs[i] = { ...secs[i], title: e.target.value };
                                  setEditingTemplate({ ...editingTemplate, sections: secs });
                                }}
                                className="flex-1 text-xs rounded border border-gray-200 px-2 py-0.5 focus:outline-none focus:ring-1 focus:ring-purple-300"
                              />
                              <input
                                type="text"
                                placeholder="AI hint (optional)"
                                value={s.hint}
                                onChange={(e) => {
                                  const secs = [...editingTemplate.sections];
                                  secs[i] = { ...secs[i], hint: e.target.value };
                                  setEditingTemplate({ ...editingTemplate, sections: secs });
                                }}
                                className="w-36 text-xs rounded border border-gray-200 px-2 py-0.5 text-gray-400 focus:outline-none focus:ring-1 focus:ring-purple-300"
                              />
                              <button type="button" onClick={() => setEditingTemplate({ ...editingTemplate, sections: editingTemplate.sections.filter((_, j) => j !== i) })} className="text-gray-300 hover:text-red-500">
                                <X className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          ))}
                        </div>

                        <div className="flex items-center gap-2 flex-wrap pt-1">
                          <button type="button" onClick={() => setEditingTemplate({ ...editingTemplate, sections: [...editingTemplate.sections, { level: "h2", title: "", hint: "" }] })} className="flex items-center gap-1 text-xs text-purple-600 hover:text-purple-800 border border-dashed border-purple-300 rounded px-2 py-0.5">
                            <Plus className="h-3 w-3" /> H2 tab
                          </button>
                          <button type="button" onClick={() => setEditingTemplate({ ...editingTemplate, sections: [...editingTemplate.sections, { level: "h3", title: "", hint: "" }] })} className="flex items-center gap-1 text-xs text-purple-600 hover:text-purple-800 border border-dashed border-purple-300 rounded px-2 py-0.5">
                            <Plus className="h-3 w-3" /> H3 dropdown
                          </button>
                          <div className="ml-auto flex gap-2">
                            {editingTemplate.id && (
                              <button type="button" onClick={() => deleteTemplateMutation.mutate(editingTemplate.id!)} className="text-xs text-red-500 hover:text-red-700">Delete</button>
                            )}
                            <Button
                              size="sm"
                              disabled={!editingTemplate.name?.trim() || saveTemplateMutation.isPending}
                              onClick={() => saveTemplateMutation.mutate()}
                              className="bg-purple-600 hover:bg-purple-700 text-white h-6 text-xs px-3"
                            >
                              {saveTemplateMutation.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : "Save"}
                            </Button>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Editor / Preview */}
                {descTab === "edit" ? (
                  <Textarea
                    rows={8}
                    value={form.body_html ?? ""}
                    onChange={(e) => setField("body_html", e.target.value)}
                    placeholder="Product description (HTML supported)"
                  />
                ) : (
                  <div
                    className="min-h-[10rem] rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-sm prose prose-sm max-w-none overflow-auto"
                    dangerouslySetInnerHTML={{ __html: form.body_html || "<p class='text-gray-400 italic'>No description yet.</p>" }}
                  />
                )}
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Vendor / Brand</Label>
                  <Input
                    className="mt-1"
                    value={form.vendor ?? ""}
                    onChange={(e) => setField("vendor", e.target.value)}
                  />
                </div>
                <div>
                  <Label>Product Type</Label>
                  <Input
                    className="mt-1"
                    value={form.product_type ?? ""}
                    onChange={(e) => setField("product_type", e.target.value)}
                  />
                </div>
              </div>
              <div>
                <Label>Tags</Label>
                <div className="mt-1 min-h-[2.25rem] flex flex-wrap gap-1 items-center px-2 py-1.5 rounded-md border border-input bg-background focus-within:ring-1 focus-within:ring-ring">
                  {(form.tags ?? []).map((t) => (
                    <span key={t} className="inline-flex items-center gap-1 bg-gray-100 text-gray-700 text-xs px-2 py-0.5 rounded-full">
                      {t}
                      <button
                        type="button"
                        className="text-gray-400 hover:text-gray-600 leading-none"
                        onClick={() => setField("tags", (form.tags ?? []).filter((x) => x !== t))}
                      >×</button>
                    </span>
                  ))}
                  <input
                    className="flex-1 min-w-[80px] text-sm bg-transparent outline-none placeholder:text-muted-foreground"
                    placeholder={(form.tags ?? []).length === 0 ? "Type a tag and press Enter or comma" : "Add tag…"}
                    value={tagInput}
                    onChange={(e) => setTagInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === ",") {
                        e.preventDefault();
                        const val = tagInput.trim().replace(/,$/, "");
                        if (val && !(form.tags ?? []).includes(val)) {
                          setField("tags", [...(form.tags ?? []), val]);
                        }
                        setTagInput("");
                      } else if (e.key === "Backspace" && !tagInput && (form.tags ?? []).length > 0) {
                        setField("tags", (form.tags ?? []).slice(0, -1));
                      }
                    }}
                    onBlur={() => {
                      const val = tagInput.trim().replace(/,$/, "");
                      if (val && !(form.tags ?? []).includes(val)) {
                        setField("tags", [...(form.tags ?? []), val]);
                      }
                      setTagInput("");
                    }}
                  />
                </div>
                {p.ai_tags && p.ai_tags.filter((t) => !(form.tags ?? []).includes(t)).length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    <span className="text-xs text-gray-400">AI suggests:</span>
                    {p.ai_tags.filter((t) => !(form.tags ?? []).includes(t)).map((t) => (
                      <button
                        key={t}
                        type="button"
                        className="text-xs bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded hover:bg-blue-100"
                        onClick={() => setField("tags", [...(form.tags ?? []), t])}
                      >
                        + {t}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* SEO */}
          <Card>
            <CardHeader className="pb-4">
              <CardTitle className="text-base">SEO</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>SEO Title <span className="text-xs text-gray-400">(max 70 chars)</span></Label>
                <Input
                  className="mt-1"
                  value={form.seo_title ?? ""}
                  onChange={(e) => setField("seo_title", e.target.value)}
                  maxLength={70}
                />
                <p className="text-xs text-gray-400 mt-1">{(form.seo_title ?? "").length}/70</p>
              </div>
              <div>
                <Label>SEO Description <span className="text-xs text-gray-400">(max 160 chars)</span></Label>
                <Textarea
                  rows={2}
                  className="mt-1"
                  value={form.seo_description ?? ""}
                  onChange={(e) => setField("seo_description", e.target.value)}
                  maxLength={160}
                />
                <p className="text-xs text-gray-400 mt-1">{(form.seo_description ?? "").length}/160</p>
              </div>
            </CardContent>
          </Card>

          {/* Variants */}
          <VariantEditor productId={id} variants={p.variants} options={p.options} />
        </div>

        {/* Sidebar — 1/3 width */}
        <div className="space-y-6">
          {/* Product status */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <Label className="text-xs text-gray-500">Product Status</Label>
                <Select
                  className="mt-1"
                  value={form.status ?? p.status}
                  onChange={(e) => setField("status", e.target.value)}
                >
                  <option value="draft">Draft</option>
                  <option value="enriched">Enriched</option>
                  <option value="approved">Approved</option>
                  <option value="archived">Archived</option>
                </Select>
              </div>
              <div>
                <Label className="text-xs text-gray-500">Supplier</Label>
                <Select
                  className="mt-1"
                  value={form.supplier_id ?? p.supplier_id ?? ""}
                  onChange={(e) => setField("supplier_id", e.target.value || null)}
                >
                  <option value="">— None —</option>
                  {(suppliersData ?? []).map((s: any) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </Select>
              </div>
              {p.source_url && (
                <div>
                  <Label className="text-xs text-gray-500">Source</Label>
                  <a
                    href={p.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-xs text-blue-600 hover:underline mt-1 truncate"
                  >
                    <ExternalLink className="h-3 w-3 flex-shrink-0" />
                    {p.source_url}
                  </a>
                </div>
              )}
              {p.shopify_product_id && (
                <div>
                  <Label className="text-xs text-gray-500">Shopify ID</Label>
                  <p className="text-xs font-mono mt-1">{p.shopify_product_id}</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Pricing */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Pricing</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {/* MAP Warning */}
              {(() => {
                const bp = parseFloat(String(form.base_price ?? ""));
                const mp = parseFloat(String(form.map_price ?? p.map_price ?? ""));
                if (!isNaN(bp) && !isNaN(mp) && bp < mp) {
                  return (
                    <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                      <span className="font-bold">⚠</span>
                      <span>Price is below MAP (${mp.toFixed(2)}). Check your reseller agreement.</span>
                    </div>
                  );
                }
                return null;
              })()}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs">Cost Price</Label>
                  <Input
                    className="mt-1"
                    type="number"
                    step="0.01"
                    value={form.cost_price ?? ""}
                    onChange={(e) => setField("cost_price", e.target.value)}
                    placeholder="0.00"
                  />
                </div>
                <div>
                  <Label className="text-xs">Retail Price</Label>
                  <Input
                    className="mt-1"
                    type="number"
                    step="0.01"
                    value={form.base_price ?? ""}
                    onChange={(e) => setField("base_price", e.target.value)}
                    placeholder="0.00"
                  />
                </div>
              </div>
              {/* Margin badge */}
              {(() => {
                const bp = parseFloat(String(form.base_price ?? ""));
                const cp = parseFloat(String(form.cost_price ?? ""));
                if (!isNaN(bp) && !isNaN(cp) && bp > 0 && cp > 0) {
                  const margin = ((bp - cp) / bp) * 100;
                  const cls = margin >= 25 ? "bg-green-100 text-green-700" : margin >= 10 ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-700";
                  return (
                    <p className="text-xs">
                      Margin: <span className={`px-2 py-0.5 rounded font-medium ${cls}`}>{margin.toFixed(1)}%</span>
                    </p>
                  );
                }
                return null;
              })()}
              <div>
                <Label className="text-xs">MAP (Min Advertised Price)</Label>
                <Input
                  className="mt-1"
                  type="number"
                  step="0.01"
                  value={form.map_price ?? p.map_price ?? ""}
                  onChange={(e) => setField("map_price", e.target.value)}
                  placeholder="0.00"
                />
              </div>
              <div>
                <Label className="text-xs">Compare At Price</Label>
                <Input
                  className="mt-1"
                  type="number"
                  step="0.01"
                  value={form.compare_at_price ?? ""}
                  onChange={(e) => setField("compare_at_price", e.target.value)}
                  placeholder="0.00"
                />
              </div>
              {(form.supplier_id ?? p.supplier_id) && (
                <div className="pt-2 border-t space-y-1.5">
                  {p.supplier_price ? (
                    <p className="text-xs text-gray-500">
                      Supplier price: <strong>{formatPrice(Number(p.supplier_price))}</strong>
                      {p.supplier_price_at && (
                        <span className="text-gray-400 ml-1">
                          (updated {new Date(p.supplier_price_at).toLocaleDateString()})
                        </span>
                      )}
                    </p>
                  ) : (
                    <p className="text-xs text-gray-400">No supplier price on file yet — save to enable tracking.</p>
                  )}
                  <label className="flex items-center gap-1.5 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      className="w-3.5 h-3.5 accent-blue-600"
                      checked={!!form.use_supplier_price}
                      onChange={(e) => {
                        setField("use_supplier_price", e.target.checked);
                        if (e.target.checked && p.supplier_price) setField("base_price", p.supplier_price);
                      }}
                    />
                    <span className="text-xs text-gray-600">Track supplier price <span className="text-gray-400">(auto-syncs daily)</span></span>
                  </label>
                </div>
              )}
            </CardContent>
          </Card>

          {/* AI Attributes */}
          {p.ai_attributes && Object.keys(p.ai_attributes).length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-1.5">
                  <Sparkles className="h-4 w-4 text-blue-500" /> AI Attributes
                </CardTitle>
              </CardHeader>
              <CardContent>
                <dl className="space-y-1.5">
                  {Object.entries(p.ai_attributes).map(([k, v]) => (
                    <div key={k} className="flex gap-2 text-xs">
                      <dt className="font-medium text-gray-500 capitalize min-w-[90px]">{k}:</dt>
                      <dd className="text-gray-700">{String(v)}</dd>
                    </div>
                  ))}
                </dl>
              </CardContent>
            </Card>
          )}

          {/* Price History */}
          <PriceHistoryChart productId={id} />

          {/* Images */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">
                Images {p.images.length > 0 && <span className="text-sm font-normal text-gray-400">({p.images.length})</span>}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {p.images.length > 0 ? (
                <div className="grid grid-cols-3 gap-2 mb-3">
                  {p.images.map((img) => (
                    <div key={img.id} className="relative group aspect-square rounded overflow-hidden bg-gray-100">
                      <img src={img.src} alt={img.alt ?? ""} className="w-full h-full object-cover" />
                      <button
                        onClick={() => deleteImageMutation.mutate(img.id)}
                        disabled={deleteImageMutation.isPending}
                        className="absolute top-1 right-1 bg-black/60 hover:bg-black/80 text-white rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
                        title="Remove image"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-400 italic mb-3">No images yet.</p>
              )}
              <div className="flex gap-2">
                <Input
                  placeholder="https://example.com/image.jpg"
                  value={imageUrlInput}
                  onChange={(e) => setImageUrlInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && imageUrlInput.trim()) {
                      e.preventDefault();
                      addImageMutation.mutate(imageUrlInput.trim());
                    }
                  }}
                  className="flex-1 text-xs"
                />
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => addImageMutation.mutate(imageUrlInput.trim())}
                  disabled={!imageUrlInput.trim() || addImageMutation.isPending}
                >
                  {addImageMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Enrichment panel slide-over */}
      {showEnrichment && (
        <EnrichmentPanel
          product={p}
          onClose={() => setShowEnrichment(false)}
          onAccept={(fields) => {
            saveMutation.mutate(fields);
            setShowEnrichment(false);
          }}
        />
      )}
    </PageShell>
  );
}
