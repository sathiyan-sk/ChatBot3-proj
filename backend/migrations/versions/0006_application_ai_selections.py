"""Add application-level AI provider and model selections.

Revision ID: 0006_application_ai_selections
Revises: 0005_storage_upload_intents
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_application_ai_selections"
down_revision = "0005_storage_upload_intents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "application_settings",
        sa.Column("parser_provider", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "application_settings",
        sa.Column("embedding_provider", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "application_settings",
        sa.Column("embedding_model", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "application_settings",
        sa.Column("llm_provider", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "application_settings",
        sa.Column("llm_model", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("application_settings", "llm_model")
    op.drop_column("application_settings", "llm_provider")
    op.drop_column("application_settings", "embedding_model")
    op.drop_column("application_settings", "embedding_provider")
    op.drop_column("application_settings", "parser_provider")
