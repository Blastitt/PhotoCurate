"""FastAPI dependency injection — database sessions, current user, blob store, queue."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photocurate.api.auth import decode_access_token
from photocurate.core.database import get_db
from photocurate.core.models.tenant import User
from photocurate.core.queue import MessageQueue
from photocurate.core.storage import BlobStore
from photocurate.infrastructure.factory import create_blob_store, create_message_queue

security = HTTPBearer()

# Singleton instances (created once, reused)
_blob_store: BlobStore | None = None
_message_queue: MessageQueue | None = None


def get_blob_store() -> BlobStore:
    """Get or create the BlobStore singleton."""
    global _blob_store
    if _blob_store is None:
        _blob_store = create_blob_store()
    return _blob_store


def get_message_queue() -> MessageQueue:
    """Get or create the MessageQueue singleton."""
    global _message_queue
    if _message_queue is None:
        _message_queue = create_message_queue()
    return _message_queue


def reset_dependency_singletons() -> None:
    """Reset cached infrastructure singletons.

    Tests use this to prevent state leakage across cases.
    """
    global _blob_store, _message_queue
    _blob_store = None
    _message_queue = None


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Decode JWT and return the authenticated User object."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(credentials.credentials)
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


# Type aliases for cleaner route signatures
DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
BlobStoreDep = Annotated[BlobStore, Depends(get_blob_store)]
QueueDep = Annotated[MessageQueue, Depends(get_message_queue)]
