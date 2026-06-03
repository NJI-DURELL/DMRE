"""Add email_verified + OTP columns to users for the OTP signup flow.

Revision ID: 005_email_verification
Revises: 004_user_is_admin
Create Date: 2026-05-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_email_verification"
down_revision: Union[str, None] = "004_user_is_admin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.add_column("users", sa.Column("email_otp_hash", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("email_otp_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "users",
        sa.Column("email_otp_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("users", sa.Column("email_otp_last_sent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "email_otp_last_sent_at")
    op.drop_column("users", "email_otp_attempts")
    op.drop_column("users", "email_otp_expires_at")
    op.drop_column("users", "email_otp_hash")
    op.drop_column("users", "email_verified")
