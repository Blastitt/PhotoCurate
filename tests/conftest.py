"""Shared backend test fixtures for DB-backed API and worker tests."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from photocurate.api import deps as api_deps
from photocurate.api.auth import create_access_token, hash_password
from photocurate.config import settings
from photocurate.core.models.base import Base
from photocurate.core.models.gallery import Delivery, EditedPhoto, Gallery, GalleryPhoto, Selection, SelectionPhoto
from photocurate.core.models.session import AIScore, Photo, ShootSession
from photocurate.core.models.tenant import Client, Tenant, TenantBranding, User
from photocurate.main import app

# Ensure all models are registered on Base.metadata before create_all.
assert Tenant and ShootSession and Gallery

TEST_DATABASE_NAME = "photocurate_test"
TEST_DATABASE_URL_ENV = "PHOTOCURATE_TEST_DATABASE_URL"
DEFAULT_TEST_DATABASE_URL = (
    "postgresql+asyncpg://photocurate:photocurate@127.0.0.1:5433/photocurate_test"
)
TEST_COMPOSE_FILE = "docker-compose.test.yml"


class FakeBlobStore:
    """Simple in-memory blob store for deterministic API and worker tests."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.generated_upload_urls: list[str] = []
        self.generated_download_urls: list[str] = []
        self.deleted_keys: list[str] = []

    async def generate_presigned_upload_url(self, key: str, ttl: timedelta = timedelta(minutes=15)) -> str:
        del ttl
        url = f"https://blob.test/upload/{quote(key, safe='/')}"
        self.generated_upload_urls.append(url)
        return url

    async def generate_presigned_download_url(self, key: str, ttl: timedelta = timedelta(hours=1)) -> str:
        del ttl
        url = f"https://blob.test/download/{quote(key, safe='/')}"
        self.generated_download_urls.append(url)
        return url

    async def download(self, key: str) -> bytes:
        return self.objects[key]

    async def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        del content_type
        self.objects[key] = data

    async def delete(self, key: str) -> None:
        self.deleted_keys.append(key)
        self.objects.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self.objects

    async def get_size(self, key: str) -> int:
        return len(self.objects[key])


class FakeQueue:
    """Recording queue fake for route and worker assertions."""

    def __init__(self) -> None:
        self.published: list[tuple[str, bytes]] = []
        self.subscriptions: list[tuple[str, Callable[[bytes], Any]]] = []
        self.connected = False
        self.disconnected = False

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.disconnected = True

    async def publish(self, topic: str, msg: bytes) -> None:
        self.published.append((topic, msg))

    async def subscribe(self, topic: str, handler: Callable[[bytes], Any]) -> None:
        self.subscriptions.append((topic, handler))


@dataclass
class AuthContext:
    tenant: Tenant
    user: User
    password: str
    token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


def _build_test_database_url() -> str:
    explicit_url = os.getenv(TEST_DATABASE_URL_ENV)
    if explicit_url:
        return explicit_url

    return DEFAULT_TEST_DATABASE_URL


@pytest_asyncio.fixture(scope="session")
async def test_database_url() -> str:
    test_url = make_url(_build_test_database_url()).set(database=TEST_DATABASE_NAME)
    admin_url = test_url.set(database="postgres")
    engine = create_async_engine(
        admin_url,
        isolation_level="AUTOCOMMIT",
        connect_args={"ssl": False},
        poolclass=NullPool,
    )
    try:
        try:
            async with engine.connect() as conn:
                exists = await conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": TEST_DATABASE_NAME})
                if not exists:
                    await conn.execute(text(f'CREATE DATABASE "{TEST_DATABASE_NAME}"'))
        except SQLAlchemyError as exc:
            raise RuntimeError(
                "Could not connect to the isolated test Postgres instance. "
                f"Start it with 'docker compose -f {TEST_COMPOSE_FILE} up -d postgres-test' "
                f"or set {TEST_DATABASE_URL_ENV} to a reachable PostgreSQL DSN."
            ) from exc
    finally:
        await engine.dispose()

    return str(test_url)


@pytest_asyncio.fixture(scope="session")
async def test_engine(test_database_url: str):
    engine = create_async_engine(
        test_database_url,
        echo=False,
        connect_args={"ssl": False},
        poolclass=NullPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def db_session_factory(test_engine):
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def isolate_database(test_engine) -> AsyncIterator[None]:
    table_names = ", ".join(f'"{table.name}"' for table in reversed(Base.metadata.sorted_tables))
    if table_names:
        async with test_engine.begin() as conn:
            await conn.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))

    api_deps.reset_dependency_singletons()
    app.dependency_overrides.clear()
    yield
    api_deps.reset_dependency_singletons()
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def db_session(isolate_database, db_session_factory) -> AsyncIterator[AsyncSession]:
    del isolate_database
    async with db_session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def fake_blob_store() -> FakeBlobStore:
    return FakeBlobStore()


@pytest_asyncio.fixture
async def fake_queue() -> FakeQueue:
    return FakeQueue()


@pytest_asyncio.fixture
async def api_client(
    isolate_database,
    db_session_factory,
    fake_blob_store: FakeBlobStore,
    fake_queue: FakeQueue,
) -> AsyncIterator[AsyncClient]:
    del isolate_database

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with db_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[api_deps.get_db] = override_get_db
    app.dependency_overrides[api_deps.get_blob_store] = lambda: fake_blob_store
    app.dependency_overrides[api_deps.get_message_queue] = lambda: fake_queue

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def auth_context_factory(db_session: AsyncSession):
    async def _create_auth_context(
        *,
        email: str | None = None,
        password: str = "super-secret-password",
        name: str = "Photographer",
        tenant_name: str = "Tenant",
        tenant_slug: str | None = None,
        role: str = "photographer",
    ) -> AuthContext:
        unique = uuid.uuid4().hex[:8]
        tenant = Tenant(name=f"{tenant_name} {unique}", slug=tenant_slug or f"tenant-{unique}")
        db_session.add(tenant)
        await db_session.flush()

        user = User(
            tenant_id=tenant.id,
            email=email or f"user-{unique}@example.com",
            name=name,
            password_hash=hash_password(password),
            role=role,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(tenant)
        await db_session.refresh(user)

        token = create_access_token(user_id=user.id, tenant_id=tenant.id, role=user.role)
        return AuthContext(tenant=tenant, user=user, password=password, token=token)

    return _create_auth_context


@pytest_asyncio.fixture
async def client_record_factory(db_session: AsyncSession):
    async def _create_client(tenant_id: uuid.UUID, name: str = "Client", email: str | None = None) -> Client:
        client = Client(tenant_id=tenant_id, name=name, email=email)
        db_session.add(client)
        await db_session.commit()
        await db_session.refresh(client)
        return client

    return _create_client


@pytest_asyncio.fixture
async def session_record_factory(db_session: AsyncSession):
    async def _create_session(
        tenant_id: uuid.UUID,
        photographer_id: uuid.UUID,
        *,
        title: str = "Session",
        client_id: uuid.UUID | None = None,
        status: str = "created",
        auto_pick_count: int = 50,
    ) -> ShootSession:
        session = ShootSession(
            tenant_id=tenant_id,
            photographer_id=photographer_id,
            client_id=client_id,
            title=title,
            status=status,
            auto_pick_count=auto_pick_count,
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)
        return session

    return _create_session


@pytest_asyncio.fixture
async def photo_record_factory(db_session: AsyncSession):
    async def _create_photo(
        session_id: uuid.UUID,
        tenant_id: uuid.UUID,
        *,
        filename: str = "photo.jpg",
        original_key: str | None = None,
        status: str = "uploaded",
        thumbnail_key: str | None = None,
        preview_key: str | None = None,
        watermarked_key: str | None = None,
        perceptual_hash: str | None = None,
    ) -> Photo:
        photo = Photo(
            session_id=session_id,
            tenant_id=tenant_id,
            filename=filename,
            original_key=original_key or f"tenants/{tenant_id}/sessions/{session_id}/{uuid.uuid4()}_{filename}",
            status=status,
            thumbnail_key=thumbnail_key,
            preview_key=preview_key,
            watermarked_key=watermarked_key,
            perceptual_hash=perceptual_hash,
        )
        db_session.add(photo)
        await db_session.commit()
        await db_session.refresh(photo)
        return photo

    return _create_photo


@pytest_asyncio.fixture
async def ai_score_record_factory(db_session: AsyncSession):
    async def _create_ai_score(photo_id: uuid.UUID, *, composite_score: float = 0.8, auto_picked: bool = False) -> AIScore:
        score = AIScore(
            photo_id=photo_id,
            sharpness=0.7,
            exposure=0.6,
            composition=0.65,
            aesthetic=0.75,
            face_quality=0.5,
            uniqueness=1.0,
            composite_score=composite_score,
            auto_picked=auto_picked,
        )
        db_session.add(score)
        await db_session.commit()
        await db_session.refresh(score)
        return score

    return _create_ai_score


@pytest_asyncio.fixture
async def gallery_record_factory(db_session: AsyncSession):
    async def _create_gallery(
        session_id: uuid.UUID,
        tenant_id: uuid.UUID,
        *,
        slug: str | None = None,
        pin_hash: str | None = None,
        max_selections: int | None = None,
        expires_at: datetime | None = None,
        status: str = "active",
    ) -> Gallery:
        gallery = Gallery(
            session_id=session_id,
            tenant_id=tenant_id,
            slug=slug or uuid.uuid4().hex[:12],
            pin_hash=pin_hash,
            max_selections=max_selections,
            expires_at=expires_at,
            status=status,
        )
        db_session.add(gallery)
        await db_session.commit()
        await db_session.refresh(gallery)
        return gallery

    return _create_gallery


@pytest_asyncio.fixture
async def gallery_photo_record_factory(db_session: AsyncSession):
    async def _create_gallery_photo(gallery_id: uuid.UUID, photo_id: uuid.UUID, sort_order: int = 0) -> GalleryPhoto:
        gallery_photo = GalleryPhoto(gallery_id=gallery_id, photo_id=photo_id, sort_order=sort_order)
        db_session.add(gallery_photo)
        await db_session.commit()
        await db_session.refresh(gallery_photo)
        return gallery_photo

    return _create_gallery_photo


@pytest_asyncio.fixture
async def selection_record_factory(db_session: AsyncSession):
    async def _create_selection(
        gallery_id: uuid.UUID,
        *,
        client_name: str | None = None,
        client_email: str | None = None,
        notes: str | None = None,
    ) -> Selection:
        selection = Selection(
            gallery_id=gallery_id,
            client_name=client_name,
            client_email=client_email,
            notes=notes,
        )
        db_session.add(selection)
        await db_session.commit()
        await db_session.refresh(selection)
        return selection

    return _create_selection


@pytest_asyncio.fixture
async def selection_photo_record_factory(db_session: AsyncSession):
    async def _create_selection_photo(selection_id: uuid.UUID, photo_id: uuid.UUID) -> SelectionPhoto:
        selection_photo = SelectionPhoto(selection_id=selection_id, photo_id=photo_id)
        db_session.add(selection_photo)
        await db_session.commit()
        await db_session.refresh(selection_photo)
        return selection_photo

    return _create_selection_photo


@pytest_asyncio.fixture
async def branding_record_factory(db_session: AsyncSession):
    async def _create_branding(tenant_id: uuid.UUID, **kwargs: Any) -> TenantBranding:
        branding = TenantBranding(tenant_id=tenant_id, **kwargs)
        db_session.add(branding)
        await db_session.commit()
        await db_session.refresh(branding)
        return branding

    return _create_branding


@pytest_asyncio.fixture
async def edited_photo_record_factory(db_session: AsyncSession):
    async def _create_edited_photo(original_photo_id: uuid.UUID, session_id: uuid.UUID, edited_key: str) -> EditedPhoto:
        edited_photo = EditedPhoto(original_photo_id=original_photo_id, session_id=session_id, edited_key=edited_key)
        db_session.add(edited_photo)
        await db_session.commit()
        await db_session.refresh(edited_photo)
        return edited_photo

    return _create_edited_photo


@pytest_asyncio.fixture
async def delivery_record_factory(db_session: AsyncSession):
    async def _create_delivery(session_id: uuid.UUID, tenant_id: uuid.UUID, provider: str = "dropbox", status: str = "pending") -> Delivery:
        delivery = Delivery(session_id=session_id, tenant_id=tenant_id, provider=provider, status=status)
        db_session.add(delivery)
        await db_session.commit()
        await db_session.refresh(delivery)
        return delivery

    return _create_delivery