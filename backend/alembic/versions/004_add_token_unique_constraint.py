"""add unique constraint on tokens(user_id, platform)

Revision ID: 004
Revises: 003
Create Date: 2026-02-26

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_tokens_user_platform", "tokens", ["user_id", "platform"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_tokens_user_platform", "tokens", type_="unique")
