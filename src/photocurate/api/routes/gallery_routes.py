"""Gallery management routes (photographer-facing) and delivery."""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from photocurate.api.auth import hash_pin
from photocurate.api.deps import BlobStoreDep, CurrentUser, DbSession, QueueDep
from photocurate.core.models.gallery import Delivery, EditedPhoto, Gallery, GalleryPhoto, Selection, SelectionPhoto
from photocurate.core.models.session import Photo, ShootSession
from photocurate.core.models.tenant import TenantBranding
from photocurate.core.schemas.gallery import (
    BrandingResponse,
    BrandingUpdate,
    DeliveryCreate,
    DeliveryResponse,
    GalleryCreate,
    GalleryResponse,
    SelectionDetailResponse,
)

router = APIRouter(tags=["galleries"])


# ─── Gallery Creation ────────────────────────────────────────────────

@router.post("/sessions/{session_id}/gallery", response_model=GalleryResponse, status_code=status.HTTP_201_CREATED)
async def create_gallery(session_id: uuid.UUID, body: GalleryCreate, db: DbSession, user: CurrentUser):
    """Create a shareable gallery for a session."""
    # Validate session
    result = await db.execute(
        select(ShootSession).where(
            ShootSession.id == session_id,
            ShootSession.tenant_id == user.tenant_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # Generate unguessable slug
    slug = uuid.uuid4().hex[:12]

    gallery = Gallery(
        session_id=session.id,
        tenant_id=user.tenant_id,
        slug=slug,
        pin_hash=hash_pin(body.pin) if body.pin else None,
        max_selections=body.max_selections,
    )
    db.add(gallery)
    await db.flush()

    # Add photos to gallery
    if body.photo_ids:
        photo_ids = body.photo_ids
    else:
        # Auto: include all auto-picked or gallery-ready photos
        photo_result = await db.execute(
            select(Photo.id).where(
                Photo.session_id == session_id,
                Photo.tenant_id == user.tenant_id,
                Photo.status.in_(["auto_picked", "gallery_ready", "scored"]),
            )
        )
        photo_ids = [row[0] for row in photo_result.all()]

    for i, photo_id in enumerate(photo_ids):
        db.add(GalleryPhoto(gallery_id=gallery.id, photo_id=photo_id, sort_order=i))

    # Update session status
    session.status = "gallery_shared"
    await db.flush()
    await db.refresh(gallery)

    return GalleryResponse(
        id=gallery.id,
        session_id=gallery.session_id,
        slug=gallery.slug,
        max_selections=gallery.max_selections,
        expires_at=gallery.expires_at,
        status=gallery.status,
        created_at=gallery.created_at,
        gallery_url=f"/gallery/{gallery.slug}",
    )


# ─── Selections (photographer-facing) ────────────────────────────────

@router.get("/sessions/{session_id}/selections", response_model=list[SelectionDetailResponse])
async def get_session_selections(
    session_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    blob_store: BlobStoreDep,
):
    """Get all client selections for a session's gallery."""
    # Verify session ownership
    result = await db.execute(
        select(ShootSession).where(
            ShootSession.id == session_id,
            ShootSession.tenant_id == user.tenant_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # Find gallery for this session
    gal_result = await db.execute(
        select(Gallery).where(
            Gallery.session_id == session_id,
            Gallery.tenant_id == user.tenant_id,
        )
    )
    gallery = gal_result.scalar_one_or_none()
    if not gallery:
        return []

    # Get selections with their photos
    sel_result = await db.execute(
        select(Selection)
        .where(Selection.gallery_id == gallery.id)
        .options(selectinload(Selection.selection_photos))
    )
    selections = sel_result.scalars().all()

    return [
        SelectionDetailResponse(
            id=s.id,
            gallery_id=s.gallery_id,
            client_name=s.client_name,
            client_email=s.client_email,
            notes=s.notes,
            submitted_at=s.submitted_at,
            photo_ids=[sp.photo_id for sp in s.selection_photos],
        )
        for s in selections
    ]


# ─── Delivery ────────────────────────────────────────────────────────

@router.post("/galleries/{gallery_id}/deliver", response_model=DeliveryResponse, status_code=status.HTTP_201_CREATED)
async def create_delivery(
    gallery_id: uuid.UUID,
    body: DeliveryCreate,
    db: DbSession,
    user: CurrentUser,
    queue: QueueDep,
):
    """Trigger delivery of selected photos to cloud storage."""
    result = await db.execute(
        select(Gallery).where(Gallery.id == gallery_id, Gallery.tenant_id == user.tenant_id)
    )
    gallery = result.scalar_one_or_none()
    if not gallery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gallery not found")

    delivery = Delivery(
        session_id=gallery.session_id,
        tenant_id=user.tenant_id,
        provider=body.provider,
        status="pending",
    )
    db.add(delivery)
    await db.flush()
    await db.refresh(delivery)

    # Publish delivery event to the queue
    event = json.dumps({
        "type": "delivery.execute",
        "delivery_id": str(delivery.id),
        "access_token": body.access_token or "",
    }).encode()
    await queue.publish("photo.delivery", event)

    return delivery


# ─── Edited Photos Upload ────────────────────────────────────────────

@router.post("/sessions/{session_id}/edited", status_code=status.HTTP_201_CREATED)
async def upload_edited_photos(
    session_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    blob_store: BlobStoreDep,
):
    """Get presigned upload URLs for edited photos in a session.

    After the photographer edits selected photos locally, they upload the
    edited versions here.  Expects a JSON body with photo_ids to generate
    upload URLs for.
    """
    # Verify session ownership
    result = await db.execute(
        select(ShootSession).where(
            ShootSession.id == session_id,
            ShootSession.tenant_id == user.tenant_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # Get selected photos (those the client chose)
    photo_result = await db.execute(
        select(Photo).where(
            Photo.session_id == session_id,
            Photo.tenant_id == user.tenant_id,
            Photo.status.in_(["client_selected", "editing", "auto_picked"]),
        )
    )
    photos = photo_result.scalars().all()

    urls = []
    for photo in photos:
        edited_key = f"tenants/{user.tenant_id}/sessions/{session_id}/edited/{photo.id}.jpg"
        upload_url = await blob_store.generate_presigned_upload_url(edited_key)

        # Create or update edited photo record
        existing = await db.execute(
            select(EditedPhoto).where(
                EditedPhoto.original_photo_id == photo.id,
                EditedPhoto.session_id == session_id,
            )
        )
        edited = existing.scalar_one_or_none()
        if not edited:
            edited = EditedPhoto(
                original_photo_id=photo.id,
                session_id=session_id,
                edited_key=edited_key,
            )
            db.add(edited)

        photo.status = "editing"
        urls.append({"photo_id": str(photo.id), "upload_url": upload_url, "key": edited_key})

    session.status = "editing"
    await db.flush()

    return {"urls": urls}


# ─── Branding / Watermark Config ─────────────────────────────────────

@router.get("/tenants/branding", response_model=BrandingResponse)
async def get_branding(db: DbSession, user: CurrentUser, blob_store: BlobStoreDep):
    """Get current tenant branding / watermark config."""
    result = await db.execute(
        select(TenantBranding).where(TenantBranding.tenant_id == user.tenant_id)
    )
    branding = result.scalar_one_or_none()
    if not branding:
        # Return defaults
        return BrandingResponse(
            watermark_logo_key=None,
            watermark_logo_url=None,
            watermark_opacity=0.3,
            watermark_position="bottom-right",
            watermark_scale=0.15,
            watermark_padding=0.02,
            watermark_tile_rotation=45.0,
            watermark_tile_spacing=0.5,
        )
    resp = BrandingResponse.model_validate(branding)
    if branding.watermark_logo_key:
        resp.watermark_logo_url = await blob_store.generate_presigned_download_url(branding.watermark_logo_key)
    return resp


@router.post("/tenants/branding", response_model=BrandingResponse)
async def update_branding(
    body: BrandingUpdate,
    db: DbSession,
    user: CurrentUser,
    blob_store: BlobStoreDep,
):
    """Update tenant branding / watermark configuration."""
    result = await db.execute(
        select(TenantBranding).where(TenantBranding.tenant_id == user.tenant_id)
    )
    branding = result.scalar_one_or_none()

    if not branding:
        branding = TenantBranding(tenant_id=user.tenant_id)
        db.add(branding)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(branding, field, value)

    await db.flush()
    await db.refresh(branding)
    resp = BrandingResponse.model_validate(branding)
    if branding.watermark_logo_key:
        resp.watermark_logo_url = await blob_store.generate_presigned_download_url(branding.watermark_logo_key)
    return resp


@router.post("/tenants/branding/logo", response_model=BrandingResponse)
async def upload_watermark_logo(
    file: UploadFile,
    db: DbSession,
    user: CurrentUser,
    blob_store: BlobStoreDep,
):
    """Upload a watermark logo PNG for the tenant."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File must be an image")

    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File too large (max 5MB)")

    key = f"tenants/{user.tenant_id}/branding/watermark_logo.png"
    await blob_store.upload(key, contents, content_type=file.content_type)

    # Update branding record
    result = await db.execute(
        select(TenantBranding).where(TenantBranding.tenant_id == user.tenant_id)
    )
    branding = result.scalar_one_or_none()
    if not branding:
        branding = TenantBranding(tenant_id=user.tenant_id)
        db.add(branding)
    branding.watermark_logo_key = key

    await db.flush()
    await db.refresh(branding)
    resp = BrandingResponse.model_validate(branding)
    resp.watermark_logo_url = await blob_store.generate_presigned_download_url(key)
    return resp
