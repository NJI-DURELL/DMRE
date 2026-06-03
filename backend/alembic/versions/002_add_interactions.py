"""Add click_count and scroll_depth to memories table.

Revision ID: 002_add_interactions
Revises: 001_initial_schema
Create Date: 2026-04-24
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "002_add_interactions"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("memories", sa.Column("click_count",  sa.Integer(), nullable=False, server_default="0"))
    op.add_column("memories", sa.Column("scroll_depth", sa.Float(),   nullable=False, server_default="0.0"))


def downgrade() -> None:
    op.drop_column("memories", "scroll_depth")
    op.drop_column("memories", "click_count")
