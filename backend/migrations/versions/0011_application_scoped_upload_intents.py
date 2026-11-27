"""Associate upload intents with their application."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0011_app_upload_intents"
down_revision = "0010_conversation_closed_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "storage_upload_intents",
        sa.Column(
            "application_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE storage_upload_intents AS intent
            SET application_id = knowledge_base.application_id
            FROM knowledge_bases AS knowledge_base
            WHERE knowledge_base.id::text = split_part(intent.storage_path, '/', 1)
            """
        )
    )
    op.create_foreign_key(
        "fk_storage_upload_intents_application_id_applications",
        "storage_upload_intents",
        "applications",
        ["application_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_storage_upload_intents_application_id",
        "storage_upload_intents",
        ["application_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_storage_upload_intents_application_id",
        table_name="storage_upload_intents",
    )
    op.drop_constraint(
        "fk_storage_upload_intents_application_id_applications",
        "storage_upload_intents",
        type_="foreignkey",
    )
    op.drop_column("storage_upload_intents", "application_id")
