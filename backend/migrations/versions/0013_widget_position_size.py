"""Persist widget launcher position and panel size."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0013_widget_position_size"
down_revision = "0012_website_refresh_schedule"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "widgets",
        sa.Column(
            "launcher_position",
            sa.String(length=10),
            server_default="right",
            nullable=False,
        ),
    )
    op.add_column(
        "widgets",
        sa.Column(
            "panel_size",
            sa.String(length=16),
            server_default="standard",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "launcher_position",
        "widgets",
        "launcher_position IN ('left', 'right')",
    )
    op.create_check_constraint(
        "panel_size",
        "widgets",
        "panel_size IN ('compact', 'standard', 'wide')",
    )


def downgrade() -> None:
    op.drop_constraint("panel_size", "widgets", type_="check")
    op.drop_constraint("launcher_position", "widgets", type_="check")
    op.drop_column("widgets", "panel_size")
    op.drop_column("widgets", "launcher_position")
