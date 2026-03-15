"""Azure Blob Storage implementation of BlobStore."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from azure.storage.blob import BlobSasPermissions, BlobServiceClient, generate_blob_sas

from photocurate.config import settings
from photocurate.core.storage import BlobStore

logger = logging.getLogger(__name__)


class AzureBlobStore(BlobStore):
    """Azure Blob Storage implementation."""

    def __init__(self) -> None:
        if not settings.azure_storage_connection_string:
            raise ValueError("AZURE_STORAGE_CONNECTION_STRING is required for Azure blob storage")
        self._service_client = BlobServiceClient.from_connection_string(settings.azure_storage_connection_string)
        self._container_name = settings.azure_storage_container
        self._ensure_container()

    def _ensure_container(self) -> None:
        """Create the container if it doesn't exist."""
        try:
            self._service_client.create_container(self._container_name)
            logger.info("Created container: %s", self._container_name)
        except Exception:
            pass  # Container already exists

    def _get_account_info(self) -> tuple[str, str]:
        """Extract account name and key from connection string."""
        conn_str = settings.azure_storage_connection_string or ""
        parts = dict(part.split("=", 1) for part in conn_str.split(";") if "=" in part)
        return parts.get("AccountName", ""), parts.get("AccountKey", "")

    async def generate_presigned_upload_url(self, key: str, ttl: timedelta = timedelta(minutes=15)) -> str:
        account_name, account_key = self._get_account_info()
        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=self._container_name,
            blob_name=key,
            account_key=account_key,
            permission=BlobSasPermissions(write=True, create=True),
            expiry=datetime.now(timezone.utc) + ttl,
        )
        return f"https://{account_name}.blob.core.windows.net/{self._container_name}/{key}?{sas_token}"

    async def generate_presigned_download_url(self, key: str, ttl: timedelta = timedelta(hours=1)) -> str:
        account_name, account_key = self._get_account_info()
        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=self._container_name,
            blob_name=key,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(timezone.utc) + ttl,
        )
        return f"https://{account_name}.blob.core.windows.net/{self._container_name}/{key}?{sas_token}"

    async def download(self, key: str) -> bytes:
        blob_client = self._service_client.get_blob_client(self._container_name, key)
        return blob_client.download_blob().readall()

    async def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        from azure.storage.blob import ContentSettings
        blob_client = self._service_client.get_blob_client(self._container_name, key)
        blob_client.upload_blob(
            data,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )

    async def delete(self, key: str) -> None:
        blob_client = self._service_client.get_blob_client(self._container_name, key)
        blob_client.delete_blob()

    async def exists(self, key: str) -> bool:
        blob_client = self._service_client.get_blob_client(self._container_name, key)
        try:
            blob_client.get_blob_properties()
            return True
        except Exception:
            return False

    async def get_size(self, key: str) -> int:
        blob_client = self._service_client.get_blob_client(self._container_name, key)
        props = blob_client.get_blob_properties()
        return props.size
