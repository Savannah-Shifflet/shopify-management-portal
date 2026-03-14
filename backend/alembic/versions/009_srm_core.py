"""SRM core — supplier pipeline, emails, documents, checklist, reorders, email templates, audit log, store settings

Revision ID: 009
Revises: 008
Create Date: 2026-03-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade():
    # Extend suppliers table
    op.add_column("suppliers", sa.Column("status", sa.String(50), nullable=True, server_default="LEAD"))
    op.add_column("suppliers", sa.Column("company_email", sa.String(255), nullable=True))
    op.add_column("suppliers", sa.Column("contact_name", sa.String(255), nullable=True))
    op.add_column("suppliers", sa.Column("phone", sa.String(100), nullable=True))
    op.add_column("suppliers", sa.Column("product_categories", ARRAY(sa.String), nullable=True, server_default="{}"))
    op.add_column("suppliers", sa.Column("follow_up_date", sa.DateTime, nullable=True))
    op.add_column("suppliers", sa.Column("approved_at", sa.DateTime, nullable=True))
    op.add_column("suppliers", sa.Column("payment_terms", sa.String(100), nullable=True))
    op.add_column("suppliers", sa.Column("min_order_qty", sa.Integer, nullable=True))
    op.add_column("suppliers", sa.Column("lead_time_days", sa.Integer, nullable=True))
    op.add_column("suppliers", sa.Column("return_policy", sa.Text, nullable=True))
    op.add_column("suppliers", sa.Column("map_enforced", sa.Boolean, nullable=True, server_default="false"))
    op.add_column("suppliers", sa.Column("warranty_info", sa.Text, nullable=True))
    op.add_column("suppliers", sa.Column("map_price", sa.Numeric(10, 2), nullable=True))

    # Extend products table
    op.add_column("products", sa.Column("map_price", sa.Numeric(10, 2), nullable=True))

    # supplier_emails
    op.create_table("supplier_emails",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("supplier_id", UUID(as_uuid=True), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("subject", sa.String(500)),
        sa.Column("body", sa.Text),
        sa.Column("sent_at", sa.DateTime, nullable=False),
        sa.Column("attachments", JSONB, server_default="[]"),
    )
    op.create_index("ix_supplier_emails_supplier_id", "supplier_emails", ["supplier_id"])

    # supplier_documents
    op.create_table("supplier_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("supplier_id", UUID(as_uuid=True), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100)),
        sa.Column("file_path", sa.Text),
        sa.Column("file_name", sa.String(255)),
        sa.Column("mime_type", sa.String(100)),
        sa.Column("expires_at", sa.DateTime, nullable=True),
        sa.Column("uploaded_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_supplier_documents_supplier_id", "supplier_documents", ["supplier_id"])

    # checklist_templates
    op.create_table("checklist_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("order", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime),
    )

    # supplier_checklist_items
    op.create_table("supplier_checklist_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("supplier_id", UUID(as_uuid=True), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("template_item_id", UUID(as_uuid=True), sa.ForeignKey("checklist_templates.id"), nullable=True),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("completed", sa.Boolean, server_default="false"),
        sa.Column("notes", sa.Text),
        sa.Column("file_path", sa.Text),
        sa.Column("file_name", sa.String(255)),
        sa.Column("created_at", sa.DateTime),
    )
    op.create_index("ix_supplier_checklist_items_supplier_id", "supplier_checklist_items", ["supplier_id"])

    # reorder_logs
    op.create_table("reorder_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("supplier_id", UUID(as_uuid=True), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("po_number", sa.String(100)),
        sa.Column("order_date", sa.Date),
        sa.Column("expected_delivery", sa.Date),
        sa.Column("status", sa.String(50), server_default="Pending"),
        sa.Column("line_items", JSONB, server_default="[]"),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )
    op.create_index("ix_reorder_logs_supplier_id", "reorder_logs", ["supplier_id"])

    # email_templates
    op.create_table("email_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(500)),
        sa.Column("body", sa.Text),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )

    # audit_logs
    op.create_table("audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("timestamp", sa.DateTime, nullable=False),
        sa.Column("action_type", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(100)),
        sa.Column("entity_id", sa.String(255)),
        sa.Column("description", sa.Text),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])

    # store_settings
    op.create_table("store_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("store_name", sa.String(255)),
        sa.Column("owner_name", sa.String(255)),
        sa.Column("logo_path", sa.Text),
        sa.Column("currency", sa.String(10), server_default="USD"),
        sa.Column("timezone", sa.String(100), server_default="America/New_York"),
        sa.Column("smtp_host", sa.String(255)),
        sa.Column("smtp_port", sa.Integer, server_default="587"),
        sa.Column("smtp_user", sa.String(255)),
        sa.Column("smtp_password", sa.Text),
        sa.Column("smtp_from_name", sa.String(255)),
        sa.Column("smtp_from_email", sa.String(255)),
        sa.Column("map_hard_block", sa.Boolean, server_default="false"),
        sa.Column("low_stock_threshold", sa.Integer, server_default="5"),
    )


def downgrade():
    op.drop_table("store_settings")
    op.drop_index("ix_audit_logs_timestamp", "audit_logs")
    op.drop_index("ix_audit_logs_user_id", "audit_logs")
    op.drop_table("audit_logs")
    op.drop_table("email_templates")
    op.drop_index("ix_reorder_logs_supplier_id", "reorder_logs")
    op.drop_table("reorder_logs")
    op.drop_index("ix_supplier_checklist_items_supplier_id", "supplier_checklist_items")
    op.drop_table("supplier_checklist_items")
    op.drop_table("checklist_templates")
    op.drop_index("ix_supplier_documents_supplier_id", "supplier_documents")
    op.drop_table("supplier_documents")
    op.drop_index("ix_supplier_emails_supplier_id", "supplier_emails")
    op.drop_table("supplier_emails")
    op.drop_column("products", "map_price")
    op.drop_column("suppliers", "map_price")
    op.drop_column("suppliers", "warranty_info")
    op.drop_column("suppliers", "map_enforced")
    op.drop_column("suppliers", "return_policy")
    op.drop_column("suppliers", "lead_time_days")
    op.drop_column("suppliers", "min_order_qty")
    op.drop_column("suppliers", "payment_terms")
    op.drop_column("suppliers", "approved_at")
    op.drop_column("suppliers", "follow_up_date")
    op.drop_column("suppliers", "product_categories")
    op.drop_column("suppliers", "phone")
    op.drop_column("suppliers", "contact_name")
    op.drop_column("suppliers", "company_email")
    op.drop_column("suppliers", "status")
