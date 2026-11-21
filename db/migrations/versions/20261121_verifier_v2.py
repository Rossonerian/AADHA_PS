"""Private tip quality, timestamped transcripts and display-only provider facts."""

import sqlalchemy as sa
from alembic import op

revision = "20261121_verifier_v2"
down_revision = "20261121_user_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Name the legacy anonymous uniqueness constraint consistently on SQLite.
    naming = {"uq": "uq_%(table_name)s_%(column_0_name)s"}
    constraints = sa.inspect(op.get_bind()).get_unique_constraints("claims")
    legacy = next(c for c in constraints if c["column_names"] == ["submission_id"])
    with op.batch_alter_table("claims", naming_convention=naming) as batch:
        batch.drop_constraint(
            legacy["name"] or "uq_claims_submission_id", type_="unique"
        )
        batch.add_column(sa.Column("tip_quality", sa.JSON()))
        batch.add_column(sa.Column("tip_quality_version", sa.String(64)))
    with op.batch_alter_table("submissions") as batch:
        batch.add_column(sa.Column("transcript_segments", sa.JSON()))
    with op.batch_alter_table("sources") as batch:
        batch.add_column(sa.Column("enforcement_flag", sa.Boolean()))
        batch.add_column(sa.Column("enforcement_refs", sa.JSON()))
    with op.batch_alter_table("source_rating_history") as batch:
        batch.add_column(sa.Column("formula_version", sa.String(64)))
    op.create_table(
        "source_mentions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_id", sa.Uuid(), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("title", sa.String(1000), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_origin", sa.String(9), nullable=False),
        sa.UniqueConstraint("source_id", "url", name="uq_source_mentions_url"),
        sa.CheckConstraint(
            "data_origin IN ('real', 'synthetic')", name="ck_source_mentions_origin"
        ),
    )
    op.create_index("ix_source_mentions_source_id", "source_mentions", ["source_id"])


def downgrade() -> None:
    # Never silently discard extra claims to restore the old uniqueness rule.
    duplicate = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT submission_id FROM claims GROUP BY submission_id HAVING count(*) > 1 LIMIT 1"
            )
        )
        .first()
    )
    if duplicate:
        raise RuntimeError(
            "Reconcile multi-claim submissions before downgrading Verifier v2"
        )
    op.drop_table("source_mentions")
    # Native DROP COLUMN avoids rebuilding referenced parent tables on SQLite
    # (Python 3.11 SQLite >=3.35). Never disable foreign-key enforcement.
    op.drop_column("source_rating_history", "formula_version")
    op.drop_column("sources", "enforcement_refs")
    op.drop_column("sources", "enforcement_flag")
    op.drop_column("submissions", "transcript_segments")
    with op.batch_alter_table("claims") as batch:
        batch.drop_column("tip_quality_version")
        batch.drop_column("tip_quality")
        batch.create_unique_constraint("uq_claims_submission_id", ["submission_id"])
