"""Add applied_template_id to products

Revision ID: 011
Revises: 010
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "products",
        sa.Column(
            "applied_template_id",
            UUID(as_uuid=True),
            sa.ForeignKey("description_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("products", "applied_template_id")
