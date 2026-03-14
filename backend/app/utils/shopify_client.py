import hashlib
import json
import time
from datetime import datetime, timedelta
import httpx
from typing import Optional
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from app.config import settings

# ---------------------------------------------------------------------------
# GraphQL query / mutation strings
# ---------------------------------------------------------------------------

_PRODUCT_FIELDS = """
    id legacyResourceId title bodyHtml vendor productType handle tags status
    options { name position values }
    variants(first: 100) {
      edges {
        node {
          id legacyResourceId sku barcode price compareAtPrice
          inventoryQuantity inventoryPolicy taxable
          inventoryItem {
            requiresShipping
            measurement { weight { value unit } }
          }
          selectedOptions { name value }
        }
      }
    }
    images(first: 50) {
      edges { node { id url altText } }
    }
"""

_GQL_GET_PRODUCTS = f"""
query GetProducts($cursor: String) {{
  products(first: 250, after: $cursor) {{
    pageInfo {{ hasNextPage endCursor }}
    edges {{ node {{ {_PRODUCT_FIELDS} }} }}
  }}
}}"""

_GQL_GET_PRODUCT = f"""
query GetProduct($id: ID!) {{
  product(id: $id) {{ {_PRODUCT_FIELDS} }}
}}"""

_GQL_PRODUCT_CREATE = """
mutation productCreate($input: ProductInput!) {
  productCreate(input: $input) {
    product {
      id legacyResourceId
      variants(first: 100) {
        edges { node { id legacyResourceId selectedOptions { name value } } }
      }
    }
    userErrors { field message }
  }
}"""

_GQL_PRODUCT_UPDATE = """
mutation productUpdate($input: ProductInput!) {
  productUpdate(input: $input) {
    product { id legacyResourceId }
    userErrors { field message }
  }
}"""

_GQL_VARIANTS_BULK_UPDATE = """
mutation productVariantsBulkUpdate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    productVariants { id legacyResourceId }
    userErrors { field message }
  }
}"""

_GQL_VARIANTS_BULK_CREATE = """
mutation productVariantsBulkCreate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkCreate(productId: $productId, variants: $variants) {
    productVariants { id legacyResourceId selectedOptions { name value } }
    userErrors { field message }
  }
}"""

_GQL_CREATE_MEDIA = """
mutation productCreateMedia($productId: ID!, $media: [CreateMediaInput!]!) {
  productCreateMedia(productId: $productId, media: $media) {
    media { ... on MediaImage { image { url } } }
    userErrors { field message }
  }
}"""

# ---------------------------------------------------------------------------
# Weight unit helpers
# ---------------------------------------------------------------------------

_WEIGHT_GQL_TO_KG = {
    "KILOGRAMS": 1.0, "GRAMS": 0.001, "POUNDS": 0.453592, "OUNCES": 0.0283495,
}
_WEIGHT_UNIT_TO_GQL = {
    "kg": "KILOGRAMS", "g": "GRAMS", "lb": "POUNDS", "oz": "OUNCES",
}


def _gql_weight_to_kg(weight, unit: str) -> Optional[float]:
    if weight is None:
        return None
    factor = _WEIGHT_GQL_TO_KG.get((unit or "KILOGRAMS").upper(), 1.0)
    return round(float(weight) * factor, 3)


# ---------------------------------------------------------------------------
# Response normalizer — GraphQL → internal dict format
# ---------------------------------------------------------------------------

def _parse_gql_product(node: dict) -> dict:
    """Normalize a GraphQL product node to our internal snake_case dict."""
    # Options — filter out Shopify's synthetic "Title" option
    raw_opts = node.get("options") or []
    options = [
        {"name": o["name"], "position": o.get("position", i + 1)}
        for i, o in enumerate(raw_opts)
        if o.get("name") and o.get("name") != "Title"
    ]
    opt_names = [o["name"] for o in sorted(options, key=lambda x: x["position"])]

    # Variants
    variants = []
    for edge in (node.get("variants") or {}).get("edges", []):
        v = edge["node"]
        sel = {o["name"]: o["value"] for o in (v.get("selectedOptions") or [])}
        inv_item = v.get("inventoryItem") or {}
        measurement = (inv_item.get("measurement") or {}).get("weight") or {}
        variant = {
            "id": int(v["legacyResourceId"]),
            "sku": v.get("sku") or "",
            "barcode": v.get("barcode"),
            "price": v.get("price") or "0",
            "compare_at_price": v.get("compareAtPrice"),
            "inventory_quantity": v.get("inventoryQuantity") or 0,
            "inventory_policy": (v.get("inventoryPolicy") or "DENY").lower(),
            "requires_shipping": inv_item.get("requiresShipping", True),
            "taxable": v.get("taxable", True),
            "weight": _gql_weight_to_kg(measurement.get("value"), measurement.get("unit")),
            "weight_unit": "kg",
            "option1": sel.get(opt_names[0]) if len(opt_names) > 0 else (v.get("selectedOptions") or [{}])[0].get("value"),
            "option2": sel.get(opt_names[1]) if len(opt_names) > 1 else None,
            "option3": sel.get(opt_names[2]) if len(opt_names) > 2 else None,
            "title": " / ".join(o["value"] for o in (v.get("selectedOptions") or [])) or "Default Title",
        }
        variants.append(variant)

    # Images
    images = []
    for edge in (node.get("images") or {}).get("edges", []):
        img = edge["node"]
        gid = img.get("id", "")
        img_id = int(gid.split("/")[-1]) if gid else None
        images.append({
            "id": img_id,
            "src": img.get("url") or "",
            "alt": img.get("altText") or "",
        })

    # Tags — GQL returns array; REST returns comma string
    tags = node.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    return {
        "id": int(node["legacyResourceId"]),
        "title": node.get("title") or "",
        "body_html": node.get("bodyHtml") or "",
        "vendor": node.get("vendor") or "",
        "product_type": node.get("productType") or "",
        "handle": node.get("handle") or "",
        "tags": tags,
        "options": options,
        "variants": variants,
        "images": images,
    }


# ---------------------------------------------------------------------------
# ShopifyClient
# ---------------------------------------------------------------------------

class ShopifyRateLimitError(Exception):
    pass


class ShopifyClient:
    API_VERSION = "2025-01"

    def __init__(self, store: str, token: str):
        store = store.removeprefix("https://").removeprefix("http://").rstrip("/")
        self.store = store
        self.token = token
        self.base_url = f"https://{self.store}/admin/api/{self.API_VERSION}"
        self.gql_url = f"{self.base_url}/graphql.json"
        self._call_limit = 0.0
        self._call_limit_max = 40.0

    @classmethod
    def fetch_token(cls, store: str) -> tuple[str, datetime]:
        """Obtain an access token via client credentials grant."""
        store = store.removeprefix("https://").removeprefix("http://").rstrip("/")
        client_id = settings.shopify_client_id
        client_secret = settings.shopify_client_secret
        if not client_id or not client_secret:
            raise RuntimeError(
                "Shopify app credentials not configured. Set SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET in .env"
            )
        url = f"https://{store}/admin/oauth/access_token"
        resp = httpx.post(
            url,
            data={"client_id": client_id, "client_secret": client_secret, "grant_type": "client_credentials"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        if not resp.is_success:
            raise RuntimeError(f"Shopify returned HTTP {resp.status_code}: {resp.text}")
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise RuntimeError(f"No access_token in Shopify response: {resp.text}")
        expires_in = data.get("expires_in", 86400)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 300)
        return token, expires_at

    @classmethod
    def from_user(cls, user, db=None) -> "ShopifyClient":
        """Build a client from a user record, auto-refreshing the token if expired."""
        if not user.shopify_store or not user.shopify_token:
            raise RuntimeError("Shopify not connected. Go to Settings to connect your store.")
        if db and (
            not user.shopify_token_expires_at
            or datetime.utcnow() >= user.shopify_token_expires_at
        ):
            token, expires_at = cls.fetch_token(user.shopify_store)
            user.shopify_token = token
            user.shopify_token_expires_at = expires_at
            db.commit()
        return cls(store=user.shopify_store, token=user.shopify_token)

    @property
    def headers(self) -> dict:
        return {
            "X-Shopify-Access-Token": self.token,
            "Content-Type": "application/json",
        }

    def test_connection(self) -> dict:
        try:
            resp = httpx.get(f"{self.base_url}/shop.json", headers=self.headers, timeout=10)
            if resp.status_code == 200:
                shop = resp.json().get("shop", {})
                return {"connected": True, "shop_name": shop.get("name"), "domain": shop.get("domain")}
            return {"connected": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"connected": False, "error": str(e)}

    @retry(
        wait=wait_exponential(min=1, max=10),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(ShopifyRateLimitError),
    )
    def _graphql(self, query: str, variables: Optional[dict] = None) -> dict:
        """Execute a GraphQL query or mutation, handling rate limits."""
        resp = httpx.post(
            self.gql_url,
            headers=self.headers,
            json={"query": query, "variables": variables or {}},
            timeout=30,
        )
        if resp.status_code == 429:
            raise ShopifyRateLimitError("Rate limited by Shopify")
        resp.raise_for_status()
        data = resp.json()
        # Throttle on cost extension
        ext = data.get("extensions", {}).get("cost", {})
        if ext.get("throttleStatus", {}).get("currentlyAvailable", 1000) < 100:
            time.sleep(0.5)
        errors = data.get("errors")
        if errors:
            raise RuntimeError(f"GraphQL errors: {errors}")
        return data.get("data", {})

    @staticmethod
    def _gid(resource_type: str, numeric_id: int) -> str:
        return f"gid://shopify/{resource_type}/{numeric_id}"

    def _raise_user_errors(self, user_errors: list) -> None:
        if user_errors:
            msgs = "; ".join(f"{e.get('field')}: {e.get('message')}" for e in user_errors)
            raise RuntimeError(f"Shopify userErrors: {msgs}")

    # ── Product reads ────────────────────────────────────────────────────────

    def get_all_products(self) -> list[dict]:
        """Fetch all products via GraphQL (paginated), normalized to internal format."""
        products = []
        cursor = None
        while True:
            data = self._graphql(_GQL_GET_PRODUCTS, {"cursor": cursor})
            connection = data.get("products", {})
            for edge in connection.get("edges", []):
                products.append(_parse_gql_product(edge["node"]))
            page_info = connection.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")
        return products

    def get_product(self, shopify_id: int) -> dict:
        """Fetch a single product by numeric ID, normalized to internal format."""
        data = self._graphql(_GQL_GET_PRODUCT, {"id": self._gid("Product", shopify_id)})
        node = data.get("product")
        if not node:
            raise RuntimeError(f"Product {shopify_id} not found in Shopify")
        return _parse_gql_product(node)

    # ── Product writes ───────────────────────────────────────────────────────

    def _build_gql_variant_inputs(self, variants, option_names: list[str]) -> list[dict]:
        """Build GraphQL variant inputs with selectedOptions from local variant records."""
        result = []
        for v in variants:
            option_vals = [v.option1, v.option2, v.option3]
            selected_options = [
                {"name": name, "value": val}
                for name, val in zip(option_names, option_vals)
                if val
            ]
            if not selected_options:
                selected_options = [{"name": "Title", "value": "Default Title"}]

            vi: dict = {
                "price": str(v.price),
                "compareAtPrice": str(v.compare_at_price) if v.compare_at_price else None,
                "sku": v.sku or "",
                "inventoryPolicy": (v.inventory_policy or "deny").upper(),
                "requiresShipping": v.requires_shipping,
                "taxable": v.taxable,
                "selectedOptions": selected_options,
            }
            if v.shopify_variant_id:
                vi["id"] = self._gid("ProductVariant", v.shopify_variant_id)
            if v.barcode:
                vi["barcode"] = v.barcode
            if v.weight:
                vi["weight"] = float(v.weight)
                vi["weightUnit"] = _WEIGHT_UNIT_TO_GQL.get(v.weight_unit or "kg", "KILOGRAMS")
            result.append(vi)
        return result

    def create_product(self, product, variants, images) -> dict:
        """
        Create a product on Shopify via GraphQL.
        Accepts SQLAlchemy model objects directly.
        Returns normalized internal dict with id + variants[].id for DB storage.
        """
        option_names = [o["name"] for o in sorted(product.options or [], key=lambda x: x.get("position", 0))]
        # Deduplicate option names (keep order)
        seen = set()
        unique_opt_names = [n for n in option_names if not (n in seen or seen.add(n))]

        gql_input: dict = {
            "title": product.title,
            "bodyHtml": product.body_html or product.ai_description or "",
            "vendor": product.vendor or "",
            "productType": product.product_type or "",
            "tags": product.tags or product.ai_tags or [],
            "status": "ACTIVE",
        }
        if unique_opt_names:
            gql_input["options"] = unique_opt_names

        variant_inputs = self._build_gql_variant_inputs(variants, unique_opt_names or ["Title"])
        gql_input["variants"] = variant_inputs

        data = self._graphql(_GQL_PRODUCT_CREATE, {"input": gql_input})
        result = data.get("productCreate", {})
        self._raise_user_errors(result.get("userErrors", []))
        gql_product = result.get("product", {})

        # Add images via productCreateMedia
        product_gid = gql_product.get("id")
        if product_gid and images:
            media_input = [
                {"mediaContentType": "IMAGE", "originalSource": img.src, "alt": img.alt or ""}
                for img in images if img.src
            ]
            if media_input:
                self._graphql(_GQL_CREATE_MEDIA, {"productId": product_gid, "media": media_input})

        return self._normalize_create_response(gql_product)

    def update_product(self, shopify_id: int, product, variants, images) -> dict:
        """
        Update an existing Shopify product via GraphQL.
        Accepts SQLAlchemy model objects. Returns normalized dict.
        """
        product_gid = self._gid("Product", shopify_id)
        option_names = [o["name"] for o in sorted(product.options or [], key=lambda x: x.get("position", 0))]
        seen = set()
        unique_opt_names = [n for n in option_names if not (n in seen or seen.add(n))]

        # 1. Update product metadata
        gql_input: dict = {
            "id": product_gid,
            "title": product.title,
            "bodyHtml": product.body_html or product.ai_description or "",
            "vendor": product.vendor or "",
            "productType": product.product_type or "",
            "tags": product.tags or product.ai_tags or [],
            "status": "ACTIVE",
        }
        data = self._graphql(_GQL_PRODUCT_UPDATE, {"input": gql_input})
        result = data.get("productUpdate", {})
        self._raise_user_errors(result.get("userErrors", []))
        gql_product = result.get("product", {})

        # 2. Update / create variants
        existing_variants = [v for v in variants if v.shopify_variant_id]
        new_variants = [v for v in variants if not v.shopify_variant_id]

        returned_variants = []

        if existing_variants:
            variant_inputs = self._build_gql_variant_inputs(existing_variants, unique_opt_names or ["Title"])
            vdata = self._graphql(_GQL_VARIANTS_BULK_UPDATE, {
                "productId": product_gid,
                "variants": variant_inputs,
            })
            vresult = vdata.get("productVariantsBulkUpdate", {})
            self._raise_user_errors(vresult.get("userErrors", []))
            returned_variants.extend(vresult.get("productVariants", []))

        if new_variants:
            variant_inputs = self._build_gql_variant_inputs(new_variants, unique_opt_names or ["Title"])
            vcdata = self._graphql(_GQL_VARIANTS_BULK_CREATE, {
                "productId": product_gid,
                "variants": variant_inputs,
            })
            vcresult = vcdata.get("productVariantsBulkCreate", {})
            self._raise_user_errors(vcresult.get("userErrors", []))
            returned_variants.extend(vcresult.get("productVariants", []))

        # 3. Add any new images (those without shopify_image_id are locally added)
        new_images = [img for img in images if not img.shopify_image_id]
        if new_images:
            media_input = [
                {"mediaContentType": "IMAGE", "originalSource": img.src, "alt": img.alt or ""}
                for img in new_images if img.src
            ]
            if media_input:
                self._graphql(_GQL_CREATE_MEDIA, {"productId": product_gid, "media": media_input})

        return self._normalize_create_response(gql_product, returned_variants)

    def _normalize_create_response(self, gql_product: dict, extra_variants: list = None) -> dict:
        """Build a response dict compatible with what sync_tasks expects."""
        numeric_id = int(gql_product.get("legacyResourceId", 0)) if gql_product.get("legacyResourceId") else None

        # Collect all variant data
        all_variants = list(extra_variants or [])
        for edge in (gql_product.get("variants") or {}).get("edges", []):
            all_variants.append(edge["node"])

        variants_out = []
        for v in all_variants:
            vid = v.get("legacyResourceId")
            if vid:
                variants_out.append({"id": int(vid)})

        return {
            "product": {
                "id": numeric_id,
                "variants": variants_out,
            }
        }

    # ── Variant prices (GraphQL, already existed) ────────────────────────────

    def update_variant_prices(self, product_id: int, variants: list[dict]) -> dict:
        """GraphQL bulk price update."""
        query = """
        mutation productVariantsBulkUpdate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
            productVariantsBulkUpdate(productId: $productId, variants: $variants) {
                productVariants { id price compareAtPrice }
                userErrors { field message }
            }
        }
        """
        variables = {
            "productId": self._gid("Product", product_id),
            "variants": [
                {
                    "id": self._gid("ProductVariant", v["shopify_variant_id"]),
                    "price": str(v["price"]),
                    "compareAtPrice": str(v["compare_at_price"]) if v.get("compare_at_price") else None,
                }
                for v in variants
                if v.get("shopify_variant_id")
            ],
        }
        return self._graphql(query, variables)

    # ── Payload builder (for hash comparison / backward compat) ─────────────

    @staticmethod
    def build_payload(product, variants, images) -> dict:
        """
        Build a normalized dict for payload hashing and comparison.
        This is NOT sent directly to Shopify — it's used for change detection.
        """
        option_names = [o["name"] for o in sorted(product.options or [], key=lambda x: x.get("position", 0))]

        def selected_options(v):
            pairs = [(name, val) for name, val in zip(option_names, [v.option1, v.option2, v.option3]) if val]
            return pairs or [("Title", "Default Title")]

        return {
            "title": product.title,
            "body_html": product.body_html or product.ai_description or "",
            "vendor": product.vendor or "",
            "product_type": product.product_type or "",
            "tags": sorted(product.tags or product.ai_tags or []),
            "options": option_names,
            "variants": [
                {
                    "id": v.shopify_variant_id,
                    "sku": v.sku or "",
                    "price": str(v.price),
                    "compare_at_price": str(v.compare_at_price) if v.compare_at_price else None,
                    "selected_options": selected_options(v),
                    "barcode": v.barcode or "",
                }
                for v in variants
            ],
            "image_srcs": [img.src for img in images],
        }

    @staticmethod
    def payload_hash(payload: dict) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
