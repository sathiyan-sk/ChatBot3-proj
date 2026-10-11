"""Add durable ingestion leases and bounded retry metadata.

Revision ID: 0004_ingestion_leases
Revises: 0003_version_document_chunks
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_ingestion_leases"
down_revision = "0003_version_document_chunks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "failure_code",
            sa.String(length=100),
            nullable=True,
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "ingestion_attempt_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "ingestion_next_attempt_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "ingestion_lease_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.execute(
        """
        UPDATE documents
        SET ingestion_lease_expires_at = updated_at + interval '15 minutes'
        WHERE status = 'processing'
        """
    )


def downgrade() -> None:
    op.drop_column("documents", "ingestion_lease_expires_at")
    op.drop_column("documents", "ingestion_next_attempt_at")
    op.drop_column("documents", "ingestion_attempt_count")
    op.drop_column("documents", "failure_code")
