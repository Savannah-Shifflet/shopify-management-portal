import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatPrice(value: number | string | null | undefined): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(
    Number(value)
  );
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function formatPercent(value: number | string | null | undefined): string {
  if (value == null) return "—";
  return `${Number(value).toFixed(1)}%`;
}

export function statusColor(status: string): string {
  const map: Record<string, string> = {
    draft: "bg-gray-100 text-gray-700",
    enriched: "bg-blue-100 text-blue-700",
    approved: "bg-green-100 text-green-700",
    synced: "bg-emerald-100 text-emerald-700",
    archived: "bg-red-100 text-red-700",
    never_synced: "bg-gray-100 text-gray-600",
    pending: "bg-yellow-100 text-yellow-700",
    out_of_sync: "bg-orange-100 text-orange-700",
    failed: "bg-red-100 text-red-700",
    running: "bg-blue-100 text-blue-700",
    done: "bg-green-100 text-green-700",
    queued: "bg-gray-100 text-gray-600",
  };
  return map[status] ?? "bg-gray-100 text-gray-600";
}
