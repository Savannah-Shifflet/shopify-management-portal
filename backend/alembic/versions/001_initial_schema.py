"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-02

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("name", sa.String(255)),
        sa.Column("hashed_password", sa.String(255)),
        sa.Column("shopify_store", sa.String(255)),
        sa.Column("shopify_token", sa.Text),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # Insert a stub user for development (no auth yet)
    op.execute("""
        INSERT INTO users (id, email, name, created_at)
        VALUES ('00000000-0000-0000-0000-000000000001', 'dev@localhost', 'Dev User', NOW())
        ON CONFLICT DO NOTHING
    """)

    op.create_table(
        "suppliers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("website_url", sa.Text),
        sa.Column("scrape_config", JSONB),
        sa.Column("pricing_config", JSONB),
        sa.Column("auto_approve_threshold", sa.String(10), server_default="0"),
        sa.Column("monitor_enabled", sa.Boolean, server_default="true"),
        sa.Column("monitor_interval", sa.Integer, server_default="1440"),
        sa.Column("last_scraped_at", sa.DateTime),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime),
    )

    op.create_table(
        "products",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("supplier_id", UUID(as_uuid=True), sa.ForeignKey("suppliers.id")),
        sa.Column("shopify_product_id", sa.BigInteger, unique=True),
        sa.Column("status", sa.String(50), server_default="draft"),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body_html", sa.Text),
        sa.Column("vendor", sa.String(255)),
        sa.Column("product_type", sa.String(255)),
        sa.Column("handle", sa.String(255)),
        sa.Column("tags", ARRAY(sa.String)),
        sa.Column("raw_title", sa.String(500)),
        sa.Column("raw_description", sa.Text),
        sa.Column("source_url", sa.Text),
        sa.Column("source_type", sa.String(50)),
        sa.Column("ai_description", sa.Text),
        sa.Column("ai_tags", ARRAY(sa.String)),
        sa.Column("ai_attributes", JSONB),
        sa.Column("seo_title", sa.String(255)),
        sa.Column("seo_description", sa.String(500)),
        sa.Column("enrichment_status", sa.String(50), server_default="pending"),
        sa.Column("enrichment_model", sa.String(100)),
        sa.Column("enrichment_at", sa.DateTime),
        sa.Column("cost_price", sa.Numeric(10, 2)),
        sa.Column("base_price", sa.Numeric(10, 2)),
        sa.Column("compare_at_price", sa.Numeric(10, 2)),
        sa.Column("supplier_price", sa.Numeric(10, 2)),
        sa.Column("supplier_price_at", sa.DateTime),
        sa.Column("sync_status", sa.String(50), server_default="never_synced"),
        sa.Column("synced_at", sa.DateTime),
        sa.Column("shopify_hash", sa.String(64)),
        sa.Column("metafields", JSONB),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime),
    )
    op.create_index("ix_products_status", "products", ["status"])
    op.create_index("ix_products_shopify_product_id", "products", ["shopify_product_id"])

    op.create_table(
        "product_images",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shopify_image_id", sa.BigInteger),
        sa.Column("src", sa.Text, nullable=False),
        sa.Column("alt", sa.String(500)),
        sa.Column("position", sa.Integer, server_default="1"),
        sa.Column("width", sa.Integer),
        sa.Column("height", sa.Integer),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "product_variants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shopify_variant_id", sa.BigInteger, unique=True),
        sa.Column("title", sa.String(255)),
        sa.Column("sku", sa.String(255)),
        sa.Column("barcode", sa.String(255)),
        sa.Column("option1", sa.String(100)),
        sa.Column("option2", sa.String(100)),
        sa.Column("option3", sa.String(100)),
        sa.Column("price", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("compare_at_price", sa.Numeric(10, 2)),
        sa.Column("cost", sa.Numeric(10, 2)),
        sa.Column("inventory_quantity", sa.Integer, server_default="0"),
        sa.Column("inventory_policy", sa.String(50), server_default="deny"),
        sa.Column("inventory_management", sa.String(50), server_default="shopify"),
        sa.Column("weight", sa.Numeric(8, 3)),
        sa.Column("weight_unit", sa.String(10), server_default="kg"),
        sa.Column("requires_shipping", sa.Boolean, server_default="true"),
        sa.Column("taxable", sa.Boolean, server_default="true"),
        sa.Column("image_id", UUID(as_uuid=True), sa.ForeignKey("product_images.id")),
        sa.Column("position", sa.Integer, server_default="1"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime),
    )
    op.create_index("ix_product_variants_sku", "product_variants", ["sku"])

    op.create_table(
        "import_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("supplier_id", UUID(as_uuid=True), sa.ForeignKey("suppliers.id")),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), server_default="queued"),
        sa.Column("celery_task_id", sa.String(255)),
        sa.Column("source_file", sa.Text),
        sa.Column("source_url", sa.Text),
        sa.Column("total_rows", sa.Integer, server_default="0"),
        sa.Column("processed_rows", sa.Integer, server_default="0"),
        sa.Column("success_rows", sa.Integer, server_default="0"),
        sa.Column("error_rows", sa.Integer, server_default="0"),
        sa.Column("error_details", JSONB),
        sa.Column("column_mapping", JSONB),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("started_at", sa.DateTime),
        sa.Column("completed_at", sa.DateTime),
    )

    op.create_table(
        "price_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("variant_id", UUID(as_uuid=True), sa.ForeignKey("product_variants.id")),
        sa.Column("supplier_id", UUID(as_uuid=True), sa.ForeignKey("suppliers.id")),
        sa.Column("price_type", sa.String(50)),
        sa.Column("old_price", sa.Numeric(10, 2)),
        sa.Column("new_price", sa.Numeric(10, 2)),
        sa.Column("change_pct", sa.Numeric(6, 3)),
        sa.Column("source", sa.String(50)),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "pricing_alerts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("variant_id", UUID(as_uuid=True), sa.ForeignKey("product_variants.id")),
        sa.Column("supplier_id", UUID(as_uuid=True), sa.ForeignKey("suppliers.id")),
        sa.Column("alert_type", sa.String(50), server_default="price_change"),
        sa.Column("old_price", sa.Numeric(10, 2)),
        sa.Column("new_price", sa.Numeric(10, 2)),
        sa.Column("change_pct", sa.Numeric(6, 3)),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("reviewed_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "pricing_schedules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE")),
        sa.Column("variant_id", UUID(as_uuid=True), sa.ForeignKey("product_variants.id")),
        sa.Column("supplier_id", UUID(as_uuid=True), sa.ForeignKey("suppliers.id")),
        sa.Column("tag_filter", sa.String(255)),
        sa.Column("schedule_type", sa.String(50), server_default="one_time"),
        sa.Column("price_action", sa.String(50)),
        sa.Column("price_value", sa.Numeric(10, 2)),
        sa.Column("original_price", sa.Numeric(10, 2)),
        sa.Column("starts_at", sa.DateTime, nullable=False),
        sa.Column("ends_at", sa.DateTime),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("celery_task_id", sa.String(255)),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime),
    )

    op.create_table(
        "pricing_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("supplier_id", UUID(as_uuid=True), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("rule_name", sa.String(255)),
        sa.Column("priority", sa.Integer, server_default="0"),
        sa.Column("condition_type", sa.String(50), server_default="always"),
        sa.Column("condition_value", JSONB),
        sa.Column("markup_type", sa.String(50), server_default="percent"),
        sa.Column("markup_value", sa.Numeric(10, 4), server_default="0"),
        sa.Column("round_to", sa.Numeric(6, 2)),
        sa.Column("min_price", sa.Numeric(10, 2)),
        sa.Column("max_price", sa.Numeric(10, 2)),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "shopify_sync_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE")),
        sa.Column("operation", sa.String(50)),
        sa.Column("status", sa.String(50)),
        sa.Column("shopify_id", sa.BigInteger),
        sa.Column("request_payload", JSONB),
        sa.Column("response_body", JSONB),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "scrape_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("supplier_id", UUID(as_uuid=True), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("import_job_id", UUID(as_uuid=True), sa.ForeignKey("import_jobs.id")),
        sa.Column("url", sa.Text),
        sa.Column("status", sa.String(50), server_default="running"),
        sa.Column("pages_scraped", sa.Integer, server_default="0"),
        sa.Column("products_found", sa.Integer, server_default="0"),
        sa.Column("raw_data", JSONB),
        sa.Column("error_details", sa.Text),
        sa.Column("started_at", sa.DateTime),
        sa.Column("completed_at", sa.DateTime),
    )


def downgrade() -> None:
    op.drop_table("scrape_sessions")
    op.drop_table("shopify_sync_log")
    op.drop_table("pricing_rules")
    op.drop_table("pricing_schedules")
    op.drop_table("pricing_alerts")
    op.drop_table("price_history")
    op.drop_table("import_jobs")
    op.drop_table("product_variants")
    op.drop_table("product_images")
    op.drop_table("products")
    op.drop_table("suppliers")
    op.drop_table("users")
