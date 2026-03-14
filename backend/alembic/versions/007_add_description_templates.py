"""add description_templates table

Revision ID: 007
Revises: 006
Create Date: 2026-03-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'description_templates',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('sections', JSONB(), nullable=True, server_default='[]'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_description_templates_user_id', 'description_templates', ['user_id'])


def downgrade():
    op.drop_index('ix_description_templates_user_id', table_name='description_templates')
    op.drop_table('description_templates')
