"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { pricingApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Calendar, Loader2 } from "lucide-react";

const PRICE_ACTIONS = [
  { value: "percent_off", label: "Percent Off (%)" },
  { value: "fixed_off", label: "Fixed Amount Off ($)" },
  { value: "set", label: "Set Exact Price ($)" },
];

interface ScheduleFormProps {
  onCancel: () => void;
}

export function ScheduleForm({ onCancel }: ScheduleFormProps) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    product_id: "",
    price_action: "percent_off",
    price_value: "",
    starts_at: "",
    ends_at: "",
  });

  const createMutation = useMutation({
    mutationFn: () =>
      pricingApi.createSchedule({
        price_action: form.price_action,
        price_value: form.price_value,
        starts_at: new Date(form.starts_at).toISOString(),
        ends_at: form.ends_at ? new Date(form.ends_at).toISOString() : undefined,
        product_id: form.product_id || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pricing-schedules"] });
      onCancel();
    },
  });

  const setField = (field: string, value: string) =>
    setForm((f) => ({ ...f, [field]: value }));

  const isValid = form.price_value && form.starts_at;

  return (
    <Card className="border-blue-200 bg-blue-50/30">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Calendar className="h-4 w-4 text-blue-600" />
          Create Price Schedule
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label className="text-xs">Price Action</Label>
            <select
              value={form.price_action}
              onChange={(e) => setField("price_action", e.target.value)}
              className="mt-1 w-full h-9 text-sm border rounded px-2 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              {PRICE_ACTIONS.map((a) => (
                <option key={a.value} value={a.value}>{a.label}</option>
              ))}
            </select>
          </div>

          <div>
            <Label className="text-xs">
              Value ({form.price_action === "percent_off" ? "%" : "$"})
            </Label>
            <Input
              className="mt-1 h-9"
              type="number"
              step="0.01"
              min="0"
              placeholder={form.price_action === "percent_off" ? "e.g. 20" : "e.g. 5.00"}
              value={form.price_value}
              onChange={(e) => setField("price_value", e.target.value)}
            />
          </div>

          <div>
            <Label className="text-xs">Starts At</Label>
            <Input
              className="mt-1 h-9"
              type="datetime-local"
              value={form.starts_at}
              onChange={(e) => setField("starts_at", e.target.value)}
            />
          </div>

          <div>
            <Label className="text-xs">Ends At <span className="text-gray-400">(optional — leave blank for no expiry)</span></Label>
            <Input
              className="mt-1 h-9"
              type="datetime-local"
              value={form.ends_at}
              onChange={(e) => setField("ends_at", e.target.value)}
            />
          </div>

          <div className="col-span-2">
            <Label className="text-xs">Product ID <span className="text-gray-400">(optional — leave blank to apply to all products)</span></Label>
            <Input
              className="mt-1 h-9"
              placeholder="Paste product UUID to target a specific product"
              value={form.product_id}
              onChange={(e) => setField("product_id", e.target.value)}
            />
          </div>
        </div>

        <div className="flex gap-2 mt-4 justify-end">
          <Button variant="outline" size="sm" onClick={onCancel} disabled={createMutation.isPending}>
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={() => createMutation.mutate()}
            disabled={!isValid || createMutation.isPending}
          >
            {createMutation.isPending ? (
              <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />Creating...</>
            ) : (
              "Create Schedule"
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
