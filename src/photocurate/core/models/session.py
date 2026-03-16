"""ShootSession, Photo, AIScore models."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from photocurate.core.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ShootSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "shoot_sessions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    photographer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    shoot_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="created")
    auto_pick_count: Mapped[int] = mapped_column(Integer, default=50)

    # White balance settings
    wb_mode: Mapped[str] = mapped_column(String(20), default="auto")
    wb_temp_shift: Mapped[float] = mapped_column(Float, default=0.0)
    wb_tint_shift: Mapped[float] = mapped_column(Float, default=0.0)
    wb_strength: Mapped[float] = mapped_column(Float, default=0.7)

    # AI processing
    ai_processing_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Adobe Lightroom sync
    lightroom_sync: Mapped[bool] = mapped_column(Boolean, default=False)
    lightroom_target_album_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    lightroom_target_album_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    photos: Mapped[list[Photo]] = relationship("Photo", back_populates="session", cascade="all, delete-orphan")
    galleries: Mapped[list] = relationship("Gallery", back_populates="session")


class Photo(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "photos"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shoot_sessions.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    original_key: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    preview_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    watermarked_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    exif_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="uploaded")
    face_center_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    face_center_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    perceptual_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    duplicate_group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Adobe Lightroom
    lightroom_asset_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    lightroom_sync_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    session: Mapped[ShootSession] = relationship("ShootSession", back_populates="photos")
    ai_score: Mapped[AIScore | None] = relationship("AIScore", back_populates="photo", uselist=False)


class AIScore(Base):
    __tablename__ = "ai_scores"

    photo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("photos.id", ondelete="CASCADE"), primary_key=True
    )
    sharpness: Mapped[float | None] = mapped_column(Float, nullable=True)
    exposure: Mapped[float | None] = mapped_column(Float, nullable=True)
    composition: Mapped[float | None] = mapped_column(Float, nullable=True)
    aesthetic: Mapped[float | None] = mapped_column(Float, nullable=True)
    face_quality: Mapped[float | None] = mapped_column(Float, nullable=True)
    uniqueness: Mapped[float | None] = mapped_column(Float, nullable=True)
    composite_score: Mapped[float] = mapped_column(Float, nullable=False)
    auto_picked: Mapped[bool] = mapped_column(Boolean, default=False)
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    photo: Mapped[Photo] = relationship("Photo", back_populates="ai_score")
