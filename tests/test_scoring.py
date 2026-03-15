"""Tests for the AI scoring worker and auto-pick logic."""

from __future__ import annotations

import uuid
from io import BytesIO
from unittest.mock import AsyncMock

import numpy as np
import pytest
from PIL import Image as PILImage
from sqlalchemy import select

from photocurate.core.analyzer import (
    FaceResult,
    HashResult,
    SharpnessResult,
)
from photocurate.core.models.session import AIScore, Photo
from photocurate.workers.autopick import (
    _group_by_hash,
    _hamming_distance,
)


# ─── Helpers ──────────────────────────────────────────────────────────


def _make_jpeg_bytes(width: int = 200, height: int = 150) -> bytes:
    """Create a synthetic JPEG image as bytes."""
    img = PILImage.new("RGB", (width, height), color=(128, 128, 128))
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_colored_jpeg(r: int, g: int, b: int, width: int = 200, height: int = 150) -> bytes:
    """Create a solid-color JPEG."""
    img = PILImage.new("RGB", (width, height), color=(r, g, b))
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# ─── Hamming Distance Tests ──────────────────────────────────────────


class TestHammingDistance:
    def test_identical_hashes(self):
        assert _hamming_distance("abcd", "abcd") == 0

    def test_one_bit_diff(self):
        # 0xa = 1010, 0xb = 1011 → 1 bit difference
        assert _hamming_distance("a", "b") == 1

    def test_completely_different(self):
        # 0x0 vs 0xf: 4 bits differ
        assert _hamming_distance("0", "f") == 4

    def test_different_length_returns_large(self):
        assert _hamming_distance("ab", "abc") == 999

    def test_invalid_hex_returns_large(self):
        assert _hamming_distance("zz", "zz") == 999


# ─── Group By Hash Tests ─────────────────────────────────────────────


class TestGroupByHash:
    def test_no_duplicates(self):
        """Distinct hashes → each photo in its own group."""
        photos = [
            {"id": 1, "perceptual_hash": "aaaaaaaaaaaaaaaa"},
            {"id": 2, "perceptual_hash": "ffffffffffffffff"},
        ]
        groups = _group_by_hash(photos)
        assert len(groups) == 2

    def test_identical_hashes_grouped(self):
        """Identical hashes → same group."""
        photos = [
            {"id": 1, "perceptual_hash": "abcdef1234567890"},
            {"id": 2, "perceptual_hash": "abcdef1234567890"},
        ]
        groups = _group_by_hash(photos)
        assert len(groups) == 1
        assert len(groups[0]) == 2

    def test_no_hash_treated_as_unique(self):
        """Photos without a hash get their own group."""
        photos = [
            {"id": 1, "perceptual_hash": None},
            {"id": 2, "perceptual_hash": None},
        ]
        groups = _group_by_hash(photos)
        assert len(groups) == 2

    def test_similar_hashes_grouped(self):
        """Hashes within threshold → same group."""
        # These two 16-char hex hashes differ by very few bits
        h1 = "abcdef1234567890"
        # Change last char: 0x0=0000, 0x1=0001 → 1 bit diff
        h2 = "abcdef1234567891"
        photos = [
            {"id": 1, "perceptual_hash": h1},
            {"id": 2, "perceptual_hash": h2},
        ]
        groups = _group_by_hash(photos)
        assert len(groups) == 1


# ─── Local Analyzer Tests ────────────────────────────────────────────


class TestLocalAnalyzer:
    """Test the local OpenCV analyzer with synthetic images."""

    @pytest.fixture
    def analyzer(self):
        from photocurate.infrastructure.local_analyzer import LocalImageAnalyzer
        return LocalImageAnalyzer()

    @pytest.mark.asyncio
    async def test_sharpness_blurry_vs_sharp(self, analyzer):
        """A blurred image should score lower than a sharp one."""
        # Sharp: high-frequency stripe pattern
        sharp_arr = np.zeros((100, 100, 3), dtype=np.uint8)
        sharp_arr[:, ::2] = 255
        sharp_img = PILImage.fromarray(sharp_arr)
        buf = BytesIO()
        sharp_img.save(buf, format="JPEG")
        sharp_bytes = buf.getvalue()

        # Blurry: solid gray
        blurry_bytes = _make_jpeg_bytes()

        sharp_result = await analyzer.analyze_sharpness(sharp_bytes)
        blurry_result = await analyzer.analyze_sharpness(blurry_bytes)
        assert sharp_result.score > blurry_result.score

    @pytest.mark.asyncio
    async def test_exposure_returns_valid_score(self, analyzer):
        result = await analyzer.analyze_exposure(_make_jpeg_bytes())
        assert 0.0 <= result.score <= 1.0

    @pytest.mark.asyncio
    async def test_composition_returns_valid_score(self, analyzer):
        result = await analyzer.analyze_composition(_make_jpeg_bytes())
        assert 0.0 <= result.score <= 1.0

    @pytest.mark.asyncio
    async def test_aesthetic_returns_valid_score(self, analyzer):
        result = await analyzer.analyze_aesthetic(_make_jpeg_bytes())
        assert 0.0 <= result.score <= 1.0

    @pytest.mark.asyncio
    async def test_face_detection_no_faces(self, analyzer):
        """A solid-color image should have no faces."""
        result = await analyzer.detect_faces(_make_jpeg_bytes())
        assert result.quality_score is None
        assert len(result.faces) == 0

    @pytest.mark.asyncio
    async def test_hash_returns_string(self, analyzer):
        result = await analyzer.compute_hash(_make_jpeg_bytes())
        assert isinstance(result.perceptual_hash, str)
        assert len(result.perceptual_hash) > 0

    @pytest.mark.asyncio
    async def test_similar_images_same_hash(self, analyzer):
        """Two very similar images should produce the same perceptual hash."""
        img1 = _make_colored_jpeg(128, 128, 128)
        img2 = _make_colored_jpeg(127, 128, 128)  # barely different
        h1 = await analyzer.compute_hash(img1)
        h2 = await analyzer.compute_hash(img2)
        assert h1.perceptual_hash == h2.perceptual_hash

    @pytest.mark.asyncio
    async def test_overexposed_scores_lower(self, analyzer):
        """A nearly-white image should score worse on exposure."""
        normal = _make_colored_jpeg(128, 128, 128)
        overexposed = _make_colored_jpeg(250, 250, 250)
        normal_score = await analyzer.analyze_exposure(normal)
        over_score = await analyzer.analyze_exposure(overexposed)
        assert normal_score.score > over_score.score


# ─── Scoring Worker Tests (mocked DB + BlobStore) ────────────────────


class TestScoringWorker:
    @pytest.mark.asyncio
    async def test_score_single_photo_persists_scores_and_hash(
        self,
        auth_context_factory,
        session_record_factory,
        photo_record_factory,
        fake_blob_store,
        db_session_factory,
        monkeypatch,
    ):
        from photocurate.workers import scoring

        auth_context = await auth_context_factory()
        session = await session_record_factory(auth_context.tenant.id, auth_context.user.id)
        photo = await photo_record_factory(session.id, auth_context.tenant.id, original_key="originals/photo.jpg", status="processing")
        fake_blob_store.objects[photo.original_key] = _make_jpeg_bytes()

        analyzer = AsyncMock()
        analyzer.analyze_sharpness.return_value = SharpnessResult(score=0.5)
        analyzer.analyze_exposure.return_value = type("Exposure", (), {"score": 0.6})()
        analyzer.analyze_composition.return_value = type("Composition", (), {"score": 0.7})()
        analyzer.analyze_aesthetic.return_value = type("Aesthetic", (), {"score": 0.8})()
        analyzer.detect_faces.return_value = FaceResult(faces=[], quality_score=None)
        analyzer.compute_hash.return_value = HashResult(perceptual_hash="deadbeef")

        monkeypatch.setattr(scoring, "async_session_factory", db_session_factory)

        await scoring.score_single_photo(photo.id, fake_blob_store, analyzer)

        async with db_session_factory() as db:
            stored_score = (await db.execute(select(AIScore).where(AIScore.photo_id == photo.id))).scalar_one()
            stored_photo = (await db.execute(select(Photo).where(Photo.id == photo.id))).scalar_one()

        assert stored_photo.status == "scored"
        assert stored_photo.perceptual_hash == "deadbeef"
        assert stored_score.exposure == 0.6
        assert stored_score.face_quality is None
        assert stored_score.uniqueness == 1.0
        assert stored_score.composite_score == 0.685
        analyzer.analyze_exposure.assert_awaited_once()
        analyzer.detect_faces.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_score_single_photo_fast_reject_skips_slow_metrics(
        self,
        auth_context_factory,
        session_record_factory,
        photo_record_factory,
        fake_blob_store,
        db_session_factory,
        monkeypatch,
    ):
        from photocurate.workers import scoring

        auth_context = await auth_context_factory()
        session = await session_record_factory(auth_context.tenant.id, auth_context.user.id)
        photo = await photo_record_factory(session.id, auth_context.tenant.id, original_key="originals/soft.jpg", status="processing")
        fake_blob_store.objects[photo.original_key] = _make_jpeg_bytes()

        analyzer = AsyncMock()
        analyzer.analyze_sharpness.return_value = SharpnessResult(score=0.01)
        analyzer.compute_hash.return_value = HashResult(perceptual_hash="cafebabe")

        monkeypatch.setattr(scoring, "async_session_factory", db_session_factory)

        await scoring.score_single_photo(photo.id, fake_blob_store, analyzer)

        async with db_session_factory() as db:
            stored_score = (await db.execute(select(AIScore).where(AIScore.photo_id == photo.id))).scalar_one()

        assert stored_score.exposure == 0.0
        assert stored_score.composition == 0.0
        assert stored_score.aesthetic == 0.0
        assert stored_score.face_quality is None
        assert stored_score.composite_score == 0.1028
        analyzer.analyze_exposure.assert_not_called()
        analyzer.analyze_composition.assert_not_called()
        analyzer.analyze_aesthetic.assert_not_called()
        analyzer.detect_faces.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_scoring_event_parses_ids_and_chains_autopick(self, monkeypatch):
        """Verify the scoring event handler parses events correctly."""
        import json

        from photocurate.workers import scoring

        session_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        blob_store = object()
        analyzer = object()
        score_session_photos = AsyncMock()
        run_auto_pick = AsyncMock()

        monkeypatch.setattr(scoring, "score_session_photos", score_session_photos)
        monkeypatch.setattr("photocurate.api.deps.get_blob_store", lambda: blob_store)
        monkeypatch.setattr("photocurate.infrastructure.factory.create_image_analyzer", lambda: analyzer)
        monkeypatch.setattr("photocurate.workers.autopick.run_auto_pick", run_auto_pick)

        await scoring.handle_scoring_event(
            json.dumps({"type": "session.score", "session_id": str(session_id), "tenant_id": str(tenant_id)}).encode()
        )

        score_session_photos.assert_awaited_once_with(session_id, tenant_id, blob_store, analyzer)
        run_auto_pick.assert_awaited_once_with(session_id, tenant_id)
