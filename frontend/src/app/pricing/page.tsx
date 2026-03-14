"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { pricingApi } from "@/lib/api";
import { PageShell } from "@/components/layout/PageShell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RuleBuilder } from "@/components/pricing/RuleBuilder";
import { ScheduleForm } from "@/components/pricing/ScheduleForm";
import {
  Check, X, TrendingUp, TrendingDown, Calendar, DollarSign, Loader2, Plus,
} from "lucide-react";
import { formatDate, formatPrice } from "@/lib/utils";
import { cn } from "@/lib/utils";

const STATUS_BADGE: Record<string, string> = {
  active: "bg-green-100 text-green-700",
  pending: "bg-yellow-100 text-yellow-700",
  completed: "bg-gray-100 text-gray-600",
  cancelled: "bg-red-100 text-red-600",
};

export default function PricingPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<"alerts" | "schedules" | "rules">("alerts");
  const [selectedAlerts, setSelectedAlerts] = useState<Set<string>>(new Set());
  const [showScheduleForm, setShowScheduleForm] = useState(false);

  const { data: alerts, isLoading: alertsLoading } = useQuery({
    queryKey: ["pricing-alerts", "pending"],
    queryFn: () => pricingApi.alerts({ status: "pending" }).then((r) => r.data),
    enabled: tab === "alerts",
    refetchInterval: 30000,
  });

  const { data: schedules, isLoading: schedulesLoading } = useQuery({
    queryKey: ["pricing-schedules"],
    queryFn: () => pricingApi.schedules().then((r) => r.data),
    enabled: tab === "schedules",
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) => pricingApi.approveAlert(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pricing-alerts"] }),
  });

  const rejectMutation = useMutation({
    mutationFn: (id: string) => pricingApi.rejectAlert(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pricing-alerts"] }),
  });

  const bulkApproveMutation = useMutation({
    mutationFn: () => pricingApi.bulkApproveAlerts([...selectedAlerts]),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pricing-alerts"] });
      setSelectedAlerts(new Set());
    },
  });

  const cancelScheduleMutation = useMutation({
    mutationFn: (id: string) => pricingApi.cancelSchedule(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pricing-schedules"] }),
  });

  const toggleAlert = (id: string) => {
    setSelectedAlerts((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const pendingCount = alerts?.length ?? 0;

  return (
    <PageShell title="Pricing" description="Manage pricing alerts, schedules, and markup rules">
      {/* Tab bar */}
      <div className="flex gap-1 mb-6">
        {(["alerts", "schedules", "rules"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "px-4 py-2 rounded-md text-sm font-medium capitalize transition-colors",
              tab === t ? "bg-blue-600 text-white" : "bg-white border text-gray-600 hover:bg-gray-50"
            )}
          >
            {t}
            {t === "alerts" && pendingCount > 0 && (
              <span className="ml-2 bg-red-500 text-white text-xs rounded-full px-1.5 py-0.5">
                {pendingCount}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Alerts tab ─────────────────────────────────────────────────── */}
      {tab === "alerts" && (
        <div className="space-y-4">
          {selectedAlerts.size > 0 && (
            <div className="flex items-center gap-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <span className="text-sm font-medium text-blue-700">{selectedAlerts.size} selected</span>
              <Button
                size="sm" className="ml-auto"
                onClick={() => bulkApproveMutation.mutate()}
                disabled={bulkApproveMutation.isPending}
              >
                {bulkApproveMutation.isPending
                  ? <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                  : <Check className="h-3.5 w-3.5 mr-1" />}
                Approve All Selected
              </Button>
              <Button size="sm" variant="outline" onClick={() => setSelectedAlerts(new Set())}>
                Clear
              </Button>
            </div>
          )}

          {alertsLoading ? (
            <div className="flex justify-center p-8">
              <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
            </div>
          ) : !alerts || alerts.length === 0 ? (
            <Card>
              <CardContent className="p-12 text-center">
                <DollarSign className="h-10 w-10 mx-auto text-gray-300 mb-3" />
                <p className="text-gray-500 font-medium">No pending price alerts</p>
                <p className="text-sm text-gray-400 mt-1">
                  Supplier price changes will appear here for review
                </p>
              </CardContent>
            </Card>
          ) : (
            alerts.map((alert: any) => {
              const isIncrease = Number(alert.new_price) > Number(alert.old_price);
              const isSelected = selectedAlerts.has(alert.id);
              return (
                <Card
                  key={alert.id}
                  className={cn(
                    "hover:shadow-sm transition-shadow",
                    isSelected && "ring-1 ring-blue-400"
                  )}
                >
                  <CardContent className="p-5">
                    <div className="flex items-start gap-4">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleAlert(alert.id)}
                        className="mt-1 rounded"
                      />
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-gray-900">
                          {alert.product_title || "Unknown product"}
                        </p>
                        <p className="text-xs text-gray-500 mt-0.5">
                          {alert.supplier_name} • {formatDate(alert.created_at)}
                        </p>
                        <div className="flex items-center gap-6 mt-3">
                          <div>
                            <p className="text-xs text-gray-400">Old price</p>
                            <p className="font-medium text-sm">{formatPrice(alert.old_price)}</p>
                          </div>
                          <div className={cn(
                            "flex items-center gap-1 text-sm font-semibold",
                            isIncrease ? "text-red-600" : "text-green-600"
                          )}>
                            {isIncrease
                              ? <TrendingUp className="h-4 w-4" />
                              : <TrendingDown className="h-4 w-4" />}
                            {isIncrease ? "+" : ""}{Number(alert.change_pct).toFixed(1)}%
                          </div>
                          <div>
                            <p className="text-xs text-gray-400">New price</p>
                            <p className={cn(
                              "font-medium text-sm",
                              isIncrease ? "text-red-600" : "text-green-600"
                            )}>
                              {formatPrice(alert.new_price)}
                            </p>
                          </div>
                        </div>
                      </div>
                      <div className="flex gap-2 flex-shrink-0">
                        <Button
                          size="sm"
                          onClick={() => approveMutation.mutate(alert.id)}
                          disabled={approveMutation.isPending || rejectMutation.isPending}
                        >
                          <Check className="h-3.5 w-3.5 mr-1" /> Approve
                        </Button>
                        <Button
                          size="sm" variant="outline"
                          onClick={() => rejectMutation.mutate(alert.id)}
                          disabled={approveMutation.isPending || rejectMutation.isPending}
                        >
                          <X className="h-3.5 w-3.5 mr-1" /> Reject
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })
          )}
        </div>
      )}

      {/* ── Schedules tab ──────────────────────────────────────────────── */}
      {tab === "schedules" && (
        <div className="space-y-4">
          {showScheduleForm ? (
            <ScheduleForm onCancel={() => setShowScheduleForm(false)} />
          ) : (
            <div className="flex justify-end">
              <Button size="sm" onClick={() => setShowScheduleForm(true)}>
                <Plus className="h-3.5 w-3.5 mr-1" /> New Schedule
              </Button>
            </div>
          )}

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Calendar className="h-4 w-4" /> Promotional Price Schedules
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {schedulesLoading ? (
                <div className="p-8 flex justify-center">
                  <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
                </div>
              ) : !schedules || schedules.length === 0 ? (
                <div className="p-8 text-center text-gray-400">
                  No scheduled price changes — click "New Schedule" to create one
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-gray-50">
                      <th className="text-left px-4 py-3 font-medium text-gray-500">Action</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-500">Value</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-500">Starts</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-500">Ends</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-500">Status</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {schedules.map((s: any) => (
                      <tr key={s.id} className="border-b last:border-0">
                        <td className="px-4 py-3 capitalize text-sm">
                          {s.price_action?.replace(/_/g, " ")}
                        </td>
                        <td className="px-4 py-3 font-medium">
                          {s.price_action === "percent_off"
                            ? `${s.price_value}%`
                            : formatPrice(s.price_value)}
                        </td>
                        <td className="px-4 py-3 text-xs text-gray-600">{formatDate(s.starts_at)}</td>
                        <td className="px-4 py-3 text-xs text-gray-600">
                          {s.ends_at ? formatDate(s.ends_at) : "—"}
                        </td>
                        <td className="px-4 py-3">
                          <span className={cn(
                            "px-2 py-0.5 rounded-full text-xs font-medium capitalize",
                            STATUS_BADGE[s.status] ?? "bg-gray-100 text-gray-600"
                          )}>
                            {s.status}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          {s.status === "pending" && (
                            <Button
                              size="sm" variant="ghost"
                              className="text-red-500 hover:text-red-700 h-7 text-xs"
                              onClick={() => cancelScheduleMutation.mutate(s.id)}
                              disabled={cancelScheduleMutation.isPending}
                            >
                              Cancel
                            </Button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* ── Rules tab ──────────────────────────────────────────────────── */}
      {tab === "rules" && <RuleBuilder />}
    </PageShell>
  );
}
