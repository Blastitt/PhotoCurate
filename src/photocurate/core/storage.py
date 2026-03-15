"""BlobStore abstract base class — cloud storage abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import timedelta


class BlobStore(ABC):
    """Abstract interface for blob/object storage operations."""

    @abstractmethod
    async def generate_presigned_upload_url(self, key: str, ttl: timedelta = timedelta(minutes=15)) -> str:
        """Generate a presigned URL for uploading a file directly to storage."""
        ...

    @abstractmethod
    async def generate_presigned_download_url(self, key: str, ttl: timedelta = timedelta(hours=1)) -> str:
        """Generate a presigned URL for downloading a file."""
        ...

    @abstractmethod
    async def download(self, key: str) -> bytes:
        """Download an object's contents as bytes."""
        ...

    @abstractmethod
    async def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        """Upload bytes to storage at the given key."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete an object from storage."""
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if an object exists in storage."""
        ...

    @abstractmethod
    async def get_size(self, key: str) -> int:
        """Get the size of an object in bytes."""
        ...
