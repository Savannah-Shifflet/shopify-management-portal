"""Fix enrichment_status default from pending to not_started

Revision ID: 012
Revises: 011
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade():
    # Change the column default
    op.alter_column(
        "products",
        "enrichment_status",
        server_default="not_started",
    )
    # Update existing rows that are still at the old default "pending"
    # and have never actually been queued (no enrichment_at timestamp)
    op.execute(
        "UPDATE products SET enrichment_status = 'not_started' "
        "WHERE enrichment_status = 'pending' AND enrichment_at IS NULL"
    )


def downgrade():
    op.alter_column(
        "products",
        "enrichment_status",
        server_default="pending",
    )
    op.execute(
        "UPDATE products SET enrichment_status = 'pending' "
        "WHERE enrichment_status = 'not_started'"
    )
