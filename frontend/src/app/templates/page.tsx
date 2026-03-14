"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { templatesApi } from "@/lib/api";
import { PageShell } from "@/components/layout/PageShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Plus, Trash2, Edit2, ChevronUp, ChevronDown, Save, X, Sparkles, ArrowRight } from "lucide-react";
import Link from "next/link";

interface Section {
  level: "h2" | "h3";
  title: string;
  hint: string;
}

interface Template {
  id: string;
  name: string;
  sections: Section[];
}

const emptySection = (): Section => ({ level: "h2", title: "", hint: "" });

export default function TemplatesPage() {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<string | null>(null); // template id or "new"
  const [formName, setFormName] = useState("");
  const [formSections, setFormSections] = useState<Section[]>([emptySection()]);

  const { data: templates = [], isLoading } = useQuery<Template[]>({
    queryKey: ["templates"],
    queryFn: () => templatesApi.list().then((r) => r.data),
  });

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
    setFormSections(t.sections.length ? t.sections : [emptySection()]);
  };

  const addSection = () => setFormSections((s) => [...s, emptySection()]);

  const removeSection = (i: number) =>
    setFormSections((s) => s.filter((_, idx) => idx !== i));

  const updateSection = (i: number, field: keyof Section, value: string) =>
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
                <label className="text-sm font-medium text-gray-700">Sections</label>
                <Button size="sm" variant="outline" onClick={addSection}>
                  <Plus className="h-3.5 w-3.5 mr-1" /> Add Section
                </Button>
              </div>

              <div className="space-y-2">
                {formSections.map((sec, i) => (
                  <div key={i} className="flex items-start gap-2 p-3 border rounded-lg bg-gray-50">
                    <div className="flex flex-col gap-1 mt-1">
                      <button onClick={() => moveSection(i, -1)} disabled={i === 0} className="text-gray-400 hover:text-gray-600 disabled:opacity-30">
                        <ChevronUp className="h-3.5 w-3.5" />
                      </button>
                      <button onClick={() => moveSection(i, 1)} disabled={i === formSections.length - 1} className="text-gray-400 hover:text-gray-600 disabled:opacity-30">
                        <ChevronDown className="h-3.5 w-3.5" />
                      </button>
                    </div>

                    <select
                      value={sec.level}
                      onChange={(e) => updateSection(i, "level", e.target.value)}
                      className="border border-gray-300 rounded px-2 py-1.5 text-sm w-20 flex-shrink-0"
                    >
                      <option value="h2">H2 (Tab)</option>
                      <option value="h3">H3 (Accordion)</option>
                    </select>

                    <div className="flex-1 space-y-1.5">
                      <Input
                        value={sec.title}
                        onChange={(e) => updateSection(i, "title", e.target.value)}
                        placeholder="Section title (e.g. Features, Specifications)"
                        className="h-8 text-sm"
                      />
                      <Input
                        value={sec.hint}
                        onChange={(e) => updateSection(i, "hint", e.target.value)}
                        placeholder="AI hint — what content belongs here (optional)"
                        className="h-8 text-sm text-gray-500"
                      />
                    </div>

                    <button
                      onClick={() => removeSection(i)}
                      disabled={formSections.length === 1}
                      className="text-gray-400 hover:text-red-500 disabled:opacity-30 mt-1"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
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
          {templates.map((t) => (
            <Card key={t.id} className={editing === t.id ? "opacity-40 pointer-events-none" : ""}>
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="font-medium">{t.name}</p>
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {t.sections.map((s, i) => (
                        <span
                          key={i}
                          className={`px-2 py-0.5 rounded text-xs font-medium ${
                            s.level === "h2" ? "bg-blue-100 text-blue-700" : "bg-gray-100 text-gray-600"
                          }`}
                        >
                          {s.level.toUpperCase()}: {s.title}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="flex gap-2 flex-shrink-0">
                    <Link href={`/templates/${t.id}/apply`}>
                      <Button size="sm">
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
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </PageShell>
  );
}
