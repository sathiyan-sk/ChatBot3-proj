from __future__ import annotations

from uuid import UUID as PyUUID

from sqlalchemy import (
    ARRAY,
    Boolean,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.infrastructure.db.base import (
    Base,
    TimestampMixin,
    UuidPrimaryKeyMixin,
)


class WidgetModel(
    UuidPrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    __tablename__ = "widgets"

    __table_args__ = (
        Index(
            "ix_widgets_application_id",
            "application_id",
        ),
        Index(
            "ix_widgets_is_enabled",
            "is_enabled",
        ),
        Index(
            "ix_widgets_public_key",
            "public_key",
        ),
    )

    application_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "applications.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    display_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    public_key: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
        unique=True,
    )

    theme: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="light",
        server_default="light",
    )

    launcher_label: Mapped[str | None] = (
        mapped_column(
            String(100),
            nullable=True,
        )
    )

    welcome_message: Mapped[str | None] = (
        mapped_column(
            Text,
            nullable=True,
        )
    )

    placeholder_text: Mapped[str | None] = (
        mapped_column(
            String(255),
            nullable=True,
        )
    )

    # Optional accent colour (hex, e.g. "#00D4FF") applied to the launcher,
    # send button and (in light theme) the header. None => use theme default.
    accent_color: Mapped[str | None] = (
        mapped_column(
            String(20),
            nullable=True,
        )
    )

    # Ordered list of starter prompt chips shown above the input so visitors
    # can begin a conversation with one tap.
    starter_prompts: Mapped[list[str] | None] = (
        mapped_column(
            ARRAY(String),
            nullable=True,
        )
    )

    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    application = relationship(
        "ApplicationModel",
        back_populates="widgets",
    )