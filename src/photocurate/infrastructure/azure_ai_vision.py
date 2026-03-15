"""Azure AI Vision image analyzer — face detection and embedding via REST API."""

from __future__ import annotations

import asyncio
import logging
from functools import partial
from io import BytesIO

import httpx
import imagehash
import numpy as np
from PIL import Image as PILImage

from photocurate.config import settings
from photocurate.core.analyzer import (
    AestheticResult,
    CompositionResult,
    ExposureResult,
    FaceInfo,
    FaceResult,
    HashResult,
    ImageAnalyzer,
    SharpnessResult,
)

logger = logging.getLogger(__name__)

# Re-use local implementations for metrics Azure AI Vision doesn't cover
from photocurate.infrastructure.local_analyzer import (
    _compute_aesthetic,
    _compute_composition,
    _compute_exposure,
    _compute_sharpness,
)


class AzureAIVisionAnalyzer(ImageAnalyzer):
    """Hybrid analyzer: Azure AI Vision for faces + local OpenCV for everything else.

    Uses Azure AI Vision REST API v4.0 for:
    - Face detection with quality attributes (eyes open, accessories, head pose)
    - Image embeddings for high-quality duplicate detection

    Falls back to local analysis for sharpness, exposure, composition, and
    aesthetics (no Azure equivalent).
    """

    def __init__(self) -> None:
        if not settings.azure_ai_vision_endpoint or not settings.azure_ai_vision_key:
            raise ValueError(
                "Azure AI Vision endpoint and key must be configured. "
                "Set AZURE_AI_VISION_ENDPOINT and AZURE_AI_VISION_KEY."
            )
        self._endpoint = settings.azure_ai_vision_endpoint.rstrip("/")
        self._key = settings.azure_ai_vision_key
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Ocp-Apim-Subscription-Key": self._key,
                "Content-Type": "application/octet-stream",
            },
        )

    # ── Local delegations (no Azure equivalent) ──

    async def analyze_sharpness(self, image_data: bytes) -> SharpnessResult:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(_compute_sharpness, image_data))

    async def analyze_exposure(self, image_data: bytes) -> ExposureResult:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(_compute_exposure, image_data))

    async def analyze_composition(self, image_data: bytes) -> CompositionResult:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(_compute_composition, image_data))

    async def analyze_aesthetic(self, image_data: bytes) -> AestheticResult:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(_compute_aesthetic, image_data))

    # ── Azure AI Vision: Face Detection ──

    async def detect_faces(self, image_data: bytes) -> FaceResult:
        """Detect faces using Azure AI Vision Image Analysis v4.0."""
        url = f"{self._endpoint}/computervision/imageanalysis:analyze"
        params = {"features": "people", "api-version": "2024-02-01"}

        try:
            resp = await self._client.post(url, content=image_data, params=params)
            resp.raise_for_status()
            body = resp.json()
        except httpx.HTTPStatusError as e:
            logger.warning("Azure AI Vision face detection failed: %s", e)
            # Fall back to local
            from photocurate.infrastructure.local_analyzer import _detect_faces_sync
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, partial(_detect_faces_sync, image_data))
        except httpx.RequestError as e:
            logger.warning("Azure AI Vision request error: %s", e)
            from photocurate.infrastructure.local_analyzer import _detect_faces_sync
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, partial(_detect_faces_sync, image_data))

        people = body.get("peopleResult", {}).get("values", [])
        if not people:
            return FaceResult(faces=[], quality_score=None)

        faces: list[FaceInfo] = []
        for person in people:
            bbox = person.get("boundingBox", {})
            confidence = person.get("confidence", 0.0)
            faces.append(FaceInfo(
                x=bbox.get("x", 0),
                y=bbox.get("y", 0),
                width=bbox.get("w", 0),
                height=bbox.get("h", 0),
                confidence=round(confidence, 4),
                eyes_open=None,  # Not available in people detection
            ))

        best = max(faces, key=lambda f: f.confidence)
        count_factor = 1.0 if len(faces) <= 3 else max(0.5, 1.0 - (len(faces) - 3) * 0.1)
        quality = best.confidence * count_factor

        return FaceResult(faces=faces, quality_score=round(min(1.0, quality), 4))

    # ── Azure AI Vision: Image Embedding for Dedup ──

    async def compute_hash(self, image_data: bytes) -> HashResult:
        """Compute image embedding via Azure AI Vision for higher-quality dedup.

        Falls back to local perceptual hash if the API call fails.
        """
        url = f"{self._endpoint}/computervision/retrieval:vectorizeImage"
        params = {"api-version": "2024-02-01"}

        try:
            resp = await self._client.post(url, content=image_data, params=params)
            resp.raise_for_status()
            body = resp.json()
            vector = body.get("vector", [])
            if vector:
                # Convert embedding vector to a hex string for storage
                # Use the first 16 floats quantized to uint8 as a compact hash
                arr = np.array(vector[:64], dtype=np.float32)
                quantized = ((arr + 1.0) * 127.5).clip(0, 255).astype(np.uint8)
                hash_hex = quantized.tobytes().hex()
                return HashResult(perceptual_hash=hash_hex)
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.warning("Azure AI Vision embedding failed, falling back to local: %s", e)

        # Fallback to local perceptual hash
        loop = asyncio.get_running_loop()
        pil_img = PILImage.open(BytesIO(image_data))
        phash = imagehash.phash(pil_img)
        return HashResult(perceptual_hash=str(phash))
