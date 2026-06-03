"""Make memories.user_id NOT NULL and switch FK to ON DELETE CASCADE.

Anonymous (user_id NULL) rows from the pre-multi-tenant prototype are deleted
because they cannot be safely reassigned to any specific user.

Revision ID: 003_user_scoped_memories
Revises: 002_add_interactions
Create Date: 2026-05-08
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_user_scoped_memories"
down_revision: Union[str, None] = "002_add_interactions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Postgres auto-names FKs as "<table>_<column>_fkey" when no name is given.
_FK_NAME = "memories_user_id_fkey"


def upgrade() -> None:
    # 1. Drop anonymous data — cascades to embedding_references + blockchain_records.
    op.execute("DELETE FROM memories WHERE user_id IS NULL")

    # 2. Replace the SET NULL FK with a CASCADE FK.
    op.drop_constraint(_FK_NAME, "memories", type_="foreignkey")
    op.alter_column(
        "memories",
        "user_id",
        existing_type=sa.String(length=32),
        nullable=False,
    )
    op.create_foreign_key(
        _FK_NAME,
        source_table="memories",
        referent_table="users",
        local_cols=["user_id"],
        remote_cols=["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(_FK_NAME, "memories", type_="foreignkey")
    op.alter_column(
        "memories",
        "user_id",
        existing_type=sa.String(length=32),
        nullable=True,
    )
    op.create_foreign_key(
        _FK_NAME,
        source_table="memories",
        referent_table="users",
        local_cols=["user_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )
