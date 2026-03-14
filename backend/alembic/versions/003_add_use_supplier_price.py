"""add use_supplier_price to products

Revision ID: 003
Revises: 002
Create Date: 2026-03-07
"""
from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('products', sa.Column('use_supplier_price', sa.Boolean(), nullable=False, server_default='false'))


def downgrade():
    op.drop_column('products', 'use_supplier_price')
