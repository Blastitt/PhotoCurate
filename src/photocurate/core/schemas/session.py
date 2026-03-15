"""Pydantic schemas for shoot sessions and photos."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


# --- Session Schemas ---

class SessionCreate(BaseModel):
    title: str
    description: str | None = None
    shoot_date: date | None = None
    client_id: UUID | None = None
    auto_pick_count: int = Field(default=50, ge=1, le=500)


class SessionUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    shoot_date: date | None = None
    client_id: UUID | None = None
    auto_pick_count: int | None = Field(default=None, ge=1, le=500)
    status: str | None = None


class ProcessingConfigUpdate(BaseModel):
    wb_mode: str | None = Field(default=None, pattern="^(auto|manual|off)$")
    wb_temp_shift: float | None = Field(default=None, ge=-500, le=500)
    wb_tint_shift: float | None = Field(default=None, ge=-1.0, le=1.0)
    wb_strength: float | None = Field(default=None, ge=0.0, le=1.0)


class SessionResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    photographer_id: UUID
    client_id: UUID | None
    title: str
    description: str | None
    shoot_date: date | None
    status: str
    auto_pick_count: int
    wb_mode: str
    wb_temp_shift: float
    wb_tint_shift: float
    wb_strength: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Photo Schemas ---

class PhotoResponse(BaseModel):
    id: UUID
    session_id: UUID
    filename: str
    file_size_bytes: int | None
    width: int | None
    height: int | None
    mime_type: str | None
    status: str
    created_at: datetime
    ai_score: AIScoreResponse | None = None
    thumbnail_url: str | None = None
    preview_url: str | None = None
    face_center_x: float | None = None
    face_center_y: float | None = None

    model_config = {"from_attributes": True}


class PhotoUpdate(BaseModel):
    status: str | None = None


class AIScoreResponse(BaseModel):
    sharpness: float | None
    exposure: float | None
    composition: float | None
    aesthetic: float | None
    face_quality: float | None
    uniqueness: float | None
    composite_score: float
    auto_picked: bool
    scored_at: datetime

    model_config = {"from_attributes": True}


# Resolve forward reference
PhotoResponse.model_rebuild()


# --- Upload Schemas ---

class UploadURLRequest(BaseModel):
    filenames: list[str] = Field(..., min_length=1, max_length=100)


class PresignedURL(BaseModel):
    filename: str
    upload_url: str
    key: str


class UploadURLResponse(BaseModel):
    urls: list[PresignedURL]


# --- Client Schemas ---

class ClientCreate(BaseModel):
    name: str
    email: str | None = None


class ClientResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    email: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
