"""Dropbox delivery provider."""

from __future__ import annotations

import logging

import httpx

from photocurate.core.delivery import DeliveryProvider

logger = logging.getLogger(__name__)

DROPBOX_API = "https://api.dropboxapi.com/2"
DROPBOX_CONTENT_API = "https://content.dropboxapi.com/2"


class DropboxProvider(DeliveryProvider):
    """Upload files to Dropbox via Dropbox API v2."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=60.0)

    async def create_folder(self, folder_name: str, access_token: str) -> str:
        path = f"/{folder_name}"
        resp = await self._client.post(
            f"{DROPBOX_API}/files/create_folder_v2",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"path": path, "autorename": True},
        )
        resp.raise_for_status()
        metadata = resp.json().get("metadata", {})
        return metadata.get("path_lower", path)

    async def upload_file(
        self,
        folder_id: str,
        filename: str,
        data: bytes,
        content_type: str,
        access_token: str,
    ) -> None:
        import json as _json

        path = f"{folder_id}/{filename}"
        arg = {"path": path, "mode": "add", "autorename": True, "mute": False}
        resp = await self._client.post(
            f"{DROPBOX_CONTENT_API}/files/upload",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/octet-stream",
                "Dropbox-API-Arg": _json.dumps(arg),
            },
            content=data,
        )
        resp.raise_for_status()
        logger.info("Uploaded %s to Dropbox %s", filename, path)

    async def get_share_link(self, folder_id: str, access_token: str) -> str:
        resp = await self._client.post(
            f"{DROPBOX_API}/sharing/create_shared_link_with_settings",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "path": folder_id,
                "settings": {"requested_visibility": "public", "audience": "public"},
            },
        )
        if resp.status_code == 409:
            # Link already exists — fetch it
            resp2 = await self._client.post(
                f"{DROPBOX_API}/sharing/list_shared_links",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"path": folder_id, "direct_only": True},
            )
            resp2.raise_for_status()
            links = resp2.json().get("links", [])
            if links:
                return links[0].get("url", "")
            return ""
        resp.raise_for_status()
        return resp.json().get("url", "")
