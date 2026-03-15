"""Google Drive delivery provider."""

from __future__ import annotations

import logging

import httpx

from photocurate.core.delivery import DeliveryProvider

logger = logging.getLogger(__name__)

DRIVE_API = "https://www.googleapis.com/drive/v3"
UPLOAD_API = "https://www.googleapis.com/upload/drive/v3"


class GoogleDriveProvider(DeliveryProvider):
    """Upload files to Google Drive via Drive API v3."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=60.0)

    async def create_folder(self, folder_name: str, access_token: str) -> str:
        resp = await self._client.post(
            f"{DRIVE_API}/files",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
            },
        )
        resp.raise_for_status()
        return resp.json()["id"]

    async def upload_file(
        self,
        folder_id: str,
        filename: str,
        data: bytes,
        content_type: str,
        access_token: str,
    ) -> None:
        # Use multipart upload (metadata + media) for files up to 5MB.
        # For larger files, a resumable upload should be used.
        metadata = {"name": filename, "parents": [folder_id]}

        import json as _json  # noqa: F811

        boundary = "photocurate_boundary"
        body = (
            f"--{boundary}\r\n"
            f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
            f"{_json.dumps(metadata)}\r\n"
            f"--{boundary}\r\n"
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode() + data + f"\r\n--{boundary}--".encode()

        resp = await self._client.post(
            f"{UPLOAD_API}/files?uploadType=multipart",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": f"multipart/related; boundary={boundary}",
            },
            content=body,
        )
        resp.raise_for_status()
        logger.info("Uploaded %s to Google Drive folder %s", filename, folder_id)

    async def get_share_link(self, folder_id: str, access_token: str) -> str:
        # Create a "reader" permission for anyone with the link
        await self._client.post(
            f"{DRIVE_API}/files/{folder_id}/permissions",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"role": "reader", "type": "anyone"},
        )
        resp = await self._client.get(
            f"{DRIVE_API}/files/{folder_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"fields": "webViewLink"},
        )
        resp.raise_for_status()
        return resp.json().get("webViewLink", f"https://drive.google.com/drive/folders/{folder_id}")
