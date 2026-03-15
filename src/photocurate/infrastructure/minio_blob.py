"""MinIO (S3-compatible) implementation of BlobStore."""

from __future__ import annotations

import logging
from datetime import timedelta

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from photocurate.config import settings
from photocurate.core.storage import BlobStore

logger = logging.getLogger(__name__)


class MinioBlobStore(BlobStore):
    """S3-compatible blob store using boto3 (works with MinIO and AWS S3)."""

    def __init__(self) -> None:
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.minio_endpoint,
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            region_name=settings.minio_region,
            config=BotoConfig(signature_version="s3v4"),
        )
        # Separate client for presigned URLs that the browser will hit directly
        self._public_client = boto3.client(
            "s3",
            endpoint_url=settings.minio_public_endpoint,
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            region_name=settings.minio_region,
            config=BotoConfig(signature_version="s3v4"),
        )
        self._bucket = settings.minio_bucket
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        """Create the bucket if it doesn't exist."""
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError:
            logger.info("Creating bucket: %s", self._bucket)
            self._client.create_bucket(Bucket=self._bucket)

    async def generate_presigned_upload_url(self, key: str, ttl: timedelta = timedelta(minutes=15)) -> str:
        return self._public_client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=int(ttl.total_seconds()),
        )

    async def generate_presigned_download_url(self, key: str, ttl: timedelta = timedelta(hours=1)) -> str:
        return self._public_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=int(ttl.total_seconds()),
        )

    async def download(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        return response["Body"].read()

    async def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        from io import BytesIO
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=BytesIO(data),
            ContentLength=len(data),
            ContentType=content_type,
        )

    async def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    async def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError:
            return False

    async def get_size(self, key: str) -> int:
        response = self._client.head_object(Bucket=self._bucket, Key=key)
        return response["ContentLength"]
