"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { productsApi } from "@/lib/api";
import { PageShell } from "@/components/layout/PageShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowLeft, Plus, Loader2 } from "lucide-react";
import Link from "next/link";

export default function NewProductPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    title: "",
    body_html: "",
    vendor: "",
    product_type: "",
    tags: "",
    base_price: "",
    cost_price: "",
  });

  const createMutation = useMutation({
    mutationFn: () =>
      productsApi.create({
        title: form.title,
        body_html: form.body_html || undefined,
        vendor: form.vendor || undefined,
        product_type: form.product_type || undefined,
        tags: form.tags ? form.tags.split(",").map((t) => t.trim()).filter(Boolean) : undefined,
        base_price: form.base_price ? Number(form.base_price) : undefined,
        cost_price: form.cost_price ? Number(form.cost_price) : undefined,
        source_type: "manual",
      }),
    onSuccess: (res) => {
      router.push(`/products/${res.data.id}`);
    },
  });

  const setField = (field: string, value: string) =>
    setForm((prev) => ({ ...prev, [field]: value }));

  return (
    <PageShell
      title="New Product"
      description="Manually enter product details"
      actions={
        <Link href="/products">
          <Button variant="ghost" size="sm"><ArrowLeft className="h-4 w-4 mr-1" />Back</Button>
        </Link>
      }
    >
      <div className="max-w-2xl space-y-6">
        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="text-base">Product Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label>Title <span className="text-red-500">*</span></Label>
              <Input
                className="mt-1"
                value={form.title}
                onChange={(e) => setField("title", e.target.value)}
                placeholder="e.g. Nike Air Max 270"
              />
            </div>
            <div>
              <Label>Description</Label>
              <Textarea
                className="mt-1"
                rows={5}
                value={form.body_html}
                onChange={(e) => setField("body_html", e.target.value)}
                placeholder="Product description..."
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Vendor / Brand</Label>
                <Input className="mt-1" value={form.vendor} onChange={(e) => setField("vendor", e.target.value)} placeholder="Nike" />
              </div>
              <div>
                <Label>Product Type</Label>
                <Input className="mt-1" value={form.product_type} onChange={(e) => setField("product_type", e.target.value)} placeholder="Shoes" />
              </div>
            </div>
            <div>
              <Label>Tags <span className="text-xs text-gray-400">(comma separated)</span></Label>
              <Input
                className="mt-1"
                value={form.tags}
                onChange={(e) => setField("tags", e.target.value)}
                placeholder="running, athletic, footwear"
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="text-base">Pricing</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-4">
            <div>
              <Label>Cost Price</Label>
              <div className="relative mt-1">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">$</span>
                <Input
                  className="pl-7"
                  type="number"
                  step="0.01"
                  value={form.cost_price}
                  onChange={(e) => setField("cost_price", e.target.value)}
                  placeholder="0.00"
                />
              </div>
            </div>
            <div>
              <Label>Retail Price</Label>
              <div className="relative mt-1">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">$</span>
                <Input
                  className="pl-7"
                  type="number"
                  step="0.01"
                  value={form.base_price}
                  onChange={(e) => setField("base_price", e.target.value)}
                  placeholder="0.00"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="flex gap-3">
          <Button
            onClick={() => createMutation.mutate()}
            disabled={!form.title || createMutation.isPending}
          >
            {createMutation.isPending
              ? <><Loader2 className="h-4 w-4 mr-1 animate-spin" />Creating...</>
              : <><Plus className="h-4 w-4 mr-1" />Create Product</>}
          </Button>
          <Link href="/products">
            <Button variant="outline">Cancel</Button>
          </Link>
        </div>
      </div>
    </PageShell>
  );
}
