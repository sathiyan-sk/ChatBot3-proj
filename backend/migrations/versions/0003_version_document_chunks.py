"""Associate vector rows with explicit document ingestion versions.

Revision ID: 0003_version_document_chunks
Revises: 0002_document_ingestion_versions
Create Date: 2026-10-10
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_version_document_chunks"
down_revision = "0002_document_ingestion_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_chunks",
        sa.Column(
            "ingestion_version",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
    )
    op.drop_constraint(
        op.f("pk_document_chunks"),
        "document_chunks",
        type_="primary",
    )
    op.create_primary_key(
        op.f("pk_document_chunks"),
        "document_chunks",
        ["chunk_id", "ingestion_version"],
    )
    op.create_index(
        "document_chunks_document_version_idx",
        "document_chunks",
        ["document_id", "ingestion_version"],
    )


def downgrade() -> None:
    op.drop_index(
        "document_chunks_document_version_idx",
        table_name="document_chunks",
    )
    op.drop_constraint(
        op.f("pk_document_chunks"),
        "document_chunks",
        type_="primary",
    )
    op.create_primary_key(
        op.f("pk_document_chunks"),
        "document_chunks",
        ["chunk_id"],
    )
    op.drop_column("document_chunks", "ingestion_version")
