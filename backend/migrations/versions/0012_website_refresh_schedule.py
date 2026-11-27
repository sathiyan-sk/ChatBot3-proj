"""Add opt-in refresh scheduling for website documents."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0012_website_refresh_schedule"
down_revision = "0011_app_upload_intents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("refresh_interval_hours", sa.Integer(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("next_refresh_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_documents_next_refresh_at",
        "documents",
        ["next_refresh_at"],
    )
    op.create_check_constraint(
        "refresh_interval_hours",
        "documents",
        "refresh_interval_hours IS NULL OR "
        "(refresh_interval_hours >= 1 AND refresh_interval_hours <= 720)",
    )
    op.create_check_constraint(
        "refresh_website_only",
        "documents",
        "refresh_interval_hours IS NULL OR source_type = 'website'",
    )


def downgrade() -> None:
    op.drop_constraint(
        "refresh_website_only",
        "documents",
        type_="check",
    )
    op.drop_constraint(
        "refresh_interval_hours",
        "documents",
        type_="check",
    )
    op.drop_index("ix_documents_next_refresh_at", table_name="documents")
    op.drop_column("documents", "next_refresh_at")
    op.drop_column("documents", "refresh_interval_hours")
