"""Simplify product status to draft | active | archived (mirrors Shopify).

Revision ID: 013
Revises: 012
Create Date: 2026-03-15
"""
from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade():
    # Map old workflow statuses to the new Shopify-aligned values:
    #   draft     → draft    (no change)
    #   enriched  → draft    (AI suggestions don't change readiness)
    #   approved  → active   (user said it was ready — treat as active)
    #   synced    → active   (was live on Shopify — still active)
    #   archived  → archived (no change)
    op.execute("""
        UPDATE products
        SET status = CASE
            WHEN status IN ('approved', 'synced') THEN 'active'
            WHEN status = 'enriched'              THEN 'draft'
            ELSE status
        END
        WHERE status IN ('enriched', 'approved', 'synced')
    """)


def downgrade():
    # Best-effort reverse: active → approved, leave draft/archived as-is
    op.execute("""
        UPDATE products
        SET status = 'approved'
        WHERE status = 'active'
    """)
