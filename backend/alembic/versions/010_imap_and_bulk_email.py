"""Add IMAP settings to store_settings; add message_id to supplier_emails

Revision ID: 010
Revises: 009
Create Date: 2026-03-14
"""
from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade():
    # IMAP settings on store_settings
    op.add_column("store_settings", sa.Column("imap_host", sa.String(255), nullable=True))
    op.add_column("store_settings", sa.Column("imap_port", sa.Integer(), nullable=True, server_default="993"))
    op.add_column("store_settings", sa.Column("imap_user", sa.String(255), nullable=True))
    op.add_column("store_settings", sa.Column("imap_password", sa.Text(), nullable=True))
    op.add_column("store_settings", sa.Column("imap_folder", sa.String(255), nullable=True, server_default="INBOX"))

    # Message-ID deduplication on supplier_emails
    op.add_column("supplier_emails", sa.Column("message_id", sa.String(500), nullable=True))
    op.create_index("ix_supplier_emails_message_id", "supplier_emails", ["message_id"])


def downgrade():
    op.drop_index("ix_supplier_emails_message_id", "supplier_emails")
    op.drop_column("supplier_emails", "message_id")
    op.drop_column("store_settings", "imap_folder")
    op.drop_column("store_settings", "imap_password")
    op.drop_column("store_settings", "imap_user")
    op.drop_column("store_settings", "imap_port")
    op.drop_column("store_settings", "imap_host")
