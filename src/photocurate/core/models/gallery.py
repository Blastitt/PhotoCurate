"""Gallery, Selection, EditedPhoto, Delivery models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from photocurate.core.models.base import Base, UUIDPrimaryKeyMixin


class Gallery(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "galleries"

    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shoot_sessions.id"), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    pin_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_selections: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped["ShootSession"] = relationship("ShootSession", back_populates="galleries")  # noqa: F821
    gallery_photos: Mapped[list[GalleryPhoto]] = relationship(
        "GalleryPhoto", back_populates="gallery", cascade="all, delete-orphan"
    )
    selections: Mapped[list[Selection]] = relationship("Selection", back_populates="gallery")


class GalleryPhoto(Base):
    __tablename__ = "gallery_photos"

    gallery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("galleries.id", ondelete="CASCADE"), primary_key=True
    )
    photo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("photos.id"), primary_key=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    gallery: Mapped[Gallery] = relationship("Gallery", back_populates="gallery_photos")
    photo: Mapped["Photo"] = relationship("Photo")  # noqa: F821


class Selection(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "selections"

    gallery_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("galleries.id"), nullable=False)
    client_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    gallery: Mapped[Gallery] = relationship("Gallery", back_populates="selections")
    selection_photos: Mapped[list[SelectionPhoto]] = relationship(
        "SelectionPhoto", back_populates="selection", cascade="all, delete-orphan"
    )


class SelectionPhoto(Base):
    __tablename__ = "selection_photos"

    selection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("selections.id", ondelete="CASCADE"), primary_key=True
    )
    photo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("photos.id"), primary_key=True
    )

    selection: Mapped[Selection] = relationship("Selection", back_populates="selection_photos")


class EditedPhoto(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "edited_photos"

    original_photo_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("photos.id"), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shoot_sessions.id"), nullable=False)
    edited_key: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Delivery(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "deliveries"

    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shoot_sessions.id"), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # google_drive, dropbox, onedrive
    provider_folder_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    photo_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
