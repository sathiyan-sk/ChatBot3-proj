from __future__ import annotations

from datetime import datetime
from uuid import UUID as PyUUID

from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class StorageUploadIntentModel(Base):
    __tablename__ = "storage_upload_intents"
    __table_args__ = (
        Index("ix_storage_upload_intents_created_at", "created_at"),
        Index(
            "ix_storage_upload_intents_application_id",
            "application_id",
        ),
    )

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
    )
    application_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=True,
    )
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
