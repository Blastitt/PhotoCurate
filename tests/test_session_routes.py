"""DB-backed route tests for sessions, photos, and clients."""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import select

from photocurate.core.models.session import AIScore, Photo, ShootSession
from photocurate.core.models.tenant import Client


@pytest.mark.asyncio
async def test_session_crud_and_tenant_isolation(api_client, auth_context_factory, db_session):
    owner = await auth_context_factory(email="owner@example.com")
    outsider = await auth_context_factory(email="outsider@example.com")

    create_response = await api_client.post(
        "/api/v1/sessions",
        json={"title": "Smith Wedding", "description": "Main gallery", "auto_pick_count": 25},
        headers=owner.headers,
    )
    assert create_response.status_code == 201
    session_id = uuid.UUID(create_response.json()["id"])

    list_response = await api_client.get("/api/v1/sessions", headers=owner.headers)
    assert list_response.status_code == 200
    assert [uuid.UUID(item["id"]) for item in list_response.json()] == [session_id]

    forbidden_get = await api_client.get(f"/api/v1/sessions/{session_id}", headers=outsider.headers)
    assert forbidden_get.status_code == 404

    update_response = await api_client.patch(
        f"/api/v1/sessions/{session_id}",
        json={"title": "Updated Wedding", "auto_pick_count": 40},
        headers=owner.headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["title"] == "Updated Wedding"
    assert update_response.json()["auto_pick_count"] == 40

    delete_response = await api_client.delete(f"/api/v1/sessions/{session_id}", headers=owner.headers)
    assert delete_response.status_code == 204
    deleted = (await db_session.execute(select(ShootSession).where(ShootSession.id == session_id))).scalar_one_or_none()
    assert deleted is None


@pytest.mark.asyncio
async def test_upload_urls_create_photo_rows_and_transition_status(
    api_client,
    auth_context_factory,
    session_record_factory,
    db_session,
):
    auth_context = await auth_context_factory()
    session = await session_record_factory(auth_context.tenant.id, auth_context.user.id, title="Uploads")

    response = await api_client.post(
        f"/api/v1/sessions/{session.id}/upload-urls",
        json={"filenames": ["a.jpg", "b.png"]},
        headers=auth_context.headers,
    )

    assert response.status_code == 200
    urls = response.json()["urls"]
    assert len(urls) == 2
    assert urls[0]["filename"] == "a.jpg"
    assert f"tenants/{auth_context.tenant.id}/sessions/{session.id}/originals/" in urls[0]["key"]
    assert urls[0]["key"].endswith("_a.jpg")
    assert urls[1]["key"].endswith("_b.png")

    photos = (await db_session.execute(select(Photo).where(Photo.session_id == session.id))).scalars().all()
    assert sorted(photo.filename for photo in photos) == ["a.jpg", "b.png"]
    assert {photo.status for photo in photos} == {"uploaded"}

    await db_session.refresh(session)
    assert session.status == "uploading"


@pytest.mark.asyncio
async def test_finalize_session_publishes_event_and_rejects_invalid_state(
    api_client,
    auth_context_factory,
    session_record_factory,
    fake_queue,
    db_session,
):
    auth_context = await auth_context_factory()
    session = await session_record_factory(auth_context.tenant.id, auth_context.user.id, status="uploading")

    response = await api_client.post(f"/api/v1/sessions/{session.id}/finalize", headers=auth_context.headers)

    assert response.status_code == 202
    assert len(fake_queue.published) == 1
    topic, payload = fake_queue.published[0]
    event = json.loads(payload)
    assert topic == "photo.processing"
    assert event == {
        "type": "session.process",
        "session_id": str(session.id),
        "tenant_id": str(auth_context.tenant.id),
    }

    await db_session.refresh(session)
    assert session.status == "processing"

    session.status = "curated"
    await db_session.commit()

    invalid_response = await api_client.post(f"/api/v1/sessions/{session.id}/finalize", headers=auth_context.headers)
    assert invalid_response.status_code == 400
    assert "cannot finalize" in invalid_response.json()["detail"]
    assert len(fake_queue.published) == 1


@pytest.mark.asyncio
async def test_list_photos_and_update_photo_are_tenant_scoped(
    api_client,
    auth_context_factory,
    session_record_factory,
    photo_record_factory,
    ai_score_record_factory,
):
    owner = await auth_context_factory(email="owner-photos@example.com")
    outsider = await auth_context_factory(email="outsider-photos@example.com")
    session = await session_record_factory(owner.tenant.id, owner.user.id)
    photo = await photo_record_factory(
        session.id,
        owner.tenant.id,
        thumbnail_key="thumb.webp",
        preview_key="preview.webp",
        status="processing",
    )
    await ai_score_record_factory(photo.id, composite_score=0.91)

    list_response = await api_client.get(f"/api/v1/sessions/{session.id}/photos", headers=owner.headers)

    assert list_response.status_code == 200
    data = list_response.json()
    assert len(data) == 1
    assert data[0]["thumbnail_url"].endswith("thumb.webp")
    assert data[0]["preview_url"].endswith("preview.webp")
    assert data[0]["ai_score"]["composite_score"] == 0.91

    update_response = await api_client.patch(
        f"/api/v1/sessions/photos/{photo.id}",
        json={"status": "gallery_ready"},
        headers=owner.headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "gallery_ready"

    forbidden_response = await api_client.patch(
        f"/api/v1/sessions/photos/{photo.id}",
        json={"status": "rejected"},
        headers=outsider.headers,
    )
    assert forbidden_response.status_code == 404


@pytest.mark.asyncio
async def test_processing_config_update_persists_and_publishes_reprocess_event(
    api_client,
    auth_context_factory,
    session_record_factory,
    fake_queue,
    db_session,
):
    auth_context = await auth_context_factory()
    session = await session_record_factory(auth_context.tenant.id, auth_context.user.id)

    response = await api_client.patch(
        f"/api/v1/sessions/{session.id}/processing-config",
        json={"wb_mode": "manual", "wb_temp_shift": 150.0, "wb_tint_shift": 0.25, "wb_strength": 0.9},
        headers=auth_context.headers,
    )

    assert response.status_code == 200
    assert response.json()["wb_mode"] == "manual"
    assert response.json()["wb_temp_shift"] == 150.0
    assert len(fake_queue.published) == 1
    topic, payload = fake_queue.published[0]
    assert topic == "photo.processing"
    assert json.loads(payload) == {
        "type": "session.reprocess_previews",
        "session_id": str(session.id),
        "tenant_id": str(auth_context.tenant.id),
    }

    await db_session.refresh(session)
    assert session.wb_mode == "manual"
    assert session.wb_strength == 0.9


@pytest.mark.asyncio
async def test_client_crud_is_tenant_scoped(api_client, auth_context_factory, db_session):
    owner = await auth_context_factory(email="clients-owner@example.com")
    outsider = await auth_context_factory(email="clients-outsider@example.com")

    create_response = await api_client.post(
        "/api/v1/clients",
        json={"name": "John Smith", "email": "john@example.com"},
        headers=owner.headers,
    )
    assert create_response.status_code == 201
    client_id = uuid.UUID(create_response.json()["id"])

    list_response = await api_client.get("/api/v1/clients", headers=owner.headers)
    assert list_response.status_code == 200
    assert [uuid.UUID(item["id"]) for item in list_response.json()] == [client_id]

    outsider_list = await api_client.get("/api/v1/clients", headers=outsider.headers)
    assert outsider_list.status_code == 200
    assert outsider_list.json() == []

    forbidden_get = await api_client.get(f"/api/v1/clients/{client_id}", headers=outsider.headers)
    assert forbidden_get.status_code == 404

    delete_response = await api_client.delete(f"/api/v1/clients/{client_id}", headers=owner.headers)
    assert delete_response.status_code == 204
    deleted = (await db_session.execute(select(Client).where(Client.id == client_id))).scalar_one_or_none()
    assert deleted is None