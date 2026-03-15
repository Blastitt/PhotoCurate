"""Delivery worker — uploads edited photos to cloud storage (Google Drive, Dropbox, OneDrive).

Pipeline:
  1. Look up the delivery record and associated edited photos
  2. Resolve the appropriate cloud storage provider
  3. Create a folder in the client's storage
  4. Download edited photos from blob storage and upload to cloud provider
  5. Generate a shareable link
  6. Update delivery status and folder URL
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update

from photocurate.core.database import async_session_factory
from photocurate.core.delivery import DeliveryProvider
from photocurate.core.models.gallery import Delivery, EditedPhoto
from photocurate.core.models.session import ShootSession
from photocurate.core.storage import BlobStore

logger = logging.getLogger(__name__)


def _get_provider(provider_name: str) -> DeliveryProvider:
    """Instantiate the correct delivery provider."""
    if provider_name == "google_drive":
        from photocurate.infrastructure.google_drive import GoogleDriveProvider
        return GoogleDriveProvider()
    elif provider_name == "dropbox":
        from photocurate.infrastructure.dropbox import DropboxProvider
        return DropboxProvider()
    elif provider_name == "onedrive":
        from photocurate.infrastructure.onedrive import OneDriveProvider
        return OneDriveProvider()
    else:
        raise ValueError(f"Unknown delivery provider: {provider_name}")


async def deliver_photos(
    delivery_id: uuid.UUID,
    access_token: str,
    blob_store: BlobStore,
) -> None:
    """Execute the delivery pipeline for a single delivery."""
    async with async_session_factory() as db:
        # Load delivery record
        result = await db.execute(select(Delivery).where(Delivery.id == delivery_id))
        delivery = result.scalar_one_or_none()
        if not delivery:
            logger.error("Delivery %s not found", delivery_id)
            return

        # Set in-progress
        delivery.status = "in_progress"
        delivery.started_at = datetime.now(timezone.utc)
        await db.commit()

        try:
            # Load session info for folder naming
            sess_result = await db.execute(
                select(ShootSession).where(ShootSession.id == delivery.session_id)
            )
            session = sess_result.scalar_one_or_none()
            folder_name = f"PhotoCurate - {session.title}" if session else f"PhotoCurate - {delivery.session_id}"

            # Load edited photos for this session
            photos_result = await db.execute(
                select(EditedPhoto).where(EditedPhoto.session_id == delivery.session_id)
            )
            edited_photos = photos_result.scalars().all()

            if not edited_photos:
                delivery.status = "completed"
                delivery.photo_count = 0
                delivery.completed_at = datetime.now(timezone.utc)
                await db.commit()
                logger.info("Delivery %s: no edited photos to deliver", delivery_id)
                return

            # Get provider
            provider = _get_provider(delivery.provider)

            # Create folder
            folder_id = await provider.create_folder(folder_name, access_token)
            logger.info("Created folder '%s' (%s) on %s", folder_name, folder_id, delivery.provider)

            # Upload each photo
            uploaded_count = 0
            for edited_photo in edited_photos:
                try:
                    data = await blob_store.download(edited_photo.edited_key)
                    # Derive filename from the key
                    filename = edited_photo.edited_key.rsplit("/", 1)[-1]
                    content_type = "image/jpeg"  # edited photos are typically JPEG
                    if filename.endswith(".webp"):
                        content_type = "image/webp"
                    elif filename.endswith(".png"):
                        content_type = "image/png"

                    await provider.upload_file(folder_id, filename, data, content_type, access_token)
                    uploaded_count += 1
                except Exception:
                    logger.exception(
                        "Failed to upload edited photo %s for delivery %s",
                        edited_photo.id, delivery_id,
                    )

            # Get share link
            share_url = await provider.get_share_link(folder_id, access_token)

            # Update delivery record
            delivery.status = "completed"
            delivery.photo_count = uploaded_count
            delivery.provider_folder_url = share_url
            delivery.completed_at = datetime.now(timezone.utc)
            await db.commit()

            logger.info(
                "Delivery %s completed: %d photos to %s (%s)",
                delivery_id, uploaded_count, delivery.provider, share_url,
            )

        except Exception as exc:
            logger.exception("Delivery %s failed", delivery_id)
            delivery.status = "failed"
            delivery.error_message = str(exc)[:500]
            await db.commit()


async def handle_delivery_event(msg: bytes) -> None:
    """Process a delivery event from the message queue.

    Expected event shape:
      {
        "type": "delivery.execute",
        "delivery_id": "...",
        "access_token": "..."
      }
    """
    from photocurate.api.deps import get_blob_store

    event = json.loads(msg)
    delivery_id = uuid.UUID(event["delivery_id"])
    access_token = event.get("access_token", "")
    blob_store = get_blob_store()

    logger.info("Delivery event received: delivery=%s", delivery_id)
    await deliver_photos(delivery_id, access_token, blob_store)
