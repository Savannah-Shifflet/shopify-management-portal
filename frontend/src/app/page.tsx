"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { syncApi, productsApi, pricingApi, suppliersApi, analyticsApi } from "@/lib/api";
import { PageShell } from "@/components/layout/PageShell";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Package, RefreshCw, AlertCircle, Sparkles, Upload, DollarSign,
  Truck, ChevronDown, ChevronUp, TrendingUp, Bell, Search,
} from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

function Widget({ title, icon: Icon, children, defaultOpen = true }: {
  title: string; icon: React.ElementType; children: React.ReactNode; defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <Card>
      <div
        className="flex items-center justify-between px-5 py-3 border-b cursor-pointer select-none"
        onClick={() => setOpen((o) => !o)}
      >
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-blue-600" />
          <p className="font-semibold text-sm">{title}</p>
        </div>
        {open ? <ChevronUp className="h-4 w-4 text-gray-400" /> : <ChevronDown className="h-4 w-4 text-gray-400" />}
      </div>
      {open && <CardContent className="p-5">{children}</CardContent>}
    </Card>
  );
}

export default function DashboardPage() {
  const { data: syncStatus } = useQuery({
    queryKey: ["sync-status"],
    queryFn: () => syncApi.status().then((r) => r.data),
    refetchInterval: 30_000,
  });

  const { data: allProducts } = useQuery({
    queryKey: ["dashboard-products"],
    queryFn: () => productsApi.list({ page: 1, page_size: 1000 }).then((r) => r.data),
  });

  const { data: alerts } = useQuery({
    queryKey: ["pricing-alerts"],
    queryFn: () => pricingApi.alerts().then((r) => r.data),
  });

  const { data: suppliers = [] } = useQuery({
    queryKey: ["suppliers"],
    queryFn: () => suppliersApi.list().then((r) => r.data as any[]),
  });

  const { data: analytics } = useQuery({
    queryKey: ["analytics-orders", 30],
    queryFn: () => analyticsApi.orders(30).then((r) => r.data),
    retry: false,
  });

  const products = allProducts?.items ?? [];
  const today = new Date();

  // Action Items
  const overdueFollowUps = (suppliers as any[]).filter(
    (s) => s.follow_up_date && new Date(s.follow_up_date) < today &&
      !["APPROVED", "REJECTED", "INACTIVE"].includes(s.status)
  );
  const lowStockProducts = products.filter((p: any) => p.is_low_stock);
  const missingCost = products.filter((p: any) => !p.cost_price && !p.base_price).length;

  // Supplier pipeline counts
  const pipelineCounts: Record<string, number> = {};
  for (const s of suppliers as any[]) {
    pipelineCounts[s.status] = (pipelineCounts[s.status] || 0) + 1;
  }

  const quickActions = [
    { href: "/products/new", label: "Add Product", icon: Package, desc: "Manual entry" },
    { href: "/import", label: "Import", icon: Upload, desc: "CSV, PDF, scrape" },
    { href: "/enrichment", label: "AI Enrich", icon: Sparkles, desc: "Improve content" },
    { href: "/pricing", label: "Pricing", icon: DollarSign, desc: "Review alerts" },
    { href: "/sync", label: "Sync", icon: RefreshCw, desc: "Push to Shopify" },
  ];

  return (
    <PageShell
      title="Dashboard"
      description="Overview of your business"
      actions={
        <button
          onClick={() => document.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true, bubbles: true }))}
          className="flex items-center gap-2 text-sm text-gray-500 border rounded-lg px-3 py-1.5 hover:bg-gray-50"
        >
          <Search className="h-3.5 w-3.5" />
          <span>Search</span>
          <kbd className="text-xs bg-gray-100 border rounded px-1">Ctrl+K</kbd>
        </button>
      }
    >
      {/* Quick actions */}
      <div className="mb-6">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Quick Actions</p>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          {quickActions.map((a) => (
            <Link key={a.href} href={a.href}>
              <Card className="hover:border-blue-300 hover:shadow-sm transition-all cursor-pointer h-full">
                <CardContent className="p-4 text-center">
                  <a.icon className="h-7 w-7 mx-auto mb-2 text-blue-600" />
                  <p className="font-medium text-sm">{a.label}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{a.desc}</p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </div>

      {/* Widgets */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        {/* Widget 1: Action Items */}
        <Widget title="Action Items" icon={Bell}>
          {overdueFollowUps.length === 0 && lowStockProducts.length === 0 && (alerts as any[])?.length === 0 ? (
            <p className="text-sm text-gray-400 italic">All clear — no action items.</p>
          ) : (
            <ul className="space-y-2">
              {overdueFollowUps.length > 0 && (
                <li>
                  <Link href="/suppliers" className="flex items-center justify-between text-sm hover:text-blue-600">
                    <span className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-amber-500" />
                      {overdueFollowUps.length} overdue supplier follow-up{overdueFollowUps.length !== 1 ? "s" : ""}
                    </span>
                    <span className="text-gray-400 text-xs">→</span>
                  </Link>
                </li>
              )}
              {lowStockProducts.length > 0 && (
                <li>
                  <Link href="/products" className="flex items-center justify-between text-sm hover:text-blue-600">
                    <span className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-red-500" />
                      {lowStockProducts.length} low-stock product{lowStockProducts.length !== 1 ? "s" : ""}
                    </span>
                    <span className="text-gray-400 text-xs">→</span>
                  </Link>
                </li>
              )}
              {(alerts as any[])?.length > 0 && (
                <li>
                  <Link href="/pricing" className="flex items-center justify-between text-sm hover:text-blue-600">
                    <span className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-blue-500" />
                      {(alerts as any[]).length} pricing alert{(alerts as any[]).length !== 1 ? "s" : ""} to review
                    </span>
                    <span className="text-gray-400 text-xs">→</span>
                  </Link>
                </li>
              )}
            </ul>
          )}
        </Widget>

        {/* Widget 2: Product Health */}
        <Widget title="Product Health" icon={Package}>
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: "Total Products", value: allProducts?.total ?? "—" },
              { label: "Synced to Shopify", value: syncStatus?.synced ?? "—" },
              { label: "Missing Cost", value: missingCost, warn: missingCost > 0 },
              { label: "Never Synced", value: syncStatus?.never_synced ?? "—", warn: (syncStatus?.never_synced ?? 0) > 0 },
            ].map((item) => (
              <div key={item.label} className={cn("p-3 rounded-lg bg-gray-50", item.warn && "bg-amber-50")}>
                <p className={cn("text-xl font-bold", item.warn ? "text-amber-600" : "text-gray-800")}>{item.value}</p>
                <p className="text-xs text-gray-500 mt-0.5">{item.label}</p>
              </div>
            ))}
          </div>
          <Link href="/products" className="mt-3 block text-xs text-blue-600 hover:underline">View all products →</Link>
        </Widget>

        {/* Widget 3: Supplier Pipeline */}
        <Widget title="Supplier Pipeline" icon={Truck}>
          {(suppliers as any[]).length === 0 ? (
            <div>
              <p className="text-sm text-gray-400 italic mb-2">No suppliers yet.</p>
              <Link href="/suppliers"><Button size="sm" variant="outline"><Truck className="h-3.5 w-3.5 mr-1" />Add Supplier</Button></Link>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {["LEAD", "CONTACTED", "NEGOTIATING", "APPROVED", "REJECTED", "INACTIVE"].map((status) => {
                const count = pipelineCounts[status] || 0;
                const colors: Record<string, string> = {
                  LEAD: "bg-gray-100 text-gray-700",
                  CONTACTED: "bg-blue-100 text-blue-700",
                  NEGOTIATING: "bg-amber-100 text-amber-700",
                  APPROVED: "bg-green-100 text-green-700",
                  REJECTED: "bg-red-100 text-red-700",
                  INACTIVE: "bg-slate-100 text-slate-500",
                };
                return (
                  <Link key={status} href={`/suppliers?status=${status}`}>
                    <div className={cn("px-3 py-1.5 rounded-full text-xs font-medium cursor-pointer hover:opacity-80", colors[status])}>
                      {status} ({count})
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </Widget>

        {/* Widget 4: Revenue Snapshot */}
        <Widget title="Revenue (Last 30 Days)" icon={TrendingUp}>
          {!analytics?.connected ? (
            <div>
              <p className="text-sm text-gray-400 italic mb-2">Connect Shopify to see revenue data.</p>
              <Link href="/settings"><Button size="sm" variant="outline">Go to Settings</Button></Link>
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: "Revenue", value: `$${Number(analytics.total_revenue).toLocaleString()}` },
                { label: "Orders", value: analytics.order_count },
                { label: "Avg Order", value: `$${Number(analytics.avg_order_value).toFixed(0)}` },
              ].map((item) => (
                <div key={item.label} className="p-3 rounded-lg bg-green-50">
                  <p className="text-xl font-bold text-green-700">{item.value}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{item.label}</p>
                </div>
              ))}
              {analytics.top_products?.length > 0 && (
                <div className="col-span-3 mt-2">
                  <p className="text-xs font-medium text-gray-500 mb-1">Top Product</p>
                  <p className="text-sm font-medium">{analytics.top_products[0].title}</p>
                  <p className="text-xs text-gray-400">${analytics.top_products[0].revenue.toLocaleString()} · {analytics.top_products[0].quantity} units</p>
                </div>
              )}
            </div>
          )}
        </Widget>

      </div>

      {/* Sync Status (existing) */}
      {syncStatus && (
        <div className="mt-4">
          <Card>
            <CardContent className="p-5 flex flex-wrap gap-6 items-center">
              {[
                { label: "Never Synced", value: syncStatus.never_synced, color: "text-gray-600" },
                { label: "Out of Sync", value: syncStatus.out_of_sync, color: "text-orange-600" },
                { label: "Pending", value: syncStatus.pending, color: "text-blue-600" },
                { label: "Synced", value: syncStatus.synced, color: "text-green-600" },
                { label: "Failed", value: syncStatus.failed, color: "text-red-600" },
              ].map((s) => (
                <div key={s.label} className="text-center">
                  <p className={cn("text-2xl font-bold", s.color)}>{s.value}</p>
                  <p className="text-xs text-muted-foreground">{s.label}</p>
                </div>
              ))}
              <div className="ml-auto">
                <Link href="/sync">
                  <Button size="sm"><RefreshCw className="h-4 w-4 mr-2" />Go to Sync</Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </PageShell>
  );
}
