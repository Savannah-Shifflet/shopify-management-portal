"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { syncApi } from "@/lib/api";
import { PageShell } from "@/components/layout/PageShell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  RefreshCw, CheckCircle, AlertCircle, Loader2, Wifi, WifiOff, Download,
} from "lucide-react";
import { cn, formatDate, statusColor } from "@/lib/utils";

export default function SyncPage() {
  const qc = useQueryClient();
  const [pullResult, setPullResult] = useState<{ pulled: number; created: number; matched: number } | null>(null);
  const [pullError, setPullError] = useState<string | null>(null);

  const { data: status } = useQuery({
    queryKey: ["sync-status"],
    queryFn: () => syncApi.status().then((r) => r.data),
    refetchInterval: 10_000,
  });

  const { data: log } = useQuery({
    queryKey: ["sync-log"],
    queryFn: () => syncApi.log({ page_size: 50 }).then((r) => r.data),
  });

  const syncAllMutation = useMutation({
    mutationFn: () => syncApi.syncAll(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sync-status"] });
      qc.invalidateQueries({ queryKey: ["sync-log"] });
    },
  });

  const pullMutation = useMutation({
    mutationFn: () => syncApi.pullFromShopify(),
    onSuccess: (res) => {
      setPullResult(res.data);
      setPullError(null);
      qc.invalidateQueries({ queryKey: ["sync-status"] });
      qc.invalidateQueries({ queryKey: ["products"] });
    },
    onError: (err: any) => {
      setPullError(err.response?.data?.detail ?? "Pull from Shopify failed");
    },
  });

  return (
    <PageShell
      title="Shopify Sync"
      description="Manage product synchronization with your Shopify store"
      actions={
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => pullMutation.mutate()}
            disabled={pullMutation.isPending}
          >
            {pullMutation.isPending
              ? <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              : <Download className="h-4 w-4 mr-2" />}
            Pull from Shopify
          </Button>
          <Button
            onClick={() => syncAllMutation.mutate()}
            disabled={syncAllMutation.isPending}
          >
            {syncAllMutation.isPending
              ? <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              : <RefreshCw className="h-4 w-4 mr-2" />}
            Sync All Approved
          </Button>
        </div>
      }
    >
      {/* Pull result banner */}
      {pullResult && (
        <div className="flex items-center gap-3 p-4 rounded-lg border border-green-200 bg-green-50 mb-6">
          <CheckCircle className="h-5 w-5 text-green-600 flex-shrink-0" />
          <p className="text-sm text-green-700">
            Pulled {pullResult.pulled} products from Shopify — {pullResult.created} new,{" "}
            {pullResult.matched} matched to existing.
          </p>
          <button
            className="ml-auto text-green-600 text-xs underline"
            onClick={() => setPullResult(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Pull error banner */}
      {pullError && (
        <div className="flex items-center gap-3 p-4 rounded-lg border border-red-200 bg-red-50 mb-6">
          <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0" />
          <p className="text-sm text-red-700">{pullError}</p>
          <button className="ml-auto text-red-600 text-xs underline" onClick={() => setPullError(null)}>Dismiss</button>
        </div>
      )}

      {/* Connection status */}
      {status && (
        <div className={`flex items-center gap-3 p-4 rounded-lg border mb-6 ${
          status.shopify_connected ? "bg-green-50 border-green-200" : "bg-red-50 border-red-200"
        }`}>
          {status.shopify_connected
            ? <Wifi className="h-5 w-5 text-green-600" />
            : <WifiOff className="h-5 w-5 text-red-600" />}
          <div>
            <p className={`font-medium ${status.shopify_connected ? "text-green-700" : "text-red-700"}`}>
              {status.shopify_connected ? "Connected to Shopify" : "Not connected to Shopify"}
            </p>
            {!status.shopify_connected && (
              <p className="text-sm text-red-600">
                Connect your store in{" "}
                <Link href="/settings" className="underline font-medium">Settings</Link>.
              </p>
            )}
          </div>
        </div>
      )}

      {/* Status counts */}
      {status && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
          {[
            { label: "Never Synced", value: status.never_synced, color: "text-gray-600", bg: "bg-gray-50" },
            { label: "Out of Sync", value: status.out_of_sync, color: "text-orange-600", bg: "bg-orange-50" },
            { label: "Pending", value: status.pending, color: "text-blue-600", bg: "bg-blue-50" },
            { label: "Synced", value: status.synced, color: "text-green-600", bg: "bg-green-50" },
            { label: "Failed", value: status.failed, color: "text-red-600", bg: "bg-red-50" },
          ].map((s) => (
            <Card key={s.label}>
              <CardContent className={`p-4 ${s.bg}`}>
                <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
                <p className="text-xs text-gray-500 mt-0.5">{s.label}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Sync log */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Recent Sync Activity</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {!log || log.length === 0 ? (
            <div className="p-8 text-center text-gray-400">No sync activity yet</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Time</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Operation</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Status</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Shopify ID</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Error</th>
                </tr>
              </thead>
              <tbody>
                {log.map((entry: any) => (
                  <tr key={entry.id} className="border-b last:border-0">
                    <td className="px-4 py-3 text-gray-500 whitespace-nowrap text-xs">
                      {formatDate(entry.created_at)}
                    </td>
                    <td className="px-4 py-3 capitalize">{entry.operation}</td>
                    <td className="px-4 py-3">
                      <span className={cn("flex items-center gap-1 text-xs font-medium", statusColor(entry.status))}>
                        {entry.status === "success"
                          ? <CheckCircle className="h-3.5 w-3.5" />
                          : <AlertCircle className="h-3.5 w-3.5" />}
                        {entry.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-gray-500">
                      {entry.shopify_id || "—"}
                    </td>
                    <td className="px-4 py-3 text-red-600 text-xs max-w-xs truncate">
                      {entry.error_message || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </PageShell>
  );
}
