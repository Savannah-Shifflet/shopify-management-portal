"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { setToken } from "@/lib/auth";
import { Loader2, AlertCircle } from "lucide-react";

export default function ShopifyOAuthCallbackPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = searchParams.get("token");
    if (token) {
      setToken(token);
      router.replace("/products");
    } else {
      setError("Shopify authentication failed — no token received. Please try again.");
    }
  }, [searchParams, router]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center max-w-sm">
          <AlertCircle className="h-10 w-10 text-red-400 mx-auto mb-3" />
          <p className="text-gray-700 font-medium mb-1">Connection failed</p>
          <p className="text-sm text-gray-500 mb-4">{error}</p>
          <a href="/settings" className="text-sm text-blue-600 hover:underline">
            Back to Settings
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500 mx-auto mb-3" />
        <p className="text-sm text-gray-500">Completing Shopify connection...</p>
      </div>
    </div>
  );
}
