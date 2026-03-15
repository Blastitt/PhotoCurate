"""AI scoring worker — processes photos and computes quality scores.

Pipeline per photo:
  1. Download the photo from blob storage
  2. Run sharpness/exposure checks (OpenCV — fast reject filter)
  3. Run composition/aesthetic scoring
  4. Run face detection
  5. Compute perceptual hash for dedup
  6. Compute weighted composite score
  7. Store AIScore record and update photo status
"""

from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from photocurate.core.analyzer import ImageAnalyzer
from photocurate.core.database import async_session_factory
from photocurate.core.models.session import AIScore, Photo
from photocurate.core.storage import BlobStore

logger = logging.getLogger(__name__)

# Weight configuration for composite score
WEIGHTS = {
    "sharpness": 0.25,
    "exposure": 0.15,
    "composition": 0.15,
    "aesthetic": 0.25,
    "face_quality": 0.10,
    "uniqueness": 0.10,
}

# Photos below this sharpness threshold are fast-rejected
SHARPNESS_REJECT_THRESHOLD = 0.08


async def score_single_photo(
    photo_id: uuid.UUID,
    blob_store: BlobStore,
    analyzer: ImageAnalyzer,
) -> None:
    """Run the full AI scoring pipeline for one photo."""
    async with async_session_factory() as db:
        result = await db.execute(select(Photo).where(Photo.id == photo_id))
        photo = result.scalar_one_or_none()
        if not photo:
            logger.error("Photo %s not found, skipping scoring", photo_id)
            return

        # Download
        logger.info("Scoring photo %s (%s)", photo_id, photo.filename)
        image_data = await blob_store.download(photo.original_key)

        # 1. Sharpness (fast — used as reject filter)
        sharpness = await analyzer.analyze_sharpness(image_data)

        if sharpness.score < SHARPNESS_REJECT_THRESHOLD:
            logger.info("Photo %s rejected: sharpness %.4f below threshold", photo_id, sharpness.score)
            # Still score it but mark as rejected later
            exposure_score = 0.0
            composition_score = 0.0
            aesthetic_score = 0.0
            face_quality = None
        else:
            # 2. Exposure
            exposure_result = await analyzer.analyze_exposure(image_data)
            exposure_score = exposure_result.score

            # 3. Composition + Aesthetic
            composition_result = await analyzer.analyze_composition(image_data)
            composition_score = composition_result.score

            aesthetic_result = await analyzer.analyze_aesthetic(image_data)
            aesthetic_score = aesthetic_result.score

            # 4. Face detection
            face_result = await analyzer.detect_faces(image_data)
            face_quality = face_result.quality_score

        # 5. Perceptual hash (always, needed for dedup)
        hash_result = await analyzer.compute_hash(image_data)

        # 6. Compute composite score
        composite = (
            WEIGHTS["sharpness"] * sharpness.score
            + WEIGHTS["exposure"] * exposure_score
            + WEIGHTS["composition"] * composition_score
            + WEIGHTS["aesthetic"] * aesthetic_score
        )
        if face_quality is not None:
            composite += WEIGHTS["face_quality"] * face_quality
        else:
            # Redistribute face weight evenly to other metrics
            redistribution = WEIGHTS["face_quality"] / 4
            composite += redistribution * (
                sharpness.score + exposure_score + composition_score + aesthetic_score
            )

        # Uniqueness starts at 1.0, reduced later during dedup grouping
        uniqueness = 1.0
        composite += WEIGHTS["uniqueness"] * uniqueness
        composite = round(min(1.0, max(0.0, composite)), 4)

        # 7. Save scores
        stmt = pg_insert(AIScore).values(
            photo_id=photo_id,
            sharpness=sharpness.score,
            exposure=exposure_score,
            composition=composition_score,
            aesthetic=aesthetic_score,
            face_quality=face_quality,
            uniqueness=uniqueness,
            composite_score=composite,
            auto_picked=False,
        ).on_conflict_do_update(
            index_elements=[AIScore.photo_id],
            set_={
                "sharpness": sharpness.score,
                "exposure": exposure_score,
                "composition": composition_score,
                "aesthetic": aesthetic_score,
                "face_quality": face_quality,
                "uniqueness": uniqueness,
                "composite_score": composite,
            },
        )
        await db.execute(stmt)

        photo.perceptual_hash = hash_result.perceptual_hash
        photo.status = "scored"

        await db.commit()
        logger.info(
            "Photo %s scored: composite=%.4f sharpness=%.4f exposure=%.4f "
            "composition=%.4f aesthetic=%.4f face=%.4f",
            photo_id, composite, sharpness.score, exposure_score,
            composition_score, aesthetic_score, face_quality or 0.0,
        )


async def score_session_photos(
    session_id: uuid.UUID,
    tenant_id: uuid.UUID,
    blob_store: BlobStore,
    analyzer: ImageAnalyzer,
) -> None:
    """Score all processed photos in a session."""
    async with async_session_factory() as db:
        result = await db.execute(
            select(Photo.id).where(
                Photo.session_id == session_id,
                Photo.tenant_id == tenant_id,
                Photo.status == "processing",
            )
        )
        photo_ids = [row[0] for row in result.all()]

    logger.info("Scoring %d photos in session %s", len(photo_ids), session_id)

    for photo_id in photo_ids:
        try:
            await score_single_photo(photo_id, blob_store, analyzer)
        except Exception:
            logger.exception("Failed to score photo %s", photo_id)


async def handle_scoring_event(msg: bytes) -> None:
    """Process a scoring event from the message queue.

    Expected event shape:
      {"type": "session.score", "session_id": "...", "tenant_id": "..."}
    """
    from photocurate.api.deps import get_blob_store
    from photocurate.infrastructure.factory import create_image_analyzer

    event = json.loads(msg)
    session_id = uuid.UUID(event["session_id"])
    tenant_id = uuid.UUID(event["tenant_id"])
    blob_store = get_blob_store()
    analyzer = create_image_analyzer()

    logger.info("Scoring event received: session=%s", session_id)
    await score_session_photos(session_id, tenant_id, blob_store, analyzer)

    # Chain: trigger auto-pick after scoring completes
    from photocurate.workers.autopick import run_auto_pick
    await run_auto_pick(session_id, tenant_id)
    logger.info("Auto-pick completed for session %s", session_id)

