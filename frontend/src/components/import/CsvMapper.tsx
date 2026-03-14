"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { importsApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Loader2, Wand2 } from "lucide-react";

const PRODUCT_FIELDS = [
  { value: "", label: "— ignore —" },
  { value: "title", label: "Title" },
  { value: "sku", label: "SKU" },
  { value: "description", label: "Description" },
  { value: "price", label: "Price" },
  { value: "cost", label: "Cost" },
  { value: "vendor", label: "Vendor" },
  { value: "product_type", label: "Product Type" },
  { value: "barcode", label: "Barcode" },
  { value: "weight", label: "Weight" },
  { value: "tags", label: "Tags" },
  { value: "option1", label: "Option 1 (e.g. Size)" },
  { value: "option2", label: "Option 2 (e.g. Color)" },
  { value: "option3", label: "Option 3" },
];

interface CsvMapperProps {
  headers: string[];
  sampleRows: string[][];
  onConfirm: (mapping: Record<string, string>) => void;
  onCancel: () => void;
  isSubmitting: boolean;
}

export function CsvMapper({ headers, sampleRows, onConfirm, onCancel, isSubmitting }: CsvMapperProps) {
  const [mapping, setMapping] = useState<Record<string, string>>(() =>
    Object.fromEntries(headers.map((h) => [h, ""]))
  );

  const suggestMutation = useMutation({
    mutationFn: () =>
      importsApi.suggestColumnMap({ headers, sample_rows: sampleRows }).then((r) => r.data),
    onSuccess: (data) => {
      setMapping((prev) => {
        const next = { ...prev };
        Object.entries(data.mapping as Record<string, string>).forEach(([col, field]) => {
          if (col in next) next[col] = field;
        });
        return next;
      });
    },
  });

  const mappedCount = Object.values(mapping).filter(Boolean).length;

  return (
    <div className="mt-4 space-y-3" onClick={(e) => e.stopPropagation()}>
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-600">
          Map your CSV columns to product fields.{" "}
          <span className="text-gray-400">{mappedCount} of {headers.length} mapped.</span>
        </p>
        <Button
          variant="outline"
          size="sm"
          onClick={() => suggestMutation.mutate()}
          disabled={suggestMutation.isPending}
        >
          {suggestMutation.isPending ? (
            <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />Thinking...</>
          ) : (
            <><Wand2 className="h-3.5 w-3.5 mr-1.5" />AI Suggest</>
          )}
        </Button>
      </div>

      <div className="border rounded-lg overflow-hidden text-sm">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-50 border-b">
              <th className="text-left px-3 py-2 font-medium text-gray-500 w-1/3">CSV Column</th>
              <th className="text-left px-3 py-2 font-medium text-gray-500 w-1/3">Sample Data</th>
              <th className="text-left px-3 py-2 font-medium text-gray-500 w-1/3">Maps To</th>
            </tr>
          </thead>
          <tbody>
            {headers.map((header, i) => (
              <tr key={header} className="border-b last:border-0">
                <td className="px-3 py-2 font-mono text-xs text-gray-700 truncate max-w-0 w-1/3">
                  {header}
                </td>
                <td className="px-3 py-2 text-gray-400 text-xs truncate max-w-0 w-1/3">
                  {sampleRows
                    .slice(0, 2)
                    .map((r) => r[i])
                    .filter(Boolean)
                    .join(", ") || "—"}
                </td>
                <td className="px-3 py-2 w-1/3">
                  <select
                    value={mapping[header] ?? ""}
                    onChange={(e) =>
                      setMapping((m) => ({ ...m, [header]: e.target.value }))
                    }
                    className="w-full text-xs border rounded px-2 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                  >
                    {PRODUCT_FIELDS.map((f) => (
                      <option key={f.value} value={f.value}>
                        {f.label}
                      </option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex gap-2 justify-end pt-1">
        <Button variant="outline" size="sm" onClick={onCancel} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button size="sm" onClick={() => onConfirm(mapping)} disabled={isSubmitting}>
          {isSubmitting ? (
            <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />Starting Import...</>
          ) : (
            "Start Import"
          )}
        </Button>
      </div>
    </div>
  );
}
