"""Add user_profiles table for profile preferences and onboarding state."""

import sqlalchemy as sa
from alembic import op

revision = "20261121_user_profiles"
down_revision = "20261121_submission_owner_fk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
            unique=True,
            nullable=False,
        ),
        sa.Column("display_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("avatar_url", sa.String(2048), nullable=True),
        sa.Column("goal", sa.String(32), nullable=True),
        sa.Column("experience", sa.String(32), nullable=True),
        sa.Column("weekly_minutes", sa.Integer(), nullable=True),
        sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "goal IS NULL OR goal IN ('learn_basics', 'avoid_scams', 'invest_smarter', 'other')",
            name="ck_user_profiles_goal",
        ),
        sa.CheckConstraint(
            "experience IS NULL OR experience IN ('new', 'some', 'experienced')",
            name="ck_user_profiles_experience",
        ),
        sa.CheckConstraint(
            "weekly_minutes IS NULL OR (weekly_minutes >= 1 AND weekly_minutes <= 10080)",
            name="ck_user_profiles_weekly_minutes",
        ),
    )


def downgrade() -> None:
    op.drop_table("user_profiles")
