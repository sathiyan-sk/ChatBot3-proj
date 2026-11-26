"""Track when an admin first marks an enquiry contacted."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0008_lead_first_contact_tracking"
down_revision = "0007_leads_feedback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "leads",
        sa.Column("first_contacted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("leads", "first_contacted_at")
