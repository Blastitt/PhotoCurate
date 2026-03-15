"""Image processing worker — resize, watermark, white balance, EXIF strip, WebP conversion.

Pipeline per photo:
  1. Download original from blob storage
  2. Decode + EXIF read (orientation, color profile)
  3. Detect face center for smart cropping
  4. Apply white balance correction (gray-world / manual) to preview variants only
  5. Generate resize variants: thumbnail (250px square, face-centered), preview (600px longest side)
  6. Composite tenant watermark logo onto preview + full-size variants
  7. Strip EXIF GPS/personal data
  8. Convert to WebP
  9. Upload all variants back to blob storage
 10. Update photo record in database with variant keys, dimensions, and face center
"""

from __future__ import annotations

import json
import logging
import uuid
from io import BytesIO

import cv2
import numpy as np
import pyvips
from PIL import Image as PILImage
from sqlalchemy import select

from photocurate.core.database import async_session_factory
from photocurate.core.models.session import Photo, ShootSession
from photocurate.core.models.tenant import Tenant, TenantBranding
from photocurate.core.storage import BlobStore

logger = logging.getLogger(__name__)

# Variant dimensions
THUMBNAIL_SIZE = 250   # square crop side length in pixels
PREVIEW_MAX_SIDE = 600 # max pixels on the longest side

# WebP quality setting for output
WEBP_QUALITY = 85


# ─── White Balance ────────────────────────────────────────────────────


def _gray_world_correction(image: pyvips.Image, strength: float) -> pyvips.Image:
    """Apply gray-world white balance correction.

    Compute per-channel means across the image and derive correction
    multipliers to shift toward neutral gray.  Blend with the original
    using *strength* (0.0 = no correction, 1.0 = full correction).
    """
    bands = [image.extract_band(i).avg() for i in range(3)]

    # Avoid division by zero
    if any(b == 0 for b in bands):
        return image

    avg = sum(bands) / 3.0

    r_mul = avg / bands[0]
    g_mul = avg / bands[1]
    b_mul = avg / bands[2]

    # Blend multipliers toward 1.0 (identity) based on strength
    r_mul = 1.0 + (r_mul - 1.0) * strength
    g_mul = 1.0 + (g_mul - 1.0) * strength
    b_mul = 1.0 + (b_mul - 1.0) * strength

    corrected = image.linear([r_mul, g_mul, b_mul], [0, 0, 0])
    corrected = corrected.cast("uchar")
    return corrected


def _manual_wb_correction(image: pyvips.Image, temp_shift: float, tint_shift: float) -> pyvips.Image:
    """Apply manual white balance via temperature/tint shifts.

    temp_shift: positive = warmer (boost R, reduce B), negative = cooler
    tint_shift: positive = more magenta (boost R+B, reduce G), negative = more green
    """
    r_mul = 1.0 + (temp_shift / 5000.0) + (tint_shift * 0.1)
    g_mul = 1.0 - (tint_shift * 0.1)
    b_mul = 1.0 - (temp_shift / 5000.0) + (tint_shift * 0.1)

    corrected = image.linear([r_mul, g_mul, b_mul], [0, 0, 0])
    corrected = corrected.cast("uchar")
    return corrected


def _apply_white_balance(
    image: pyvips.Image,
    wb_mode: str,
    wb_strength: float,
    wb_temp_shift: float,
    wb_tint_shift: float,
) -> pyvips.Image:
    """Apply white balance correction based on session settings."""
    if wb_mode == "off":
        return image
    if wb_mode == "manual":
        return _manual_wb_correction(image, wb_temp_shift, wb_tint_shift)
    # Default: auto (gray-world)
    return _gray_world_correction(image, wb_strength)


# ─── Watermark ────────────────────────────────────────────────────────


def _ensure_srgb(image: pyvips.Image) -> pyvips.Image:
    """Tag or convert an image to sRGB interpretation.

    For images already containing sRGB pixel data but tagged as 'multiband'
    (common for programmatically-constructed images or PNGs without ICC
    profiles), re-tag without pixel conversion.  For genuinely different
    colorspaces (CMYK, Lab, etc.) do a full conversion.
    """
    interp = image.interpretation
    if interp == "srgb":
        return image
    if interp in ("multiband", "b-w"):
        return image.copy(interpretation="srgb")
    return image.colourspace("srgb")


def _composite_watermark(
    image: pyvips.Image,
    logo: pyvips.Image,
    opacity: float,
    position: str,
    scale: float,
    padding: float,
    tile_rotation: float = 45.0,
    tile_spacing: float = 0.5,
) -> pyvips.Image:
    """Composite a watermark logo onto the image.

    Supports positions: center, bottom-right, bottom-left, tiled.
    """
    image = _ensure_srgb(image)

    # Properly convert logo to sRGB, handling greyscale and palette images
    has_alpha = logo.hasalpha()
    if has_alpha:
        alpha_band = logo.extract_band(logo.bands - 1)
        logo_rgb = logo.extract_band(0, n=logo.bands - 1)
    else:
        logo_rgb = logo
        alpha_band = None

    if logo_rgb.bands < 3:
        logo_rgb = logo_rgb.colourspace("srgb")
    else:
        logo_rgb = _ensure_srgb(logo_rgb)

    if alpha_band is not None:
        logo = logo_rgb.bandjoin(alpha_band)
    else:
        logo = logo_rgb

    img_w = image.width
    img_h = image.height

    # Scale logo to desired proportion of image width
    target_logo_w = max(1, int(img_w * scale))
    logo_scale = target_logo_w / logo.width
    logo_resized = logo.resize(logo_scale)

    # Apply opacity to the logo's alpha channel
    if logo_resized.bands == 4:
        rgb = logo_resized.extract_band(0, n=3)
        alpha = logo_resized.extract_band(3)
        alpha = (alpha * opacity).cast("uchar")
        logo_resized = rgb.bandjoin(alpha)
    elif logo_resized.bands == 3:
        alpha = (pyvips.Image.black(logo_resized.width, logo_resized.height) + 255 * opacity).cast("uchar")
        logo_resized = logo_resized.bandjoin(alpha)
    # Re-tag after bandjoin (which resets interpretation to multiband)
    logo_resized = logo_resized.copy(interpretation="srgb")

    # Ensure base image has alpha
    if image.bands == 3:
        alpha_band = (pyvips.Image.black(img_w, img_h) + 255).cast("uchar")
        image = image.bandjoin(alpha_band)
    # Re-tag after bandjoin
    image = image.copy(interpretation="srgb")

    if position == "tiled":
        return _tile_watermark(image, logo_resized, rotation=tile_rotation, spacing=tile_spacing)

    # Calculate position offsets
    pad_x = int(img_w * padding)
    pad_y = int(img_h * padding)
    logo_w = logo_resized.width
    logo_h = logo_resized.height

    if position == "center":
        x = (img_w - logo_w) // 2
        y = (img_h - logo_h) // 2
    elif position == "bottom-left":
        x = pad_x
        y = img_h - logo_h - pad_y
    else:  # bottom-right (default)
        x = img_w - logo_w - pad_x
        y = img_h - logo_h - pad_y

    x = max(0, x)
    y = max(0, y)

    return image.composite2(logo_resized, "over", x=x, y=y)


def _tile_watermark(
    image: pyvips.Image,
    logo: pyvips.Image,
    rotation: float = 45.0,
    spacing: float = 0.5,
) -> pyvips.Image:
    """Tile the watermark diagonally across the image with reduced opacity.

    Uses pyvips embed+replicate for reliable tiling that works regardless
    of the logo-to-image size ratio.

    Args:
        rotation: Angle in degrees to rotate each tile.
        spacing: Gap between tiles as a fraction of the tile dimensions.
    """
    img_w = image.width
    img_h = image.height

    # Reduce opacity further for tiled mode (50% of already-adjusted opacity)
    if logo.bands == 4:
        rgb = logo.extract_band(0, n=3)
        alpha = logo.extract_band(3)
        alpha = (alpha * 0.5).cast("uchar")
        logo = rgb.bandjoin(alpha)
        logo = logo.copy(interpretation="srgb")

    # Cap the logo size for tiled mode so tiles actually repeat
    max_tile_side = min(img_w, img_h) // 3
    if logo.width > max_tile_side or logo.height > max_tile_side:
        tile_scale = max_tile_side / max(logo.width, logo.height)
        logo = logo.resize(tile_scale)

    # Rotate logo by user-specified angle
    logo_rotated = logo.rotate(rotation, background=[0, 0, 0, 0])
    logo_rotated = logo_rotated.copy(interpretation="srgb")

    # Build a single tile cell: logo centered in transparent padding
    gap_x = max(10, int(logo_rotated.width * spacing))
    gap_y = max(10, int(logo_rotated.height * spacing))
    cell_w = logo_rotated.width + gap_x
    cell_h = logo_rotated.height + gap_y
    cell = logo_rotated.embed(
        gap_x // 2, gap_y // 2, cell_w, cell_h,
        background=[0, 0, 0, 0],
    )
    cell = cell.copy(interpretation="srgb")

    # Replicate the cell to cover the full image (with margin)
    nx = (img_w // cell_w) + 2
    ny = (img_h // cell_h) + 2
    tiled = cell.replicate(nx, ny)
    tiled = tiled.crop(0, 0, img_w, img_h)
    tiled = tiled.copy(interpretation="srgb")

    return image.composite2(tiled, "over")


def _text_watermark(image: pyvips.Image, text: str, opacity: float = 0.3) -> pyvips.Image:
    """Render a text watermark diagonally across the image center.

    Used as a fallback when no logo image has been uploaded.
    """
    image = image.copy(interpretation="srgb")
    img_w = image.width
    img_h = image.height

    # Scale font size relative to image width
    font_size = max(16, img_w // 12)

    # Create text image via pyvips
    text_img = pyvips.Image.text(
        text,
        font=f"sans {font_size}",
        rgba=True,
    )

    # Rotate 45 degrees
    text_img = text_img.rotate(-30, background=[0, 0, 0, 0])

    # Apply opacity to alpha channel
    rgb = text_img.extract_band(0, n=3)
    alpha = text_img.extract_band(3)
    alpha = (alpha * opacity).cast("uchar")
    text_img = rgb.bandjoin(alpha)
    text_img = text_img.copy(interpretation="srgb")

    # Ensure base image has alpha
    if image.bands == 3:
        alpha_band = (pyvips.Image.black(img_w, img_h) + 255).cast("uchar")
        image = image.bandjoin(alpha_band)
    image = image.copy(interpretation="srgb")

    # Center the text on the image
    x = max(0, (img_w - text_img.width) // 2)
    y = max(0, (img_h - text_img.height) // 2)

    return image.composite2(text_img, "over", x=x, y=y)


# ─── Resize & Conversion ─────────────────────────────────────────────


def _auto_orient(image: pyvips.Image) -> pyvips.Image:
    """Apply EXIF orientation and remove the orientation tag."""
    return image.autorot()


def _resize_to_max_side(image: pyvips.Image, max_side: int) -> pyvips.Image:
    """Resize image so its longest side equals max_side, maintaining aspect ratio.

    Only downscale — if the image already fits, return as-is.
    """
    longest = max(image.width, image.height)
    if longest <= max_side:
        return image
    scale = max_side / longest
    return image.resize(scale)


def _detect_face_center(image_data: bytes) -> tuple[float, float] | None:
    """Detect the primary face and return its center as normalized (x, y) in 0–1 range.

    Returns None if no face is found.
    """
    arr = np.frombuffer(image_data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    cascade = cv2.CascadeClassifier(cascade_path)
    if cascade.empty():
        return None

    detections = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    if len(detections) == 0:
        return None

    # Pick the largest face (most prominent)
    best = max(detections, key=lambda d: d[2] * d[3])
    fx, fy, fw, fh = best
    cx = (fx + fw / 2.0) / w
    cy = (fy + fh / 2.0) / h
    return (round(cx, 4), round(cy, 4))


def _face_centered_square_crop(image: pyvips.Image, target_size: int, face_cx: float | None, face_cy: float | None) -> pyvips.Image:
    """Crop a square region from the image centered on the face, then resize to target_size.

    face_cx/face_cy are normalized 0–1 coordinates. If None, centers on the image.
    """
    w, h = image.width, image.height
    side = min(w, h)

    if face_cx is not None and face_cy is not None:
        # Convert normalized coords to pixel
        cx_px = face_cx * w
        cy_px = face_cy * h
    else:
        cx_px = w / 2.0
        cy_px = h / 2.0

    # Compute crop origin, clamped to image bounds
    left = int(max(0, min(cx_px - side / 2.0, w - side)))
    top = int(max(0, min(cy_px - side / 2.0, h - side)))

    cropped = image.crop(left, top, side, side)
    if cropped.width != target_size:
        cropped = cropped.resize(target_size / cropped.width)
    return cropped


def _strip_exif_and_convert_webp(image: pyvips.Image) -> bytes:
    """Strip personal EXIF data and convert to WebP bytes."""
    return image.webpsave_buffer(Q=WEBP_QUALITY, strip=True)


def _extract_safe_exif(image: pyvips.Image) -> dict:
    """Extract non-sensitive EXIF fields from an image.

    Keeps technical metadata (camera model, exposure, ISO) while
    stripping GPS coordinates and personal identifiers.
    """
    exif: dict[str, str] = {}
    safe_fields = {
        "exif-ifd0-Make": "camera_make",
        "exif-ifd0-Model": "camera_model",
        "exif-ifd2-ExposureTime": "exposure_time",
        "exif-ifd2-FNumber": "f_number",
        "exif-ifd2-ISOSpeedRatings": "iso",
        "exif-ifd2-FocalLength": "focal_length",
        "exif-ifd2-DateTimeOriginal": "date_taken",
        "exif-ifd2-LensModel": "lens_model",
        "exif-ifd2-WhiteBalance": "white_balance",
    }
    for vips_key, our_key in safe_fields.items():
        try:
            val = image.get(vips_key)
            if val is not None:
                exif[our_key] = str(val).strip("\x00").strip()
        except pyvips.Error:
            pass
    return exif


def _detect_mime_type(data: bytes) -> str:
    """Detect image MIME type from magic bytes."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:4] in (b"II*\x00", b"MM\x00*"):
        return "image/tiff"
    return "application/octet-stream"


def _validate_image(data: bytes) -> None:
    """Validate that data is a real image by checking magic bytes with Pillow."""
    try:
        img = PILImage.open(BytesIO(data))
        img.verify()
    except Exception as exc:
        raise ValueError(f"Invalid image data: {exc}") from exc


# ─── Main Pipeline ────────────────────────────────────────────────────


async def process_single_photo(
    photo_id: uuid.UUID,
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    blob_store: BlobStore,
) -> None:
    """Run the full image processing pipeline for one photo."""
    async with async_session_factory() as db:
        # Load photo + session WB settings + tenant branding
        result = await db.execute(select(Photo).where(Photo.id == photo_id))
        photo = result.scalar_one_or_none()
        if not photo:
            logger.error("Photo %s not found, skipping", photo_id)
            return

        result = await db.execute(select(ShootSession).where(ShootSession.id == session_id))
        session = result.scalar_one_or_none()
        if not session:
            logger.error("Session %s not found, skipping", session_id)
            return

        result = await db.execute(
            select(TenantBranding).where(TenantBranding.tenant_id == tenant_id)
        )
        branding = result.scalar_one_or_none()

        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()

        # ── 1. Download original ──
        logger.info("Downloading original: %s", photo.original_key)
        original_data = await blob_store.download(photo.original_key)
        _validate_image(original_data)

        # ── 2. Decode + EXIF ──
        image = pyvips.Image.new_from_buffer(original_data, "")
        exif = _extract_safe_exif(image)
        image = _auto_orient(image)
        width, height = image.width, image.height

        # Ensure image is sRGB 8-bit for processing
        if image.interpretation != "srgb":
            image = image.colourspace("srgb")
        if image.format != "uchar":
            image = image.cast("uchar")

        # Only keep first 3 bands (drop embedded alpha if present in source)
        if image.bands > 3:
            image = image.extract_band(0, n=3)

        # ── 3. Detect face center (before WB to use raw image) ──
        face_center = _detect_face_center(original_data)
        face_cx = face_center[0] if face_center else None
        face_cy = face_center[1] if face_center else None

        # ── 4. White balance (applied to preview/thumbnail variants only) ──
        wb_image = _apply_white_balance(
            image,
            wb_mode=session.wb_mode,
            wb_strength=session.wb_strength,
            wb_temp_shift=session.wb_temp_shift,
            wb_tint_shift=session.wb_tint_shift,
        )

        # ── 5. Resize variants ──
        thumbnail_img = _face_centered_square_crop(wb_image, THUMBNAIL_SIZE, face_cx, face_cy)
        preview_img = _resize_to_max_side(wb_image, PREVIEW_MAX_SIDE)

        # ── 6. Watermark (preview only; thumbnails too small for legible logos) ──
        watermarked_preview = preview_img
        if branding and branding.watermark_logo_key:
            try:
                logo_data = await blob_store.download(branding.watermark_logo_key)
                logo = pyvips.Image.new_from_buffer(logo_data, "")
                watermarked_preview = _composite_watermark(
                    preview_img,
                    logo,
                    opacity=branding.watermark_opacity,
                    position=branding.watermark_position,
                    scale=branding.watermark_scale,
                    padding=branding.watermark_padding,
                    tile_rotation=branding.watermark_tile_rotation,
                    tile_spacing=branding.watermark_tile_spacing,
                )
            except Exception:
                logger.exception(
                    "Failed to apply watermark for tenant %s, falling back to text",
                    tenant_id,
                )
                watermarked_preview = _text_watermark(
                    preview_img, tenant.name if tenant else "PREVIEW"
                )
        else:
            # No logo uploaded — apply a text watermark with the tenant/studio name
            watermarked_preview = _text_watermark(
                preview_img, tenant.name if tenant else "PREVIEW"
            )

        # ── 7–8. Strip EXIF + WebP conversion ──
        # Flatten RGBA to RGB so the watermark is baked into pixel data
        if watermarked_preview.hasalpha():
            watermarked_preview = watermarked_preview.flatten(background=[0, 0, 0])
        thumbnail_bytes = _strip_exif_and_convert_webp(thumbnail_img)
        preview_bytes = _strip_exif_and_convert_webp(preview_img)
        watermarked_bytes = _strip_exif_and_convert_webp(watermarked_preview)

        # ── 9. Upload variants ──
        base_key = f"tenants/{tenant_id}/sessions/{session_id}/processed/{photo_id}"
        thumb_key = f"{base_key}/thumbnail.webp"
        preview_key = f"{base_key}/preview.webp"
        watermarked_key = f"{base_key}/watermarked_preview.webp"

        await blob_store.upload(thumb_key, thumbnail_bytes, content_type="image/webp")
        await blob_store.upload(preview_key, preview_bytes, content_type="image/webp")
        await blob_store.upload(watermarked_key, watermarked_bytes, content_type="image/webp")

        logger.info(
            "Uploaded variants for photo %s: thumbnail=%d bytes, preview=%d bytes, watermarked=%d bytes",
            photo_id,
            len(thumbnail_bytes),
            len(preview_bytes),
            len(watermarked_bytes),
        )

        # ── 10. Update photo record ──
        photo.thumbnail_key = thumb_key
        photo.preview_key = preview_key
        photo.watermarked_key = watermarked_key
        photo.width = width
        photo.height = height
        photo.file_size_bytes = len(original_data)
        photo.mime_type = _detect_mime_type(original_data)
        photo.exif_data = exif
        photo.face_center_x = face_cx
        photo.face_center_y = face_cy
        photo.status = "processing"  # transitions to "scored" after AI scoring step

        await db.commit()
        logger.info("Photo %s processing complete", photo_id)


async def process_session_photos(
    session_id: uuid.UUID,
    tenant_id: uuid.UUID,
    blob_store: BlobStore,
) -> None:
    """Process all uploaded photos in a session."""
    async with async_session_factory() as db:
        result = await db.execute(
            select(Photo.id).where(
                Photo.session_id == session_id,
                Photo.tenant_id == tenant_id,
                Photo.status.in_(["uploaded", "processing"]),
            )
        )
        photo_ids = [row[0] for row in result.all()]

    logger.info("Processing %d photos in session %s", len(photo_ids), session_id)

    for photo_id in photo_ids:
        try:
            await process_single_photo(photo_id, tenant_id, session_id, blob_store)
        except Exception:
            logger.exception("Failed to process photo %s", photo_id)
            # Reset status so the photo can be retried later
            async with async_session_factory() as db:
                result = await db.execute(select(Photo).where(Photo.id == photo_id))
                photo = result.scalar_one_or_none()
                if photo:
                    photo.status = "uploaded"
                    await db.commit()


async def reprocess_session_previews(
    session_id: uuid.UUID,
    tenant_id: uuid.UUID,
    blob_store: BlobStore,
) -> None:
    """Re-generate preview variants when WB or watermark settings change.

    Only re-processes photos that have already been processed once.
    Does not re-run AI scoring.
    """
    async with async_session_factory() as db:
        result = await db.execute(
            select(Photo.id).where(
                Photo.session_id == session_id,
                Photo.tenant_id == tenant_id,
                Photo.preview_key.isnot(None),
            )
        )
        photo_ids = [row[0] for row in result.all()]

    logger.info("Re-processing previews for %d photos in session %s", len(photo_ids), session_id)

    for photo_id in photo_ids:
        try:
            await process_single_photo(photo_id, tenant_id, session_id, blob_store)
        except Exception:
            logger.exception("Failed to re-process photo %s", photo_id)


# ─── Message Queue Handler ───────────────────────────────────────────


async def handle_image_processing_event(msg: bytes) -> None:
    """Process an image processing event from the message queue.

    Expected event shapes:
      {"type": "session.process", "session_id": "...", "tenant_id": "..."}
      {"type": "session.reprocess_previews", "session_id": "...", "tenant_id": "..."}
    """
    from photocurate.api.deps import get_blob_store

    event = json.loads(msg)
    event_type = event.get("type")
    session_id = uuid.UUID(event["session_id"])
    tenant_id = uuid.UUID(event["tenant_id"])
    blob_store = get_blob_store()

    logger.info("Image processing event: type=%s session=%s", event_type, session_id)

    if event_type == "session.process":
        await process_session_photos(session_id, tenant_id, blob_store)

        # Chain: trigger AI scoring after image processing completes
        from photocurate.api.deps import get_message_queue
        scoring_event = json.dumps({
            "type": "session.score",
            "session_id": str(session_id),
            "tenant_id": str(tenant_id),
        }).encode()
        queue = get_message_queue()
        await queue.publish("photo.scoring", scoring_event)
        logger.info("Triggered scoring for session %s", session_id)
    elif event_type == "session.reprocess_previews":
        await reprocess_session_previews(session_id, tenant_id, blob_store)
    else:
        logger.warning("Unknown event type: %s", event_type)
