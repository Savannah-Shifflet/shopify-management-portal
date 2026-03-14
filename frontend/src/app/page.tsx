"use client";

import { useQuery } from "@tanstack/react-query";
import { syncApi, productsApi, pricingApi } from "@/lib/api";
import { PageShell } from "@/components/layout/PageShell";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Package, RefreshCw, AlertCircle, Sparkles, Upload, DollarSign } from "lucide-react";
import Link from "next/link";

export default function DashboardPage() {
  const { data: syncStatus } = useQuery({
    queryKey: ["sync-status"],
    queryFn: () => syncApi.status().then((r) => r.data),
    refetchInterval: 30_000,
  });

  const { data: products } = useQuery({
    queryKey: ["products", { page: 1, page_size: 5 }],
    queryFn: () => productsApi.list({ page: 1, page_size: 5 }).then((r) => r.data),
  });

  const { data: alerts } = useQuery({
    queryKey: ["pricing-alerts"],
    queryFn: () => pricingApi.alerts().then((r) => r.data),
  });

  const stats = [
    { label: "Total Products", value: products?.total ?? "—", icon: Package, color: "text-blue-600", bg: "bg-blue-50" },
    { label: "Never Synced", value: syncStatus?.never_synced ?? "—", icon: RefreshCw, color: "text-orange-600", bg: "bg-orange-50" },
    { label: "Pricing Alerts", value: alerts?.length ?? "—", icon: AlertCircle, color: "text-red-600", bg: "bg-red-50" },
    { label: "Shopify", value: syncStatus?.shopify_connected ? "Connected" : "Disconnected", icon: syncStatus?.shopify_connected ? RefreshCw : AlertCircle, color: syncStatus?.shopify_connected ? "text-green-600" : "text-red-600", bg: syncStatus?.shopify_connected ? "bg-green-50" : "bg-red-50" },
  ];

  const quickActions = [
    { href: "/products/new", label: "Add Product", icon: Package, desc: "Manual entry" },
    { href: "/import", label: "Import", icon: Upload, desc: "CSV, PDF, scrape" },
    { href: "/enrichment", label: "AI Enrich", icon: Sparkles, desc: "Improve content" },
    { href: "/pricing", label: "Pricing", icon: DollarSign, desc: "Review alerts" },
    { href: "/sync", label: "Sync", icon: RefreshCw, desc: "Push to Shopify" },
  ];

  return (
    <PageShell title="Dashboard" description="Overview of your product catalog">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {stats.map((s) => (
          <Card key={s.label}>
            <CardContent className="p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">{s.label}</p>
                  <p className="text-2xl font-bold mt-1">{s.value}</p>
                </div>
                <div className={`p-2 rounded-lg ${s.bg}`}>
                  <s.icon className={`h-5 w-5 ${s.color}`} />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="mb-8">
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Quick Actions</h2>
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

      {syncStatus && (
        <div className="mb-8">
          <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Sync Status</h2>
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
                  <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
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

      {(products?.items?.length ?? 0) > 0 && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Recent Products</h2>
            <Link href="/products" className="text-sm text-blue-600 hover:underline">View all</Link>
          </div>
          <Card>
            <CardContent className="p-0">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-gray-50">
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Title</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Price</th>
                  </tr>
                </thead>
                <tbody>
                  {products!.items.slice(0, 5).map((p: any) => (
                    <tr key={p.id} className="border-b last:border-0 hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <Link href={`/products/${p.id}`} className="font-medium hover:text-blue-600">{p.title}</Link>
                      </td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700">{p.status}</span>
                      </td>
                      <td className="px-4 py-3 text-gray-600">
                        {p.base_price ? `$${Number(p.base_price).toFixed(2)}` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </div>
      )}
    </PageShell>
  );
}
