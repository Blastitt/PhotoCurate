"""Pydantic schemas for galleries, selections, and deliveries."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# --- Gallery Schemas ---

class GalleryCreate(BaseModel):
    pin: str | None = Field(default=None, min_length=4, max_length=6, pattern="^[0-9]+$")
    max_selections: int | None = Field(default=None, ge=1)
    photo_ids: list[UUID] | None = None  # if None, include all auto-picked photos


class GalleryResponse(BaseModel):
    id: UUID
    session_id: UUID
    slug: str
    max_selections: int | None
    expires_at: datetime | None
    status: str
    created_at: datetime
    gallery_url: str | None = None

    model_config = {"from_attributes": True}


# --- Public Gallery Schemas ---

class GalleryPublicResponse(BaseModel):
    slug: str
    max_selections: int | None
    status: str
    photos: list[GalleryPhotoPublic]


class GalleryPhotoPublic(BaseModel):
    id: UUID
    thumbnail_url: str | None
    preview_url: str | None
    face_center_x: float | None = None
    face_center_y: float | None = None
    sort_order: int


# Resolve forward reference
GalleryPublicResponse.model_rebuild()


class PinVerifyRequest(BaseModel):
    pin: str


class PinVerifyResponse(BaseModel):
    valid: bool
    token: str | None = None  # short-lived token for gallery access


# --- Selection Schemas ---

class SelectionCreate(BaseModel):
    photo_ids: list[UUID] = Field(..., min_length=1)
    client_name: str | None = None
    client_email: str | None = None
    notes: str | None = None


class SelectionResponse(BaseModel):
    id: UUID
    gallery_id: UUID
    client_name: str | None
    client_email: str | None
    notes: str | None
    submitted_at: datetime
    photo_count: int = 0

    model_config = {"from_attributes": True}


class SelectionDetailResponse(BaseModel):
    id: UUID
    gallery_id: UUID
    client_name: str | None
    client_email: str | None
    notes: str | None
    submitted_at: datetime
    photo_ids: list[UUID]

    model_config = {"from_attributes": True}


# --- Delivery Schemas ---

class DeliveryCreate(BaseModel):
    provider: str = Field(..., pattern="^(google_drive|dropbox|onedrive)$")
    access_token: str | None = Field(default=None, description="OAuth2 access token for the target provider")


class DeliveryResponse(BaseModel):
    id: UUID
    session_id: UUID
    provider: str
    provider_folder_url: str | None
    status: str
    photo_count: int | None
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Branding Schemas ---

class BrandingResponse(BaseModel):
    watermark_logo_key: str | None
    watermark_logo_url: str | None = None
    watermark_opacity: float
    watermark_position: str
    watermark_scale: float
    watermark_padding: float
    watermark_tile_rotation: float
    watermark_tile_spacing: float

    model_config = {"from_attributes": True}


class BrandingUpdate(BaseModel):
    watermark_opacity: float | None = Field(default=None, ge=0.0, le=1.0)
    watermark_position: str | None = Field(default=None, pattern="^(center|bottom-right|bottom-left|tiled)$")
    watermark_scale: float | None = Field(default=None, ge=0.01, le=0.5)
    watermark_padding: float | None = Field(default=None, ge=0.0, le=0.2)
    watermark_tile_rotation: float | None = Field(default=None, ge=0.0, le=360.0)
    watermark_tile_spacing: float | None = Field(default=None, ge=0.1, le=2.0)
