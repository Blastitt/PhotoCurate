"""Auto-pick logic — duplicate grouping, scoring aggregation, and top-N selection.

After all photos in a session have been scored, this module:
  1. Groups photos by perceptual hash similarity (duplicate detection)
  2. Within each duplicate group, keeps only the highest-scoring photo
  3. Adjusts uniqueness scores based on group sizes
  4. Ranks all surviving photos by composite score
  5. Auto-selects the top N (configurable per session)
  6. Updates photo statuses (auto_picked / rejected)
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict

from sqlalchemy import select, update

from photocurate.core.database import async_session_factory
from photocurate.core.models.session import AIScore, Photo, ShootSession

logger = logging.getLogger(__name__)

# Hamming distance threshold for considering two perceptual hashes as duplicates.
# imagehash phash produces 64-bit hashes; distance ≤ 10 ≈ near-duplicate.
HASH_SIMILARITY_THRESHOLD = 10


def _hamming_distance(h1: str, h2: str) -> int:
    """Compute Hamming distance between two hex-encoded hashes.

    Returns a large number if hashes have different lengths or are
    not standard hex (e.g. Azure embedding hashes).
    """
    if len(h1) != len(h2):
        return 999
    try:
        val1 = int(h1, 16)
        val2 = int(h2, 16)
    except ValueError:
        return 999
    xor = val1 ^ val2
    return bin(xor).count("1")


def _group_by_hash(photos: list[dict]) -> list[list[dict]]:
    """Group photos into clusters of near-duplicates based on perceptual hash.

    Uses a simple greedy clustering: each photo is assigned to the first
    group whose centroid hash is within the similarity threshold.
    """
    groups: list[list[dict]] = []
    centroids: list[str] = []

    for photo in photos:
        h = photo.get("perceptual_hash")
        if not h:
            # No hash — treat as unique
            groups.append([photo])
            centroids.append("")
            continue

        placed = False
        for i, centroid in enumerate(centroids):
            if centroid and _hamming_distance(h, centroid) <= HASH_SIMILARITY_THRESHOLD:
                groups[i].append(photo)
                placed = True
                break

        if not placed:
            groups.append([photo])
            centroids.append(h)

    return groups


async def run_auto_pick(session_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    """Execute the auto-pick pipeline for a session.

    Assumes all photos have already been scored (status='scored').
    """
    async with async_session_factory() as db:
        # Load session config
        sess_result = await db.execute(
            select(ShootSession).where(
                ShootSession.id == session_id,
                ShootSession.tenant_id == tenant_id,
            )
        )
        session = sess_result.scalar_one_or_none()
        if not session:
            logger.error("Session %s not found for auto-pick", session_id)
            return

        if not session.ai_processing_enabled:
            logger.info("AI processing disabled for session %s, skipping auto-pick", session_id)
            return

        auto_pick_count = session.auto_pick_count

        # Load scored photos with their AI scores
        result = await db.execute(
            select(
                Photo.id,
                Photo.perceptual_hash,
                AIScore.composite_score,
                AIScore.sharpness,
            )
            .join(AIScore, AIScore.photo_id == Photo.id)
            .where(
                Photo.session_id == session_id,
                Photo.tenant_id == tenant_id,
                Photo.status == "scored",
            )
        )
        rows = result.all()

        if not rows:
            logger.info("No scored photos in session %s, skipping auto-pick", session_id)
            return

        photos = [
            {
                "id": row.id,
                "perceptual_hash": row.perceptual_hash,
                "composite_score": row.composite_score,
                "sharpness": row.sharpness,
            }
            for row in rows
        ]

        logger.info(
            "Auto-pick: %d scored photos, selecting top %d",
            len(photos), auto_pick_count,
        )

        # 1. Group by duplicate hash
        groups = _group_by_hash(photos)
        logger.info("Duplicate grouping: %d groups from %d photos", len(groups), len(photos))

        # 2. Assign duplicate_group_id and pick best from each group
        best_from_groups: list[dict] = []
        rejected_ids: list[uuid.UUID] = []
        group_updates: list[tuple[uuid.UUID, uuid.UUID]] = []  # (photo_id, group_id)

        for group in groups:
            group_id = uuid.uuid4()
            # Sort by composite score descending
            group.sort(key=lambda p: p["composite_score"], reverse=True)

            best = group[0]
            best_from_groups.append(best)

            for photo in group:
                group_updates.append((photo["id"], group_id))

            # All except the best in this group are duplicates → rejected
            for photo in group[1:]:
                rejected_ids.append(photo["id"])

        # 3. Update uniqueness scores based on group sizes
        for group in groups:
            group_size = len(group)
            if group_size > 1:
                # Reduce uniqueness for photos in larger groups
                uniqueness = round(max(0.1, 1.0 / group_size), 4)
                for photo in group:
                    await db.execute(
                        update(AIScore)
                        .where(AIScore.photo_id == photo["id"])
                        .values(uniqueness=uniqueness)
                    )

        # 4. Update duplicate_group_id on all photos
        for photo_id, group_id in group_updates:
            await db.execute(
                update(Photo)
                .where(Photo.id == photo_id)
                .values(duplicate_group_id=group_id)
            )

        # 5. Rank best-from-each-group by composite score
        best_from_groups.sort(key=lambda p: p["composite_score"], reverse=True)

        # 6. Select top N
        picked_ids = {p["id"] for p in best_from_groups[:auto_pick_count]}
        not_picked_ids = {p["id"] for p in best_from_groups[auto_pick_count:]}

        # 7. Update statuses
        if picked_ids:
            await db.execute(
                update(Photo)
                .where(Photo.id.in_(picked_ids))
                .values(status="auto_picked")
            )
            await db.execute(
                update(AIScore)
                .where(AIScore.photo_id.in_(picked_ids))
                .values(auto_picked=True)
            )

        all_rejected = rejected_ids + list(not_picked_ids)
        if all_rejected:
            await db.execute(
                update(Photo)
                .where(Photo.id.in_(all_rejected))
                .values(status="rejected")
            )

        # Update session status
        session.status = "curated"
        await db.commit()

        logger.info(
            "Auto-pick complete for session %s: %d picked, %d rejected (incl. %d duplicates)",
            session_id, len(picked_ids), len(all_rejected), len(rejected_ids),
        )
