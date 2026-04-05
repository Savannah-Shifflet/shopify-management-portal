"use client";

import { useState, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { supplierSrmApi, emailTemplatesApi, storeSettingsApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Mail, X, Loader2, CheckCircle, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

interface SupplierRow {
  id: string;
  name: string;
  company_email?: string | null;
  status: string;
}

interface Props {
  suppliers: SupplierRow[];
  onClose: () => void;
}

function renderMerge(text: string, supplierName: string, storeName: string, myName: string) {
  return text
    .replace(/\{\{supplier_name\}\}/g, supplierName)
    .replace(/\{\{my_store_name\}\}/g, storeName)
    .replace(/\{\{my_name\}\}/g, myName);
}

export function BulkEmailDialog({ suppliers, onClose }: Props) {
  const qc = useQueryClient();
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [selectedTemplate, setSelectedTemplate] = useState("");
  const [result, setResult] = useState<{ sent: number; failed: number; skipped: number; results: any[] } | null>(null);
  const [step, setStep] = useState<"compose" | "preview" | "done">("compose");

  const { data: templates = [] } = useQuery({
    queryKey: ["email-templates"],
    queryFn: () => emailTemplatesApi.list().then((r) => r.data),
  });

  const { data: storeSettings } = useQuery({
    queryKey: ["store-settings"],
    queryFn: () => storeSettingsApi.get().then((r) => r.data),
  });

  const storeName = (storeSettings as any)?.store_name || "My Store";
  const myName = (storeSettings as any)?.owner_name || "";

  // Preview: render for the first supplier with an email
  const previewSupplier = suppliers.find((s) => s.company_email);
  const previewSubject = previewSupplier
    ? renderMerge(subject, previewSupplier.name, storeName, myName)
    : subject;
  const previewBody = previewSupplier
    ? renderMerge(body, previewSupplier.name, storeName, myName)
    : body;

  const withEmail = suppliers.filter((s) => s.company_email);
  const withoutEmail = suppliers.filter((s) => !s.company_email);

  function applyTemplate(templateId: string) {
    const tpl = (templates as any[]).find((t: any) => t.id === templateId);
    if (!tpl) return;
    setSubject(tpl.subject || "");
    setBody(tpl.body || "");
    setSelectedTemplate(templateId);
  }

  const sendMutation = useMutation({
    mutationFn: () =>
      supplierSrmApi.bulkEmail({
        supplier_ids: suppliers.map((s) => s.id),
        subject,
        body,
        template_id: selectedTemplate || undefined,
      }),
    onSuccess: (res) => {
      setResult(res.data);
      setStep("done");
      qc.invalidateQueries({ queryKey: ["suppliers"] });
    },
  });

  return (
    <>
      <div className="fixed inset-0 bg-black/40 z-50" onClick={onClose} />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div
          className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b flex-shrink-0">
            <div className="flex items-center gap-2">
              <Mail className="h-5 w-5 text-blue-500" />
              <div>
                <h2 className="font-semibold">Bulk Email</h2>
                <p className="text-xs text-gray-500">
                  {suppliers.length} supplier{suppliers.length !== 1 ? "s" : ""} selected
                  {withoutEmail.length > 0 && ` · ${withoutEmail.length} without email will be skipped`}
                </p>
              </div>
            </div>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto px-6 py-4">
            {step === "done" && result ? (
              <div className="space-y-4">
                <div className="flex items-center gap-3 p-4 bg-green-50 border border-green-200 rounded-lg">
                  <CheckCircle className="h-6 w-6 text-green-600 shrink-0" />
                  <div>
                    <p className="font-semibold text-green-800">Bulk send complete</p>
                    <p className="text-sm text-green-700 mt-0.5">
                      {result.sent} sent · {result.failed} failed · {result.skipped} skipped (no email)
                    </p>
                  </div>
                </div>
                {result.results.filter((r) => r.status !== "sent").length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-gray-600 mb-2">Issues:</p>
                    <div className="space-y-1">
                      {result.results
                        .filter((r) => r.status !== "sent")
                        .map((r, i) => (
                          <div key={i} className="flex items-center gap-2 text-sm text-gray-700">
                            <AlertTriangle className="h-3.5 w-3.5 text-amber-500 shrink-0" />
                            <span className="font-medium">{r.name}</span>
                            <span className="text-gray-400">—</span>
                            <span className="text-gray-500">{r.reason || r.status}</span>
                          </div>
                        ))}
                    </div>
                  </div>
                )}
              </div>
            ) : step === "preview" ? (
              <div className="space-y-4">
                <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-700">
                  Preview shows how the email will look for <strong>{previewSupplier?.name}</strong>.
                  {` {{supplier_name}}`} will be substituted for each recipient.
                </div>
                <div>
                  <p className="text-xs font-medium text-gray-600 mb-1">Subject (rendered)</p>
                  <p className="text-sm border rounded px-3 py-2 bg-gray-50">{previewSubject || "(empty)"}</p>
                </div>
                <div>
                  <p className="text-xs font-medium text-gray-600 mb-1">Body (rendered)</p>
                  <div
                    className="text-sm border rounded px-3 py-3 bg-gray-50 whitespace-pre-wrap max-h-64 overflow-y-auto"
                    dangerouslySetInnerHTML={{ __html: previewBody || "(empty)" }}
                  />
                </div>
                <div>
                  <p className="text-xs font-medium text-gray-600 mb-2">Recipients ({withEmail.length})</p>
                  <div className="space-y-1 max-h-32 overflow-y-auto">
                    {withEmail.map((s) => (
                      <div key={s.id} className="flex items-center gap-2 text-xs text-gray-600">
                        <CheckCircle className="h-3.5 w-3.5 text-green-500 shrink-0" />
                        <span className="font-medium">{s.name}</span>
                        <span className="text-gray-400">{s.company_email}</span>
                      </div>
                    ))}
                    {withoutEmail.map((s) => (
                      <div key={s.id} className="flex items-center gap-2 text-xs text-gray-400">
                        <X className="h-3.5 w-3.5 shrink-0" />
                        <span>{s.name}</span>
                        <span className="italic">no email — will be skipped</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Template picker */}
                {(templates as any[]).length > 0 && (
                  <div>
                    <label className="text-xs font-medium text-gray-600 mb-1 block">Apply template</label>
                    <select
                      className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
                      value={selectedTemplate}
                      onChange={(e) => { if (e.target.value) applyTemplate(e.target.value); else setSelectedTemplate(""); }}
                    >
                      <option value="">— choose template —</option>
                      {(templates as any[]).map((t: any) => (
                        <option key={t.id} value={t.id}>{t.name}</option>
                      ))}
                    </select>
                  </div>
                )}
                <div>
                  <label className="text-xs font-medium text-gray-600 mb-1 block">Subject</label>
                  <Input
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    placeholder="Use {{supplier_name}} for personalization"
                    className="text-sm"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-600 mb-1 block">Body</label>
                  <textarea
                    value={body}
                    onChange={(e) => setBody(e.target.value)}
                    rows={10}
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
                    placeholder={"Hello {{supplier_name}},\n\nI'm reaching out to inquire about your reseller program...\n\nBest,\n{{my_name}}"}
                  />
                  <p className="text-xs text-gray-400 mt-1">
                    Merge fields: <code>{"{{supplier_name}}"}</code> · <code>{"{{my_store_name}}"}</code> · <code>{"{{my_name}}"}</code>
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t bg-gray-50 flex gap-3 flex-shrink-0">
            {step === "compose" && (
              <>
                <Button
                  onClick={() => setStep("preview")}
                  disabled={!subject || !body || withEmail.length === 0}
                >
                  Preview & Confirm →
                </Button>
                <Button variant="outline" onClick={onClose}>Cancel</Button>
              </>
            )}
            {step === "preview" && (
              <>
                <Button
                  onClick={() => sendMutation.mutate()}
                  disabled={sendMutation.isPending}
                >
                  {sendMutation.isPending
                    ? <><Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />Sending...</>
                    : <><Mail className="h-3.5 w-3.5 mr-1" />Send to {withEmail.length} Supplier{withEmail.length !== 1 ? "s" : ""}</>}
                </Button>
                <Button variant="outline" onClick={() => setStep("compose")}>← Back</Button>
              </>
            )}
            {step === "done" && (
              <Button onClick={onClose}>Done</Button>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
