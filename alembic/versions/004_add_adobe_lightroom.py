"""Add Adobe Lightroom integration tables and columns.

Revision ID: 004
Revises: 003
Create Date: 2026-03-15

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- adobe_tokens table ---
    op.create_table(
        "adobe_tokens",
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lightroom_catalog_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- lightroom_pending_tasks table ---
    op.create_table(
        "lightroom_pending_tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_type", sa.String(20), nullable=False),  # sync | flag
        sa.Column("payload", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_retries", sa.Integer(), server_default="3", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pending_tasks_user_status", "lightroom_pending_tasks", ["user_id", "status"])

    # --- photos: add lightroom columns ---
    op.add_column("photos", sa.Column("lightroom_asset_id", sa.Text(), nullable=True))
    op.add_column(
        "photos",
        sa.Column("lightroom_sync_status", sa.String(20), nullable=True),
    )

    # --- shoot_sessions: add adobe / AI columns ---
    op.add_column(
        "shoot_sessions",
        sa.Column("ai_processing_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column(
        "shoot_sessions",
        sa.Column("lightroom_sync", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("shoot_sessions", sa.Column("lightroom_target_album_id", sa.Text(), nullable=True))
    op.add_column("shoot_sessions", sa.Column("lightroom_target_album_name", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("shoot_sessions", "lightroom_target_album_name")
    op.drop_column("shoot_sessions", "lightroom_target_album_id")
    op.drop_column("shoot_sessions", "lightroom_sync")
    op.drop_column("shoot_sessions", "ai_processing_enabled")
    op.drop_column("photos", "lightroom_sync_status")
    op.drop_column("photos", "lightroom_asset_id")
    op.drop_index("ix_pending_tasks_user_status", table_name="lightroom_pending_tasks")
    op.drop_table("lightroom_pending_tasks")
    op.drop_table("adobe_tokens")
