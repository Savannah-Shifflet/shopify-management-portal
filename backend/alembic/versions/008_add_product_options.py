"""add options column to products

Revision ID: 008
Revises: 007
Create Date: 2026-03-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "products",
        sa.Column("options", JSONB, nullable=True, server_default="[]"),
    )


def downgrade():
    op.drop_column("products", "options")
