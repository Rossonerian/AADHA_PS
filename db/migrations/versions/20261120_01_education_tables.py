"""Create Education module tables (SoT Section 6).

Revision ID: 20261120_01_edu
Revises: None
Create Date: 2026-11-20 15:15:00.000000
Owner: Divyansh (coordinated with Hardhik's db/migrations/)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261120_01_edu"
# Chained to Alembic head in monorepo (0001_initial_platform -> 20261120_verifier -> 20261120_01_edu)
down_revision = "20261120_verifier"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Applies all Education tables, constraints, and indexes."""
    # Note: `users` is owned by Hardhik; in production down_revision points to Hardhik's core users migration.
    op.create_table(
        "unlocks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tool", sa.String(32), nullable=False),
        sa.Column(
            "unlocked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "tool", name="uq_unlocks_user_tool"),
        sa.CheckConstraint(
            "tool IN ('scenarios','red_flag_check','explain_stock','verifier','dashboard')",
            name="ck_unlocks_tool",
        ),
    )
    op.create_index("ix_unlocks_user_id", "unlocks", ["user_id"])

    op.create_table(
        "skill_scores",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("skill_area", sa.String(32), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("brier", sa.Float(), nullable=False),
        sa.Column(
            "measured_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "skill_area IN ('basics','reading_stock','judging_info','risk')",
            name="ck_skill_scores_area",
        ),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_skill_scores_range"),
        sa.CheckConstraint("brier >= 0 AND brier <= 1", name="ck_skill_scores_brier"),
    )
    op.create_index(
        "ix_skill_scores_user_measured", "skill_scores", ["user_id", "measured_at"]
    )

    op.create_table(
        "questions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("skill_area", sa.String(32), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("answer", sa.String(256), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column(
            "data_origin", sa.String(16), nullable=False, server_default="synthetic"
        ),
        sa.CheckConstraint("level BETWEEN 1 AND 4", name="ck_questions_level"),
        sa.CheckConstraint(
            "difficulty BETWEEN 1 AND 5", name="ck_questions_difficulty"
        ),
        sa.CheckConstraint(
            "skill_area IN ('basics','reading_stock','judging_info','risk')",
            name="ck_questions_skill_area",
        ),
        sa.CheckConstraint(
            "data_origin IN ('real','synthetic')", name="ck_questions_origin"
        ),
    )
    op.create_index(
        "ix_questions_level_skill_diff",
        "questions",
        ["level", "skill_area", "difficulty"],
    )

    op.create_table(
        "attempts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("item_type", sa.String(32), nullable=False),
        sa.Column("item_id", sa.String(64), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("correct", sa.Boolean(), nullable=False),
        sa.Column("context", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "item_type IN ('question','scenario','verifier_guess')",
            name="ck_attempts_item_type",
        ),
        sa.CheckConstraint(
            "confidence BETWEEN 50 AND 100", name="ck_attempts_confidence"
        ),
        sa.CheckConstraint(
            "context IN ('onboarding','lesson','assessment','practice','study_pre','study_post')",
            name="ck_attempts_context",
        ),
    )
    op.create_index(
        "ix_attempts_user_context", "attempts", ["user_id", "context", "created_at"]
    )
    op.create_index(
        "ix_attempts_user_item", "attempts", ["user_id", "item_type", "item_id"]
    )

    op.create_table(
        "lessons",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("skill_area", sa.String(32), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("sections", sa.JSON(), nullable=False),
        sa.Column("check_questions", sa.JSON(), nullable=False),
        sa.Column(
            "data_origin", sa.String(16), nullable=False, server_default="synthetic"
        ),
        sa.CheckConstraint("level BETWEEN 1 AND 4", name="ck_lessons_level"),
        sa.CheckConstraint(
            "skill_area IN ('basics','reading_stock','judging_info','risk')",
            name="ck_lessons_skill_area",
        ),
        sa.CheckConstraint("minutes BETWEEN 1 AND 60", name="ck_lessons_minutes"),
        sa.CheckConstraint(
            "data_origin IN ('real','synthetic')", name="ck_lessons_origin"
        ),
    )

    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("lesson_ids", sa.JSON(), nullable=False),
        sa.Column("progress", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", name="uq_plans_user_id"),
        sa.CheckConstraint("level BETWEEN 1 AND 4", name="ck_plans_level"),
    )

    op.create_table(
        "scenarios",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("outcome", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("key_clues", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("data_origin", sa.String(16), nullable=False),
        sa.CheckConstraint(
            "difficulty BETWEEN 1 AND 5", name="ck_scenarios_difficulty"
        ),
        sa.CheckConstraint("window_days > 0", name="ck_scenarios_window_days"),
        sa.CheckConstraint(
            "data_origin IN ('real','synthetic')", name="ck_scenarios_origin"
        ),
    )
    op.create_index("ix_scenarios_difficulty", "scenarios", ["difficulty"])

    op.create_table(
        "edu_sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_type", sa.String(32), nullable=False),
        sa.Column("target_level", sa.Integer(), nullable=True),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column(
            "completed", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )

    op.create_table(
        "edu_explain_cache",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("chart", sa.JSON(), nullable=False),
        sa.Column("moves", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("data_origin", sa.String(16), nullable=False),
        sa.UniqueConstraint("symbol", "year", name="uq_explain_symbol_year"),
        sa.CheckConstraint(
            "data_origin IN ('real','synthetic')", name="ck_explain_origin"
        ),
    )


def downgrade() -> None:
    """Reverts Education tables cleanly."""
    for table in [
        "edu_explain_cache",
        "edu_sessions",
        "scenarios",
        "plans",
        "lessons",
        "attempts",
        "questions",
        "skill_scores",
        "unlocks",
    ]:
        op.drop_table(table)
