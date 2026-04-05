"use client";

import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { templatesApi, productsApi } from "@/lib/api";
import { PageShell } from "@/components/layout/PageShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Plus, Trash2, Edit2, ChevronUp, ChevronDown, Save, X, Sparkles, ArrowRight, IndentIncrease, IndentDecrease, Loader2, ClipboardCheck } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

type SectionTag = "h2" | "h3" | "p" | "ul" | "ol" | "table";

const TAG_OPTIONS: { value: SectionTag; label: string; desc: string }[] = [
  { value: "h2", label: "H2",    desc: "Heading 2 — Tab" },
  { value: "h3", label: "H3",    desc: "Heading 3 — Sub-section" },
  { value: "p",  label: "P",     desc: "Paragraph" },
  { value: "ul", label: "UL",    desc: "Bullet List" },
  { value: "ol", label: "OL",    desc: "Numbered List" },
  { value: "table", label: "Table", desc: "Specs Table" },
];

const TAG_COLOR: Record<SectionTag, string> = {
  h2:    "bg-blue-100 text-blue-700",
  h3:    "bg-indigo-100 text-indigo-700",
  p:     "bg-gray-100 text-gray-600",
  ul:    "bg-emerald-100 text-emerald-700",
  ol:    "bg-teal-100 text-teal-700",
  table: "bg-orange-100 text-orange-700",
};

interface Section {
  tag: SectionTag;
  title: string;
  hint: string;
  required: boolean;
  indent: number;
}

interface Template {
  id: string;
  name: string;
  sections: Section[];
}

const emptySection = (): Section => ({ tag: "h2", title: "", hint: "", required: true, indent: 0 });

const MAX_INDENT = 2;

function normalizeSection(s: any): Section {
  const tag: SectionTag = s.tag ?? (s.level === "h3" ? "h3" : "h2");
  return {
    tag,
    title: s.title ?? "",
    hint: s.hint ?? "",
    required: s.required !== false,
    indent: s.indent ?? 0,
  };
}

interface TemplateStats {
  processing: number;
  pendingReview: number;
  applied: number;
  failed: number;
  total: number;
}

export default function TemplatesPage() {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<string | null>(null);
  const [formName, setFormName] = useState("");
  const [formSections, setFormSections] = useState<Section[]>([emptySection()]);

  const { data: templates = [], isLoading } = useQuery<Template[]>({
    queryKey: ["templates"],
    queryFn: () => templatesApi.list().then((r) => r.data),
  });

  const { data: productsData } = useQuery({
    queryKey: ["products-for-template-progress"],
    queryFn: () => productsApi.list({ page: 1, page_size: 10000 }).then((r) => r.data),
    refetchInterval: (query) => {
      const items: any[] = query.state.data?.items ?? [];
      const anyProcessing = items.some(
        (p: any) => p.applied_template_id && (p.enrichment_status === "pending" || p.enrichment_status === "running")
      );
      return anyProcessing ? 3000 : false;
    },
  });

  const allProducts: any[] = productsData?.items ?? [];

  // Per-template enrichment stats derived from the flat products list
  const templateStats = useMemo(() => {
    const stats: Record<string, TemplateStats> = {};
    for (const p of allProducts) {
      if (!p.applied_template_id) continue;
      const tid = p.applied_template_id;
      if (!stats[tid]) stats[tid] = { processing: 0, pendingReview: 0, applied: 0, failed: 0, total: 0 };
      stats[tid].total++;
      if (p.enrichment_status === "pending" || p.enrichment_status === "running") {
        stats[tid].processing++;
      } else if (p.enrichment_status === "failed") {
        stats[tid].failed++;
      } else if (p.enrichment_status === "done" && p.ai_description) {
        stats[tid].pendingReview++;
      } else if (p.enrichment_status === "done" && !p.ai_description) {
        stats[tid].applied++;
      }
    }
    return stats;
  }, [allProducts]);

  const createMutation = useMutation({
    mutationFn: () => templatesApi.create({ name: formName.trim(), sections: formSections }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["templates"] }); resetForm(); },
  });

  const updateMutation = useMutation({
    mutationFn: (id: string) => templatesApi.update(id, { name: formName.trim(), sections: formSections }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["templates"] }); resetForm(); },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => templatesApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["templates"] }),
  });

  const resetForm = () => { setEditing(null); setFormName(""); setFormSections([emptySection()]); };
  const startNew = () => { setEditing("new"); setFormName(""); setFormSections([emptySection()]); };

  const startEdit = (t: Template) => {
    setEditing(t.id);
    setFormName(t.name);
    setFormSections(t.sections.length ? t.sections.map(normalizeSection) : [emptySection()]);
  };

  const addSection = () => setFormSections((s) => [...s, emptySection()]);
  const removeSection = (i: number) => setFormSections((s) => s.filter((_, idx) => idx !== i));

  const updateSection = <K extends keyof Section>(i: number, field: K, value: Section[K]) =>
    setFormSections((s) => s.map((sec, idx) => idx === i ? { ...sec, [field]: value } : sec));

  const moveSection = (i: number, dir: -1 | 1) => {
    setFormSections((s) => {
      const next = [...s];
      const j = i + dir;
      if (j < 0 || j >= next.length) return s;
      [next[i], next[j]] = [next[j], next[i]];
      return next;
    });
  };

  const changeIndent = (i: number, delta: number) => {
    setFormSections((s) => s.map((sec, idx) =>
      idx === i ? { ...sec, indent: Math.max(0, Math.min(MAX_INDENT, sec.indent + delta)) } : sec
    ));
  };

  const saveForm = () => {
    if (!formName.trim() || formSections.some((s) => !s.title.trim())) return;
    if (editing === "new") createMutation.mutate();
    else if (editing) updateMutation.mutate(editing);
  };

  const isSaving = createMutation.isPending || updateMutation.isPending;

  return (
    <PageShell
      title="Description Templates"
      description="Build structured templates for AI-generated product descriptions"
      actions={
        !editing && (
          <Button size="sm" onClick={startNew}>
            <Plus className="h-4 w-4 mr-1" /> New Template
          </Button>
        )
      }
    >
      {/* Editor */}
      {editing && (
        <Card className="mb-6 border-blue-200">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-blue-500" />
              {editing === "new" ? "New Template" : "Edit Template"}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium text-gray-700 mb-1 block">Template Name</label>
              <Input
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="e.g. Standard Product Page"
                className="max-w-sm"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm font-medium text-gray-700">Structure</label>
                <Button size="sm" variant="outline" onClick={addSection}>
                  <Plus className="h-3.5 w-3.5 mr-1" /> Add Row
                </Button>
              </div>

              <div className="space-y-1.5">
                {formSections.map((sec, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-2 p-2.5 border rounded-lg bg-gray-50"
                    style={{ marginLeft: sec.indent * 24 }}
                  >
                    <div className="flex flex-col gap-0.5 mt-0.5 flex-shrink-0">
                      <button onClick={() => moveSection(i, -1)} disabled={i === 0} className="text-gray-400 hover:text-gray-600 disabled:opacity-30">
                        <ChevronUp className="h-3.5 w-3.5" />
                      </button>
                      <button onClick={() => moveSection(i, 1)} disabled={i === formSections.length - 1} className="text-gray-400 hover:text-gray-600 disabled:opacity-30">
                        <ChevronDown className="h-3.5 w-3.5" />
                      </button>
                    </div>

                    <div className="flex flex-col gap-0.5 flex-shrink-0 mt-0.5">
                      <button
                        onClick={() => changeIndent(i, 1)}
                        disabled={sec.indent >= MAX_INDENT}
                        title="Indent"
                        className="text-gray-400 hover:text-gray-600 disabled:opacity-30"
                      >
                        <IndentIncrease className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => changeIndent(i, -1)}
                        disabled={sec.indent <= 0}
                        title="Outdent"
                        className="text-gray-400 hover:text-gray-600 disabled:opacity-30"
                      >
                        <IndentDecrease className="h-3.5 w-3.5" />
                      </button>
                    </div>

                    <select
                      value={sec.tag}
                      onChange={(e) => updateSection(i, "tag", e.target.value as SectionTag)}
                      className="border border-gray-300 rounded px-2 py-1.5 text-sm flex-shrink-0 w-32"
                    >
                      {TAG_OPTIONS.map((t) => (
                        <option key={t.value} value={t.value}>{t.label} — {t.desc}</option>
                      ))}
                    </select>

                    <div className="flex-1 space-y-1.5 min-w-0">
                      <Input
                        value={sec.title}
                        onChange={(e) => updateSection(i, "title", e.target.value)}
                        placeholder={
                          sec.tag === "h2" || sec.tag === "h3"
                            ? "Heading text (e.g. Features, Specifications)"
                            : "Label for this block (e.g. intro paragraph, feature bullets)"
                        }
                        className="h-8 text-sm"
                      />
                      <Input
                        value={sec.hint}
                        onChange={(e) => updateSection(i, "hint", e.target.value)}
                        placeholder="AI hint — describe what content goes here (optional)"
                        className="h-7 text-xs text-gray-500"
                      />
                    </div>

                    <label className="flex items-center gap-1 text-xs text-gray-600 cursor-pointer whitespace-nowrap select-none flex-shrink-0 mt-1.5">
                      <input
                        type="checkbox"
                        checked={sec.required}
                        onChange={(e) => updateSection(i, "required", e.target.checked)}
                        className="rounded"
                      />
                      Req.
                    </label>

                    <button
                      onClick={() => removeSection(i)}
                      disabled={formSections.length === 1}
                      className="text-gray-400 hover:text-red-500 disabled:opacity-30 mt-1 flex-shrink-0"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>

              <p className="text-xs text-gray-400 mt-2">
                Use indent (→) to nest content elements under headings — e.g. a UL or P under an H2.
                Mark sections <strong>Req.</strong> to always generate them; uncheck to let AI skip if data is sparse.
              </p>
            </div>

            <div className="flex gap-2 pt-2">
              <Button onClick={saveForm} disabled={isSaving || !formName.trim() || formSections.some((s) => !s.title.trim())}>
                {isSaving ? "Saving..." : <><Save className="h-3.5 w-3.5 mr-1" />Save Template</>}
              </Button>
              <Button variant="outline" onClick={resetForm}>
                <X className="h-3.5 w-3.5 mr-1" /> Cancel
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Template list */}
      {isLoading ? (
        <p className="text-sm text-gray-400 text-center py-8">Loading...</p>
      ) : templates.length === 0 && !editing ? (
        <Card>
          <CardContent className="p-12 text-center">
            <Sparkles className="h-10 w-10 mx-auto text-gray-300 mb-3" />
            <p className="text-gray-500 font-medium">No templates yet</p>
            <p className="text-sm text-gray-400 mt-1 mb-4">Create a template to structure AI-generated product descriptions</p>
            <Button size="sm" onClick={startNew}><Plus className="h-4 w-4 mr-1" />Create First Template</Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {templates.map((t) => {
            const stats = templateStats[t.id];
            const hasActivity = stats && stats.total > 0;
            const doneCount = stats ? stats.applied + stats.pendingReview : 0;

            return (
              <Card key={t.id} className={editing === t.id ? "opacity-40 pointer-events-none" : ""}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <p className="font-medium">{t.name}</p>

                      {/* Section structure preview */}
                      <div className="mt-2 space-y-0.5">
                        {t.sections.map((s, i) => {
                          const sec = normalizeSection(s);
                          const tagOpt = TAG_OPTIONS.find((o) => o.value === sec.tag);
                          return (
                            <div
                              key={i}
                              className="flex items-center gap-1.5"
                              style={{ paddingLeft: sec.indent * 16 + (sec.indent > 0 ? 8 : 0) }}
                            >
                              {sec.indent > 0 && <span className="text-gray-300 text-xs">└</span>}
                              <span className={cn("px-1.5 py-0.5 rounded text-[11px] font-semibold", TAG_COLOR[sec.tag])}>
                                {tagOpt?.label ?? sec.tag.toUpperCase()}
                              </span>
                              <span className="text-xs text-gray-600 truncate">{sec.title}</span>
                              {!sec.required && <span className="text-[10px] text-gray-400 italic flex-shrink-0">optional</span>}
                            </div>
                          );
                        })}
                      </div>

                      {/* Enrichment progress */}
                      {hasActivity && (
                        <div className="mt-3">
                          {/* Progress bar */}
                          <div className="flex items-center gap-2 mb-1.5">
                            {stats.processing > 0 && (
                              <Loader2 className="h-3.5 w-3.5 text-blue-500 animate-spin flex-shrink-0" />
                            )}
                            <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                              <div
                                className="h-full rounded-full bg-green-500 transition-all duration-500"
                                style={{ width: `${Math.round((doneCount / stats.total) * 100)}%` }}
                              />
                            </div>
                            <span className="text-xs text-gray-500 tabular-nums flex-shrink-0">
                              {doneCount}/{stats.total}
                            </span>
                          </div>

                          {/* Status pills */}
                          <div className="flex flex-wrap gap-1.5">
                            {stats.processing > 0 && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-blue-50 text-blue-700 border border-blue-100">
                                <Loader2 className="h-3 w-3 animate-spin" />
                                {stats.processing} processing
                              </span>
                            )}
                            {stats.pendingReview > 0 && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-100">
                                {stats.pendingReview} ready to review
                              </span>
                            )}
                            {stats.applied > 0 && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-green-50 text-green-700 border border-green-100">
                                {stats.applied} applied
                              </span>
                            )}
                            {stats.failed > 0 && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-red-50 text-red-700 border border-red-100">
                                {stats.failed} failed
                              </span>
                            )}
                          </div>
                        </div>
                      )}
                    </div>

                    <div className="flex flex-col gap-2 flex-shrink-0 items-end">
                      {/* Review button — shown whenever template has any activity */}
                      {hasActivity && (
                        <Link href={`/templates/${t.id}/review`} className="w-full">
                          {stats.pendingReview > 0 ? (
                            <Button size="sm" className="bg-amber-500 hover:bg-amber-600 w-full">
                              <ClipboardCheck className="h-3.5 w-3.5 mr-1" />
                              Review {stats.pendingReview}
                            </Button>
                          ) : stats.processing > 0 ? (
                            <Button size="sm" variant="outline" className="w-full text-blue-600 border-blue-200 hover:bg-blue-50">
                              <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                              View Progress
                            </Button>
                          ) : (
                            <Button size="sm" variant="outline" className="w-full text-gray-500">
                              <ClipboardCheck className="h-3.5 w-3.5 mr-1" />
                              View Results
                            </Button>
                          )}
                        </Link>
                      )}
                      <div className="flex gap-2">
                        <Link href={`/templates/${t.id}/apply`}>
                          <Button size="sm" variant={stats?.pendingReview ? "outline" : "default"}>
                            Apply to Products <ArrowRight className="h-3.5 w-3.5 ml-1" />
                          </Button>
                        </Link>
                        <Button size="sm" variant="outline" onClick={() => startEdit(t)}>
                          <Edit2 className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          size="sm" variant="outline"
                          className="text-red-500 hover:text-red-600 hover:border-red-300"
                          onClick={() => { if (confirm(`Delete "${t.name}"?`)) deleteMutation.mutate(t.id); }}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </PageShell>
  );
}
