"""Client management routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from photocurate.api.deps import CurrentUser, DbSession
from photocurate.core.models.tenant import Client
from photocurate.core.schemas.session import ClientCreate, ClientResponse

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(body: ClientCreate, db: DbSession, user: CurrentUser):
    """Create a new client for the current tenant."""
    client = Client(
        tenant_id=user.tenant_id,
        name=body.name,
        email=body.email,
    )
    db.add(client)
    await db.flush()
    await db.refresh(client)
    return client


@router.get("", response_model=list[ClientResponse])
async def list_clients(db: DbSession, user: CurrentUser):
    """List all clients for the current tenant."""
    result = await db.execute(
        select(Client)
        .where(Client.tenant_id == user.tenant_id)
        .order_by(Client.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(client_id: uuid.UUID, db: DbSession, user: CurrentUser):
    """Get a single client."""
    result = await db.execute(
        select(Client).where(Client.id == client_id, Client.tenant_id == user.tenant_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return client


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(client_id: uuid.UUID, db: DbSession, user: CurrentUser):
    """Delete a client."""
    result = await db.execute(
        select(Client).where(Client.id == client_id, Client.tenant_id == user.tenant_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    await db.delete(client)
