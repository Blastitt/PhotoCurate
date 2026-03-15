"""Public gallery routes — accessible via shareable link + optional PIN."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, status
from jose import jwt
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from photocurate.api.auth import verify_pin
from photocurate.api.deps import BlobStoreDep, DbSession
from photocurate.config import settings
from photocurate.core.models.gallery import Gallery, GalleryPhoto, Selection, SelectionPhoto
from photocurate.core.models.session import Photo, ShootSession
from photocurate.core.schemas.gallery import (
    GalleryPhotoPublic,
    GalleryPublicResponse,
    PinVerifyRequest,
    PinVerifyResponse,
    SelectionCreate,
    SelectionResponse,
)

router = APIRouter(prefix="/gallery", tags=["public-gallery"])


# ─── Gallery Access ──────────────────────────────────────────────────

@router.get("/{slug}", response_model=GalleryPublicResponse)
async def get_gallery(
    slug: str,
    db: DbSession,
    blob_store: BlobStoreDep,
    token: str | None = Query(default=None),
):
    """Load gallery metadata and photo list by slug."""
    gallery = await _get_gallery_by_slug(slug, db)

    # Check expiration
    if gallery.expires_at and gallery.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Gallery has expired")

    # If PIN-protected, verify gallery access token
    if gallery.pin_hash:
        if not token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="PIN required",
            )
        try:
            payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
            if payload.get("slug") != slug:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token")
        except jwt.JWTError:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or expired token")

    return await _build_gallery_response(gallery, db, blob_store)


@router.post("/{slug}/verify-pin", response_model=PinVerifyResponse)
async def verify_gallery_pin(slug: str, body: PinVerifyRequest, db: DbSession):
    """Verify PIN for a protected gallery."""
    gallery = await _get_gallery_by_slug(slug, db)

    if not gallery.pin_hash:
        return PinVerifyResponse(valid=True, token=None)

    if not verify_pin(body.pin, gallery.pin_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid PIN")

    # Issue a short-lived gallery access token
    token = jwt.encode(
        {
            "gallery_id": str(gallery.id),
            "slug": slug,
            "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return PinVerifyResponse(valid=True, token=token)


@router.get("/{slug}/photos", response_model=list[GalleryPhotoPublic])
async def get_gallery_photos(slug: str, db: DbSession, blob_store: BlobStoreDep):
    """Get all photos in a gallery with presigned URLs."""
    gallery = await _get_gallery_by_slug(slug, db)
    response = await _build_gallery_response(gallery, db, blob_store)
    return response.photos


# ─── Selections ──────────────────────────────────────────────────────

@router.post("/{slug}/selections", response_model=SelectionResponse, status_code=status.HTTP_201_CREATED)
async def submit_selection(slug: str, body: SelectionCreate, db: DbSession):
    """Submit client's photo selections."""
    gallery = await _get_gallery_by_slug(slug, db)

    if gallery.status == "selection_complete":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selections have already been submitted for this gallery",
        )

    # Validate max selections
    if gallery.max_selections and len(body.photo_ids) > gallery.max_selections:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {gallery.max_selections} selections allowed",
        )

    # Validate all photo_ids belong to this gallery
    result = await db.execute(
        select(GalleryPhoto.photo_id).where(GalleryPhoto.gallery_id == gallery.id)
    )
    valid_photo_ids = {row[0] for row in result.all()}
    invalid = set(body.photo_ids) - valid_photo_ids
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Photos not in gallery: {[str(p) for p in invalid]}",
        )

    # Create selection
    selection = Selection(
        gallery_id=gallery.id,
        client_name=body.client_name,
        client_email=body.client_email,
        notes=body.notes,
    )
    db.add(selection)
    await db.flush()

    # Add selected photos
    for photo_id in body.photo_ids:
        db.add(SelectionPhoto(selection_id=selection.id, photo_id=photo_id))

    # Update gallery and session statuses
    gallery.status = "selection_complete"

    # Update session status so the dashboard reflects the selection
    session_result = await db.execute(
        select(ShootSession).where(ShootSession.id == gallery.session_id)
    )
    sess = session_result.scalar_one_or_none()
    if sess:
        sess.status = "selection_complete"

    # Update photo statuses
    for photo_id in body.photo_ids:
        photo_result = await db.execute(select(Photo).where(Photo.id == photo_id))
        photo = photo_result.scalar_one_or_none()
        if photo:
            photo.status = "client_selected"

    await db.flush()

    return SelectionResponse(
        id=selection.id,
        gallery_id=selection.gallery_id,
        client_name=selection.client_name,
        client_email=selection.client_email,
        notes=selection.notes,
        submitted_at=selection.submitted_at,
        photo_count=len(body.photo_ids),
    )


# ─── Status ──────────────────────────────────────────────────────────

@router.get("/{slug}/status")
async def get_gallery_status(slug: str, db: DbSession):
    """Check gallery and delivery status."""
    gallery = await _get_gallery_by_slug(slug, db)
    return {
        "slug": gallery.slug,
        "status": gallery.status,
        "max_selections": gallery.max_selections,
    }


# ─── Helpers ─────────────────────────────────────────────────────────

async def _get_gallery_by_slug(slug: str, db) -> Gallery:
    result = await db.execute(select(Gallery).where(Gallery.slug == slug))
    gallery = result.scalar_one_or_none()
    if not gallery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gallery not found")
    return gallery


async def _build_gallery_response(gallery: Gallery, db, blob_store) -> GalleryPublicResponse:
    """Build the full gallery response with photo URLs."""
    result = await db.execute(
        select(GalleryPhoto)
        .where(GalleryPhoto.gallery_id == gallery.id)
        .options(selectinload(GalleryPhoto.photo))
        .order_by(GalleryPhoto.sort_order)
    )
    gallery_photos = result.scalars().all()

    photos: list[GalleryPhotoPublic] = []
    for gp in gallery_photos:
        photo = gp.photo
        thumbnail_url = None
        preview_url = None
        if photo.thumbnail_key:
            thumbnail_url = await blob_store.generate_presigned_download_url(photo.thumbnail_key)
        if photo.watermarked_key:
            preview_url = await blob_store.generate_presigned_download_url(photo.watermarked_key)
        elif photo.preview_key:
            preview_url = await blob_store.generate_presigned_download_url(photo.preview_key)

        photos.append(
            GalleryPhotoPublic(
                id=photo.id,
                thumbnail_url=thumbnail_url,
                preview_url=preview_url,
                face_center_x=photo.face_center_x,
                face_center_y=photo.face_center_y,
                sort_order=gp.sort_order,
            )
        )

    return GalleryPublicResponse(
        slug=gallery.slug,
        max_selections=gallery.max_selections,
        status=gallery.status,
        photos=photos,
    )
