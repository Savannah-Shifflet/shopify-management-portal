"""add supplier CRM and settings fields

Revision ID: 004
Revises: 003
Create Date: 2026-03-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('suppliers', sa.Column('free_shipping', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('suppliers', sa.Column('avg_fulfillment_days', sa.Integer(), nullable=True))
    op.add_column('suppliers', sa.Column('google_listings_approved', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('suppliers', sa.Column('contact_name', sa.String(255), nullable=True))
    op.add_column('suppliers', sa.Column('contact_email', sa.String(255), nullable=True))
    op.add_column('suppliers', sa.Column('contact_phone', sa.String(100), nullable=True))
    op.add_column('suppliers', sa.Column('crm_notes', JSONB(), nullable=True, server_default='[]'))


def downgrade():
    op.drop_column('suppliers', 'free_shipping')
    op.drop_column('suppliers', 'avg_fulfillment_days')
    op.drop_column('suppliers', 'google_listings_approved')
    op.drop_column('suppliers', 'contact_name')
    op.drop_column('suppliers', 'contact_email')
    op.drop_column('suppliers', 'contact_phone')
    op.drop_column('suppliers', 'crm_notes')
