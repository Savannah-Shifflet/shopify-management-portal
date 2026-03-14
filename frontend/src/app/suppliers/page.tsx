"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { suppliersApi } from "@/lib/api";
import { PageShell } from "@/components/layout/PageShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Plus, Truck, Globe, Package, Play, Loader2, X } from "lucide-react";
import { formatDate } from "@/lib/utils";
import Link from "next/link";

export default function SuppliersPage() {
  const qc = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ name: "", website_url: "", notes: "" });

  const { data: suppliers } = useQuery({
    queryKey: ["suppliers"],
    queryFn: () => suppliersApi.list().then((r) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: () => suppliersApi.create(form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["suppliers"] });
      setShowAdd(false);
      setForm({ name: "", website_url: "", notes: "" });
    },
  });

  const scrapeNowMutation = useMutation({
    mutationFn: (id: string) => suppliersApi.scrapeNow(id),
  });

  return (
    <PageShell
      title="Suppliers"
      description="Manage your product suppliers and their scraping configurations"
      actions={
        <Button size="sm" onClick={() => setShowAdd(true)}>
          <Plus className="h-4 w-4 mr-1" /> Add Supplier
        </Button>
      }
    >
      {/* Add supplier form */}
      {showAdd && (
        <Card className="mb-6">
          <CardHeader className="pb-4">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Add Supplier</CardTitle>
              <Button variant="ghost" size="icon" onClick={() => setShowAdd(false)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Name <span className="text-red-500">*</span></Label>
                <Input className="mt-1" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Supplier Co." />
              </div>
              <div>
                <Label>Website URL</Label>
                <Input className="mt-1" value={form.website_url} onChange={(e) => setForm({ ...form, website_url: e.target.value })} placeholder="https://supplier.com" />
              </div>
            </div>
            <div>
              <Label>Notes</Label>
              <Input className="mt-1" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Internal notes..." />
            </div>
            <div className="flex gap-2">
              <Button onClick={() => createMutation.mutate()} disabled={!form.name || createMutation.isPending}>
                {createMutation.isPending ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Plus className="h-4 w-4 mr-1" />}
                Add Supplier
              </Button>
              <Button variant="outline" onClick={() => setShowAdd(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Supplier list */}
      {!suppliers || suppliers.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center">
            <Truck className="h-10 w-10 mx-auto text-gray-300 mb-3" />
            <p className="text-gray-500 font-medium">No suppliers yet</p>
            <p className="text-sm text-gray-400 mt-1">Add your first supplier to start scraping and monitoring prices</p>
            <Button size="sm" className="mt-4" onClick={() => setShowAdd(true)}>
              <Plus className="h-4 w-4 mr-1" /> Add Supplier
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {suppliers.map((s: any) => (
            <Card key={s.id} className="hover:shadow-sm transition-shadow">
              <CardContent className="p-5">
                <div className="flex items-start gap-3 mb-4">
                  <div className="p-2 bg-blue-50 rounded-lg">
                    <Truck className="h-5 w-5 text-blue-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold">{s.name}</p>
                    {s.website_url && (
                      <a href={s.website_url} target="_blank" rel="noopener noreferrer"
                        className="flex items-center gap-1 text-xs text-blue-600 hover:underline mt-0.5 truncate">
                        <Globe className="h-3 w-3 flex-shrink-0" />
                        {s.website_url}
                      </a>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-4 text-xs text-gray-500 mb-4">
                  <div className="flex items-center gap-1">
                    <Package className="h-3.5 w-3.5" />
                    {s.product_count} products
                  </div>
                  {s.last_scraped_at && (
                    <div>Last scraped: {new Date(s.last_scraped_at).toLocaleDateString()}</div>
                  )}
                </div>

                {s.monitor_enabled && (
                  <div className="flex items-center gap-1.5 mb-4">
                    <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                    <span className="text-xs text-green-600">Monitoring every {s.monitor_interval}min</span>
                  </div>
                )}

                <div className="flex gap-2">
                  <Link href={`/suppliers/${s.id}`} className="flex-1">
                    <Button variant="outline" size="sm" className="w-full">Configure</Button>
                  </Link>
                  <Button
                    size="sm" variant="outline"
                    onClick={() => scrapeNowMutation.mutate(s.id)}
                    disabled={scrapeNowMutation.isPending}
                    title="Scrape now"
                  >
                    {scrapeNowMutation.isPending
                      ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      : <Play className="h-3.5 w-3.5" />}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </PageShell>
  );
}
