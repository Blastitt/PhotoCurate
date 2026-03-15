"""DB-backed route tests for gallery management, public access, branding, and delivery."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from photocurate.api.auth import hash_pin, verify_pin
from photocurate.core.models.gallery import Delivery, EditedPhoto, Gallery, GalleryPhoto, Selection, SelectionPhoto
from photocurate.core.models.session import Photo, ShootSession
from photocurate.core.models.tenant import TenantBranding


@pytest.mark.asyncio
async def test_create_gallery_hashes_pin_links_photos_and_sets_session_status(
    api_client,
    auth_context_factory,
    session_record_factory,
    photo_record_factory,
    db_session,
):
    auth_context = await auth_context_factory()
    session = await session_record_factory(auth_context.tenant.id, auth_context.user.id, status="curated")
    photo_one = await photo_record_factory(session.id, auth_context.tenant.id, filename="one.jpg", status="auto_picked")
    photo_two = await photo_record_factory(session.id, auth_context.tenant.id, filename="two.jpg", status="gallery_ready")

    response = await api_client.post(
        f"/api/v1/sessions/{session.id}/gallery",
        json={"pin": "1234", "max_selections": 10, "photo_ids": [str(photo_one.id), str(photo_two.id)]},
        headers=auth_context.headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["gallery_url"] == f"/gallery/{data['slug']}"
    assert len(data["slug"]) == 12

    gallery = (await db_session.execute(select(Gallery).where(Gallery.id == uuid.UUID(data["id"])))).scalar_one()
    gallery_photos = (await db_session.execute(select(GalleryPhoto).where(GalleryPhoto.gallery_id == gallery.id))).scalars().all()
    await db_session.refresh(session)

    assert gallery.pin_hash != "1234"
    assert verify_pin("1234", gallery.pin_hash)
    assert [item.photo_id for item in sorted(gallery_photos, key=lambda row: row.sort_order)] == [photo_one.id, photo_two.id]
    assert session.status == "gallery_shared"


@pytest.mark.asyncio
async def test_create_gallery_auto_selects_only_eligible_photos(
    api_client,
    auth_context_factory,
    session_record_factory,
    photo_record_factory,
    db_session,
):
    auth_context = await auth_context_factory()
    session = await session_record_factory(auth_context.tenant.id, auth_context.user.id)
    eligible_one = await photo_record_factory(session.id, auth_context.tenant.id, filename="picked.jpg", status="auto_picked")
    eligible_two = await photo_record_factory(session.id, auth_context.tenant.id, filename="scored.jpg", status="scored")
    await photo_record_factory(session.id, auth_context.tenant.id, filename="uploaded.jpg", status="uploaded")

    response = await api_client.post(
        f"/api/v1/sessions/{session.id}/gallery",
        json={"max_selections": 5},
        headers=auth_context.headers,
    )

    assert response.status_code == 201
    gallery_id = uuid.UUID(response.json()["id"])
    selected_ids = [
        row.photo_id
        for row in (await db_session.execute(select(GalleryPhoto).where(GalleryPhoto.gallery_id == gallery_id))).scalars().all()
    ]
    assert set(selected_ids) == {eligible_one.id, eligible_two.id}


@pytest.mark.asyncio
async def test_public_gallery_pin_and_verify_flow(
    api_client,
    auth_context_factory,
    session_record_factory,
    photo_record_factory,
    gallery_record_factory,
    gallery_photo_record_factory,
):
    auth_context = await auth_context_factory()
    session = await session_record_factory(auth_context.tenant.id, auth_context.user.id)
    photo = await photo_record_factory(session.id, auth_context.tenant.id, status="auto_picked")
    gallery = await gallery_record_factory(session.id, auth_context.tenant.id, slug="pin-gallery", pin_hash=hash_pin("4321"))
    await gallery_photo_record_factory(gallery.id, photo.id)

    get_response = await api_client.get("/api/v1/gallery/pin-gallery")
    assert get_response.status_code == 200
    assert get_response.json()["photos"] == []

    invalid_response = await api_client.post("/api/v1/gallery/pin-gallery/verify-pin", json={"pin": "9999"})
    assert invalid_response.status_code == 403
    assert invalid_response.json()["detail"] == "Invalid PIN"

    valid_response = await api_client.post("/api/v1/gallery/pin-gallery/verify-pin", json={"pin": "4321"})
    assert valid_response.status_code == 200
    assert valid_response.json()["valid"] is True
    assert valid_response.json()["token"]


@pytest.mark.asyncio
async def test_public_gallery_returns_photos_and_rejects_expired_galleries(
    api_client,
    auth_context_factory,
    session_record_factory,
    photo_record_factory,
    gallery_record_factory,
    gallery_photo_record_factory,
):
    auth_context = await auth_context_factory()
    session = await session_record_factory(auth_context.tenant.id, auth_context.user.id)
    photo = await photo_record_factory(
        session.id,
        auth_context.tenant.id,
        thumbnail_key="thumb.webp",
        preview_key="preview.webp",
        watermarked_key="watermarked.webp",
        status="gallery_ready",
    )
    gallery = await gallery_record_factory(session.id, auth_context.tenant.id, slug="open-gallery")
    await gallery_photo_record_factory(gallery.id, photo.id)

    open_response = await api_client.get("/api/v1/gallery/open-gallery")
    assert open_response.status_code == 200
    photos = open_response.json()["photos"]
    assert len(photos) == 1
    assert photos[0]["thumbnail_url"].endswith("thumb.webp")
    assert photos[0]["preview_url"].endswith("watermarked.webp")

    expired = await gallery_record_factory(
        session.id,
        auth_context.tenant.id,
        slug="expired-gallery",
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    await gallery_photo_record_factory(expired.id, photo.id)

    expired_response = await api_client.get("/api/v1/gallery/expired-gallery")
    assert expired_response.status_code == 410
    assert expired_response.json()["detail"] == "Gallery has expired"


@pytest.mark.asyncio
async def test_submit_selection_validates_and_updates_state(
    api_client,
    auth_context_factory,
    session_record_factory,
    photo_record_factory,
    gallery_record_factory,
    gallery_photo_record_factory,
    db_session,
):
    auth_context = await auth_context_factory()
    session = await session_record_factory(auth_context.tenant.id, auth_context.user.id, status="gallery_shared")
    photo_one = await photo_record_factory(session.id, auth_context.tenant.id, status="auto_picked")
    photo_two = await photo_record_factory(session.id, auth_context.tenant.id, status="auto_picked")
    gallery = await gallery_record_factory(session.id, auth_context.tenant.id, slug="selection-gallery", max_selections=1)
    await gallery_photo_record_factory(gallery.id, photo_one.id, sort_order=0)
    await gallery_photo_record_factory(gallery.id, photo_two.id, sort_order=1)

    too_many = await api_client.post(
        "/api/v1/gallery/selection-gallery/selections",
        json={"photo_ids": [str(photo_one.id), str(photo_two.id)]},
    )
    assert too_many.status_code == 400
    assert too_many.json()["detail"] == "Maximum 1 selections allowed"

    outsider_id = str(uuid.uuid4())
    invalid_photo = await api_client.post(
        "/api/v1/gallery/selection-gallery/selections",
        json={"photo_ids": [outsider_id]},
    )
    assert invalid_photo.status_code == 400
    assert outsider_id in invalid_photo.json()["detail"]

    success = await api_client.post(
        "/api/v1/gallery/selection-gallery/selections",
        json={
            "photo_ids": [str(photo_one.id)],
            "client_name": "John Smith",
            "client_email": "john@example.com",
            "notes": "Please edit this one",
        },
    )
    assert success.status_code == 201
    assert success.json()["photo_count"] == 1

    await db_session.refresh(gallery)
    await db_session.refresh(session)
    await db_session.refresh(photo_one)
    selection = (await db_session.execute(select(Selection).where(Selection.gallery_id == gallery.id))).scalar_one()
    selection_photo = (await db_session.execute(select(SelectionPhoto).where(SelectionPhoto.selection_id == selection.id))).scalar_one()

    assert gallery.status == "selection_complete"
    assert session.status == "selection_complete"
    assert photo_one.status == "client_selected"
    assert selection.client_email == "john@example.com"
    assert selection_photo.photo_id == photo_one.id


@pytest.mark.asyncio
async def test_get_session_selections_returns_saved_selection_details(
    api_client,
    auth_context_factory,
    session_record_factory,
    gallery_record_factory,
    selection_record_factory,
    selection_photo_record_factory,
    photo_record_factory,
):
    auth_context = await auth_context_factory()
    session = await session_record_factory(auth_context.tenant.id, auth_context.user.id)
    photo = await photo_record_factory(session.id, auth_context.tenant.id, status="client_selected")
    gallery = await gallery_record_factory(session.id, auth_context.tenant.id)
    selection = await selection_record_factory(gallery.id, client_name="Jane Doe", client_email="jane@example.com")
    await selection_photo_record_factory(selection.id, photo.id)

    response = await api_client.get(f"/api/v1/sessions/{session.id}/selections", headers=auth_context.headers)

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(selection.id),
            "gallery_id": str(gallery.id),
            "client_name": "Jane Doe",
            "client_email": "jane@example.com",
            "notes": None,
            "submitted_at": response.json()[0]["submitted_at"],
            "photo_ids": [str(photo.id)],
        }
    ]


@pytest.mark.asyncio
async def test_branding_defaults_update_and_logo_upload(
    api_client,
    auth_context_factory,
    fake_blob_store,
    db_session,
):
    auth_context = await auth_context_factory()

    default_response = await api_client.get("/api/v1/tenants/branding", headers=auth_context.headers)
    assert default_response.status_code == 200
    assert default_response.json() == {
        "watermark_logo_key": None,
        "watermark_opacity": 0.3,
        "watermark_position": "bottom-right",
        "watermark_scale": 0.15,
        "watermark_padding": 0.02,
    }

    update_response = await api_client.post(
        "/api/v1/tenants/branding",
        json={"watermark_opacity": 0.6, "watermark_position": "center", "watermark_scale": 0.2},
        headers=auth_context.headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["watermark_position"] == "center"

    invalid_logo = await api_client.post(
        "/api/v1/tenants/branding/logo",
        files={"file": ("logo.txt", b"not-an-image", "text/plain")},
        headers=auth_context.headers,
    )
    assert invalid_logo.status_code == 400
    assert invalid_logo.json()["detail"] == "File must be an image"

    valid_logo = await api_client.post(
        "/api/v1/tenants/branding/logo",
        files={"file": ("logo.png", b"png-bytes", "image/png")},
        headers=auth_context.headers,
    )
    assert valid_logo.status_code == 200
    assert valid_logo.json()["watermark_logo_key"] == f"tenants/{auth_context.tenant.id}/branding/watermark_logo.png"
    assert fake_blob_store.generated_upload_urls[-1].endswith(f"tenants/{auth_context.tenant.id}/branding/watermark_logo.png")

    branding = (await db_session.execute(select(TenantBranding).where(TenantBranding.tenant_id == auth_context.tenant.id))).scalar_one()
    assert branding.watermark_logo_key == f"tenants/{auth_context.tenant.id}/branding/watermark_logo.png"


@pytest.mark.asyncio
async def test_create_delivery_persists_row_and_publishes_event(
    api_client,
    auth_context_factory,
    session_record_factory,
    gallery_record_factory,
    fake_queue,
    db_session,
):
    auth_context = await auth_context_factory()
    session = await session_record_factory(auth_context.tenant.id, auth_context.user.id)
    gallery = await gallery_record_factory(session.id, auth_context.tenant.id)

    response = await api_client.post(
        f"/api/v1/galleries/{gallery.id}/deliver",
        json={"provider": "dropbox", "access_token": "tok-123"},
        headers=auth_context.headers,
    )

    assert response.status_code == 201
    delivery = (await db_session.execute(select(Delivery).where(Delivery.id == uuid.UUID(response.json()["id"])))).scalar_one()
    assert delivery.status == "pending"
    assert delivery.provider == "dropbox"
    assert len(fake_queue.published) == 1
    topic, payload = fake_queue.published[0]
    assert topic == "photo.delivery"
    assert json.loads(payload) == {
        "type": "delivery.execute",
        "delivery_id": str(delivery.id),
        "access_token": "tok-123",
    }


@pytest.mark.asyncio
async def test_upload_edited_photos_creates_records_and_changes_statuses(
    api_client,
    auth_context_factory,
    session_record_factory,
    photo_record_factory,
    db_session,
):
    auth_context = await auth_context_factory()
    session = await session_record_factory(auth_context.tenant.id, auth_context.user.id, status="selection_complete")
    photo_one = await photo_record_factory(session.id, auth_context.tenant.id, status="client_selected")
    photo_two = await photo_record_factory(session.id, auth_context.tenant.id, status="auto_picked")
    await photo_record_factory(session.id, auth_context.tenant.id, filename="ignored.jpg", status="uploaded")

    response = await api_client.post(f"/api/v1/sessions/{session.id}/edited", headers=auth_context.headers)

    assert response.status_code == 201
    urls = response.json()["urls"]
    assert len(urls) == 2
    assert all(item["key"].endswith(".jpg") for item in urls)

    edited_rows = (await db_session.execute(select(EditedPhoto).where(EditedPhoto.session_id == session.id))).scalars().all()
    assert len(edited_rows) == 2

    await db_session.refresh(photo_one)
    await db_session.refresh(photo_two)
    await db_session.refresh(session)
    assert {photo_one.status, photo_two.status} == {"editing"}
    assert session.status == "editing"