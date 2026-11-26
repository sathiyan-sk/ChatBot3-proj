from __future__ import annotations

from datetime import datetime
from uuid import UUID as PyUUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class LeadModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint(
            "application_id",
            "idempotency_key",
            name="uq_leads_application_idempotency_key",
        ),
        CheckConstraint(
            "status IN ('new', 'contacted', 'closed')",
            name="valid_status",
        ),
        CheckConstraint(
            "email IS NOT NULL OR phone IS NOT NULL",
            name="contact_required",
        ),
        Index("ix_leads_application_created", "application_id", "created_at"),
        Index("ix_leads_application_status", "application_id", "status"),
        Index("ix_leads_conversation_id", "conversation_id"),
    )

    application_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    conversation_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="new",
        server_default="new",
    )
    internal_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    consent_given: Mapped[bool] = mapped_column(nullable=False)
    consent_text_version: Mapped[str] = mapped_column(String(32), nullable=False)
    consent_text: Mapped[str] = mapped_column(Text, nullable=False)
    consented_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    first_contacted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    application = relationship("ApplicationModel")


class ConversationFeedbackModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversation_feedback"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            name="uq_conversation_feedback_conversation_id",
        ),
        CheckConstraint("rating >= 1 AND rating <= 5", name="valid_rating"),
        Index("ix_conversation_feedback_application_id", "application_id"),
    )

    application_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    conversation_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
