"""Shoot session and photo management routes."""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from photocurate.api.deps import BlobStoreDep, CurrentUser, DbSession, QueueDep
from photocurate.core.models.session import Photo, ShootSession
from photocurate.core.schemas.session import (
    PhotoResponse,
    PhotoUpdate,
    PresignedURL,
    ProcessingConfigUpdate,
    SessionCreate,
    SessionResponse,
    SessionUpdate,
    UploadURLRequest,
    UploadURLResponse,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


# ─── Session CRUD ────────────────────────────────────────────────────

@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(body: SessionCreate, db: DbSession, user: CurrentUser):
    """Create a new shoot session."""
    session = ShootSession(
        tenant_id=user.tenant_id,
        photographer_id=user.id,
        client_id=body.client_id,
        title=body.title,
        description=body.description,
        shoot_date=body.shoot_date,
        auto_pick_count=body.auto_pick_count,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


@router.get("", response_model=list[SessionResponse])
async def list_sessions(db: DbSession, user: CurrentUser):
    """List all shoot sessions for the current tenant."""
    result = await db.execute(
        select(ShootSession)
        .where(ShootSession.tenant_id == user.tenant_id)
        .order_by(ShootSession.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: uuid.UUID, db: DbSession, user: CurrentUser):
    """Get a single shoot session."""
    session = await _get_session_or_404(session_id, user.tenant_id, db)
    return session


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(session_id: uuid.UUID, body: SessionUpdate, db: DbSession, user: CurrentUser):
    """Update a shoot session."""
    session = await _get_session_or_404(session_id, user.tenant_id, db)
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(session, field, value)
    await db.flush()
    await db.refresh(session)
    return session


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: uuid.UUID, db: DbSession, user: CurrentUser):
    """Delete a shoot session and all associated photos."""
    session = await _get_session_or_404(session_id, user.tenant_id, db)
    await db.delete(session)


# ─── Upload URLs ─────────────────────────────────────────────────────

@router.post("/{session_id}/upload-urls", response_model=UploadURLResponse)
async def get_upload_urls(
    session_id: uuid.UUID,
    body: UploadURLRequest,
    db: DbSession,
    user: CurrentUser,
    blob_store: BlobStoreDep,
):
    """Generate presigned upload URLs for batch photo upload."""
    session = await _get_session_or_404(session_id, user.tenant_id, db)

    urls: list[PresignedURL] = []
    for filename in body.filenames:
        key = f"tenants/{user.tenant_id}/sessions/{session_id}/originals/{uuid.uuid4()}_{filename}"
        upload_url = await blob_store.generate_presigned_upload_url(key)
        urls.append(PresignedURL(filename=filename, upload_url=upload_url, key=key))

        # Create photo record in DB
        photo = Photo(
            session_id=session.id,
            tenant_id=user.tenant_id,
            original_key=key,
            filename=filename,
            status="uploaded",
        )
        db.add(photo)

    # Update session status
    if session.status == "created":
        session.status = "uploading"

    await db.flush()
    return UploadURLResponse(urls=urls)


# ─── Finalize (trigger AI processing) ───────────────────────────────

@router.post("/{session_id}/finalize", status_code=status.HTTP_202_ACCEPTED)
async def finalize_session(
    session_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    queue: QueueDep,
):
    """Finalize upload and trigger AI processing for all photos in the session."""
    session = await _get_session_or_404(session_id, user.tenant_id, db)

    if session.status not in ("uploading", "created"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session is in '{session.status}' state, cannot finalize",
        )

    session.status = "processing"
    await db.flush()

    # Publish processing event
    event = {
        "type": "session.process",
        "session_id": str(session_id),
        "tenant_id": str(user.tenant_id),
    }
    await queue.publish("photo.processing", json.dumps(event).encode())

    return {"detail": "Processing started", "session_id": str(session_id)}


# ─── Photos ──────────────────────────────────────────────────────────

@router.get("/{session_id}/photos", response_model=list[PhotoResponse])
async def list_photos(session_id: uuid.UUID, db: DbSession, user: CurrentUser, blob_store: BlobStoreDep):
    """List all photos in a session with their AI scores."""
    await _get_session_or_404(session_id, user.tenant_id, db)
    result = await db.execute(
        select(Photo)
        .where(Photo.session_id == session_id, Photo.tenant_id == user.tenant_id)
        .options(selectinload(Photo.ai_score))
        .order_by(Photo.created_at)
    )
    photos = result.scalars().all()
    responses = []
    for photo in photos:
        data = PhotoResponse.model_validate(photo)
        if photo.thumbnail_key:
            data.thumbnail_url = await blob_store.generate_presigned_download_url(photo.thumbnail_key)
        if photo.watermarked_key:
            data.preview_url = await blob_store.generate_presigned_download_url(photo.watermarked_key)
        elif photo.preview_key:
            data.preview_url = await blob_store.generate_presigned_download_url(photo.preview_key)
        responses.append(data)
    return responses


@router.patch("/photos/{photo_id}", response_model=PhotoResponse)
async def update_photo(photo_id: uuid.UUID, body: PhotoUpdate, db: DbSession, user: CurrentUser):
    """Update a photo's metadata or status."""
    result = await db.execute(
        select(Photo)
        .where(Photo.id == photo_id, Photo.tenant_id == user.tenant_id)
        .options(selectinload(Photo.ai_score))
    )
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(photo, field, value)
    await db.flush()
    await db.refresh(photo)
    return photo


# ─── Processing Config (White Balance) ───────────────────────────────

@router.patch("/{session_id}/processing-config", response_model=SessionResponse)
async def update_processing_config(
    session_id: uuid.UUID,
    body: ProcessingConfigUpdate,
    db: DbSession,
    user: CurrentUser,
    queue: QueueDep,
):
    """Update white balance / processing settings and retrigger preview generation."""
    session = await _get_session_or_404(session_id, user.tenant_id, db)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(session, field, value)
    await db.flush()
    await db.refresh(session)

    # Trigger re-processing of previews
    event = {
        "type": "session.reprocess_previews",
        "session_id": str(session_id),
        "tenant_id": str(user.tenant_id),
    }
    await queue.publish("photo.processing", json.dumps(event).encode())

    return session


# ─── Helpers ─────────────────────────────────────────────────────────

async def _get_session_or_404(
    session_id: uuid.UUID, tenant_id: uuid.UUID, db
) -> ShootSession:
    """Fetch a session scoped to tenant, or raise 404."""
    result = await db.execute(
        select(ShootSession).where(
            ShootSession.id == session_id,
            ShootSession.tenant_id == tenant_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session
