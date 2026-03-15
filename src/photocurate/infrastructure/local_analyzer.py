"""Local image analyzer — OpenCV + imagehash for scoring without external APIs."""

from __future__ import annotations

import asyncio
import logging
from functools import partial
from pathlib import Path

import cv2
import imagehash
import numpy as np
from PIL import Image as PILImage

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

# Laplacian variance thresholds for sharpness normalization
_SHARPNESS_LOW = 50.0
_SHARPNESS_HIGH = 800.0

# OpenCV face detector (Haar cascade, bundled with OpenCV)
_face_cascade: cv2.CascadeClassifier | None = None


def _get_face_cascade() -> cv2.CascadeClassifier:
    global _face_cascade
    if _face_cascade is None:
        cv2_data = getattr(cv2, "data", None)
        if cv2_data is not None and getattr(cv2_data, "haarcascades", None):
            cascade_path = Path(cv2_data.haarcascades) / "haarcascade_frontalface_default.xml"
        else:
            cascade_path = Path(cv2.__file__).resolve().parent / "data" / "haarcascade_frontalface_default.xml"

        _face_cascade = cv2.CascadeClassifier(str(cascade_path))
        if _face_cascade.empty():
            raise RuntimeError(f"OpenCV Haar cascade not found at {cascade_path}")
    return _face_cascade


def _decode_image(data: bytes) -> np.ndarray:
    """Decode image bytes to a BGR NumPy array."""
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image")
    return img


def _compute_sharpness(data: bytes) -> SharpnessResult:
    """Sharpness via Laplacian variance — higher means sharper."""
    img = _decode_image(data)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    variance = cv2.Laplacian(gray, cv2.CV_64F).var()
    # Normalize to 0–1 range
    score = max(0.0, min(1.0, (variance - _SHARPNESS_LOW) / (_SHARPNESS_HIGH - _SHARPNESS_LOW)))
    return SharpnessResult(score=round(score, 4))


def _compute_exposure(data: bytes) -> ExposureResult:
    """Exposure quality from luminance histogram analysis.

    Good exposure → histogram spread across the full range.
    Over/under-exposed → histogram bunched at one end.
    """
    img = _decode_image(data)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
    hist = hist / hist.sum()

    mean_lum = np.average(np.arange(256), weights=hist)
    std_lum = np.sqrt(np.average((np.arange(256) - mean_lum) ** 2, weights=hist))

    # Penalize if mean is too far from middle (128)
    mean_penalty = 1.0 - abs(mean_lum - 128) / 128.0

    # Reward good spread (std ~50–70 is ideal)
    ideal_std = 60.0
    std_score = max(0.0, 1.0 - abs(std_lum - ideal_std) / ideal_std)

    # Check for clipping (blown highlights / crushed shadows)
    clip_lo = hist[:10].sum()
    clip_hi = hist[246:].sum()
    clip_penalty = max(0.0, 1.0 - (clip_lo + clip_hi) * 5)

    score = mean_penalty * 0.4 + std_score * 0.3 + clip_penalty * 0.3
    return ExposureResult(score=round(max(0.0, min(1.0, score)), 4))


def _compute_composition(data: bytes) -> CompositionResult:
    """Composition analysis using rule of thirds and edge distribution.

    Checks whether salient regions align with rule-of-thirds grid lines.
    """
    img = _decode_image(data)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # Detect edges (proxy for salient features)
    edges = cv2.Canny(gray, 50, 150)

    # Rule of thirds: check edge density near the 4 intersection points
    third_h, third_w = h // 3, w // 3
    roi_size_h = max(1, h // 12)
    roi_size_w = max(1, w // 12)

    total_edge = edges.sum() / 255.0
    if total_edge == 0:
        return CompositionResult(score=0.5)

    roi_score = 0.0
    for row_mult in (1, 2):
        for col_mult in (1, 2):
            cy = third_h * row_mult
            cx = third_w * col_mult
            y1, y2 = max(0, cy - roi_size_h), min(h, cy + roi_size_h)
            x1, x2 = max(0, cx - roi_size_w), min(w, cx + roi_size_w)
            roi_edges = edges[y1:y2, x1:x2].sum() / 255.0
            roi_score += roi_edges

    # Fraction of edges near rule-of-thirds points
    thirds_ratio = roi_score / total_edge

    # Also check horizon alignment (edges in middle horizontal band)
    mid_y1, mid_y2 = h // 3, 2 * h // 3
    mid_band = edges[mid_y1:mid_y2, :].sum() / 255.0
    horizon_score = min(1.0, mid_band / total_edge * 2)

    score = thirds_ratio * 0.6 + horizon_score * 0.4
    return CompositionResult(score=round(max(0.0, min(1.0, score)), 4))


def _compute_aesthetic(data: bytes) -> AestheticResult:
    """Simplified aesthetic scoring based on color harmony and contrast.

    A lightweight proxy for NIMA — uses color distribution, saturation,
    and contrast measurements rather than a neural network.
    """
    img = _decode_image(data)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Saturation (vivid colors tend to be more appealing)
    sat_mean = hsv[:, :, 1].mean() / 255.0

    # Value contrast (dynamic range in brightness)
    val = hsv[:, :, 2].astype(np.float64)
    val_std = val.std() / 128.0  # normalize

    # Color harmony: fewer dominant hues → more harmonious
    hue_hist = cv2.calcHist([hsv], [0], None, [18], [0, 180]).flatten()
    hue_hist = hue_hist / (hue_hist.sum() + 1e-8)
    hue_entropy = -np.sum(hue_hist * np.log2(hue_hist + 1e-8))
    # Lower entropy → more harmonious (max ~4.17 for 18 bins)
    harmony_score = max(0.0, 1.0 - hue_entropy / 4.17)

    score = sat_mean * 0.3 + min(1.0, val_std) * 0.35 + harmony_score * 0.35
    return AestheticResult(score=round(max(0.0, min(1.0, score)), 4))


def _detect_faces_sync(data: bytes) -> FaceResult:
    """Face detection using OpenCV's Haar cascade."""
    img = _decode_image(data)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cascade = _get_face_cascade()

    detections = cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
    )

    if len(detections) == 0:
        return FaceResult(faces=[], quality_score=None)

    faces: list[FaceInfo] = []
    h, w = gray.shape
    for x, y, fw, fh in detections:
        # Confidence proxy: larger face relative to image → higher confidence
        area_ratio = (fw * fh) / (w * h)
        confidence = min(1.0, area_ratio * 20)
        faces.append(FaceInfo(
            x=int(x), y=int(y), width=int(fw), height=int(fh),
            confidence=round(confidence, 4), eyes_open=None,
        ))

    # Face quality: based on face count, size, and position
    if len(faces) == 0:
        return FaceResult(faces=faces, quality_score=None)

    best_face = max(faces, key=lambda f: f.confidence)
    # Slightly penalize too many faces (group shots are harder to score)
    count_factor = 1.0 if len(faces) <= 3 else max(0.5, 1.0 - (len(faces) - 3) * 0.1)
    quality = best_face.confidence * count_factor
    return FaceResult(faces=faces, quality_score=round(min(1.0, quality), 4))


def _compute_hash(data: bytes) -> HashResult:
    """Compute perceptual hash using average hash from imagehash."""
    from io import BytesIO

    pil_img = PILImage.open(BytesIO(data))
    phash = imagehash.phash(pil_img)
    return HashResult(perceptual_hash=str(phash))


class LocalImageAnalyzer(ImageAnalyzer):
    """Image analyzer using OpenCV, imagehash, and Haar cascades.

    All compute-heavy operations are run in a thread executor to avoid
    blocking the async event loop.
    """

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

    async def detect_faces(self, image_data: bytes) -> FaceResult:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(_detect_faces_sync, image_data))

    async def compute_hash(self, image_data: bytes) -> HashResult:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(_compute_hash, image_data))
