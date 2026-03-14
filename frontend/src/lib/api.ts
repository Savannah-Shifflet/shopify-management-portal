import axios from "axios";
import { getToken, clearToken } from "./auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  headers: { "Content-Type": "application/json" },
});

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Redirect to login on 401 (but not for auth endpoints themselves)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const isAuthRoute = error.config?.url?.startsWith("/auth/");
    if (error.response?.status === 401 && !isAuthRoute && typeof window !== "undefined") {
      clearToken();
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

// Auth
export const authApi = {
  register: (data: { email: string; password: string; name?: string }) =>
    api.post("/auth/register", data),
  login: (data: { email: string; password: string }) =>
    api.post("/auth/login", data),
  me: () => api.get("/auth/me"),
};

// Products
export const productsApi = {
  list: (params?: Record<string, unknown>) => api.get("/products", { params }),
  get: (id: string) => api.get(`/products/${id}`),
  create: (data: unknown) => api.post("/products", data),
  update: (id: string, data: unknown) => api.patch(`/products/${id}`, data),
  delete: (id: string) => api.delete(`/products/${id}`),
  bulk: (data: unknown) => api.post("/products/bulk", data),
  variants: {
    list: (productId: string) => api.get(`/products/${productId}/variants`),
    create: (productId: string, data: unknown) => api.post(`/products/${productId}/variants`, data),
    update: (productId: string, variantId: string, data: unknown) =>
      api.patch(`/products/${productId}/variants/${variantId}`, data),
    delete: (productId: string, variantId: string) =>
      api.delete(`/products/${productId}/variants/${variantId}`),
  },
  images: {
    list: (productId: string) => api.get(`/products/${productId}/images`),
    delete: (productId: string, imageId: string) =>
      api.delete(`/products/${productId}/images/${imageId}`),
    addByUrl: (productId: string, src: string, alt?: string) =>
      api.post(`/products/${productId}/images`, { src, alt }),
    upload: (productId: string, formData: FormData) =>
      api.post(`/products/${productId}/images`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      }),
  },
  priceHistory: (productId: string) => api.get(`/products/${productId}/price-history`),
  rescrape: (productId: string) => api.post(`/products/${productId}/rescrape`),
  merge: (payload: { primary_id: string; secondary_ids: string[]; overrides?: import("@/types/product").MergeOverrides }) =>
    api.post("/products/merge", payload),
  syncSupplierPrices: (supplierId?: string) =>
    api.post("/products/sync-supplier-prices", null, {
      params: supplierId ? { supplier_id: supplierId } : {},
    }),
  duplicateSkus: () => api.get("/products/duplicate-skus"),
};

// Enrichment
export const enrichmentApi = {
  enrich: (productId: string, options?: { fields?: string[]; template_id?: string }) =>
    api.post(`/enrichment/product/${productId}`, options ?? {}),
  bulkEnrich: (productIds: string[], fields?: string[], templateId?: string) =>
    api.post("/enrichment/bulk", {
      product_ids: productIds,
      fields: fields ?? null,
      template_id: templateId ?? null,
    }),
  status: (taskId: string) => api.get(`/enrichment/status/${taskId}`),
};

// Suppliers
export const suppliersApi = {
  list: () => api.get("/suppliers"),
  get: (id: string) => api.get(`/suppliers/${id}`),
  create: (data: unknown) => api.post("/suppliers", data),
  update: (id: string, data: unknown) => api.patch(`/suppliers/${id}`, data),
  delete: (id: string) => api.delete(`/suppliers/${id}`),
  testScrape: (id: string) => api.post(`/suppliers/${id}/test-scrape`),
  scrapeNow: (id: string) => api.post(`/suppliers/${id}/scrape-now`),
  scrapeStatus: (id: string) => api.get(`/suppliers/${id}/scrape-status`),
  scrapeSessionStatus: (id: string, sessionId: string) => api.get(`/suppliers/${id}/scrape-sessions/${sessionId}/status`),
  scrapeSessionItems: (id: string, sessionId: string) => api.get(`/suppliers/${id}/scrape-sessions/${sessionId}/items`),
  scrapeApprove: (id: string, sessionId: string, indices: number[]) => api.post(`/suppliers/${id}/scrape-sessions/${sessionId}/approve`, { indices }),
  suggestSelectors: (id: string, catalog_url?: string) => api.post(`/suppliers/${id}/suggest-selectors`, { catalog_url: catalog_url || null }),
  rescrapeProducts: (id: string) => api.post(`/suppliers/${id}/rescrape-products`),
  bulkApplySupplierPrice: (id: string, enable_tracking: boolean) =>
    api.post(`/suppliers/${id}/bulk-apply-supplier-price`, { enable_tracking }),
  scrapeHistory: (id: string) => api.get(`/suppliers/${id}/scrape-history`),
  stats: (id: string) => api.get(`/suppliers/${id}/stats`),
};

// Imports
export const importsApi = {
  uploadCsv: (formData: FormData) =>
    api.post("/imports/csv", formData, { headers: { "Content-Type": "multipart/form-data" } }),
  uploadPdf: (formData: FormData) =>
    api.post("/imports/pdf", formData, { headers: { "Content-Type": "multipart/form-data" } }),
  startScrape: (data: unknown) => api.post("/imports/scrape", data),
  uploadImages: (formData: FormData) =>
    api.post("/imports/images", formData, { headers: { "Content-Type": "multipart/form-data" } }),
  jobs: () => api.get("/imports/jobs"),
  job: (id: string) => api.get(`/imports/jobs/${id}`),
  suggestColumnMap: (data: unknown) => api.post("/imports/csv/column-map", data),
};

// Pricing
export const pricingApi = {
  alerts: (params?: Record<string, unknown>) => api.get("/pricing/alerts", { params }),
  approveAlert: (id: string, notes?: string) =>
    api.post(`/pricing/alerts/${id}/approve`, { notes }),
  rejectAlert: (id: string, notes?: string) =>
    api.post(`/pricing/alerts/${id}/reject`, { notes }),
  bulkApproveAlerts: (ids: string[]) => api.post("/pricing/alerts/bulk-approve", ids),
  rules: (supplierId?: string) =>
    api.get("/pricing/rules", { params: supplierId ? { supplier_id: supplierId } : {} }),
  createRule: (data: unknown) => api.post("/pricing/rules", data),
  updateRule: (id: string, data: unknown) => api.patch(`/pricing/rules/${id}`, data),
  deleteRule: (id: string) => api.delete(`/pricing/rules/${id}`),
  schedules: () => api.get("/pricing/schedules"),
  createSchedule: (data: unknown) => api.post("/pricing/schedules", data),
  updateSchedule: (id: string, data: unknown) => api.patch(`/pricing/schedules/${id}`, data),
  cancelSchedule: (id: string) => api.delete(`/pricing/schedules/${id}`),
  calculatePrice: (data: unknown) => api.post("/pricing/calculate", data),
};

// Description Templates
export const templatesApi = {
  list: () => api.get("/templates/"),
  create: (data: { name: string; sections: { level: string; title: string; hint?: string }[] }) =>
    api.post("/templates", data),
  update: (id: string, data: { name?: string; sections?: { level: string; title: string; hint?: string }[] }) =>
    api.patch(`/templates/${id}`, data),
  delete: (id: string) => api.delete(`/templates/${id}`),
  aiFill: (templateId: string, productId: string) =>
    api.post("/templates/ai-fill", { template_id: templateId, product_id: productId }),
};

// Settings
export const settingsApi = {
  getShopify: () => api.get("/settings/shopify"),
  connectShopify: (store_domain: string) => api.post("/settings/shopify/connect", { store_domain }),
  disconnectShopify: () => api.post("/settings/shopify/disconnect"),
};

// Sync
export const syncApi = {
  status: () => api.get("/sync/status"),
  syncProduct: (id: string) => api.post(`/sync/product/${id}`),
  syncSelected: (ids: string[]) => api.post("/sync/products", { product_ids: ids }),
  syncAll: () => api.post("/sync/all"),
  log: (params?: Record<string, unknown>) => api.get("/sync/log", { params }),
  testConnection: () => api.get("/sync/shopify/connection"),
  pullFromShopify: () => api.post("/sync/shopify/pull"),
};
