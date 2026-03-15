"""DB-backed route tests for authentication and current-user resolution."""

from __future__ import annotations

import uuid

import pytest
from jose import jwt
from sqlalchemy import select

from photocurate.api.auth import decode_access_token
from photocurate.config import settings
from photocurate.core.models.tenant import Tenant, User


@pytest.mark.asyncio
async def test_register_creates_tenant_and_admin_user(api_client, db_session):
    payload = {
        "email": "new-user@example.com",
        "name": "New User",
        "password": "s3cret-pass",
        "tenant_name": "New Tenant",
        "tenant_slug": "new-tenant",
    }

    response = await api_client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 201
    token = response.json()["access_token"]
    claims = decode_access_token(token)

    user = (await db_session.execute(select(User).where(User.email == payload["email"]))).scalar_one()
    tenant = (await db_session.execute(select(Tenant).where(Tenant.slug == payload["tenant_slug"]))).scalar_one()

    assert claims["sub"] == str(user.id)
    assert claims["tenant_id"] == str(tenant.id)
    assert user.password_hash != payload["password"]
    assert user.role == "admin"
    assert tenant.name == payload["tenant_name"]


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email(api_client, auth_context_factory, db_session):
    await auth_context_factory(email="duplicate@example.com")

    response = await api_client.post(
        "/api/v1/auth/register",
        json={
            "email": "duplicate@example.com",
            "name": "Second User",
            "password": "another-pass",
            "tenant_name": "Another Tenant",
            "tenant_slug": "another-tenant",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"
    count = len((await db_session.execute(select(User).where(User.email == "duplicate@example.com"))).scalars().all())
    assert count == 1


@pytest.mark.asyncio
async def test_register_rejects_duplicate_tenant_slug(api_client, auth_context_factory, db_session):
    await auth_context_factory(tenant_slug="existing-tenant")

    response = await api_client.post(
        "/api/v1/auth/register",
        json={
            "email": "fresh@example.com",
            "name": "Fresh User",
            "password": "fresh-pass",
            "tenant_name": "Clashing Tenant",
            "tenant_slug": "existing-tenant",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Tenant slug already taken"
    count = len((await db_session.execute(select(Tenant).where(Tenant.slug == "existing-tenant"))).scalars().all())
    assert count == 1


@pytest.mark.asyncio
async def test_login_returns_access_token_for_valid_credentials(api_client, auth_context_factory):
    auth_context = await auth_context_factory(email="login@example.com", password="login-pass")

    response = await api_client.post(
        "/api/v1/auth/login",
        json={"email": auth_context.user.email, "password": auth_context.password},
    )

    assert response.status_code == 200
    claims = decode_access_token(response.json()["access_token"])
    assert claims["sub"] == str(auth_context.user.id)
    assert claims["tenant_id"] == str(auth_context.tenant.id)
    assert claims["role"] == auth_context.user.role


@pytest.mark.asyncio
async def test_login_rejects_invalid_password(api_client, auth_context_factory):
    auth_context = await auth_context_factory(email="invalid-pass@example.com", password="correct-pass")

    response = await api_client.post(
        "/api/v1/auth/login",
        json={"email": auth_context.user.email, "password": "wrong-pass"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_me_returns_current_user(api_client, auth_context_factory):
    auth_context = await auth_context_factory(email="me@example.com")

    response = await api_client.get("/api/v1/auth/me", headers=auth_context.headers)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(auth_context.user.id)
    assert data["tenant_id"] == str(auth_context.tenant.id)
    assert data["email"] == auth_context.user.email


@pytest.mark.asyncio
async def test_me_requires_bearer_credentials(api_client):
    response = await api_client.get("/api/v1/auth/me")

    assert response.status_code == 403
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_me_rejects_malformed_token(api_client):
    response = await api_client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


@pytest.mark.asyncio
async def test_me_rejects_token_without_subject(api_client, auth_context_factory):
    auth_context = await auth_context_factory()
    token = jwt.encode(
        {
            "tenant_id": str(auth_context.tenant.id),
            "role": auth_context.user.role,
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    response = await api_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


@pytest.mark.asyncio
async def test_me_rejects_token_for_deleted_user(api_client, auth_context_factory, db_session):
    auth_context = await auth_context_factory(email="deleted@example.com")
    user = (await db_session.execute(select(User).where(User.id == auth_context.user.id))).scalar_one()
    await db_session.delete(user)
    await db_session.commit()

    response = await api_client.get("/api/v1/auth/me", headers=auth_context.headers)

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"