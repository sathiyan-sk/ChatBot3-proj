from __future__ import annotations

from uuid import UUID as PyUUID

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class SettingsModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "application_settings"
    __table_args__ = (
        Index("ix_application_settings_application_id", "application_id"),
    )

    application_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    llm_temperature: Mapped[str] = mapped_column(String(20), nullable=False, default="0.2", server_default="0.2")
    max_context_messages: Mapped[int] = mapped_column(Integer, nullable=False, default=12, server_default="12")
    inactivity_timeout_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30, server_default="30")
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30, server_default="30")
    prompt_system_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    parser_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    embedding_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    llm_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(255), nullable=True)

    application = relationship("ApplicationModel", back_populates="settings")