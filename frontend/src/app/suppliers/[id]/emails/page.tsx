"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { suppliersApi, supplierSrmApi, emailTemplatesApi } from "@/lib/api";
import { PageShell } from "@/components/layout/PageShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Send, ArrowLeft, Loader2, Mail, Inbox, ChevronDown, ChevronUp } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

export default function SupplierEmailsPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const [showCompose, setShowCompose] = useState(false);
  const [showLogInbound, setShowLogInbound] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [compose, setCompose] = useState({ subject: "", body: "" });
  const [inbound, setInbound] = useState({ subject: "", body: "", sent_at: "" });
  const [selectedTemplate, setSelectedTemplate] = useState("");

  const { data: supplier } = useQuery({ queryKey: ["supplier", id], queryFn: () => suppliersApi.get(id).then((r) => r.data) });
  const { data: emails = [], isLoading } = useQuery({ queryKey: ["supplier-emails", id], queryFn: () => supplierSrmApi.listEmails(id).then((r) => r.data) });
  const { data: templates = [] } = useQuery({ queryKey: ["email-templates"], queryFn: () => emailTemplatesApi.list().then((r) => r.data) });

  const sendMutation = useMutation({
    mutationFn: () => supplierSrmApi.sendEmail(id, { to_email: (supplier as any)?.company_email, ...compose }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["supplier-emails", id] }); setShowCompose(false); setCompose({ subject: "", body: "" }); },
  });

  const logInboundMutation = useMutation({
    mutationFn: () => supplierSrmApi.logEmail(id, { direction: "INBOUND", ...inbound }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["supplier-emails", id] }); setShowLogInbound(false); setInbound({ subject: "", body: "", sent_at: "" }); },
  });

  const applyTemplate = (templateId: string) => {
    const t = (templates as any[]).find((t: any) => t.id === templateId);
    if (!t) return;
    const supplierName = (supplier as any)?.name || "Supplier";
    const fill = (s: string) => s?.replace(/\{\{supplier_name\}\}/g, supplierName).replace(/\{\{my_store_name\}\}/g, "My Store").replace(/\{\{my_name\}\}/g, "");
    setCompose({ subject: fill(t.subject || ""), body: fill(t.body || "") });
    setSelectedTemplate(templateId);
  };

  const toggleExpand = (emailId: string) => setExpanded(prev => { const n = new Set(prev); n.has(emailId) ? n.delete(emailId) : n.add(emailId); return n; });

  return (
    <PageShell
      title="Email Thread"
      description={(supplier as any)?.name}
      actions={
        <div className="flex gap-2">
          <Link href={`/suppliers/${id}`}><Button variant="outline" size="sm"><ArrowLeft className="h-4 w-4 mr-1" />Back</Button></Link>
          <Button size="sm" variant="outline" onClick={() => setShowLogInbound(true)}><Inbox className="h-4 w-4 mr-1" />Log Response</Button>
          <Button size="sm" onClick={() => setShowCompose(true)}><Send className="h-4 w-4 mr-1" />Compose</Button>
        </div>
      }
    >
      {/* Compose panel */}
      {showCompose && (
        <Card className="mb-5 border-blue-200">
          <CardContent className="p-5 space-y-3">
            <div className="flex items-center justify-between">
              <p className="font-semibold">New Email to {(supplier as any)?.name}</p>
              <button onClick={() => setShowCompose(false)} className="text-gray-400 hover:text-gray-600 text-lg">×</button>
            </div>
            {(templates as any[]).length > 0 && (
              <div>
                <label className="text-xs font-medium text-gray-600 mb-1 block">Apply Template</label>
                <select value={selectedTemplate} onChange={(e) => applyTemplate(e.target.value)} className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm">
                  <option value="">— Select a template —</option>
                  {(templates as any[]).map((t: any) => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
              </div>
            )}
            <div>
              <label className="text-xs font-medium text-gray-600 mb-1 block">To</label>
              <Input value={(supplier as any)?.company_email || ""} disabled className="bg-gray-50" />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 mb-1 block">Subject</label>
              <Input value={compose.subject} onChange={(e) => setCompose({ ...compose, subject: e.target.value })} />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 mb-1 block">Body</label>
              <textarea value={compose.body} onChange={(e) => setCompose({ ...compose, body: e.target.value })} rows={8} className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div className="flex gap-2">
              <Button onClick={() => sendMutation.mutate()} disabled={sendMutation.isPending || !compose.subject}>
                {sendMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Send className="h-4 w-4 mr-1" />}Send
              </Button>
              <Button variant="outline" onClick={() => setShowCompose(false)}>Cancel</Button>
            </div>
            {sendMutation.isError && <p className="text-xs text-red-600">Failed to send. Check SMTP settings.</p>}
          </CardContent>
        </Card>
      )}

      {/* Log inbound panel */}
      {showLogInbound && (
        <Card className="mb-5 border-green-200">
          <CardContent className="p-5 space-y-3">
            <div className="flex items-center justify-between">
              <p className="font-semibold">Log Inbound Email</p>
              <button onClick={() => setShowLogInbound(false)} className="text-gray-400 hover:text-gray-600 text-lg">×</button>
            </div>
            <div><label className="text-xs font-medium text-gray-600 mb-1 block">Subject</label><Input value={inbound.subject} onChange={(e) => setInbound({ ...inbound, subject: e.target.value })} /></div>
            <div><label className="text-xs font-medium text-gray-600 mb-1 block">Date Received</label><Input type="datetime-local" value={inbound.sent_at} onChange={(e) => setInbound({ ...inbound, sent_at: e.target.value })} /></div>
            <div><label className="text-xs font-medium text-gray-600 mb-1 block">Body</label><textarea value={inbound.body} onChange={(e) => setInbound({ ...inbound, body: e.target.value })} rows={6} className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" /></div>
            <div className="flex gap-2">
              <Button onClick={() => logInboundMutation.mutate()} disabled={logInboundMutation.isPending}>{logInboundMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}Log Response</Button>
              <Button variant="outline" onClick={() => setShowLogInbound(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Thread */}
      {isLoading ? (
        <div className="flex justify-center p-8"><Loader2 className="h-6 w-6 animate-spin text-blue-500" /></div>
      ) : (emails as any[]).length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <Mail className="h-10 w-10 mx-auto mb-3 text-gray-300" />
          <p className="font-medium text-gray-500">No emails yet</p>
          <p className="text-sm mt-1">Compose your first outreach message above</p>
        </div>
      ) : (
        <div className="space-y-3">
          {(emails as any[]).map((e: any) => {
            const isOut = e.direction === "OUTBOUND";
            const isExpanded = expanded.has(e.id);
            return (
              <div key={e.id} className={cn("flex", isOut ? "justify-end" : "justify-start")}>
                <div className={cn("max-w-[75%] rounded-xl p-4 shadow-sm", isOut ? "bg-blue-600 text-white" : "bg-white border text-gray-800")}>
                  <div className="flex items-center justify-between gap-4 mb-1">
                    <p className="font-medium text-sm">{e.subject || "(no subject)"}</p>
                    <button onClick={() => toggleExpand(e.id)} className={cn("text-xs flex items-center gap-0.5", isOut ? "text-blue-200 hover:text-white" : "text-gray-400 hover:text-gray-600")}>
                      {isExpanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                    </button>
                  </div>
                  <p className={cn("text-xs mb-2", isOut ? "text-blue-200" : "text-gray-400")}>{new Date(e.sent_at).toLocaleString()}</p>
                  {isExpanded && (
                    <div className={cn("text-sm mt-2 whitespace-pre-wrap border-t pt-2", isOut ? "border-blue-500" : "border-gray-100")}
                      dangerouslySetInnerHTML={{ __html: e.body || "" }} />
                  )}
                  {!isExpanded && e.body && (
                    <p className={cn("text-xs line-clamp-2", isOut ? "text-blue-100" : "text-gray-500")}>{e.body.replace(/<[^>]*>/g, "")}</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </PageShell>
  );
}
