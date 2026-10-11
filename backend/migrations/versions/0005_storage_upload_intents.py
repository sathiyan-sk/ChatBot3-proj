"""Track in-flight storage uploads for orphan recovery.

Revision ID: 0005_storage_upload_intents
Revises: 0004_ingestion_leases
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_storage_upload_intents"
down_revision = "0004_ingestion_leases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "storage_upload_intents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_storage_upload_intents_created_at",
        "storage_upload_intents",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_storage_upload_intents_created_at",
        table_name="storage_upload_intents",
    )
    op.drop_table("storage_upload_intents")
