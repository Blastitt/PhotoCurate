"""PhotoCurate application configuration via Pydantic Settings."""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application ---
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = True
    app_secret_key: str = "change-me-to-a-random-secret-key"

    # --- Database ---
    database_url: str = "postgresql+asyncpg://photocurate:photocurate@localhost:5432/photocurate"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Storage ---
    storage_provider: Literal["azure", "minio"] = "minio"

    # MinIO
    minio_endpoint: str = "http://localhost:9000"
    minio_public_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "photocurate"
    minio_region: str = "us-east-1"

    # Azure Blob
    azure_storage_connection_string: str | None = None
    azure_storage_container: str = "photocurate"

    # --- Message Queue ---
    queue_provider: Literal["nats", "azure_servicebus"] = "nats"

    # NATS
    nats_url: str = "nats://localhost:4222"

    # Azure Service Bus
    azure_servicebus_connection_string: str | None = None

    # --- JWT ---
    jwt_secret_key: str = "change-me-to-a-random-jwt-secret"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # --- Azure AI Vision ---
    azure_ai_vision_endpoint: str | None = None
    azure_ai_vision_key: str | None = None

    # --- Adobe Lightroom (optional — feature disabled when unset) ---
    adobe_client_id: str | None = None
    adobe_client_secret: str | None = None
    adobe_oauth_redirect_uri: str | None = None
    adobe_token_encryption_key: str | None = None  # Fernet key for encrypting stored tokens

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def adobe_enabled(self) -> bool:
        """True when Adobe Lightroom integration is configured."""
        return self.adobe_client_id is not None


settings = Settings()
