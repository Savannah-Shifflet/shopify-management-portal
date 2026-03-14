"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { suppliersApi, supplierSrmApi } from "@/lib/api";
import { PageShell } from "@/components/layout/PageShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Plus, Truck, Globe, Package, Play, Loader2, X, Search, Mail, Calendar } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

const STATUSES = ["LEAD", "CONTACTED", "NEGOTIATING", "APPROVED", "REJECTED", "INACTIVE"] as const;
type SupplierStatus = typeof STATUSES[number];

const STATUS_COLORS: Record<SupplierStatus, string> = {
  LEAD: "bg-gray-100 text-gray-700",
  CONTACTED: "bg-blue-100 text-blue-700",
  NEGOTIATING: "bg-amber-100 text-amber-700",
  APPROVED: "bg-green-100 text-green-700",
  REJECTED: "bg-red-100 text-red-700",
  INACTIVE: "bg-slate-100 text-slate-500",
};

const EMPTY_FORM = { name: "", company_email: "", contact_name: "", phone: "", website_url: "", notes: "", product_categories: "" };

export default function SuppliersPage() {
  const qc = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const { data: suppliers = [], isLoading } = useQuery({
    queryKey: ["suppliers"],
    queryFn: () => suppliersApi.list().then((r) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: () => suppliersApi.create({
      ...form,
      product_categories: form.product_categories ? form.product_categories.split(",").map((s) => s.trim()).filter(Boolean) : [],
      status: "LEAD",
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["suppliers"] });
      setShowAdd(false);
      setForm(EMPTY_FORM);
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      supplierSrmApi.updateStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["suppliers"] }),
  });

  const filtered = (suppliers as any[]).filter((s: any) => {
    const matchSearch = !search || s.name.toLowerCase().includes(search.toLowerCase()) ||
      (s.company_email ?? "").toLowerCase().includes(search.toLowerCase());
    const matchStatus = statusFilter === "all" || s.status === statusFilter;
    return matchSearch && matchStatus;
  });

  // Pipeline counts
  const counts: Record<string, number> = {};
  for (const s of suppliers as any[]) counts[s.status] = (counts[s.status] || 0) + 1;

  return (
    <PageShell
      title="Suppliers"
      description="Manage supplier relationships and outreach pipeline"
      actions={
        <Button size="sm" onClick={() => setShowAdd(true)}>
          <Plus className="h-4 w-4 mr-1" /> Add Supplier
        </Button>
      }
    >
      {/* Pipeline status bar */}
      <div className="flex gap-2 mb-5 overflow-x-auto pb-1">
        <button
          onClick={() => setStatusFilter("all")}
          className={cn("px-3 py-1.5 rounded-md text-sm font-medium whitespace-nowrap transition-colors",
            statusFilter === "all" ? "bg-slate-800 text-white" : "bg-white border text-gray-600 hover:bg-gray-50")}
        >
          All ({(suppliers as any[]).length})
        </button>
        {STATUSES.map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={cn("px-3 py-1.5 rounded-md text-sm font-medium whitespace-nowrap transition-colors",
              statusFilter === s ? "bg-slate-800 text-white" : "bg-white border text-gray-600 hover:bg-gray-50")}
          >
            {s} ({counts[s] || 0})
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="relative mb-4 max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
        <Input placeholder="Search suppliers..." className="pl-9" value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>

      {/* Add form */}
      {showAdd && (
        <Card className="mb-5 border-blue-200">
          <CardContent className="p-5 space-y-4">
            <div className="flex items-center justify-between">
              <p className="font-semibold">Add Supplier Lead</p>
              <button onClick={() => setShowAdd(false)} className="text-gray-400 hover:text-gray-600"><X className="h-4 w-4" /></button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-gray-600 mb-1 block">Company Name *</label>
                <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Acme Corp" />
              </div>
              <div>
                <label className="text-xs font-medium text-gray-600 mb-1 block">Contact Email *</label>
                <Input type="email" value={form.company_email} onChange={(e) => setForm({ ...form, company_email: e.target.value })} placeholder="contact@supplier.com" />
              </div>
              <div>
                <label className="text-xs font-medium text-gray-600 mb-1 block">Contact Name</label>
                <Input value={form.contact_name} onChange={(e) => setForm({ ...form, contact_name: e.target.value })} placeholder="Jane Smith" />
              </div>
              <div>
                <label className="text-xs font-medium text-gray-600 mb-1 block">Phone</label>
                <Input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="+1 555 000 0000" />
              </div>
              <div>
                <label className="text-xs font-medium text-gray-600 mb-1 block">Website</label>
                <Input value={form.website_url} onChange={(e) => setForm({ ...form, website_url: e.target.value })} placeholder="https://supplier.com" />
              </div>
              <div>
                <label className="text-xs font-medium text-gray-600 mb-1 block">Product Categories (comma-separated)</label>
                <Input value={form.product_categories} onChange={(e) => setForm({ ...form, product_categories: e.target.value })} placeholder="Electronics, Audio" />
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 mb-1 block">Notes</label>
              <Input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Internal notes..." />
            </div>
            <div className="flex gap-2">
              <Button onClick={() => createMutation.mutate()} disabled={!form.name || !form.company_email || createMutation.isPending}>
                {createMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Plus className="h-4 w-4 mr-1" />}
                Add Lead
              </Button>
              <Button variant="outline" onClick={() => setShowAdd(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Supplier table */}
      {isLoading ? (
        <div className="flex justify-center p-12"><Loader2 className="h-6 w-6 animate-spin text-blue-500" /></div>
      ) : filtered.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center">
            <Truck className="h-10 w-10 mx-auto text-gray-300 mb-3" />
            <p className="text-gray-500 font-medium">No suppliers found</p>
            <Button size="sm" className="mt-4" onClick={() => setShowAdd(true)}><Plus className="h-4 w-4 mr-1" />Add First Supplier</Button>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Company</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Contact</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Products</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Follow-up</th>
                  <th className="w-20"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((s: any) => {
                  const isOverdue = s.follow_up_date && new Date(s.follow_up_date) < new Date();
                  return (
                    <tr key={s.id} className="border-b last:border-0 hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <div>
                          <Link href={`/suppliers/${s.id}`} className="font-medium hover:text-blue-600">{s.name}</Link>
                          {s.website_url && (
                            <a href={s.website_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-xs text-gray-400 hover:text-blue-500 mt-0.5">
                              <Globe className="h-3 w-3" />{s.website_url.replace(/^https?:\/\//, "").slice(0, 30)}
                            </a>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        {s.company_email && <div className="flex items-center gap-1 text-xs text-gray-500"><Mail className="h-3 w-3" />{s.company_email}</div>}
                        {s.contact_name && <div className="text-xs text-gray-400 mt-0.5">{s.contact_name}</div>}
                      </td>
                      <td className="px-4 py-3">
                        <select
                          value={s.status || "LEAD"}
                          onChange={(e) => statusMutation.mutate({ id: s.id, status: e.target.value })}
                          className={cn("px-2 py-1 rounded text-xs font-medium border-0 cursor-pointer", STATUS_COLORS[s.status as SupplierStatus] || STATUS_COLORS.LEAD)}
                        >
                          {STATUSES.map((st) => <option key={st} value={st}>{st}</option>)}
                        </select>
                      </td>
                      <td className="px-4 py-3 text-gray-500">{s.product_count}</td>
                      <td className="px-4 py-3">
                        {s.follow_up_date && (
                          <span className={cn("flex items-center gap-1 text-xs", isOverdue ? "text-red-600 font-medium" : "text-gray-500")}>
                            <Calendar className="h-3 w-3" />
                            {new Date(s.follow_up_date).toLocaleDateString()}
                            {isOverdue && " ⚠"}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <Link href={`/suppliers/${s.id}`}>
                          <Button size="sm" variant="outline">Open</Button>
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </PageShell>
  );
}
