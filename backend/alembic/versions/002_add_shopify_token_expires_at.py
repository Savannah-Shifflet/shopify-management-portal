"""add shopify_token_expires_at

Revision ID: 002
Revises: 001
Create Date: 2026-03-07
"""
from alembic import op
import sqlalchemy as sa

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('shopify_token_expires_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('users', 'shopify_token_expires_at')
