"use client";

import { useState, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useQueries, useMutation, useQueryClient } from "@tanstack/react-query";
import { productsApi } from "@/lib/api";
import { PageShell } from "@/components/layout/PageShell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MergeFieldRow } from "@/components/products/MergeFieldRow";
import { cn, statusColor } from "@/lib/utils";
import type { Product, MergeOverrides } from "@/types/product";
import { GitMerge, Loader2, Package, ArrowLeft, X, Plus } from "lucide-react";
import { Input } from "@/components/ui/input";

type FieldKey =
  | "title" | "body_html" | "vendor" | "product_type"
  | "seo_title" | "seo_description"
  | "base_price" | "cost_price" | "compare_at_price";

interface MergeState {
  primaryId: string;
  fieldChoices: Record<FieldKey, string>; // productId
  tagsStrategy: string;
  imagesStrategy: string;
  // null = use imagesStrategy; string[] = custom ordered list of src URLs
  customImages: string[] | null;
}

const FIELD_SECTIONS: { label: string; fields: { key: FieldKey; label: string; multiline?: boolean }[] }[] = [
  {
    label: "Text Fields",
    fields: [
      { key: "title", label: "Title" },
      { key: "vendor", label: "Vendor" },
      { key: "product_type", label: "Product Type" },
    ],
  },
  {
    label: "Description",
    fields: [{ key: "body_html", label: "Description", multiline: true }],
  },
  {
    label: "Pricing",
    fields: [
      { key: "base_price", label: "Base Price" },
      { key: "cost_price", label: "Cost Price" },
      { key: "compare_at_price", label: "Compare At" },
    ],
  },
  {
    label: "SEO",
    fields: [
      { key: "seo_title", label: "SEO Title" },
      { key: "seo_description", label: "SEO Description", multiline: true },
    ],
  },
];

function defaultState(products: Product[]): MergeState {
  const firstId = products[0].id;
  const fieldChoices = {} as Record<FieldKey, string>;
  const allFieldKeys: FieldKey[] = [
    "title", "body_html", "vendor", "product_type",
    "seo_title", "seo_description", "base_price", "cost_price", "compare_at_price",
  ];
  // For each field, default to the first product that has a non-empty value
  for (const key of allFieldKeys) {
    const bestProduct = products.find((p) => {
      const v = p[key as keyof Product];
      return v != null && v !== "";
    });
    fieldChoices[key] = bestProduct?.id ?? firstId;
  }
  return { primaryId: firstId, fieldChoices, tagsStrategy: "union", imagesStrategy: "union", customImages: null };
}

function buildPayload(state: MergeState, products: Product[], ids: string[]) {
  const overrides: MergeOverrides = {};
  const allFieldKeys: FieldKey[] = [
    "title", "body_html", "vendor", "product_type",
    "seo_title", "seo_description", "base_price", "cost_price", "compare_at_price",
  ];
  for (const key of allFieldKeys) {
    const sourceProduct = products.find((p) => p.id === state.fieldChoices[key]);
    const val = sourceProduct?.[key as keyof Product];
    if (val != null && val !== "") {
      (overrides as Record<string, unknown>)[key] = String(val);
    }
  }
  overrides.tags_strategy = state.tagsStrategy;
  if (state.customImages !== null) {
    overrides.image_srcs = state.customImages;
  } else {
    overrides.images_strategy = state.imagesStrategy;
  }

  return {
    primary_id: state.primaryId,
    secondary_ids: ids.filter((id) => id !== state.primaryId),
    overrides,
  };
}

export default function MergePage() {
  const router = useRouter();
  const qc = useQueryClient();
  const searchParams = useSearchParams();
  const rawIds = searchParams.get("ids") ?? "";
  const ids = rawIds.split(",").filter(Boolean);

  const results = useQueries({
    queries: ids.map((id) => ({
      queryKey: ["product", id],
      queryFn: () => productsApi.get(id).then((r) => r.data as Product),
    })),
  });

  const products = results.map((r) => r.data).filter(Boolean) as Product[];
  const isLoading = results.some((r) => r.isLoading);
  const isError = results.some((r) => r.isError);

  const [mergeState, setMergeState] = useState<MergeState | null>(null);
  const [urlInput, setUrlInput] = useState("");

  useEffect(() => {
    if (products.length >= 2 && !mergeState) {
      setMergeState(defaultState(products));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [products.length]);

  const mergeMutation = useMutation({
    mutationFn: () => {
      if (!mergeState) throw new Error("No state");
      return productsApi.merge(buildPayload(mergeState, products, ids));
    },
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["products"] });
      qc.invalidateQueries({ queryKey: ["products", "duplicate-skus"] });
      qc.removeQueries({ queryKey: ["product", res.data.primary_id] });
      router.push(`/products/${res.data.primary_id}`);
    },
  });

  const setFieldChoice = (key: FieldKey, productId: string) => {
    setMergeState((s) => s ? { ...s, fieldChoices: { ...s.fieldChoices, [key]: productId } } : s);
  };

  // Collect all unique image srcs from all products (deduped by src)
  const allImageSrcs = (() => {
    const seen = new Set<string>();
    const out: string[] = [];
    for (const p of products) {
      for (const img of p.images ?? []) {
        if (!seen.has(img.src)) { seen.add(img.src); out.push(img.src); }
      }
    }
    return out;
  })();

  const enterCustomImages = () => {
    // Initialise with current effective set based on selected strategy
    let initial: string[];
    if (mergeState!.imagesStrategy === "union") {
      initial = allImageSrcs;
    } else if (mergeState!.imagesStrategy.startsWith("product:")) {
      const pid = mergeState!.imagesStrategy.split(":")[1];
      initial = (products.find((p) => p.id === pid)?.images ?? []).map((i) => i.src);
    } else {
      initial = allImageSrcs;
    }
    setMergeState((s) => s ? { ...s, customImages: initial } : s);
  };

  const addImageUrl = () => {
    const trimmed = urlInput.trim();
    if (!trimmed) return;
    setMergeState((s) => s ? { ...s, customImages: [...(s.customImages ?? []), trimmed] } : s);
    setUrlInput("");
  };

  const removeImage = (src: string) => {
    setMergeState((s) => s ? { ...s, customImages: (s.customImages ?? []).filter((u) => u !== src) } : s);
  };

  if (ids.length < 2) {
    return (
      <PageShell title="Merge Products">
        <div className="text-center py-20">
          <p className="text-gray-500">Select at least 2 products to merge.</p>
          <Button variant="outline" onClick={() => router.push("/products")} className="mt-4">
            <ArrowLeft className="h-4 w-4 mr-1" /> Back to Products
          </Button>
        </div>
      </PageShell>
    );
  }

  if (isLoading || !mergeState) {
    return (
      <PageShell title="Merge Products">
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
        </div>
      </PageShell>
    );
  }

  if (isError) {
    return (
      <PageShell title="Merge Products">
        <div className="text-center py-20">
          <p className="text-red-500">Failed to load product data.</p>
          <Button variant="outline" onClick={() => router.push("/products")} className="mt-4">
            <ArrowLeft className="h-4 w-4 mr-1" /> Back to Products
          </Button>
        </div>
      </PageShell>
    );
  }

  // Compute preview of all tags (for union display)
  const allTags = [...new Set(products.flatMap((p) => p.tags ?? []))];

  return (
    <PageShell
      title="Merge Products"
      description={`${products.length} products sharing the same SKU`}
      actions={
        <div className="flex items-center gap-3">
          <Button variant="outline" onClick={() => router.push("/products")}>
            <ArrowLeft className="h-4 w-4 mr-1" /> Back
          </Button>
          <Button
            onClick={() => mergeMutation.mutate()}
            disabled={mergeMutation.isPending}
          >
            {mergeMutation.isPending ? (
              <><Loader2 className="h-4 w-4 mr-1 animate-spin" /> Merging…</>
            ) : (
              <><GitMerge className="h-4 w-4 mr-1" /> Merge {products.length} Products</>
            )}
          </Button>
        </div>
      }
    >
      {mergeMutation.isError && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {(mergeMutation.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Merge failed — please try again."}
        </div>
      )}

      {/* ── Primary product selector ── */}
      <Card className="mb-6">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Surviving Record</CardTitle>
          <p className="text-sm text-gray-500">
            The primary product keeps its ID and Shopify link. All others will be deleted after merging.
          </p>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            {products.map((p) => {
              const isSelected = mergeState.primaryId === p.id;
              return (
                <label
                  key={p.id}
                  className={cn(
                    "flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors flex-1 min-w-[200px]",
                    isSelected ? "border-blue-500 bg-blue-50" : "border-gray-200 hover:bg-gray-50"
                  )}
                >
                  <input
                    type="radio"
                    name="primary"
                    checked={isSelected}
                    onChange={() => setMergeState((s) => s ? { ...s, primaryId: p.id } : s)}
                    className="shrink-0 accent-blue-600"
                  />
                  {p.images?.[0]?.src ? (
                    <img src={p.images[0].src} alt="" className="w-10 h-10 object-cover rounded shrink-0" />
                  ) : (
                    <div className="w-10 h-10 bg-gray-100 rounded flex items-center justify-center shrink-0">
                      <Package className="h-4 w-4 text-gray-400" />
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm text-gray-900 truncate">{p.title}</p>
                    <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                      <span className={cn("px-1.5 py-0.5 rounded-full text-xs capitalize", statusColor(p.status))}>
                        {p.status}
                      </span>
                      {p.shopify_product_id && (
                        <span className="text-xs text-gray-400">Shopify linked</span>
                      )}
                    </div>
                  </div>
                  {isSelected && (
                    <span className="text-xs font-semibold text-blue-700 bg-blue-100 px-2 py-0.5 rounded-full shrink-0">
                      Primary
                    </span>
                  )}
                </label>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* ── Field picker sections ── */}
      {FIELD_SECTIONS.map((section) => (
        <Card key={section.label} className="mb-4">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
              {section.label}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-gray-50">
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 w-36">Field</th>
                    {products.map((p) => (
                      <th key={p.id} className="px-4 py-2 text-left text-xs font-medium text-gray-500">
                        <div className="truncate max-w-[180px]">{p.title}</div>
                        <span className={cn("px-1.5 py-0.5 rounded-full text-xs capitalize", statusColor(p.status))}>
                          {p.status}
                        </span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {section.fields.map(({ key, label, multiline }) => (
                    <MergeFieldRow
                      key={key}
                      label={label}
                      fieldKey={key}
                      products={products}
                      selectedProductId={mergeState.fieldChoices[key]}
                      onChange={(productId) => setFieldChoice(key, productId)}
                      multiline={multiline}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      ))}

      {/* ── Tags ── */}
      <Card className="mb-4">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Tags</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <label className={cn(
            "flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors",
            mergeState.tagsStrategy === "union" ? "border-blue-500 bg-blue-50" : "border-gray-200 hover:bg-gray-50"
          )}>
            <input
              type="radio"
              checked={mergeState.tagsStrategy === "union"}
              onChange={() => setMergeState((s) => s ? { ...s, tagsStrategy: "union" } : s)}
              className="mt-0.5 shrink-0 accent-blue-600"
            />
            <div>
              <p className="text-sm font-medium text-gray-800">Union all tags <span className="text-xs font-normal text-gray-500">(recommended)</span></p>
              {allTags.length > 0 ? (
                <div className="flex flex-wrap gap-1 mt-1">
                  {allTags.map((t) => (
                    <span key={t} className="px-1.5 py-0.5 bg-gray-100 rounded text-xs text-gray-600">{t}</span>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-gray-400 italic mt-0.5">No tags across any product</p>
              )}
            </div>
          </label>
          {products.map((p) => {
            const stratVal = `product:${p.id}`;
            const isSelected = mergeState.tagsStrategy === stratVal;
            return (
              <label key={p.id} className={cn(
                "flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors",
                isSelected ? "border-blue-500 bg-blue-50" : "border-gray-200 hover:bg-gray-50"
              )}>
                <input
                  type="radio"
                  checked={isSelected}
                  onChange={() => setMergeState((s) => s ? { ...s, tagsStrategy: stratVal } : s)}
                  className="mt-0.5 shrink-0 accent-blue-600"
                />
                <div>
                  <p className="text-sm font-medium text-gray-800 truncate">{p.title}</p>
                  {(p.tags ?? []).length > 0 ? (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {(p.tags ?? []).map((t) => (
                        <span key={t} className="px-1.5 py-0.5 bg-gray-100 rounded text-xs text-gray-600">{t}</span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-gray-400 italic mt-0.5">No tags</p>
                  )}
                </div>
              </label>
            );
          })}
        </CardContent>
      </Card>

      {/* ── Images ── */}
      <Card className="mb-8">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Images</CardTitle>
            {mergeState.customImages === null ? (
              <button
                onClick={enterCustomImages}
                className="text-xs text-blue-600 hover:underline"
              >
                Customize
              </button>
            ) : (
              <button
                onClick={() => setMergeState((s) => s ? { ...s, customImages: null } : s)}
                className="text-xs text-gray-500 hover:underline"
              >
                Reset to preset
              </button>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-2">
          {mergeState.customImages === null ? (
            /* ── Strategy presets ── */
            <>
              <label className={cn(
                "flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors",
                mergeState.imagesStrategy === "union" ? "border-blue-500 bg-blue-50" : "border-gray-200 hover:bg-gray-50"
              )}>
                <input
                  type="radio"
                  checked={mergeState.imagesStrategy === "union"}
                  onChange={() => setMergeState((s) => s ? { ...s, imagesStrategy: "union" } : s)}
                  className="mt-0.5 shrink-0 accent-blue-600"
                />
                <div>
                  <p className="text-sm font-medium text-gray-800">
                    Combine images from all products <span className="text-xs font-normal text-gray-500">(recommended)</span>
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {allImageSrcs.length} unique images
                  </p>
                </div>
              </label>
              {products.map((p) => {
                const stratVal = `product:${p.id}`;
                const isSelected = mergeState.imagesStrategy === stratVal;
                const imgs = p.images ?? [];
                return (
                  <label key={p.id} className={cn(
                    "flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors",
                    isSelected ? "border-blue-500 bg-blue-50" : "border-gray-200 hover:bg-gray-50"
                  )}>
                    <input
                      type="radio"
                      checked={isSelected}
                      onChange={() => setMergeState((s) => s ? { ...s, imagesStrategy: stratVal } : s)}
                      className="mt-0.5 shrink-0 accent-blue-600"
                    />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-gray-800 truncate">{p.title}</p>
                      <p className="text-xs text-gray-500 mt-0.5">{imgs.length} {imgs.length === 1 ? "image" : "images"}</p>
                      {imgs.length > 0 && (
                        <div className="flex gap-2 mt-2 flex-wrap">
                          {imgs.slice(0, 6).map((img) => (
                            <img key={img.id} src={img.src} alt={img.alt ?? ""} className="w-14 h-14 object-cover rounded border border-gray-200" />
                          ))}
                          {imgs.length > 6 && (
                            <div className="w-14 h-14 rounded border border-gray-200 bg-gray-100 flex items-center justify-center text-xs text-gray-500">
                              +{imgs.length - 6}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </label>
                );
              })}
            </>
          ) : (
            /* ── Custom image editor ── */
            <div>
              {mergeState.customImages.length === 0 ? (
                <p className="text-sm text-gray-400 italic py-2">No images — add some below.</p>
              ) : (
                <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-3 mb-4">
                  {mergeState.customImages.map((src) => (
                    <div key={src} className="relative group">
                      <img
                        src={src}
                        alt=""
                        className="w-full aspect-square object-cover rounded-lg border border-gray-200"
                        onError={(e) => { (e.target as HTMLImageElement).src = ""; }}
                      />
                      <button
                        onClick={() => removeImage(src)}
                        className="absolute top-1 right-1 bg-black/60 hover:bg-black/80 text-white rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
                        title="Remove image"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              {/* Add by URL */}
              <div className="flex gap-2 mt-2">
                <Input
                  placeholder="https://example.com/image.jpg"
                  value={urlInput}
                  onChange={(e) => setUrlInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addImageUrl(); } }}
                  className="flex-1 text-sm"
                />
                <Button
                  size="sm"
                  variant="outline"
                  onClick={addImageUrl}
                  disabled={!urlInput.trim()}
                >
                  <Plus className="h-3.5 w-3.5 mr-1" /> Add
                </Button>
              </div>
              <p className="text-xs text-gray-400 mt-1.5">
                {mergeState.customImages.length} {mergeState.customImages.length === 1 ? "image" : "images"} · hover to remove · paste a URL and press Enter or Add
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Bottom action bar */}
      <div className="flex justify-end gap-3">
        <Button variant="outline" onClick={() => router.push("/products")}>
          Cancel
        </Button>
        <Button
          onClick={() => mergeMutation.mutate()}
          disabled={mergeMutation.isPending}
        >
          {mergeMutation.isPending ? (
            <><Loader2 className="h-4 w-4 mr-1 animate-spin" /> Merging…</>
          ) : (
            <><GitMerge className="h-4 w-4 mr-1" /> Merge {products.length} Products</>
          )}
        </Button>
      </div>
    </PageShell>
  );
}
