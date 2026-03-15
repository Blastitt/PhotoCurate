"""Authentication routes — register, login."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from photocurate.api.auth import create_access_token, hash_password, verify_password
from photocurate.api.deps import CurrentUser, DbSession
from photocurate.core.models.tenant import Tenant, User
from photocurate.core.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: DbSession):
    """Register a new photographer with a new tenant."""
    # Check if email already exists
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    # Check if tenant slug is taken
    existing_tenant = await db.execute(select(Tenant).where(Tenant.slug == body.tenant_slug))
    if existing_tenant.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tenant slug already taken")

    # Create tenant
    tenant = Tenant(name=body.tenant_name, slug=body.tenant_slug)
    db.add(tenant)
    await db.flush()  # Get tenant.id

    # Create user
    user = User(
        tenant_id=tenant.id,
        email=body.email,
        name=body.name,
        password_hash=hash_password(body.password),
        role="admin",  # First user is admin
    )
    db.add(user)
    await db.flush()

    token = create_access_token(user_id=user.id, tenant_id=tenant.id, role=user.role)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: DbSession):
    """Authenticate and get an access token."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token = create_access_token(user_id=user.id, tenant_id=user.tenant_id, role=user.role)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(user: CurrentUser):
    """Get the current authenticated user."""
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        tenant_id=str(user.tenant_id),
    )
