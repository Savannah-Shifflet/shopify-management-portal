"use client";

import { useQuery } from "@tanstack/react-query";
import { auditApi } from "@/lib/api";
import { PageShell } from "@/components/layout/PageShell";
import { Card, CardContent } from "@/components/ui/card";
import { ClipboardList, Loader2 } from "lucide-react";

const ACTION_COLORS: Record<string, string> = {
  EMAIL_SENT: "bg-blue-100 text-blue-700",
  EMAIL_LOGGED: "bg-blue-50 text-blue-600",
  SUPPLIER_STATUS_CHANGE: "bg-purple-100 text-purple-700",
  REORDER_CREATED: "bg-amber-100 text-amber-700",
  PRODUCT_UPDATED: "bg-gray-100 text-gray-600",
};

export default function AuditLogPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["audit-log"],
    queryFn: () => auditApi.list({ limit: 200 }).then((r) => r.data),
  });

  const items = (data as any)?.items ?? [];

  return (
    <PageShell title="Audit Log" description="Full activity history — read only">
      {isLoading ? (
        <div className="flex justify-center p-12"><Loader2 className="h-6 w-6 animate-spin text-blue-500" /></div>
      ) : items.length === 0 ? (
        <Card><CardContent className="p-12 text-center">
          <ClipboardList className="h-10 w-10 mx-auto text-gray-300 mb-3" />
          <p className="text-gray-500">No activity recorded yet</p>
        </CardContent></Card>
      ) : (
        <Card><CardContent className="p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="text-left px-4 py-3 font-medium text-gray-600">Time</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Action</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Entity</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Description</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row: any) => (
                <tr key={row.id} className="border-b last:border-0 hover:bg-gray-50">
                  <td className="px-4 py-3 text-xs text-gray-400 whitespace-nowrap">{new Date(row.timestamp).toLocaleString()}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${ACTION_COLORS[row.action_type] || "bg-gray-100 text-gray-600"}`}>{row.action_type.replace(/_/g, " ")}</span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">{row.entity_type}</td>
                  <td className="px-4 py-3 text-gray-700">{row.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent></Card>
      )}
    </PageShell>
  );
}
