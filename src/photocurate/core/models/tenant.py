"""Tenant and User models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from photocurate.core.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(50), default="free")
    storage_quota_bytes: Mapped[int] = mapped_column(BigInteger, default=10_737_418_240)  # 10GB

    # Relationships
    branding: Mapped[TenantBranding | None] = relationship("TenantBranding", back_populates="tenant", uselist=False)
    users: Mapped[list[User]] = relationship("User", back_populates="tenant")
    clients: Mapped[list[Client]] = relationship("Client", back_populates="tenant")


class TenantBranding(Base):
    __tablename__ = "tenant_branding"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True
    )
    watermark_logo_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    watermark_opacity: Mapped[float] = mapped_column(Float, default=0.3)
    watermark_position: Mapped[str] = mapped_column(String(50), default="bottom-right")
    watermark_scale: Mapped[float] = mapped_column(Float, default=0.15)
    watermark_padding: Mapped[float] = mapped_column(Float, default=0.02)
    watermark_tile_rotation: Mapped[float] = mapped_column(Float, default=45.0)
    watermark_tile_spacing: Mapped[float] = mapped_column(Float, default=0.5)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="branding")


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="photographer")

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="users")


class Client(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "clients"

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="clients")
