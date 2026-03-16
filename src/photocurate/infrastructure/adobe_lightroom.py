"""Adobe Lightroom API async client.

Wraps the Lightroom REST API (https://lr.adobe.io/v2/) using httpx.
All methods require a valid OAuth2 access_token obtained from Adobe IMS.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from photocurate.config import settings

logger = logging.getLogger(__name__)

LR_API_BASE = "https://lr.adobe.io/v2"
CHUNK_SIZE = 200 * 1024 * 1024  # 200 MB — Lightroom single-upload limit


class LightroomAPIError(Exception):
    """Raised when a Lightroom API call fails."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Lightroom API {status_code}: {detail}")


class LightroomClient:
    """Async client for the Adobe Lightroom API."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=120.0)

    def _headers(self, access_token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "X-API-Key": settings.adobe_client_id or "",
        }

    async def _request(
        self,
        method: str,
        path: str,
        access_token: str,
        *,
        json: dict | None = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        hdrs = self._headers(access_token)
        if headers:
            hdrs.update(headers)

        resp = await self._client.request(
            method,
            f"{LR_API_BASE}{path}",
            headers=hdrs,
            json=json,
            content=content,
            params=params,
        )

        if resp.status_code == 401:
            raise LightroomAPIError(401, "Adobe token invalid or expired")
        if resp.status_code == 403:
            raise LightroomAPIError(403, "Lightroom subscription required or access denied")
        if resp.status_code == 429:
            raise LightroomAPIError(429, "Rate limited by Adobe API")
        if resp.status_code >= 400:
            detail = resp.text[:500]
            raise LightroomAPIError(resp.status_code, detail)

        return resp

    # ── Catalog ───────────────────────────────────────────────────────────

    async def get_catalog_id(self, access_token: str) -> str:
        """GET /v2/catalog → returns the user's catalog UUID."""
        resp = await self._request("GET", "/catalog", access_token)
        return resp.json()["id"]

    # ── Albums ────────────────────────────────────────────────────────────

    async def list_albums(
        self,
        catalog_id: str,
        access_token: str,
        limit: int = 100,
        after: str | None = None,
    ) -> dict[str, Any]:
        """GET /v2/catalogs/{id}/albums → paginated album list."""
        params: dict[str, Any] = {"limit": limit}
        if after:
            params["after"] = after
        resp = await self._request(
            "GET", f"/catalogs/{catalog_id}/albums", access_token, params=params
        )
        return resp.json()

    async def list_album_assets(
        self,
        catalog_id: str,
        album_id: str,
        access_token: str,
        limit: int = 100,
        after: str | None = None,
    ) -> dict[str, Any]:
        """GET /v2/catalogs/{id}/albums/{album_id}/assets → paginated asset list for an album."""
        params: dict[str, Any] = {"limit": limit}
        if after:
            params["after"] = after
        resp = await self._request(
            "GET",
            f"/catalogs/{catalog_id}/albums/{album_id}/assets",
            access_token,
            params=params,
        )
        return resp.json()

    async def list_all_album_assets(
        self, catalog_id: str, album_id: str, access_token: str
    ) -> list[dict[str, Any]]:
        """Iterate all pages of an album's assets and return the full list."""
        all_assets: list[dict[str, Any]] = []
        after: str | None = None
        while True:
            data = await self.list_album_assets(
                catalog_id, album_id, access_token, limit=100, after=after
            )
            resources = data.get("resources", [])
            all_assets.extend(resources)
            # Pagination: Lightroom uses 'links.next' or returns fewer than limit
            links = data.get("links", {})
            if "next" not in links or len(resources) == 0:
                break
            after = resources[-1]["id"]
        return all_assets

    async def create_album(
        self, catalog_id: str, album_name: str, access_token: str
    ) -> str:
        """PUT /v2/catalogs/{id}/albums/{album_id} → create album, return album_id."""
        album_id = str(uuid.uuid4()).replace("-", "")
        await self._request(
            "PUT",
            f"/catalogs/{catalog_id}/albums/{album_id}",
            access_token,
            json={
                "payload": {
                    "name": album_name,
                    "userCreated": datetime.now(timezone.utc).isoformat(),
                }
            },
        )
        return album_id

    async def add_assets_to_album(
        self,
        catalog_id: str,
        album_id: str,
        asset_ids: list[str],
        access_token: str,
    ) -> None:
        """PUT /v2/catalogs/{id}/albums/{album_id}/assets → add assets to album."""
        resources = {aid: {"payload": {}} for aid in asset_ids}
        await self._request(
            "PUT",
            f"/catalogs/{catalog_id}/albums/{album_id}/assets",
            access_token,
            json={"resources": resources},
        )

    # ── Assets ────────────────────────────────────────────────────────────

    async def list_assets(
        self,
        catalog_id: str,
        access_token: str,
        limit: int = 100,
        after: str | None = None,
    ) -> dict[str, Any]:
        """GET /v2/catalogs/{id}/assets → paginated asset list."""
        params: dict[str, Any] = {"limit": limit, "subtype": "image"}
        if after:
            params["after"] = after
        resp = await self._request(
            "GET", f"/catalogs/{catalog_id}/assets", access_token, params=params
        )
        return resp.json()

    async def get_asset(
        self, catalog_id: str, asset_id: str, access_token: str
    ) -> dict[str, Any]:
        """GET /v2/catalogs/{id}/assets/{asset_id} → asset metadata."""
        resp = await self._request(
            "GET", f"/catalogs/{catalog_id}/assets/{asset_id}", access_token
        )
        return resp.json()

    async def create_asset(
        self,
        catalog_id: str,
        asset_id: str,
        filename: str,
        access_token: str,
    ) -> None:
        """PUT /v2/catalogs/{id}/assets/{asset_id} → create asset record."""
        await self._request(
            "PUT",
            f"/catalogs/{catalog_id}/assets/{asset_id}",
            access_token,
            json={
                "subtype": "image",
                "payload": {
                    "importSource": {
                        "fileName": filename,
                        "importedOnDevice": "PhotoCurate",
                        "importTimestamp": datetime.now(timezone.utc).isoformat(),
                    }
                },
            },
        )

    async def upload_original(
        self,
        catalog_id: str,
        asset_id: str,
        data: bytes,
        content_type: str,
        access_token: str,
    ) -> None:
        """PUT /v2/catalogs/{id}/assets/{asset_id}/master → upload original file.

        Uses chunked upload with Content-Range header for files > 200 MB.
        """
        path = f"/catalogs/{catalog_id}/assets/{asset_id}/master"

        if len(data) <= CHUNK_SIZE:
            await self._request(
                "PUT",
                path,
                access_token,
                content=data,
                headers={"Content-Type": content_type},
            )
        else:
            # Chunked upload
            total = len(data)
            offset = 0
            while offset < total:
                end = min(offset + CHUNK_SIZE, total)
                chunk = data[offset:end]
                await self._request(
                    "PUT",
                    path,
                    access_token,
                    content=chunk,
                    headers={
                        "Content-Type": content_type,
                        "Content-Range": f"bytes {offset}-{end - 1}/{total}",
                    },
                )
                offset = end
                logger.debug("Uploaded chunk %d-%d/%d for asset %s", offset, end, total, asset_id)

    # ── Renditions ────────────────────────────────────────────────────────

    async def get_rendition(
        self,
        catalog_id: str,
        asset_id: str,
        rendition_type: str,
        access_token: str,
    ) -> bytes:
        """GET /v2/catalogs/{id}/assets/{asset_id}/renditions/{type} → rendition bytes.

        rendition_type: thumbnail2x, 1280, 2048, fullsize
        """
        resp = await self._request(
            "GET",
            f"/catalogs/{catalog_id}/assets/{asset_id}/renditions/{rendition_type}",
            access_token,
        )
        return resp.content

    # ── Flags ─────────────────────────────────────────────────────────────

    async def set_asset_flag(
        self,
        catalog_id: str,
        asset_id: str,
        flag: str,
        access_token: str,
    ) -> None:
        """Set pick/reject/unflagged flag on an asset.

        flag: "pick", "reject", or "unflagged"
        """
        if flag not in ("pick", "reject", "unflagged"):
            raise ValueError(f"Invalid flag value: {flag}")
        await self._request(
            "PUT",
            f"/catalogs/{catalog_id}/assets/{asset_id}",
            access_token,
            json={"payload": {"develop": {"flag": flag}}},
        )
