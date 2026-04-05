import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
import httpx
from typing import Optional
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

logger = logging.getLogger(__name__)

from app.config import settings

# ---------------------------------------------------------------------------
# GraphQL query / mutation strings
# ---------------------------------------------------------------------------

_PRODUCT_FIELDS = """
    id legacyResourceId title descriptionHtml vendor productType handle tags status
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

_GQL_PRODUCT_OPTIONS_CREATE = """
mutation productOptionsCreate($productId: ID!, $options: [OptionCreateInput!]!, $variantStrategy: ProductOptionCreateVariantStrategy) {
  productOptionsCreate(productId: $productId, options: $options, variantStrategy: $variantStrategy) {
    userErrors { field message code }
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
mutation productVariantsBulkCreate($productId: ID!, $variants: [ProductVariantsBulkInput!]!, $strategy: ProductVariantsBulkCreateStrategy) {
  productVariantsBulkCreate(productId: $productId, variants: $variants, strategy: $strategy) {
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

_GQL_GET_COLLECTIONS = """
query GetCollections($cursor: String) {
  collections(first: 250, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id legacyResourceId title handle sortOrder
        ruleSet {
          appliedDisjunctively
          rules { column relation condition }
        }
      }
    }
  }
}"""

_GQL_FILE_DELETE = """
mutation fileDelete($fileIds: [ID!]!) {
  fileDelete(fileIds: $fileIds) {
    deletedFileIds
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

    # Map Shopify status (ACTIVE/DRAFT/ARCHIVED) to our lowercase values
    shopify_status = (node.get("status") or "DRAFT").upper()
    status = {"ACTIVE": "active", "ARCHIVED": "archived"}.get(shopify_status, "draft")

    return {
        "id": int(node["legacyResourceId"]),
        "title": node.get("title") or "",
        "body_html": node.get("descriptionHtml") or "",
        "vendor": node.get("vendor") or "",
        "product_type": node.get("productType") or "",
        "handle": node.get("handle") or "",
        "tags": tags,
        "options": options,
        "variants": variants,
        "images": images,
        "status": status,
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
        # Throttle on cost extension — use `or {}` guards since Shopify may return null
        ext = (data.get("extensions") or {}).get("cost") or {}
        if (ext.get("throttleStatus") or {}).get("currentlyAvailable", 1000) < 100:
            time.sleep(0.5)
        errors = data.get("errors")
        if errors:
            raise RuntimeError(f"GraphQL errors: {errors}")
        return data.get("data") or {}

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

    def get_all_collections(self) -> list[dict]:
        """Fetch all collections with their automation rules (paginated)."""
        collections = []
        cursor = None
        while True:
            data = self._graphql(_GQL_GET_COLLECTIONS, {"cursor": cursor})
            connection = data.get("collections", {})
            for edge in connection.get("edges", []):
                node = edge["node"]
                rule_set = node.get("ruleSet")
                collections.append({
                    "id": int(node["legacyResourceId"]),
                    "title": node.get("title") or "",
                    "handle": node.get("handle") or "",
                    "sort_order": node.get("sortOrder"),
                    "automated": rule_set is not None,
                    "disjunctive": rule_set.get("appliedDisjunctively", False) if rule_set else False,
                    "rules": rule_set.get("rules", []) if rule_set else [],
                })
            page_info = connection.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")
        return collections

    # ── Product writes ───────────────────────────────────────────────────────

    def _build_gql_variant_inputs(
        self,
        variants,
        option_names: list[str],
        *,
        for_create: bool = False,
        shopify_variants: Optional[dict] = None,
    ) -> list[dict]:
        """Build GraphQL variant inputs compatible with Shopify API 2025-01+.

        In 2025-01 ProductVariantsBulkInput:
        - sku / requiresShipping are nested under inventoryItem
        - selectedOptions is replaced by optionValues (create only; options are immutable on updates)

        shopify_variants: dict keyed by shopify_variant_id (int) with current Shopify values,
        used as fallbacks for any empty/zero local fields.
        """
        sv_by_id = shopify_variants or {}
        result = []
        for v in variants:
            sv = sv_by_id.get(v.shopify_variant_id) or {}

            # Price fallback: use Shopify's price if local is 0 / unset
            local_price = float(str(v.price)) if v.price else 0.0
            effective_price = str(v.price) if local_price != 0.0 else (sv.get("price") or str(v.price))

            # compare_at_price fallback
            effective_cap = (
                str(v.compare_at_price) if v.compare_at_price
                else sv.get("compare_at_price")  # None is fine — clears it in Shopify
            )

            # barcode fallback
            effective_barcode = v.barcode or sv.get("barcode")

            # weight fallback (both stored in kg)
            effective_weight = v.weight or sv.get("weight")

            # sku fallback
            effective_sku = v.sku or sv.get("sku") or ""

            vi: dict = {
                "price": effective_price,
                "compareAtPrice": effective_cap,
                "inventoryPolicy": (v.inventory_policy or "deny").upper(),
                "taxable": v.taxable,
                "inventoryItem": {
                    "sku": effective_sku,
                    "requiresShipping": bool(v.requires_shipping),
                },
            }
            if v.shopify_variant_id:
                vi["id"] = self._gid("ProductVariant", v.shopify_variant_id)
            if effective_barcode:
                vi["barcode"] = effective_barcode
            if effective_weight:
                vi["weight"] = float(effective_weight)
                vi["weightUnit"] = _WEIGHT_UNIT_TO_GQL.get(v.weight_unit or "kg", "KILOGRAMS")
            # optionValues only for creates — existing variant options are immutable
            if for_create:
                option_vals = [v.option1, v.option2, v.option3]
                option_values = [
                    {"optionName": name, "name": val}
                    for name, val in zip(option_names, option_vals)
                    if val
                ]
                if not option_values:
                    option_values = [{"optionName": "Title", "name": "Default Title"}]
                vi["optionValues"] = option_values
            result.append(vi)
        return result

    def create_product(self, product, variants, images) -> dict:
        """
        Create a product on Shopify via GraphQL (API 2025-01+).
        Accepts SQLAlchemy model objects directly.
        Returns normalized internal dict with id + variants[].id for DB storage.

        Two-step process required in 2025-01 (variants removed from ProductInput):
        1. productCreate — creates product shell; Shopify auto-creates one "Default Title" variant
        2a. For single "Default Title" variant: productVariantsBulkUpdate the auto-created variant
        2b. For multi-variant / custom options: productVariantsBulkCreate with REMOVE_STANDALONE_VARIANT
        """
        option_names = [o["name"] for o in sorted(product.options or [], key=lambda x: x.get("position", 0))]
        # Deduplicate option names (keep order)
        seen = set()
        unique_opt_names = [n for n in option_names if not (n in seen or seen.add(n))]

        # Determine if this is a simple single "Default Title" variant product
        is_default_title = (
            len(variants) <= 1
            and not unique_opt_names
            and (not variants or not variants[0].option1 or variants[0].option1 == "Default Title")
        )

        gql_input: dict = {
            "title": product.title,
            "descriptionHtml": product.body_html or product.ai_description or "",
            "vendor": product.vendor or "",
            "productType": product.product_type or "",
            "tags": product.tags or product.ai_tags or [],
            "status": "ARCHIVED" if product.status == "archived" else ("DRAFT" if product.status == "draft" else "ACTIVE"),
        }
        # For multi-option products: include productOptions so Shopify pre-creates the
        # right variant structure. In 2025-01, ProductInput uses productOptions (not options).
        if unique_opt_names and not is_default_title:
            opt_values: dict[str, list] = {n: [] for n in unique_opt_names}
            for v in variants:
                for n, val in zip(unique_opt_names, [v.option1, v.option2, v.option3]):
                    if val and val not in opt_values[n]:
                        opt_values[n].append(val)
            gql_input["productOptions"] = [
                {"name": n, "values": [{"name": val} for val in vals]}
                for n, vals in opt_values.items() if vals
            ]

        # Step 1: Create product shell.
        # - No options: Shopify auto-creates one "Default Title" variant.
        # - With productOptions: Shopify auto-creates one variant per option value combination.
        data = self._graphql(_GQL_PRODUCT_CREATE, {"input": gql_input})
        result = data.get("productCreate") or {}
        self._raise_user_errors(result.get("userErrors") or [])
        gql_product = result.get("product") or {}
        product_gid = gql_product.get("id")

        # Step 2: Update auto-created variants with our price/SKU/inventory data.
        returned_variants = []
        auto_variants = [
            edge["node"]
            for edge in (gql_product.get("variants") or {}).get("edges", [])
        ]

        if variants and product_gid:
            if is_default_title and auto_variants:
                # Single "Default Title" variant — update the one Shopify auto-created.
                vi = self._build_gql_variant_inputs(variants, ["Title"], for_create=False)[0]
                vi["id"] = auto_variants[0]["id"]
                vdata = self._graphql(_GQL_VARIANTS_BULK_UPDATE, {
                    "productId": product_gid,
                    "variants": [vi],
                })
                vresult = vdata.get("productVariantsBulkUpdate") or {}
                self._raise_user_errors(vresult.get("userErrors") or [])
                returned_variants.extend(vresult.get("productVariants") or [])
            else:
                # Multi-option: productCreate auto-created one variant per option value.
                # Match local variants to auto-created by selectedOptions, then bulk-update.
                auto_by_opts: dict[tuple, dict] = {}
                for av in auto_variants:
                    sel = {o["name"]: o["value"] for o in (av.get("selectedOptions") or [])}
                    key = tuple(sel.get(n, "") for n in unique_opt_names)
                    auto_by_opts[key] = av

                update_inputs = []
                unmatched_locals = []
                for lv in variants:
                    key = tuple([lv.option1 or "", lv.option2 or "", lv.option3 or ""][:len(unique_opt_names)])
                    av = auto_by_opts.get(key)
                    if av:
                        vi = self._build_gql_variant_inputs([lv], unique_opt_names, for_create=False)[0]
                        vi["id"] = av["id"]
                        update_inputs.append(vi)
                    else:
                        unmatched_locals.append(lv)

                if update_inputs:
                    vdata = self._graphql(_GQL_VARIANTS_BULK_UPDATE, {
                        "productId": product_gid,
                        "variants": update_inputs,
                    })
                    vresult = vdata.get("productVariantsBulkUpdate") or {}
                    self._raise_user_errors(vresult.get("userErrors") or [])
                    returned_variants.extend(vresult.get("productVariants") or [])

                # Fallback: local variants whose option values weren't in productOptions
                if unmatched_locals:
                    variant_inputs = self._build_gql_variant_inputs(
                        unmatched_locals, unique_opt_names, for_create=True
                    )
                    vcdata = self._graphql(_GQL_VARIANTS_BULK_CREATE, {
                        "productId": product_gid,
                        "variants": variant_inputs,
                    })
                    vcresult = vcdata.get("productVariantsBulkCreate") or {}
                    self._raise_user_errors(vcresult.get("userErrors") or [])
                    returned_variants.extend(vcresult.get("productVariants") or [])

        # Step 3: Add images via productCreateMedia
        if product_gid and images:
            media_input = [
                {"mediaContentType": "IMAGE", "originalSource": img.src, "alt": img.alt or ""}
                for img in images if img.src
            ]
            if media_input:
                self._graphql(_GQL_CREATE_MEDIA, {"productId": product_gid, "media": media_input})

        return self._normalize_create_response(gql_product, returned_variants)

    def update_product(self, shopify_id: int, product, variants, images, shopify_current: Optional[dict] = None) -> dict:
        """
        Update an existing Shopify product via GraphQL.
        Accepts SQLAlchemy model objects. Returns normalized dict.

        shopify_current: normalized dict from get_product(), used as fallbacks for empty local fields.
        """
        sc = shopify_current or {}
        sc_variants = sc.get("variants", [])
        sv_by_id = {sv["id"]: sv for sv in sc_variants}

        product_gid = self._gid("Product", shopify_id)
        option_names = [o["name"] for o in sorted(product.options or [], key=lambda x: x.get("position", 0))]
        seen = set()
        unique_opt_names = [n for n in option_names if not (n in seen or seen.add(n))]

        # 1. Update product metadata — fall back to current Shopify values for empty local fields
        gql_input: dict = {
            "id": product_gid,
            "title": product.title or sc.get("title") or "",
            "descriptionHtml": product.body_html or product.ai_description or sc.get("body_html") or "",
            "vendor": product.vendor or sc.get("vendor") or "",
            "productType": product.product_type or sc.get("product_type") or "",
            "tags": product.tags or product.ai_tags or sc.get("tags") or [],
            "status": "ARCHIVED" if product.status == "archived" else ("DRAFT" if product.status == "draft" else "ACTIVE"),
        }
        data = self._graphql(_GQL_PRODUCT_UPDATE, {"input": gql_input})
        result = data.get("productUpdate") or {}
        self._raise_user_errors(result.get("userErrors") or [])
        gql_product = result.get("product") or {}

        # 2. Update / create variants
        existing_variants = [v for v in variants if v.shopify_variant_id]
        new_variants = [v for v in variants if not v.shopify_variant_id]

        returned_variants = []

        # Broken product state: 0 variants / 0 options on Shopify (caused by a previous
        # failed REMOVE_STANDALONE_VARIANT call that removed the auto-variant but didn't
        # create replacements). productUpdate ignores the `options` field for existing
        # products, so we must use productOptionsCreate to restore the option before
        # productVariantsBulkCreate can reference it via optionValues.
        if not sc_variants and new_variants:
            opt_names_to_restore = unique_opt_names or ["Title"]
            options_input = [
                {"name": n, "values": [{"name": "Default Title" if n == "Title" else n}]}
                for n in opt_names_to_restore
            ]
            try:
                self._graphql(_GQL_PRODUCT_OPTIONS_CREATE, {
                    "productId": product_gid,
                    "options": options_input,
                    "variantStrategy": "LEAVE_AS_IS",
                })
            except Exception as opt_err:
                logger.warning(f"productOptionsCreate failed (non-fatal): {opt_err}")

        if existing_variants:
            variant_inputs = self._build_gql_variant_inputs(
                existing_variants, unique_opt_names or ["Title"], for_create=False, shopify_variants=sv_by_id,
            )
            vdata = self._graphql(_GQL_VARIANTS_BULK_UPDATE, {
                "productId": product_gid,
                "variants": variant_inputs,
            })
            vresult = vdata.get("productVariantsBulkUpdate") or {}
            self._raise_user_errors(vresult.get("userErrors") or [])
            returned_variants.extend(vresult.get("productVariants") or [])

        if new_variants:
            variant_inputs = self._build_gql_variant_inputs(
                new_variants, unique_opt_names or ["Title"], for_create=True, shopify_variants=sv_by_id,
            )
            vcdata = self._graphql(_GQL_VARIANTS_BULK_CREATE, {
                "productId": product_gid,
                "variants": variant_inputs,
            })
            vcresult = vcdata.get("productVariantsBulkCreate") or {}
            self._raise_user_errors(vcresult.get("userErrors") or [])
            returned_variants.extend(vcresult.get("productVariants") or [])

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
        """Build a response dict compatible with what sync_tasks expects.

        Prefers extra_variants (from separate variant mutations) over gql_product.variants,
        since gql_product.variants reflects the auto-created Shopify variant which may have
        been updated or replaced by the time this is called.
        """
        numeric_id = int(gql_product.get("legacyResourceId", 0)) if gql_product.get("legacyResourceId") else None

        if extra_variants:
            # Use the variants returned by the explicit variant mutation (updated/created)
            variants_out = [
                {"id": int(v["legacyResourceId"])}
                for v in extra_variants
                if v.get("legacyResourceId")
            ]
        else:
            # Fall back to the auto-created variants from the product create response
            variants_out = [
                {"id": int(edge["node"]["legacyResourceId"])}
                for edge in (gql_product.get("variants") or {}).get("edges", [])
                if edge["node"].get("legacyResourceId")
            ]

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

    def delete_product(self, shopify_product_id: int) -> None:
        """Delete a product from Shopify (REST). Used after local merge to remove orphaned Shopify products."""
        url = f"{self.base_url}/products/{shopify_product_id}.json"
        resp = httpx.delete(url, headers=self.headers, timeout=15)
        if resp.status_code == 404:
            return  # already gone — treat as success
        if not resp.is_success:
            raise RuntimeError(f"Failed to delete Shopify product {shopify_product_id}: HTTP {resp.status_code}")

    def delete_product_image(self, shopify_image_id: int) -> None:
        """Delete a single product image from Shopify via the file delete mutation."""
        gid = self._gid("MediaImage", shopify_image_id)
        data = self._graphql(_GQL_FILE_DELETE, {"fileIds": [gid]})
        self._raise_user_errors(data.get("fileDelete", {}).get("userErrors", []))

    # ── Payload builder (for hash comparison / backward compat) ─────────────

    @staticmethod
    def build_payload(product, variants, images, shopify_current: Optional[dict] = None) -> dict:
        """
        Build a normalized dict for payload hashing and comparison.
        This is NOT sent directly to Shopify — it's used for change detection.

        shopify_current: normalized dict from get_product(), used as fallbacks so the hash
        reflects the effective values that will actually be sent (same logic as update_product).
        """
        sc = shopify_current or {}
        sv_by_id = {sv["id"]: sv for sv in sc.get("variants", [])}
        option_names = [o["name"] for o in sorted(product.options or [], key=lambda x: x.get("position", 0))]

        def selected_options(v):
            pairs = [(name, val) for name, val in zip(option_names, [v.option1, v.option2, v.option3]) if val]
            return pairs or [("Title", "Default Title")]

        def eff_price(v):
            sv = sv_by_id.get(v.shopify_variant_id) or {}
            local = float(str(v.price)) if v.price else 0.0
            return str(v.price) if local != 0.0 else (sv.get("price") or str(v.price))

        def eff_cap(v):
            sv = sv_by_id.get(v.shopify_variant_id) or {}
            return str(v.compare_at_price) if v.compare_at_price else sv.get("compare_at_price")

        def eff_barcode(v):
            sv = sv_by_id.get(v.shopify_variant_id) or {}
            return v.barcode or sv.get("barcode") or ""

        def eff_sku(v):
            sv = sv_by_id.get(v.shopify_variant_id) or {}
            return v.sku or sv.get("sku") or ""

        return {
            "title": product.title or sc.get("title") or "",
            "body_html": product.body_html or product.ai_description or sc.get("body_html") or "",
            "vendor": product.vendor or sc.get("vendor") or "",
            "product_type": product.product_type or sc.get("product_type") or "",
            "tags": sorted(product.tags or product.ai_tags or sc.get("tags") or []),
            "status": product.status or "draft",
            "options": option_names,
            "variants": [
                {
                    "id": v.shopify_variant_id,
                    "sku": eff_sku(v),
                    "price": eff_price(v),
                    "compare_at_price": eff_cap(v),
                    "selected_options": selected_options(v),
                    "barcode": eff_barcode(v),
                }
                for v in variants
            ],
            "image_srcs": [img.src for img in images],
        }

    @staticmethod
    def payload_hash(payload: dict) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
