"""Cloud storage delivery provider — abstract base class."""

from __future__ import annotations

from abc import ABC, abstractmethod


class DeliveryProvider(ABC):
    """Abstract interface for delivering photos to third-party cloud storage."""

    @abstractmethod
    async def create_folder(self, folder_name: str, access_token: str) -> str:
        """Create a folder in the user's cloud storage.

        Returns the folder ID or path.
        """
        ...

    @abstractmethod
    async def upload_file(
        self,
        folder_id: str,
        filename: str,
        data: bytes,
        content_type: str,
        access_token: str,
    ) -> None:
        """Upload a file to a folder in the user's cloud storage."""
        ...

    @abstractmethod
    async def get_share_link(self, folder_id: str, access_token: str) -> str:
        """Generate a shareable link for the folder."""
        ...
