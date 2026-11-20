"""Persist private Nasdaq keys with owner and TTL (no process-local state)."""

import sqlalchemy as sa
from alembic import op

revision = "20261121_nasdaq_challenges"
down_revision = "20261120_01_edu"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nasdaq_challenges",
        sa.Column("id", sa.String(66), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(as_uuid=False), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_origin", sa.String(9), nullable=False),
        sa.CheckConstraint("data_origin = 'real'", name="ck_nasdaq_challenges_origin"),
    )
    op.create_index("ix_nasdaq_challenges_expires", "nasdaq_challenges", ["expires_at"])


def downgrade() -> None:
    op.drop_table("nasdaq_challenges")
