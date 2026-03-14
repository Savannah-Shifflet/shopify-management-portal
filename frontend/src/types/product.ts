export interface ProductVariant {
  id: string;
  product_id: string;
  shopify_variant_id?: number;
  title?: string;
  sku?: string;
  barcode?: string;
  option1?: string;
  option2?: string;
  option3?: string;
  price: string;
  compare_at_price?: string;
  cost?: string;
  inventory_quantity: number;
  inventory_policy: string;
  weight?: string;
  weight_unit: string;
  requires_shipping: boolean;
  taxable: boolean;
  position: number;
  created_at: string;
  updated_at?: string;
}

export interface ProductImage {
  id: string;
  product_id: string;
  shopify_image_id?: number;
  src: string;
  alt?: string;
  position: number;
  width?: number;
  height?: number;
  created_at: string;
}

export interface Product {
  id: string;
  user_id: string;
  supplier_id?: string;
  shopify_product_id?: number;
  status: "draft" | "enriched" | "approved" | "synced" | "archived";
  title: string;
  body_html?: string;
  vendor?: string;
  product_type?: string;
  handle?: string;
  tags?: string[];
  options?: ProductOption[];
  source_type?: string;
  source_url?: string;
  raw_title?: string;
  raw_description?: string;
  ai_description?: string;
  ai_tags?: string[];
  ai_attributes?: Record<string, string>;
  seo_title?: string;
  seo_description?: string;
  enrichment_status: "pending" | "running" | "done" | "failed";
  enrichment_at?: string;
  cost_price?: string;
  base_price?: string;
  compare_at_price?: string;
  supplier_price?: string;
  supplier_price_at?: string;
  sync_status: "never_synced" | "pending" | "synced" | "out_of_sync" | "failed";
  synced_at?: string;
  metafields?: Record<string, unknown>;
  created_at: string;
  updated_at?: string;
  variants: ProductVariant[];
  images: ProductImage[];
}

export interface ProductListItem {
  id: string;
  title: string;
  status: string;
  sync_status: string;
  enrichment_status: string;
  product_type?: string;
  vendor?: string;
  base_price?: string;
  supplier_id?: string;
  shopify_product_id?: number;
  created_at: string;
  updated_at?: string;
  thumbnail?: string;
  body_html?: string | null;
  ai_description?: string | null;
}

export interface ProductListResponse {
  items: ProductListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ProductOption {
  name: string;
  position: number;
}

export interface MergeOverrides {
  title?: string;
  body_html?: string;
  vendor?: string;
  product_type?: string;
  seo_title?: string;
  seo_description?: string;
  cost_price?: string;
  base_price?: string;
  compare_at_price?: string;
  tags_strategy?: string;    // "union" | "product:<uuid>"
  images_strategy?: string;  // "union" | "product:<uuid>"
  image_srcs?: string[];     // if set, overrides images_strategy with this exact ordered list
}
