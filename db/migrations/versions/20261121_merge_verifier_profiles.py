"""Join independently merged Verifier v2 and profile migration branches.

No schema or data operations: restore a single target for `upgrade head`.
"""

revision = "20261121_merge_verifier_profiles"
down_revision = ("20261121_verifier_v2", "20261121_user_profiles")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
