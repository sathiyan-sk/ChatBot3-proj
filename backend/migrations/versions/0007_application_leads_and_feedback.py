"""Add application-owned leads and conversation feedback.

Revision ID: 0007_leads_feedback
Revises: 0006_application_ai_selections
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_leads_feedback"
down_revision = "0006_application_ai_selections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="new",
            nullable=False,
        ),
        sa.Column("internal_note", sa.Text(), nullable=True),
        sa.Column("consent_given", sa.Boolean(), nullable=False),
        sa.Column("consent_text_version", sa.String(length=32), nullable=False),
        sa.Column("consent_text", sa.Text(), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('new', 'contacted', 'closed')",
            name="valid_status",
        ),
        sa.CheckConstraint(
            "email IS NOT NULL OR phone IS NOT NULL",
            name="contact_required",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_leads_application_id_applications",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="fk_leads_conversation_id_conversations",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "application_id",
            "idempotency_key",
            name="uq_leads_application_idempotency_key",
        ),
    )
    op.create_index(
        "ix_leads_application_created",
        "leads",
        ["application_id", "created_at"],
    )
    op.create_index(
        "ix_leads_application_status",
        "leads",
        ["application_id", "status"],
    )
    op.create_index("ix_leads_conversation_id", "leads", ["conversation_id"])

    op.create_table(
        "conversation_feedback",
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.CheckConstraint(
            "rating >= 1 AND rating <= 5",
            name="valid_rating",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_conversation_feedback_application_id_applications",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="fk_conversation_feedback_conversation_id_conversations",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "conversation_id",
            name="uq_conversation_feedback_conversation_id",
        ),
    )
    op.create_index(
        "ix_conversation_feedback_application_id",
        "conversation_feedback",
        ["application_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversation_feedback_application_id",
        table_name="conversation_feedback",
    )
    op.drop_table("conversation_feedback")
    op.drop_index("ix_leads_conversation_id", table_name="leads")
    op.drop_index("ix_leads_application_status", table_name="leads")
    op.drop_index("ix_leads_application_created", table_name="leads")
    op.drop_table("leads")
