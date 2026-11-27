"""Ensure one active conversation per application visitor identity."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0009_unique_active_conversations"
down_revision = "0008_lead_first_contact_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            WITH ranked_active AS (
                SELECT
                    id,
                    row_number() OVER (
                        PARTITION BY application_id, conversation_identity
                        ORDER BY created_at DESC, id DESC
                    ) AS position
                FROM conversations
                WHERE is_active IS TRUE
            )
            UPDATE conversations
            SET is_active = FALSE
            FROM ranked_active
            WHERE conversations.id = ranked_active.id
              AND ranked_active.position > 1
            """
        )
    )
    op.create_index(
        "uq_conversations_active_identity",
        "conversations",
        ["application_id", "conversation_identity"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_conversations_active_identity",
        table_name="conversations",
    )
