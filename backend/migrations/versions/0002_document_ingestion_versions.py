"""Track ingestion attempts and the last atomically published version.

Revision ID: 0002_document_ingestion_versions
Revises: 0001_initial_schema
Create Date: 2026-10-10
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_document_ingestion_versions"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "ingestion_version",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "documents",
        sa.Column("ready_version", sa.Integer(), nullable=True),
    )
    op.execute(
        """
        UPDATE documents AS document
        SET ingestion_version = 1,
            ready_version = 1
        WHERE document.status = 'ready'
           OR EXISTS (
                SELECT 1
                FROM document_chunks AS chunk
                WHERE chunk.document_id = document.id::text
           )
        """
    )


def downgrade() -> None:
    op.drop_column("documents", "ready_version")
    op.drop_column("documents", "ingestion_version")
