"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { reordersApi } from "@/lib/api";
import { PageShell } from "@/components/layout/PageShell";
import { Card, CardContent } from "@/components/ui/card";
import { Package, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import Link from "next/link";

const STATUS_COLORS: Record<string, string> = {
  Pending: "bg-amber-100 text-amber-700",
  Shipped: "bg-blue-100 text-blue-700",
  Received: "bg-green-100 text-green-700",
  Cancelled: "bg-gray-100 text-gray-500",
};

export default function ReordersPage() {
  const [statusFilter, setStatusFilter] = useState("all");

  const { data: reorders = [], isLoading } = useQuery({
    queryKey: ["reorders"],
    queryFn: () => reordersApi.list().then((r) => r.data),
  });

  const filtered = statusFilter === "all" ? reorders : (reorders as any[]).filter((r: any) => r.status === statusFilter);

  return (
    <PageShell title="Reorder Log" description="Track purchase orders across all suppliers">
      <div className="flex gap-2 mb-4">
        {["all", "Pending", "Shipped", "Received", "Cancelled"].map((s) => (
          <button key={s} onClick={() => setStatusFilter(s)}
            className={cn("px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
              statusFilter === s ? "bg-slate-800 text-white" : "bg-white border text-gray-600 hover:bg-gray-50")}>
            {s === "all" ? `All (${(reorders as any[]).length})` : s}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="flex justify-center p-12"><Loader2 className="h-6 w-6 animate-spin text-blue-500" /></div>
      ) : (filtered as any[]).length === 0 ? (
        <Card><CardContent className="p-12 text-center">
          <Package className="h-10 w-10 mx-auto text-gray-300 mb-3" />
          <p className="text-gray-500 font-medium">No reorders yet</p>
          <p className="text-sm text-gray-400 mt-1">Log reorders from a supplier profile page</p>
        </CardContent></Card>
      ) : (
        <Card><CardContent className="p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="text-left px-4 py-3 font-medium text-gray-600">PO #</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Supplier</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Order Date</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Expected Delivery</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Items</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
              </tr>
            </thead>
            <tbody>
              {(filtered as any[]).map((r: any) => (
                <tr key={r.id} className="border-b last:border-0 hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-xs">{r.po_number || "—"}</td>
                  <td className="px-4 py-3">
                    <Link href={`/suppliers/${r.supplier_id}`} className="text-blue-600 hover:underline">{r.supplier_name}</Link>
                  </td>
                  <td className="px-4 py-3 text-gray-500">{r.order_date ? new Date(r.order_date).toLocaleDateString() : "—"}</td>
                  <td className="px-4 py-3 text-gray-500">{r.expected_delivery ? new Date(r.expected_delivery).toLocaleDateString() : "—"}</td>
                  <td className="px-4 py-3 text-gray-500">{(r.line_items || []).length} item{(r.line_items || []).length !== 1 ? "s" : ""}</td>
                  <td className="px-4 py-3">
                    <span className={cn("px-2 py-0.5 rounded text-xs font-medium", STATUS_COLORS[r.status] || "bg-gray-100 text-gray-600")}>{r.status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent></Card>
      )}
    </PageShell>
  );
}
