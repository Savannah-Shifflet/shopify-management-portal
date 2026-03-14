"use client";

import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { productsApi, suppliersApi } from "@/lib/api";
import { useRouter } from "next/navigation";
import { Package, Search, Truck, X } from "lucide-react";

export function GlobalSearch() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const router = useRouter();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []);

  const { data: products } = useQuery({
    queryKey: ["search-products", query],
    queryFn: () =>
      productsApi.list({ search: query, page_size: 5 }).then((r) => r.data.items ?? []),
    enabled: query.length >= 2,
  });

  const { data: suppliers } = useQuery({
    queryKey: ["search-suppliers", query],
    queryFn: () =>
      suppliersApi.list().then((r) =>
        (r.data as any[])
          .filter(
            (s: any) =>
              s.name?.toLowerCase().includes(query.toLowerCase()) ||
              s.company_email?.toLowerCase().includes(query.toLowerCase())
          )
          .slice(0, 5)
      ),
    enabled: query.length >= 2,
  });

  const navigate = (href: string) => {
    setOpen(false);
    setQuery("");
    router.push(href);
  };

  if (!open) return null;

  const productResults = (products ?? []) as any[];
  const supplierResults = (suppliers ?? []) as any[];
  const hasResults = productResults.length > 0 || supplierResults.length > 0;

  return (
    <>
      <div className="fixed inset-0 bg-black/40 z-50" onClick={() => setOpen(false)} />
      <div className="fixed top-20 left-1/2 -translate-x-1/2 z-50 w-full max-w-lg bg-white rounded-xl shadow-2xl overflow-hidden">
        <div className="flex items-center gap-3 px-4 py-3 border-b">
          <Search className="h-5 w-5 text-gray-400 flex-shrink-0" />
          <input
            autoFocus
            placeholder="Search products, suppliers... (Esc to close)"
            className="flex-1 outline-none text-sm"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button onClick={() => setOpen(false)}>
            <X className="h-4 w-4 text-gray-400 hover:text-gray-600" />
          </button>
        </div>

        {query.length >= 2 ? (
          <div className="max-h-80 overflow-y-auto">
            {productResults.length > 0 && (
              <div>
                <p className="px-4 py-2 text-xs font-semibold text-gray-400 uppercase tracking-wide bg-gray-50">
                  Products
                </p>
                {productResults.map((p: any) => (
                  <button
                    key={p.id}
                    onClick={() => navigate(`/products/${p.id}`)}
                    className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-blue-50 text-left border-b border-gray-50"
                  >
                    <Package className="h-4 w-4 text-gray-400 flex-shrink-0" />
                    <div>
                      <p className="text-sm font-medium">{p.title}</p>
                      {p.vendor && <p className="text-xs text-gray-400">{p.vendor}</p>}
                    </div>
                    {p.base_price && (
                      <span className="ml-auto text-xs text-gray-500">
                        ${Number(p.base_price).toFixed(2)}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            )}
            {supplierResults.length > 0 && (
              <div>
                <p className="px-4 py-2 text-xs font-semibold text-gray-400 uppercase tracking-wide bg-gray-50">
                  Suppliers
                </p>
                {supplierResults.map((s: any) => (
                  <button
                    key={s.id}
                    onClick={() => navigate(`/suppliers/${s.id}`)}
                    className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-blue-50 text-left border-b border-gray-50"
                  >
                    <Truck className="h-4 w-4 text-gray-400 flex-shrink-0" />
                    <div>
                      <p className="text-sm font-medium">{s.name}</p>
                      {s.company_email && (
                        <p className="text-xs text-gray-400">{s.company_email}</p>
                      )}
                    </div>
                    <span className="ml-auto text-xs text-gray-400">{s.status}</span>
                  </button>
                ))}
              </div>
            )}
            {!hasResults && (
              <p className="px-4 py-8 text-center text-sm text-gray-400">
                No results for &quot;{query}&quot;
              </p>
            )}
          </div>
        ) : (
          <p className="px-4 py-6 text-center text-sm text-gray-400">
            Type at least 2 characters to search
          </p>
        )}

        <div className="px-4 py-2 border-t bg-gray-50 flex items-center gap-4 text-xs text-gray-400">
          <span><kbd className="bg-white border rounded px-1">↵</kbd> to open</span>
          <span><kbd className="bg-white border rounded px-1">Esc</kbd> to close</span>
          <span className="ml-auto"><kbd className="bg-white border rounded px-1">Ctrl</kbd>+<kbd className="bg-white border rounded px-1">K</kbd> to toggle</span>
        </div>
      </div>
    </>
  );
}
