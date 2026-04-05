"""Add ai_title to products for non-destructive title enrichment staging.

Revision ID: 015
Revises: 014
Create Date: 2026-04-04
"""
from alembic import op
import sqlalchemy as sa

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("products", sa.Column("ai_title", sa.String(500), nullable=True))


def downgrade():
    op.drop_column("products", "ai_title")
