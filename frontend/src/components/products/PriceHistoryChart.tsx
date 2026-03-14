"use client";

import { useQuery } from "@tanstack/react-query";
import { productsApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TrendingUp, Loader2 } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { formatDate } from "@/lib/utils";

interface Props {
  productId: string;
}

function formatShort(dateStr: string) {
  return new Date(dateStr).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function PriceHistoryChart({ productId }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: ["price-history", productId],
    queryFn: () => productsApi.priceHistory(productId).then((r) => r.data),
  });

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex justify-center p-8">
          <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
        </CardContent>
      </Card>
    );
  }

  if (!data || data.length === 0) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <TrendingUp className="h-4 w-4" /> Price History
          </CardTitle>
        </CardHeader>
        <CardContent className="p-8 text-center text-gray-400 text-sm">
          No price history yet — price changes will appear here
        </CardContent>
      </Card>
    );
  }

  const chartData = data.map((entry: any) => ({
    date: formatShort(entry.created_at),
    price: parseFloat(entry.new_price),
    old: parseFloat(entry.old_price),
    source: entry.source,
  }));

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <TrendingUp className="h-4 w-4" /> Price History
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: "#9ca3af" }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 11, fill: "#9ca3af" }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => `$${v}`}
              width={50}
            />
            <Tooltip
              formatter={(value: number) => [`$${value.toFixed(2)}`, "Price"]}
              labelStyle={{ fontSize: 12 }}
              contentStyle={{ fontSize: 12, borderRadius: 6 }}
            />
            <Line
              type="monotone"
              dataKey="price"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={{ r: 3, fill: "#3b82f6" }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
        <p className="text-xs text-gray-400 mt-2">
          {data.length} price change{data.length !== 1 ? "s" : ""} recorded
        </p>
      </CardContent>
    </Card>
  );
}
