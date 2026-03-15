"""Image analyzer abstract base class — AI scoring abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SharpnessResult:
    score: float  # 0.0–1.0


@dataclass
class ExposureResult:
    score: float  # 0.0–1.0


@dataclass
class CompositionResult:
    score: float  # 0.0–1.0


@dataclass
class AestheticResult:
    score: float  # 0.0–1.0


@dataclass
class FaceInfo:
    x: int
    y: int
    width: int
    height: int
    confidence: float  # 0.0–1.0
    eyes_open: bool | None = None


@dataclass
class FaceResult:
    faces: list[FaceInfo] = field(default_factory=list)
    quality_score: float | None = None  # 0.0–1.0, None if no faces


@dataclass
class HashResult:
    perceptual_hash: str  # hex string for comparison


class ImageAnalyzer(ABC):
    """Abstract interface for image analysis operations."""

    @abstractmethod
    async def analyze_sharpness(self, image_data: bytes) -> SharpnessResult:
        """Compute sharpness score using Laplacian variance."""
        ...

    @abstractmethod
    async def analyze_exposure(self, image_data: bytes) -> ExposureResult:
        """Compute exposure quality from histogram analysis."""
        ...

    @abstractmethod
    async def analyze_composition(self, image_data: bytes) -> CompositionResult:
        """Compute composition score (rule of thirds, etc.)."""
        ...

    @abstractmethod
    async def analyze_aesthetic(self, image_data: bytes) -> AestheticResult:
        """Compute overall aesthetic quality score."""
        ...

    @abstractmethod
    async def detect_faces(self, image_data: bytes) -> FaceResult:
        """Detect faces and compute face quality score."""
        ...

    @abstractmethod
    async def compute_hash(self, image_data: bytes) -> HashResult:
        """Compute perceptual hash for duplicate detection."""
        ...
