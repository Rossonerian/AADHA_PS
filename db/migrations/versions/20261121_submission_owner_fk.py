"""Reconcile Verifier owners with platform users; reject orphaned ownership."""

from alembic import op

revision = "20261121_submission_owner_fk"
down_revision = "20261121_nasdaq_challenges"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Deliberately do not invent users or delete submissions to hide orphaned rows.
    # Existing owners must be reconciled before this migration can succeed.
    with op.batch_alter_table("submissions") as batch:
        batch.create_foreign_key(
            "fk_submissions_user_id_users", "users", ["user_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("submissions") as batch:
        batch.drop_constraint("fk_submissions_user_id_users", type_="foreignkey")
