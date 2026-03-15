"""Factory functions for creating infrastructure instances based on configuration."""

from __future__ import annotations

from photocurate.config import settings
from photocurate.core.analyzer import ImageAnalyzer
from photocurate.core.queue import MessageQueue
from photocurate.core.storage import BlobStore


def create_blob_store() -> BlobStore:
    """Create a BlobStore instance based on the configured provider."""
    if settings.storage_provider == "azure":
        from photocurate.infrastructure.azure_blob import AzureBlobStore
        return AzureBlobStore()
    else:
        from photocurate.infrastructure.minio_blob import MinioBlobStore
        return MinioBlobStore()


def create_message_queue() -> MessageQueue:
    """Create a MessageQueue instance based on the configured provider."""
    if settings.queue_provider == "azure_servicebus":
        from photocurate.infrastructure.azure_queue import AzureServiceBusQueue
        return AzureServiceBusQueue()
    else:
        from photocurate.infrastructure.nats_queue import NatsMessageQueue
        return NatsMessageQueue()


def create_image_analyzer() -> ImageAnalyzer:
    """Create an ImageAnalyzer based on configuration.

    Uses Azure AI Vision when endpoint/key are configured, otherwise falls
    back to local OpenCV + imagehash analysis.
    """
    if settings.azure_ai_vision_endpoint and settings.azure_ai_vision_key:
        from photocurate.infrastructure.azure_ai_vision import AzureAIVisionAnalyzer
        return AzureAIVisionAnalyzer()
    else:
        from photocurate.infrastructure.local_analyzer import LocalImageAnalyzer
        return LocalImageAnalyzer()
