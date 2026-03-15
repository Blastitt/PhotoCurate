"""Initial schema — all tables.

Revision ID: 001
Revises: 
Create Date: 2026-03-14

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Tenants ---
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.String(255), unique=True, nullable=False),
        sa.Column("plan", sa.String(50), server_default="free"),
        sa.Column("storage_quota_bytes", sa.BigInteger(), server_default="10737418240"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- Tenant Branding ---
    op.create_table(
        "tenant_branding",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), primary_key=True),
        sa.Column("watermark_logo_key", sa.Text(), nullable=True),
        sa.Column("watermark_opacity", sa.Float(), server_default="0.3"),
        sa.Column("watermark_position", sa.String(50), server_default="'bottom-right'"),
        sa.Column("watermark_scale", sa.Float(), server_default="0.15"),
        sa.Column("watermark_padding", sa.Float(), server_default="0.02"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- Users ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("email", sa.String(320), unique=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(50), server_default="'photographer'"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- Clients ---
    op.create_table(
        "clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- Shoot Sessions ---
    op.create_table(
        "shoot_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("photographer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("shoot_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(50), server_default="'created'"),
        sa.Column("auto_pick_count", sa.Integer(), server_default="50"),
        sa.Column("wb_mode", sa.String(20), server_default="'auto'"),
        sa.Column("wb_temp_shift", sa.Float(), server_default="0.0"),
        sa.Column("wb_tint_shift", sa.Float(), server_default="0.0"),
        sa.Column("wb_strength", sa.Float(), server_default="0.7"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- Photos ---
    op.create_table(
        "photos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shoot_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("original_key", sa.Text(), nullable=False),
        sa.Column("thumbnail_key", sa.Text(), nullable=True),
        sa.Column("preview_key", sa.Text(), nullable=True),
        sa.Column("watermarked_key", sa.Text(), nullable=True),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("exif_data", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(50), server_default="'uploaded'"),
        sa.Column("perceptual_hash", sa.String(255), nullable=True),
        sa.Column("duplicate_group_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- AI Scores ---
    op.create_table(
        "ai_scores",
        sa.Column("photo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("photos.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("sharpness", sa.Float(), nullable=True),
        sa.Column("exposure", sa.Float(), nullable=True),
        sa.Column("composition", sa.Float(), nullable=True),
        sa.Column("aesthetic", sa.Float(), nullable=True),
        sa.Column("face_quality", sa.Float(), nullable=True),
        sa.Column("uniqueness", sa.Float(), nullable=True),
        sa.Column("composite_score", sa.Float(), nullable=False),
        sa.Column("auto_picked", sa.Boolean(), server_default="false"),
        sa.Column("scored_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- Galleries ---
    op.create_table(
        "galleries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shoot_sessions.id"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("slug", sa.String(255), unique=True, nullable=False),
        sa.Column("pin_hash", sa.Text(), nullable=True),
        sa.Column("max_selections", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(50), server_default="'active'"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- Gallery Photos ---
    op.create_table(
        "gallery_photos",
        sa.Column("gallery_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("galleries.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("photo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("photos.id"), primary_key=True),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
    )

    # --- Selections ---
    op.create_table(
        "selections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("gallery_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("galleries.id"), nullable=False),
        sa.Column("client_name", sa.Text(), nullable=True),
        sa.Column("client_email", sa.String(320), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- Selection Photos ---
    op.create_table(
        "selection_photos",
        sa.Column("selection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("selections.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("photo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("photos.id"), primary_key=True),
    )

    # --- Edited Photos ---
    op.create_table(
        "edited_photos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("original_photo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("photos.id"), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shoot_sessions.id"), nullable=False),
        sa.Column("edited_key", sa.Text(), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- Deliveries ---
    op.create_table(
        "deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shoot_sessions.id"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_folder_url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(50), server_default="'pending'"),
        sa.Column("photo_count", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- Indexes ---
    op.create_index("ix_photos_session_id", "photos", ["session_id"])
    op.create_index("ix_photos_tenant_id", "photos", ["tenant_id"])
    op.create_index("ix_shoot_sessions_tenant_id", "shoot_sessions", ["tenant_id"])
    op.create_index("ix_galleries_slug", "galleries", ["slug"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_table("deliveries")
    op.drop_table("edited_photos")
    op.drop_table("selection_photos")
    op.drop_table("selections")
    op.drop_table("gallery_photos")
    op.drop_table("galleries")
    op.drop_table("ai_scores")
    op.drop_table("photos")
    op.drop_table("shoot_sessions")
    op.drop_table("clients")
    op.drop_table("users")
    op.drop_table("tenant_branding")
    op.drop_table("tenants")
