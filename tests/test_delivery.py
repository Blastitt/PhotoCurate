"""Tests for the delivery worker and cloud storage providers."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from photocurate.core.delivery import DeliveryProvider
from photocurate.core.models.gallery import Delivery
from photocurate.infrastructure.dropbox import DropboxProvider
from photocurate.infrastructure.google_drive import GoogleDriveProvider
from photocurate.infrastructure.onedrive import OneDriveProvider


class TestProviderInstantiation:
    """Verify all delivery providers implement the ABC correctly."""

    def test_google_drive_is_delivery_provider(self):
        p = GoogleDriveProvider()
        assert isinstance(p, DeliveryProvider)

    def test_dropbox_is_delivery_provider(self):
        p = DropboxProvider()
        assert isinstance(p, DeliveryProvider)

    def test_onedrive_is_delivery_provider(self):
        p = OneDriveProvider()
        assert isinstance(p, DeliveryProvider)


class TestDeliveryWorkerProviderSelection:
    def test_get_provider_google_drive(self):
        from photocurate.workers.delivery import _get_provider
        p = _get_provider("google_drive")
        assert isinstance(p, GoogleDriveProvider)

    def test_get_provider_dropbox(self):
        from photocurate.workers.delivery import _get_provider
        p = _get_provider("dropbox")
        assert isinstance(p, DropboxProvider)

    def test_get_provider_onedrive(self):
        from photocurate.workers.delivery import _get_provider
        p = _get_provider("onedrive")
        assert isinstance(p, OneDriveProvider)

    def test_get_provider_unknown_raises(self):
        from photocurate.workers.delivery import _get_provider
        with pytest.raises(ValueError, match="Unknown delivery provider"):
            _get_provider("ftp")


class TestDeliveryCreateSchema:
    def test_valid_providers(self):
        from photocurate.core.schemas.gallery import DeliveryCreate
        for provider in ("google_drive", "dropbox", "onedrive"):
            d = DeliveryCreate(provider=provider)
            assert d.provider == provider

    def test_invalid_provider_rejected(self):
        from pydantic import ValidationError
        from photocurate.core.schemas.gallery import DeliveryCreate
        with pytest.raises(ValidationError):
            DeliveryCreate(provider="ftp")

    def test_access_token_optional(self):
        from photocurate.core.schemas.gallery import DeliveryCreate
        d = DeliveryCreate(provider="google_drive")
        assert d.access_token is None

    def test_access_token_provided(self):
        from photocurate.core.schemas.gallery import DeliveryCreate
        d = DeliveryCreate(provider="dropbox", access_token="tok_123")
        assert d.access_token == "tok_123"


class TestDeliveryWorkerBehavior:
    @pytest.mark.asyncio
    async def test_deliver_photos_marks_completed_when_no_edited_photos(
        self,
        auth_context_factory,
        session_record_factory,
        delivery_record_factory,
        fake_blob_store,
        db_session_factory,
        monkeypatch,
    ):
        from photocurate.workers import delivery as delivery_worker

        auth_context = await auth_context_factory()
        session = await session_record_factory(auth_context.tenant.id, auth_context.user.id, title="No edits")
        delivery = await delivery_record_factory(session.id, auth_context.tenant.id, provider="dropbox")

        monkeypatch.setattr(delivery_worker, "async_session_factory", db_session_factory)

        await delivery_worker.deliver_photos(delivery.id, "token", fake_blob_store)

        async with db_session_factory() as db:
            stored = (await db.execute(select(Delivery).where(Delivery.id == delivery.id))).scalar_one()

        assert stored.status == "completed"
        assert stored.photo_count == 0
        assert stored.started_at is not None
        assert stored.completed_at is not None

    @pytest.mark.asyncio
    async def test_deliver_photos_uploads_all_edited_photos(
        self,
        auth_context_factory,
        session_record_factory,
        photo_record_factory,
        edited_photo_record_factory,
        delivery_record_factory,
        fake_blob_store,
        db_session_factory,
        monkeypatch,
    ):
        from photocurate.workers import delivery as delivery_worker

        auth_context = await auth_context_factory()
        session = await session_record_factory(auth_context.tenant.id, auth_context.user.id, title="Edited gallery")
        photo_one = await photo_record_factory(session.id, auth_context.tenant.id, filename="one.jpg")
        photo_two = await photo_record_factory(session.id, auth_context.tenant.id, filename="two.png")
        edited_one = await edited_photo_record_factory(photo_one.id, session.id, "edited/one.jpg")
        edited_two = await edited_photo_record_factory(photo_two.id, session.id, "edited/two.png")
        fake_blob_store.objects[edited_one.edited_key] = b"jpeg-bytes"
        fake_blob_store.objects[edited_two.edited_key] = b"png-bytes"
        delivery = await delivery_record_factory(session.id, auth_context.tenant.id, provider="dropbox")

        provider = AsyncMock()
        provider.create_folder.return_value = "folder-123"
        provider.get_share_link.return_value = "https://dropbox.test/folder-123"

        monkeypatch.setattr(delivery_worker, "async_session_factory", db_session_factory)
        monkeypatch.setattr(delivery_worker, "_get_provider", lambda provider_name: provider)

        await delivery_worker.deliver_photos(delivery.id, "access-token", fake_blob_store)

        async with db_session_factory() as db:
            stored = (await db.execute(select(Delivery).where(Delivery.id == delivery.id))).scalar_one()

        assert stored.status == "completed"
        assert stored.photo_count == 2
        assert stored.provider_folder_url == "https://dropbox.test/folder-123"
        provider.create_folder.assert_awaited_once_with("PhotoCurate - Edited gallery", "access-token")
        assert provider.upload_file.await_count == 2

    @pytest.mark.asyncio
    async def test_deliver_photos_records_failure_when_provider_errors(
        self,
        auth_context_factory,
        session_record_factory,
        photo_record_factory,
        edited_photo_record_factory,
        delivery_record_factory,
        fake_blob_store,
        db_session_factory,
        monkeypatch,
    ):
        from photocurate.workers import delivery as delivery_worker

        auth_context = await auth_context_factory()
        session = await session_record_factory(auth_context.tenant.id, auth_context.user.id)
        photo = await photo_record_factory(session.id, auth_context.tenant.id, filename="failed.jpg")
        edited = await edited_photo_record_factory(photo.id, session.id, "edited/failed.jpg")
        fake_blob_store.objects[edited.edited_key] = b"edited-bytes"
        delivery = await delivery_record_factory(session.id, auth_context.tenant.id, provider="dropbox")

        provider = AsyncMock()
        provider.create_folder.side_effect = RuntimeError("provider exploded")

        monkeypatch.setattr(delivery_worker, "async_session_factory", db_session_factory)
        monkeypatch.setattr(delivery_worker, "_get_provider", lambda provider_name: provider)

        await delivery_worker.deliver_photos(delivery.id, "token", fake_blob_store)

        async with db_session_factory() as db:
            stored = (await db.execute(select(Delivery).where(Delivery.id == delivery.id))).scalar_one()

        assert stored.status == "failed"
        assert "provider exploded" in (stored.error_message or "")
