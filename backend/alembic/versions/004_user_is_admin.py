"""Add users.is_admin flag for admin-only operational endpoints.

Revision ID: 004_user_is_admin
Revises: 003_user_scoped_memories
Create Date: 2026-05-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_user_is_admin"
down_revision: Union[str, None] = "003_user_scoped_memories"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "is_admin")
