"""add detail_scrape_logs table

Revision ID: 006
Revises: 005
Create Date: 2026-03-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'detail_scrape_logs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('supplier_id', UUID(as_uuid=True), sa.ForeignKey('suppliers.id'), nullable=False),
        sa.Column('triggered_by', sa.String(50), nullable=False, server_default='rescrape'),
        sa.Column('item_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_detail_scrape_logs_supplier_id', 'detail_scrape_logs', ['supplier_id'])


def downgrade():
    op.drop_index('ix_detail_scrape_logs_supplier_id', table_name='detail_scrape_logs')
    op.drop_table('detail_scrape_logs')
