"""Add shipping_cost to products; add default_shipping_cost and default_markup_pct to store_settings.

Revision ID: 014
Revises: 013
Create Date: 2026-04-04
"""
from alembic import op
import sqlalchemy as sa

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade():
    # Per-product shipping cost (used to bake free-shipping into retail price)
    op.add_column("products", sa.Column("shipping_cost", sa.Numeric(10, 2), nullable=True))

    # Global pricing defaults on store_settings
    op.add_column("store_settings", sa.Column("default_shipping_cost", sa.Numeric(10, 2), nullable=True))
    op.add_column("store_settings", sa.Column("default_markup_pct", sa.Numeric(6, 2), nullable=True))


def downgrade():
    op.drop_column("store_settings", "default_markup_pct")
    op.drop_column("store_settings", "default_shipping_cost")
    op.drop_column("products", "shipping_cost")
