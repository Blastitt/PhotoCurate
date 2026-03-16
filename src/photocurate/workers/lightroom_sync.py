"""Lightroom sync and flagging worker.

Handles two queue topics:
  - photo.lightroom_sync  — push originals from PhotoCurate to Lightroom
  - photo.lightroom_flag  — flag client-selected photos as "pick" in Lightroom
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select, update

from photocurate.config import settings
from photocurate.core.database import async_session_factory
from photocurate.core.models.adobe import AdobeToken, LightroomPendingTask
from photocurate.core.models.gallery import Selection, SelectionPhoto
from photocurate.core.models.session import Photo, ShootSession
from photocurate.core.storage import BlobStore
from photocurate.infrastructure.adobe_lightroom import LightroomAPIError, LightroomClient

logger = logging.getLogger(__name__)

_lr_client: LightroomClient | None = None


def _get_lr_client() -> LightroomClient:
    global _lr_client
    if _lr_client is None:
        _lr_client = LightroomClient()
    return _lr_client


def _decrypt(value: str) -> str:
    key = settings.adobe_token_encryption_key
    if not key:
        raise RuntimeError("Adobe token encryption key not configured")
    return Fernet(key.encode()).decrypt(value.encode()).decode()


def _encrypt(value: str) -> str:
    key = settings.adobe_token_encryption_key
    if not key:
        raise RuntimeError("Adobe token encryption key not configured")
    return Fernet(key.encode()).encrypt(value.encode()).decode()


async def _get_valid_token(user_id: uuid.UUID, db) -> tuple[AdobeToken, str] | None:  # noqa: ANN001
    """Load and optionally refresh the user's Adobe token. Returns (row, access_token) or None."""
    result = await db.execute(select(AdobeToken).where(AdobeToken.user_id == user_id))
    token_row = result.scalar_one_or_none()
    if not token_row:
        return None

    # Refresh if near-expiry
    if token_row.expires_at <= datetime.now(timezone.utc) + timedelta(minutes=5):
        try:
            import httpx

            resp = await httpx.AsyncClient().post(
                "https://ims-na1.adobelogin.com/ims/token/v3",
                data={
                    "grant_type": "refresh_token",
                    "client_id": settings.adobe_client_id,
                    "client_secret": settings.adobe_client_secret,
                    "refresh_token": _decrypt(token_row.refresh_token),
                },
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            token_row.access_token = _encrypt(data["access_token"])
            token_row.expires_at = datetime.now(timezone.utc) + timedelta(seconds=data.get("expires_in", 3600))
            if "refresh_token" in data:
                token_row.refresh_token = _encrypt(data["refresh_token"])
            await db.commit()

            return token_row, data["access_token"]
        except Exception:
            logger.warning("Failed to refresh Adobe token for user %s", user_id)
            return None

    return token_row, _decrypt(token_row.access_token)


async def _park_task(
    user_id: uuid.UUID,
    task_type: str,
    payload: dict,
    db,  # noqa: ANN001
) -> None:
    """Insert a pending task row for later retry."""
    task = LightroomPendingTask(
        user_id=user_id,
        task_type=task_type,
        payload=payload,
        status="pending",
    )
    db.add(task)
    await db.commit()
    logger.info("Parked Lightroom %s task for user %s", task_type, user_id)


async def _complete_pending_task(pending_task_id: uuid.UUID | None, db) -> None:  # noqa: ANN001
    """Mark a pending task as completed if this was a retry."""
    if pending_task_id:
        await db.execute(
            update(LightroomPendingTask)
            .where(LightroomPendingTask.id == pending_task_id)
            .values(status="completed", updated_at=datetime.now(timezone.utc))
        )
        await db.commit()


# ── Sync Worker ───────────────────────────────────────────────────────

async def sync_photo_to_lightroom(
    photo_id: uuid.UUID,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    blob_store: BlobStore,
    pending_task_id: uuid.UUID | None = None,
) -> None:
    """Push a single photo's original to the user's Lightroom catalog."""
    async with async_session_factory() as db:
        # Token check
        token_result = await _get_valid_token(user_id, db)
        if token_result is None:
            # Park and set pending_auth
            await db.execute(
                update(Photo).where(Photo.id == photo_id).values(lightroom_sync_status="pending_auth")
            )
            await _park_task(user_id, "sync", {
                "type": "photo.sync",
                "photo_id": str(photo_id),
                "session_id": str(session_id),
                "user_id": str(user_id),
            }, db)
            return

        token_row, access_token = token_result

        # Load photo
        result = await db.execute(select(Photo).where(Photo.id == photo_id))
        photo = result.scalar_one_or_none()
        if not photo or not photo.original_key:
            logger.error("Photo %s not found or has no original_key", photo_id)
            return

        # Load session for album settings
        sess_result = await db.execute(select(ShootSession).where(ShootSession.id == session_id))
        session = sess_result.scalar_one_or_none()
        if not session:
            logger.error("Session %s not found", session_id)
            return

        photo.lightroom_sync_status = "syncing"
        await db.commit()

        lr = _get_lr_client()
        catalog_id = token_row.lightroom_catalog_id

        try:
            # Download original
            image_data = await blob_store.download(photo.original_key)

            # Create asset
            asset_id = str(uuid.uuid4()).replace("-", "")
            await lr.create_asset(catalog_id, asset_id, photo.filename, access_token)

            # Upload
            content_type = photo.mime_type or "image/jpeg"
            await lr.upload_original(catalog_id, asset_id, image_data, content_type, access_token)

            # Add to target album
            if session.lightroom_target_album_id:
                await lr.add_assets_to_album(
                    catalog_id, session.lightroom_target_album_id, [asset_id], access_token
                )
            elif session.lightroom_sync:
                # Create album on first photo, cache the ID
                album_name = session.lightroom_target_album_name or session.title
                new_album_id = await lr.create_album(catalog_id, album_name, access_token)
                session.lightroom_target_album_id = new_album_id
                await lr.add_assets_to_album(catalog_id, new_album_id, [asset_id], access_token)

            photo.lightroom_asset_id = asset_id
            photo.lightroom_sync_status = "synced"
            await _complete_pending_task(pending_task_id, db)
            await db.commit()

            logger.info("Photo %s synced to Lightroom as asset %s", photo_id, asset_id)

        except LightroomAPIError as e:
            if e.status_code == 401:
                photo.lightroom_sync_status = "pending_auth"
                await _park_task(user_id, "sync", {
                    "type": "photo.sync",
                    "photo_id": str(photo_id),
                    "session_id": str(session_id),
                    "user_id": str(user_id),
                }, db)
            else:
                photo.lightroom_sync_status = "failed"
                await db.commit()
                logger.exception("Failed to sync photo %s to Lightroom", photo_id)


# ── Flag Worker ───────────────────────────────────────────────────────

async def flag_selection_in_lightroom(
    selection_id: uuid.UUID,
    user_id: uuid.UUID,
    pending_task_id: uuid.UUID | None = None,
) -> None:
    """Flag client-selected photos as 'pick' in the user's Lightroom catalog."""
    async with async_session_factory() as db:
        # Token check
        token_result = await _get_valid_token(user_id, db)
        if token_result is None:
            await _park_task(user_id, "flag", {
                "type": "selection.flag",
                "selection_id": str(selection_id),
                "user_id": str(user_id),
            }, db)
            return

        token_row, access_token = token_result
        lr = _get_lr_client()
        catalog_id = token_row.lightroom_catalog_id

        # Load selected photo IDs with lightroom_asset_id
        result = await db.execute(
            select(Photo.lightroom_asset_id)
            .join(SelectionPhoto, SelectionPhoto.photo_id == Photo.id)
            .where(
                SelectionPhoto.selection_id == selection_id,
                Photo.lightroom_asset_id.isnot(None),
            )
        )
        asset_ids = [row[0] for row in result.all()]

        if not asset_ids:
            logger.info("No Lightroom-linked photos in selection %s, skipping", selection_id)
            await _complete_pending_task(pending_task_id, db)
            return

        try:
            for asset_id in asset_ids:
                await lr.set_asset_flag(catalog_id, asset_id, "pick", access_token)

            await _complete_pending_task(pending_task_id, db)
            logger.info("Flagged %d assets as 'pick' for selection %s", len(asset_ids), selection_id)

        except LightroomAPIError as e:
            if e.status_code == 401:
                await _park_task(user_id, "flag", {
                    "type": "selection.flag",
                    "selection_id": str(selection_id),
                    "user_id": str(user_id),
                }, db)
            else:
                logger.exception("Failed to flag selection %s in Lightroom", selection_id)


# ── Queue Handlers ────────────────────────────────────────────────────

async def handle_lightroom_sync_event(msg: bytes) -> None:
    """Process a photo.lightroom_sync event from the message queue."""
    from photocurate.api.deps import get_blob_store

    event = json.loads(msg)
    photo_id = uuid.UUID(event["photo_id"])
    session_id = uuid.UUID(event["session_id"])
    user_id = uuid.UUID(event["user_id"])
    pending_task_id = uuid.UUID(event["pending_task_id"]) if event.get("pending_task_id") else None
    blob_store = get_blob_store()

    logger.info("Lightroom sync event: photo=%s session=%s", photo_id, session_id)
    await sync_photo_to_lightroom(photo_id, session_id, user_id, blob_store, pending_task_id)


async def handle_lightroom_flag_event(msg: bytes) -> None:
    """Process a photo.lightroom_flag event from the message queue."""
    event = json.loads(msg)
    selection_id = uuid.UUID(event["selection_id"])
    user_id = uuid.UUID(event["user_id"])
    pending_task_id = uuid.UUID(event["pending_task_id"]) if event.get("pending_task_id") else None

    logger.info("Lightroom flag event: selection=%s", selection_id)
    await flag_selection_in_lightroom(selection_id, user_id, pending_task_id)
