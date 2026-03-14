"use client";
import type { Product } from "@/types/product";
import { cn } from "@/lib/utils";

interface Props {
  label: string;
  fieldKey: keyof Product;
  products: Product[];
  selectedProductId: string;
  onChange: (productId: string) => void;
  multiline?: boolean;
}

export function MergeFieldRow({ label, fieldKey, products, selectedProductId, onChange, multiline }: Props) {
  return (
    <tr className="border-b last:border-0">
      <td className="px-4 py-3 text-sm font-medium text-gray-600 align-top w-36 shrink-0 whitespace-nowrap">
        {label}
      </td>
      {products.map((p) => {
        const raw = p[fieldKey];
        const val = raw != null && raw !== "" ? String(raw) : null;
        const display = multiline && val
          ? val.replace(/<[^>]+>/g, "").slice(0, 160) + (val.replace(/<[^>]+>/g, "").length > 160 ? "…" : "")
          : val;
        const isSelected = selectedProductId === p.id;
        return (
          <td
            key={p.id}
            onClick={() => onChange(p.id)}
            className={cn(
              "px-4 py-3 text-sm cursor-pointer border-l-2 transition-colors align-top",
              isSelected
                ? "border-blue-500 bg-blue-50"
                : "border-transparent hover:bg-gray-50"
            )}
          >
            <div className="flex items-start gap-2">
              <input
                type="radio"
                readOnly
                checked={isSelected}
                className="mt-0.5 shrink-0 accent-blue-600"
              />
              {display != null ? (
                <span className={cn("break-words", multiline ? "text-xs text-gray-700 line-clamp-4" : "")}>
                  {display}
                </span>
              ) : (
                <span className="text-gray-400 italic">—</span>
              )}
            </div>
          </td>
        );
      })}
    </tr>
  );
}
