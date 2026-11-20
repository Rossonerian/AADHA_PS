"""Add the four Verifier-owned tables to the platform Alembic history.

Joins `0001_initial_platform` as a single linear head; adding a foreign key from
`submissions.user_id` to `users.id` can follow in a platform reconciliation revision
once existing owner UUID handling is aligned.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261120_verifier"
down_revision: str | Sequence[str] | None = "0001_initial_platform"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("handle", sa.String(255), nullable=False),
        sa.Column("sebi_reg_no", sa.String(32)),
        sa.Column("sebi_registered", sa.Boolean()),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(24), nullable=False),
        sa.Column("scored_claims", sa.Integer(), nullable=False),
        sa.Column("data_origin", sa.String(9), nullable=False),
        sa.UniqueConstraint(
            "platform", "handle", "data_origin", name="uq_sources_identity"
        ),
        sa.CheckConstraint("score BETWEEN 0 AND 100", name="ck_sources_score"),
        sa.CheckConstraint("scored_claims >= 0", name="ck_sources_scored_claims"),
        sa.CheckConstraint(
            "data_origin IN ('real', 'synthetic')", name="ck_sources_origin"
        ),
        sa.CheckConstraint(
            "label IN ('reliable', 'semi_reliable', 'not_reliable', 'not_enough_history')",
            name="ck_sources_label",
        ),
    )
    op.create_table(
        "submissions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("post_url", sa.String(2048)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("user_guess", sa.String(24)),
        sa.Column("user_confidence", sa.Integer()),
        sa.Column("red_flags", sa.JSON(), nullable=False),
        sa.Column("data_origin", sa.String(9), nullable=False),
        sa.UniqueConstraint(
            "user_id", "content_hash", name="uq_submissions_user_content"
        ),
        sa.CheckConstraint(
            "data_origin IN ('real', 'synthetic')", name="ck_submissions_origin"
        ),
        sa.CheckConstraint(
            "user_confidence BETWEEN 50 AND 100", name="ck_submissions_confidence"
        ),
    )
    op.create_index(
        "ix_submissions_user_capture", "submissions", ["user_id", "captured_at"]
    )
    op.create_index("ix_submissions_source", "submissions", ["source_id"])
    op.create_table(
        "claims",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "submission_id",
            sa.Uuid(),
            sa.ForeignKey("submissions.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column("symbol", sa.String(32)),
        sa.Column("rating_eligible", sa.Boolean(), nullable=False),
        sa.Column("direction", sa.String(4)),
        sa.Column("entry", sa.Float()),
        sa.Column("target", sa.Float()),
        sa.Column("stop", sa.Float()),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("window_end", sa.Date()),
        sa.Column("scorable", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("outcome", sa.JSON()),
        sa.Column("data_origin", sa.String(9), nullable=False),
        sa.CheckConstraint(
            "data_origin IN ('real', 'synthetic')", name="ck_claims_origin"
        ),
        sa.CheckConstraint("direction IN ('up', 'down')", name="ck_claims_direction"),
        sa.CheckConstraint(
            "window_days BETWEEN 1 AND 252", name="ck_claims_window_days"
        ),
        sa.CheckConstraint(
            "status IN ('open', 'scored', 'needs_review', 'unscorable')",
            name="ck_claims_status",
        ),
    )
    op.create_index("ix_claims_status_id", "claims", ["status", "id"])
    op.create_table(
        "source_rating_history",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_id", sa.Uuid(), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(24), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_origin", sa.String(9), nullable=False),
        sa.CheckConstraint(
            "score BETWEEN 0 AND 100", name="ck_source_rating_history_score"
        ),
        sa.CheckConstraint(
            "data_origin IN ('real', 'synthetic')",
            name="ck_source_rating_history_origin",
        ),
        sa.CheckConstraint(
            "label IN ('reliable', 'semi_reliable', 'not_reliable', 'not_enough_history')",
            name="ck_source_rating_history_label",
        ),
    )
    op.create_index(
        "ix_source_rating_history_source_time",
        "source_rating_history",
        ["source_id", "changed_at"],
    )


def downgrade() -> None:
    op.drop_table("source_rating_history")
    op.drop_table("claims")
    op.drop_table("submissions")
    op.drop_table("sources")
