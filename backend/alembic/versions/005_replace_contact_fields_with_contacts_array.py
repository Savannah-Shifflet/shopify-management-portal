"""replace flat contact fields with contacts JSONB array

Revision ID: 005
Revises: 004
Create Date: 2026-03-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('suppliers', sa.Column('contacts', JSONB(), nullable=True, server_default='[]'))

    # Migrate existing single-contact fields into the array
    op.execute("""
        UPDATE suppliers
        SET contacts = jsonb_build_array(
            jsonb_strip_nulls(jsonb_build_object(
                'name',  contact_name,
                'email', contact_email,
                'phone', contact_phone,
                'role',  NULL
            ))
        )
        WHERE contact_name IS NOT NULL
           OR contact_email IS NOT NULL
           OR contact_phone IS NOT NULL
    """)

    op.drop_column('suppliers', 'contact_name')
    op.drop_column('suppliers', 'contact_email')
    op.drop_column('suppliers', 'contact_phone')


def downgrade():
    op.add_column('suppliers', sa.Column('contact_name', sa.String(255), nullable=True))
    op.add_column('suppliers', sa.Column('contact_email', sa.String(255), nullable=True))
    op.add_column('suppliers', sa.Column('contact_phone', sa.String(100), nullable=True))

    op.execute("""
        UPDATE suppliers
        SET contact_name  = (contacts->0->>'name'),
            contact_email = (contacts->0->>'email'),
            contact_phone = (contacts->0->>'phone')
        WHERE jsonb_array_length(contacts) > 0
    """)

    op.drop_column('suppliers', 'contacts')
