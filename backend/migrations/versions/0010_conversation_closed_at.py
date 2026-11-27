"""Track conversation closure time for retention."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0010_conversation_closed_at"
down_revision = "0009_unique_active_conversations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE conversations
            SET closed_at = updated_at
            WHERE is_active IS FALSE
            """
        )
    )


def downgrade() -> None:
    op.drop_column("conversations", "closed_at")
