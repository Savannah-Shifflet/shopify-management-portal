"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { productsApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Plus, Trash2, Save, Loader2 } from "lucide-react";
import type { ProductVariant, ProductOption } from "@/types/product";

interface VariantEditorProps {
  productId: string;
  variants: ProductVariant[];
  options?: ProductOption[];
}

export function VariantEditor({ productId, variants: initialVariants, options }: VariantEditorProps) {
  // Build sorted option names from the product-level options definition
  const optionNames = (options ?? [])
    .slice()
    .sort((a, b) => a.position - b.position)
    .map((o) => o.name);
  const opt1Label = optionNames[0] ?? "Option 1";
  const opt2Label = optionNames[1] ?? "Option 2";
  const opt3Label = optionNames[2] ?? "Option 3";
  // Determine which option columns have any data
  const hasOpt1 = initialVariants.some((v) => v.option1);
  const hasOpt2 = initialVariants.some((v) => v.option2);
  const hasOpt3 = initialVariants.some((v) => v.option3);
  const qc = useQueryClient();
  const [rows, setRows] = useState<ProductVariant[]>(initialVariants);
  const [dirty, setDirty] = useState<Set<string>>(new Set());

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<ProductVariant> }) =>
      productsApi.variants.update(productId, id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["product", productId] });
      setDirty(new Set());
    },
  });

  const createMutation = useMutation({
    mutationFn: (data: Partial<ProductVariant>) =>
      productsApi.variants.create(productId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["product", productId] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (variantId: string) => productsApi.variants.delete(productId, variantId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["product", productId] }),
  });

  const updateRow = (id: string, field: keyof ProductVariant, value: unknown) => {
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, [field]: value } : r)));
    setDirty((prev) => new Set(prev).add(id));
  };

  const saveAll = async () => {
    for (const id of dirty) {
      const row = rows.find((r) => r.id === id);
      if (row) {
        await updateMutation.mutateAsync({
          id,
          data: {
            sku: row.sku,
            barcode: row.barcode,
            price: row.price,
            compare_at_price: row.compare_at_price,
            cost: row.cost,
            inventory_quantity: row.inventory_quantity,
            option1: row.option1,
            option2: row.option2,
          },
        });
      }
    }
  };

  const addVariant = () => {
    createMutation.mutate({
      title: "New Variant",
      price: 0 as unknown as string,
      position: rows.length + 1,
    });
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Variants</CardTitle>
          <div className="flex gap-2">
            {dirty.size > 0 && (
              <Button size="sm" onClick={saveAll} disabled={updateMutation.isPending}>
                {updateMutation.isPending
                  ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
                  : <Save className="h-3.5 w-3.5 mr-1" />}
                Save Changes
              </Button>
            )}
            <Button size="sm" variant="outline" onClick={addVariant}>
              <Plus className="h-3.5 w-3.5 mr-1" /> Add Variant
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="text-left px-3 py-2 font-medium text-gray-500 text-xs">SKU</th>
                {hasOpt1 && <th className="text-left px-3 py-2 font-medium text-gray-500 text-xs">{opt1Label}</th>}
                {hasOpt2 && <th className="text-left px-3 py-2 font-medium text-gray-500 text-xs">{opt2Label}</th>}
                {hasOpt3 && <th className="text-left px-3 py-2 font-medium text-gray-500 text-xs">{opt3Label}</th>}
                <th className="text-left px-3 py-2 font-medium text-gray-500 text-xs">Price</th>
                <th className="text-left px-3 py-2 font-medium text-gray-500 text-xs">Compare At</th>
                <th className="text-left px-3 py-2 font-medium text-gray-500 text-xs">Cost</th>
                <th className="text-left px-3 py-2 font-medium text-gray-500 text-xs">Inventory</th>
                <th className="w-10"></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((v) => (
                <tr
                  key={v.id}
                  className={`border-b last:border-0 ${dirty.has(v.id) ? "bg-yellow-50" : ""}`}
                >
                  <td className="px-3 py-2">
                    <Input
                      className="h-8 text-xs"
                      value={v.sku ?? ""}
                      onChange={(e) => updateRow(v.id, "sku", e.target.value)}
                    />
                  </td>
                  {hasOpt1 && (
                    <td className="px-3 py-2">
                      <Input
                        className="h-8 text-xs"
                        value={v.option1 ?? ""}
                        onChange={(e) => updateRow(v.id, "option1", e.target.value)}
                      />
                    </td>
                  )}
                  {hasOpt2 && (
                    <td className="px-3 py-2">
                      <Input
                        className="h-8 text-xs"
                        value={v.option2 ?? ""}
                        onChange={(e) => updateRow(v.id, "option2", e.target.value)}
                      />
                    </td>
                  )}
                  {hasOpt3 && (
                    <td className="px-3 py-2">
                      <Input
                        className="h-8 text-xs"
                        value={v.option3 ?? ""}
                        onChange={(e) => updateRow(v.id, "option3", e.target.value)}
                      />
                    </td>
                  )}
                  <td className="px-3 py-2">
                    <div className="relative">
                      <span className="absolute left-2 top-1/2 -translate-y-1/2 text-gray-400 text-xs">$</span>
                      <Input
                        className="h-8 text-xs pl-5"
                        type="number"
                        step="0.01"
                        value={v.price ?? ""}
                        onChange={(e) => updateRow(v.id, "price", e.target.value)}
                      />
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <div className="relative">
                      <span className="absolute left-2 top-1/2 -translate-y-1/2 text-gray-400 text-xs">$</span>
                      <Input
                        className="h-8 text-xs pl-5"
                        type="number"
                        step="0.01"
                        value={v.compare_at_price ?? ""}
                        onChange={(e) => updateRow(v.id, "compare_at_price", e.target.value || null)}
                      />
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <div className="relative">
                      <span className="absolute left-2 top-1/2 -translate-y-1/2 text-gray-400 text-xs">$</span>
                      <Input
                        className="h-8 text-xs pl-5"
                        type="number"
                        step="0.01"
                        value={v.cost ?? ""}
                        onChange={(e) => updateRow(v.id, "cost", e.target.value)}
                      />
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <Input
                      className="h-8 text-xs"
                      type="number"
                      value={v.inventory_quantity ?? 0}
                      onChange={(e) => updateRow(v.id, "inventory_quantity", Number(e.target.value))}
                    />
                  </td>
                  <td className="px-3 py-2">
                    {rows.length > 1 && (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-gray-400 hover:text-red-500"
                        onClick={() => deleteMutation.mutate(v.id)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
