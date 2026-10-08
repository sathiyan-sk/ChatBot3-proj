"""Create the application and pgvector schema for a fresh database.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-07
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("slug", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("client_type", sa.String(length=50), nullable=False),
        sa.Column("allowed_origins", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_applications")),
        sa.UniqueConstraint("name", name=op.f("uq_applications_name")),
        sa.UniqueConstraint("slug", name=op.f("uq_applications_slug")),
    )
    op.create_index("ix_applications_name", "applications", ["name"])
    op.create_index("ix_applications_slug", "applications", ["slug"])
    op.create_index("ix_applications_is_active", "applications", ["is_active"])

    op.create_table(
        "knowledge_bases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("slug", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=50), server_default=sa.text("'ready'"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            ondelete="CASCADE",
            name=op.f("fk_knowledge_bases_application_id_applications"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_bases")),
        sa.UniqueConstraint("application_id", name=op.f("uq_knowledge_bases_application_id")),
        sa.UniqueConstraint("slug", name=op.f("uq_knowledge_bases_slug")),
    )
    op.create_index("ix_knowledge_bases_application_id", "knowledge_bases", ["application_id"])
    op.create_index("ix_knowledge_bases_status", "knowledge_bases", ["status"])
    op.create_index("ix_knowledge_bases_is_active", "knowledge_bases", ["is_active"])
    op.create_index("ux_knowledge_bases_slug", "knowledge_bases", ["slug"], unique=True)

    op.create_table(
        "application_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("llm_temperature", sa.String(length=20), server_default=sa.text("'0.2'"), nullable=False),
        sa.Column("max_context_messages", sa.Integer(), server_default=sa.text("12"), nullable=False),
        sa.Column("inactivity_timeout_minutes", sa.Integer(), server_default=sa.text("30"), nullable=False),
        sa.Column("retention_days", sa.Integer(), server_default=sa.text("30"), nullable=False),
        sa.Column("prompt_system_template", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            ondelete="CASCADE",
            name=op.f("fk_application_settings_application_id_applications"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_application_settings")),
        sa.UniqueConstraint("application_id", name=op.f("uq_application_settings_application_id")),
    )
    op.create_index("ix_application_settings_application_id", "application_settings", ["application_id"])

    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("key_prefix", sa.String(length=32), nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            ondelete="CASCADE",
            name=op.f("fk_api_keys_application_id_applications"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_keys")),
    )
    op.create_index("ix_api_keys_application_id", "api_keys", ["application_id"])
    op.create_index("ix_api_keys_key_prefix", "api_keys", ["key_prefix"])
    op.create_index("ix_api_keys_is_active", "api_keys", ["is_active"])

    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_identity", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            ondelete="CASCADE",
            name=op.f("fk_conversations_application_id_applications"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversations")),
    )
    op.create_index("ix_conversations_application_id", "conversations", ["application_id"])
    op.create_index("ix_conversations_conversation_identity", "conversations", ["conversation_identity"])
    op.create_index("ix_conversations_is_active", "conversations", ["is_active"])

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=True),
        sa.Column("storage_path", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.String(length=150), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=50), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            ondelete="CASCADE",
            name=op.f("fk_documents_application_id_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_base_id"],
            ["knowledge_bases.id"],
            ondelete="CASCADE",
            name=op.f("fk_documents_knowledge_base_id_knowledge_bases"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
    )
    op.create_index("ix_documents_application_id", "documents", ["application_id"])
    op.create_index("ix_documents_knowledge_base_id", "documents", ["knowledge_base_id"])
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_index("ix_documents_source_type", "documents", ["source_type"])

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("citations_json", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            ondelete="CASCADE",
            name=op.f("fk_messages_conversation_id_conversations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_role", "messages", ["role"])
    op.create_index("ix_messages_sequence_number", "messages", ["sequence_number"])

    op.create_table(
        "widgets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(length=150), nullable=False),
        sa.Column("public_key", sa.String(length=150), nullable=True),
        sa.Column("theme", sa.String(length=50), server_default=sa.text("'light'"), nullable=False),
        sa.Column("launcher_label", sa.String(length=100), nullable=True),
        sa.Column("welcome_message", sa.Text(), nullable=True),
        sa.Column("placeholder_text", sa.String(length=255), nullable=True),
        sa.Column("accent_color", sa.String(length=20), nullable=True),
        sa.Column("starter_prompts", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            ondelete="CASCADE",
            name=op.f("fk_widgets_application_id_applications"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_widgets")),
        sa.UniqueConstraint("public_key", name=op.f("uq_widgets_public_key")),
    )
    op.create_index("ix_widgets_application_id", "widgets", ["application_id"])
    op.create_index("ix_widgets_is_enabled", "widgets", ["is_enabled"])
    op.create_index("ix_widgets_public_key", "widgets", ["public_key"])

    op.create_table(
        "document_chunks",
        sa.Column("chunk_id", sa.Text(), nullable=False),
        sa.Column("knowledge_base_id", sa.Text(), nullable=False),
        sa.Column("document_id", sa.Text(), nullable=False),
        sa.Column("document_title", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=True,
        ),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.PrimaryKeyConstraint("chunk_id", name=op.f("pk_document_chunks")),
    )
    op.create_index("document_chunks_kb_idx", "document_chunks", ["knowledge_base_id"])
    op.create_index(
        "document_chunks_embedding_idx",
        "document_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "document_chunks_content_fts_idx",
        "document_chunks",
        [sa.text("to_tsvector('english', content)")],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_table("document_chunks")
    op.drop_table("messages")
    op.drop_table("documents")
    op.drop_table("widgets")
    op.drop_table("api_keys")
    op.drop_table("application_settings")
    op.drop_table("conversations")
    op.drop_table("knowledge_bases")
    op.drop_table("applications")