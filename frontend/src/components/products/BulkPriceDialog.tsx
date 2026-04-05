"use client";

import { useState, useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { productsApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DollarSign, X, Loader2, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

type AdjustMode = "set_fixed" | "markup_over_cost" | "increase_pct" | "decrease_pct" | "increase_fixed" | "decrease_fixed";

interface ProductRow {
  id: string;
  title: string;
  base_price: number | null;
  cost_price?: number | null;
  map_price?: number | null;
}

interface Props {
  products: ProductRow[];
  onClose: () => void;
}

export function BulkPriceDialog({ products, onClose }: Props) {
  const qc = useQueryClient();
  const [mode, setMode] = useState<AdjustMode>("increase_pct");
  const [value, setValue] = useState("");
  const [confirmed, setConfirmed] = useState(false);

  const newPrices = useMemo(() => {
    const v = parseFloat(value);
    if (isNaN(v)) return null;
    return products.map((p) => {
      const oldPrice = p.base_price ?? 0;
      const cost = p.cost_price ?? 0;
      let newPrice = oldPrice;
      switch (mode) {
        case "set_fixed":       newPrice = v; break;
        case "markup_over_cost": newPrice = cost > 0 ? cost * (1 + v / 100) : oldPrice; break;
        case "increase_pct":    newPrice = oldPrice * (1 + v / 100); break;
        case "decrease_pct":    newPrice = oldPrice * (1 - v / 100); break;
        case "increase_fixed":  newPrice = oldPrice + v; break;
        case "decrease_fixed":  newPrice = oldPrice - v; break;
      }
      const mapViolation = p.map_price != null && newPrice < p.map_price;
      return { ...p, newPrice: Math.max(0, Math.round(newPrice * 100) / 100), mapViolation };
    });
  }, [products, mode, value]);

  const violations = newPrices?.filter((p) => p.mapViolation).length ?? 0;

  const applyMutation = useMutation({
    mutationFn: async () => {
      if (!newPrices) return;
      for (const p of newPrices) {
        if (!p.mapViolation || confirmed) {
          await productsApi.update(p.id, { base_price: p.newPrice });
        }
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["products"] });
      onClose();
    },
  });

  const MODES: { value: AdjustMode; label: string; unit: string }[] = [
    { value: "set_fixed",       label: "Set fixed price",        unit: "$" },
    { value: "markup_over_cost", label: "% markup over cost",    unit: "%" },
    { value: "increase_pct",    label: "Increase by %",          unit: "%" },
    { value: "decrease_pct",    label: "Decrease by %",          unit: "%" },
    { value: "increase_fixed",  label: "Increase by fixed $",    unit: "$" },
    { value: "decrease_fixed",  label: "Decrease by fixed $",    unit: "$" },
  ];

  const selectedMode = MODES.find((m) => m.value === mode)!;

  return (
    <>
      <div className="fixed inset-0 bg-black/40 z-50" onClick={onClose} />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[85vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b flex-shrink-0">
            <div className="flex items-center gap-2">
              <DollarSign className="h-5 w-5 text-blue-500" />
              <div>
                <h2 className="font-semibold">Bulk Price Adjustment</h2>
                <p className="text-xs text-gray-500">{products.length} product{products.length !== 1 ? "s" : ""} selected</p>
              </div>
            </div>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="h-5 w-5" /></button>
          </div>

          {/* Controls */}
          <div className="px-6 py-4 border-b flex-shrink-0 space-y-3">
            <div className="flex gap-3 items-end">
              <div className="flex-1">
                <label className="text-xs font-medium text-gray-600 mb-1 block">Adjustment type</label>
                <select
                  value={mode}
                  onChange={(e) => setMode(e.target.value as AdjustMode)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {MODES.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
                </select>
              </div>
              <div className="w-36">
                <label className="text-xs font-medium text-gray-600 mb-1 block">Value ({selectedMode.unit})</label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">{selectedMode.unit}</span>
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    className="pl-7"
                    value={value}
                    onChange={(e) => setValue(e.target.value)}
                    placeholder="0"
                  />
                </div>
              </div>
            </div>

            {violations > 0 && (
              <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
                <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0 text-amber-600" />
                <div>
                  <p className="font-medium">{violations} product{violations !== 1 ? "s" : ""} below MAP price</p>
                  <label className="flex items-center gap-2 mt-1 cursor-pointer">
                    <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
                    <span className="text-xs">Apply anyway (override MAP check)</span>
                  </label>
                </div>
              </div>
            )}
          </div>

          {/* Preview table */}
          <div className="flex-1 overflow-y-auto px-6 py-3">
            <p className="text-xs font-medium text-gray-500 mb-2">Preview</p>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2 font-medium text-gray-600">Product</th>
                  <th className="text-right py-2 font-medium text-gray-600">Current</th>
                  <th className="text-right py-2 font-medium text-gray-600">New Price</th>
                  <th className="text-right py-2 font-medium text-gray-600">MAP</th>
                </tr>
              </thead>
              <tbody>
                {(newPrices ?? products.map((p) => ({ ...p, newPrice: p.base_price ?? 0, mapViolation: false }))).map((p) => (
                  <tr key={p.id} className={cn("border-b last:border-0", p.mapViolation && "bg-amber-50")}>
                    <td className="py-2 text-gray-800 truncate max-w-xs">{p.title}</td>
                    <td className="py-2 text-right text-gray-500">${(p.base_price ?? 0).toFixed(2)}</td>
                    <td className={cn("py-2 text-right font-medium", p.mapViolation ? "text-amber-700" : "text-green-700")}>
                      ${p.newPrice.toFixed(2)}
                    </td>
                    <td className="py-2 text-right text-xs text-gray-400">
                      {p.map_price != null ? `$${Number(p.map_price).toFixed(2)}` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t bg-gray-50 flex gap-3 flex-shrink-0">
            <Button
              onClick={() => applyMutation.mutate()}
              disabled={!value || !newPrices || applyMutation.isPending || (violations > 0 && !confirmed)}
            >
              {applyMutation.isPending
                ? <><Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />Applying...</>
                : <><DollarSign className="h-3.5 w-3.5 mr-1" />Apply to {products.length} Products</>}
            </Button>
            <Button variant="outline" onClick={onClose}>Cancel</Button>
          </div>
        </div>
      </div>
    </>
  );
}
