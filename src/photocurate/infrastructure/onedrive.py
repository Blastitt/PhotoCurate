"""OneDrive delivery provider — via Microsoft Graph API."""

from __future__ import annotations

import logging

import httpx

from photocurate.core.delivery import DeliveryProvider

logger = logging.getLogger(__name__)

GRAPH_API = "https://graph.microsoft.com/v1.0"


class OneDriveProvider(DeliveryProvider):
    """Upload files to OneDrive via Microsoft Graph API."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=60.0)

    async def create_folder(self, folder_name: str, access_token: str) -> str:
        resp = await self._client.post(
            f"{GRAPH_API}/me/drive/root/children",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "name": folder_name,
                "folder": {},
                "@microsoft.graph.conflictBehavior": "rename",
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
        # Simple upload for files ≤4MB. For larger files, use upload sessions.
        resp = await self._client.put(
            f"{GRAPH_API}/me/drive/items/{folder_id}:/{filename}:/content",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": content_type,
            },
            content=data,
        )
        resp.raise_for_status()
        logger.info("Uploaded %s to OneDrive folder %s", filename, folder_id)

    async def get_share_link(self, folder_id: str, access_token: str) -> str:
        resp = await self._client.post(
            f"{GRAPH_API}/me/drive/items/{folder_id}/createLink",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"type": "view", "scope": "anonymous"},
        )
        resp.raise_for_status()
        link = resp.json().get("link", {})
        return link.get("webUrl", "")
