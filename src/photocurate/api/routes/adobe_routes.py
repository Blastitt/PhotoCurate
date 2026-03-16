"""Adobe Lightroom OAuth2 and integration routes."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select, update

from photocurate.api.deps import BlobStoreDep, CurrentUser, DbSession, QueueDep
from photocurate.config import settings
from photocurate.core.models.adobe import AdobeToken, LightroomPendingTask
from photocurate.infrastructure.adobe_lightroom import LightroomAPIError, LightroomClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/adobe", tags=["adobe"])

ADOBE_IMS_AUTH_URL = "https://ims-na1.adobelogin.com/ims/authorize/v2"
ADOBE_IMS_TOKEN_URL = "https://ims-na1.adobelogin.com/ims/token/v3"
ADOBE_IMS_REVOKE_URL = "https://ims-na1.adobelogin.com/ims/revoke"
ADOBE_SCOPES = "openid,creative_sdk,lr_partner_apis,lr_partner_rendition_apis"


# ── Helpers ────────────────────────────────────────────────────────────

def _require_adobe_enabled() -> None:
    if not settings.adobe_enabled:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Adobe integration not configured")


def _get_fernet() -> Fernet:
    key = settings.adobe_token_encryption_key
    if not key:
        raise HTTPException(status_code=500, detail="Adobe token encryption key not configured")
    return Fernet(key.encode())


def _encrypt(value: str) -> str:
    return _get_fernet().encrypt(value.encode()).decode()


def _decrypt(value: str) -> str:
    try:
        return _get_fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        raise HTTPException(status_code=500, detail="Failed to decrypt Adobe token")


_lr_client: LightroomClient | None = None


def _get_lr_client() -> LightroomClient:
    global _lr_client
    if _lr_client is None:
        _lr_client = LightroomClient()
    return _lr_client


async def _refresh_if_needed(token_row: AdobeToken, db: Any) -> str:
    """Return a valid access_token, refreshing via Adobe IMS if near-expiry."""
    if token_row.expires_at > datetime.now(timezone.utc) + timedelta(minutes=5):
        return _decrypt(token_row.access_token)

    import httpx

    resp = await httpx.AsyncClient().post(
        ADOBE_IMS_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": settings.adobe_client_id,
            "client_secret": settings.adobe_client_secret,
            "refresh_token": _decrypt(token_row.refresh_token),
        },
    )
    if resp.status_code != 200:
        raise LightroomAPIError(401, "Token refresh failed")

    data = resp.json()
    new_access = data["access_token"]
    expires_in = data.get("expires_in", 3600)

    token_row.access_token = _encrypt(new_access)
    token_row.expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    if "refresh_token" in data:
        token_row.refresh_token = _encrypt(data["refresh_token"])
    await db.commit()

    return new_access


# ── OAuth2 Endpoints ──────────────────────────────────────────────────

class AdobeStatusResponse(BaseModel):
    connected: bool
    catalog_id: str | None = None
    pending_task_count: int = 0


class AdobeConnectResponse(BaseModel):
    redirect_url: str


@router.get("/connect")
async def adobe_connect(user: CurrentUser) -> AdobeConnectResponse:
    """Redirect the user to Adobe IMS authorization."""
    _require_adobe_enabled()

    params = urlencode({
        "client_id": settings.adobe_client_id,
        "redirect_uri": settings.adobe_oauth_redirect_uri,
        "scope": ADOBE_SCOPES,
        "response_type": "code",
        "state": str(user.id),
    })
    return AdobeConnectResponse(redirect_url=f"{ADOBE_IMS_AUTH_URL}?{params}")


@router.get("/callback")
async def adobe_callback(
    code: str = Query(...),
    state: str = Query(...),
    *,
    db: DbSession,
    queue: QueueDep,
) -> dict[str, str]:
    """Exchange authorization code for tokens and store them."""
    _require_adobe_enabled()

    import httpx as _httpx

    resp = await _httpx.AsyncClient().post(
        ADOBE_IMS_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": settings.adobe_client_id,
            "client_secret": settings.adobe_client_secret,
            "code": code,
            "redirect_uri": settings.adobe_oauth_redirect_uri,
        },
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Adobe token exchange failed")

    data = resp.json()
    access_token = data["access_token"]
    refresh_token = data["refresh_token"]
    expires_in = data.get("expires_in", 3600)

    # Verify Lightroom access by fetching catalog
    lr = _get_lr_client()
    try:
        catalog_id = await lr.get_catalog_id(access_token)
    except LightroomAPIError as e:
        if e.status_code == 403:
            raise HTTPException(status_code=400, detail="Lightroom subscription required")
        raise HTTPException(status_code=502, detail=f"Failed to access Lightroom catalog: {e.detail}")

    import uuid as _uuid

    user_id = _uuid.UUID(state)

    # Upsert token
    existing = await db.execute(select(AdobeToken).where(AdobeToken.user_id == user_id))
    token_row = existing.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if token_row:
        token_row.access_token = _encrypt(access_token)
        token_row.refresh_token = _encrypt(refresh_token)
        token_row.expires_at = now + timedelta(seconds=expires_in)
        token_row.lightroom_catalog_id = catalog_id
        token_row.updated_at = now
    else:
        token_row = AdobeToken(
            user_id=user_id,
            access_token=_encrypt(access_token),
            refresh_token=_encrypt(refresh_token),
            expires_at=now + timedelta(seconds=expires_in),
            lightroom_catalog_id=catalog_id,
        )
        db.add(token_row)

    await db.commit()

    # Drain pending tasks
    result = await db.execute(
        select(LightroomPendingTask).where(
            LightroomPendingTask.user_id == user_id,
            LightroomPendingTask.status == "pending",
        )
    )
    pending_tasks = result.scalars().all()
    for task in pending_tasks:
        topic = f"photo.lightroom_{task.task_type}"
        await queue.publish(topic, json.dumps(task.payload).encode())
        task.status = "processing"
    if pending_tasks:
        await db.commit()
        logger.info("Drained %d pending Lightroom tasks for user %s", len(pending_tasks), user_id)

    return {"detail": "Adobe Lightroom connected successfully"}


@router.delete("/disconnect")
async def adobe_disconnect(user: CurrentUser, db: DbSession) -> dict[str, str]:
    """Revoke tokens and remove the connection."""
    _require_adobe_enabled()

    result = await db.execute(select(AdobeToken).where(AdobeToken.user_id == user.id))
    token_row = result.scalar_one_or_none()
    if not token_row:
        raise HTTPException(status_code=404, detail="No Adobe connection found")

    # Best-effort revoke at Adobe IMS
    try:
        import httpx as _httpx

        await _httpx.AsyncClient().post(
            ADOBE_IMS_REVOKE_URL,
            data={
                "client_id": settings.adobe_client_id,
                "client_secret": settings.adobe_client_secret,
                "token": _decrypt(token_row.access_token),
            },
        )
    except Exception:
        logger.warning("Failed to revoke Adobe token at IMS, removing locally")

    await db.delete(token_row)
    await db.commit()
    return {"detail": "Adobe Lightroom disconnected"}


@router.get("/status")
async def adobe_status(user: CurrentUser, db: DbSession) -> AdobeStatusResponse:
    """Return connection status and pending task count."""
    _require_adobe_enabled()

    result = await db.execute(select(AdobeToken).where(AdobeToken.user_id == user.id))
    token_row = result.scalar_one_or_none()

    if not token_row:
        return AdobeStatusResponse(connected=False)

    # Count pending tasks
    count_result = await db.execute(
        select(func.count()).select_from(LightroomPendingTask).where(
            LightroomPendingTask.user_id == user.id,
            LightroomPendingTask.status == "pending",
        )
    )
    pending_count = count_result.scalar() or 0

    return AdobeStatusResponse(
        connected=True,
        catalog_id=token_row.lightroom_catalog_id,
        pending_task_count=pending_count,
    )


@router.post("/retry-pending")
async def adobe_retry_pending(
    user: CurrentUser, db: DbSession, queue: QueueDep
) -> dict[str, Any]:
    """Re-drain all pending tasks for the current user."""
    _require_adobe_enabled()

    # Verify user has valid tokens
    result = await db.execute(select(AdobeToken).where(AdobeToken.user_id == user.id))
    token_row = result.scalar_one_or_none()
    if not token_row:
        raise HTTPException(status_code=400, detail="No Adobe connection found. Connect first.")

    result = await db.execute(
        select(LightroomPendingTask).where(
            LightroomPendingTask.user_id == user.id,
            LightroomPendingTask.status == "pending",
        )
    )
    pending_tasks = result.scalars().all()

    for task in pending_tasks:
        topic = f"photo.lightroom_{task.task_type}"
        await queue.publish(topic, json.dumps(task.payload).encode())
        task.status = "processing"

    await db.commit()

    return {"retried": len(pending_tasks)}


# ── Browse Endpoints ──────────────────────────────────────────────────

@router.get("/albums")
async def list_albums(
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(50, le=100),
    after: str | None = Query(None),
) -> dict[str, Any]:
    """List user's Lightroom albums."""
    _require_adobe_enabled()

    result = await db.execute(select(AdobeToken).where(AdobeToken.user_id == user.id))
    token_row = result.scalar_one_or_none()
    if not token_row:
        raise HTTPException(status_code=400, detail="Adobe not connected")

    access_token = await _refresh_if_needed(token_row, db)
    lr = _get_lr_client()

    try:
        return await lr.list_albums(token_row.lightroom_catalog_id, access_token, limit=limit, after=after)
    except LightroomAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.get("/albums/{album_id}/assets")
async def list_album_assets(
    album_id: str,
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(50, le=100),
    after: str | None = Query(None),
) -> dict[str, Any]:
    """List assets within a specific Lightroom album."""
    _require_adobe_enabled()

    result = await db.execute(select(AdobeToken).where(AdobeToken.user_id == user.id))
    token_row = result.scalar_one_or_none()
    if not token_row:
        raise HTTPException(status_code=400, detail="Adobe not connected")

    access_token = await _refresh_if_needed(token_row, db)
    lr = _get_lr_client()

    try:
        return await lr.list_album_assets(
            token_row.lightroom_catalog_id, album_id, access_token, limit=limit, after=after
        )
    except LightroomAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.get("/assets")
async def list_assets(
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(50, le=100),
    after: str | None = Query(None),
) -> dict[str, Any]:
    """List all user's Lightroom assets."""
    _require_adobe_enabled()

    result = await db.execute(select(AdobeToken).where(AdobeToken.user_id == user.id))
    token_row = result.scalar_one_or_none()
    if not token_row:
        raise HTTPException(status_code=400, detail="Adobe not connected")

    access_token = await _refresh_if_needed(token_row, db)
    lr = _get_lr_client()

    try:
        return await lr.list_assets(token_row.lightroom_catalog_id, access_token, limit=limit, after=after)
    except LightroomAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


# ── Feature flags ─────────────────────────────────────────────────────

features_router = APIRouter(prefix="/config", tags=["config"])


@features_router.get("/features")
async def get_features() -> dict[str, bool]:
    """Return feature flags. Public endpoint (no auth)."""
    return {
        "adobe_lightroom": settings.adobe_enabled,
    }
