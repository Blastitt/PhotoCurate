"""Tests for the image processing worker — unit tests using synthetic images."""

from __future__ import annotations

import uuid
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pyvips
import pytest
from PIL import Image as PILImage

from photocurate.workers.image_processing import (
    PREVIEW_MAX_SIDE,
    THUMBNAIL_SIZE,
    _apply_white_balance,
    _composite_watermark,
    _detect_face_center,
    _detect_mime_type,
    _extract_safe_exif,
    _face_centered_square_crop,
    _gray_world_correction,
    _manual_wb_correction,
    _resize_to_max_side,
    _strip_exif_and_convert_webp,
    _text_watermark,
    _validate_image,
)


# ─── Helpers ──────────────────────────────────────────────────────────


def _make_rgb_image(width: int = 800, height: int = 600, r: int = 128, g: int = 128, b: int = 128) -> pyvips.Image:
    """Create a synthetic solid-color RGB image."""
    return pyvips.Image.black(width, height, bands=3) + [r, g, b]


def _make_rgba_logo(width: int = 100, height: int = 50) -> pyvips.Image:
    """Create a synthetic RGBA logo with a semi-transparent white rectangle."""
    rgb = pyvips.Image.black(width, height, bands=3) + [255, 255, 255]
    alpha = pyvips.Image.black(width, height) + 200
    return rgb.bandjoin(alpha).cast("uchar")


def _image_to_jpeg_bytes(image: pyvips.Image) -> bytes:
    """Convert a pyvips image to JPEG bytes."""
    return image.jpegsave_buffer(Q=90)


def _image_to_png_bytes(image: pyvips.Image) -> bytes:
    """Convert a pyvips image to PNG bytes."""
    return image.pngsave_buffer()


# ─── White Balance Tests ──────────────────────────────────────────────


class TestGrayWorldCorrection:
    def test_neutral_image_unchanged(self):
        """A perfectly neutral gray image should be (nearly) unchanged."""
        img = _make_rgb_image(100, 100, 128, 128, 128).cast("uchar")
        result = _gray_world_correction(img, strength=1.0)
        # Check that average pixel values are still close to 128
        for i in range(3):
            band_avg = result.extract_band(i).avg()
            assert abs(band_avg - 128) < 2

    def test_warm_image_corrected(self):
        """An image with a warm (red-heavy) cast should have R reduced."""
        img = _make_rgb_image(100, 100, 200, 128, 100).cast("uchar")
        result = _gray_world_correction(img, strength=1.0)
        r_avg = result.extract_band(0).avg()
        g_avg = result.extract_band(1).avg()
        b_avg = result.extract_band(2).avg()
        # After gray-world, all channels should be closer together
        spread = max(r_avg, g_avg, b_avg) - min(r_avg, g_avg, b_avg)
        assert spread < 5

    def test_zero_strength_no_change(self):
        """With strength=0.0, image should be unchanged."""
        img = _make_rgb_image(100, 100, 200, 128, 100).cast("uchar")
        result = _gray_world_correction(img, strength=0.0)
        for i in range(3):
            assert abs(result.extract_band(i).avg() - img.extract_band(i).avg()) < 1


class TestManualWBCorrection:
    def test_warm_shift(self):
        """Positive temp_shift should boost red and reduce blue."""
        img = _make_rgb_image(100, 100, 128, 128, 128).cast("uchar")
        result = _manual_wb_correction(img, temp_shift=200, tint_shift=0.0)
        r_avg = result.extract_band(0).avg()
        b_avg = result.extract_band(2).avg()
        assert r_avg > b_avg

    def test_cool_shift(self):
        """Negative temp_shift should boost blue and reduce red."""
        img = _make_rgb_image(100, 100, 128, 128, 128).cast("uchar")
        result = _manual_wb_correction(img, temp_shift=-200, tint_shift=0.0)
        r_avg = result.extract_band(0).avg()
        b_avg = result.extract_band(2).avg()
        assert b_avg > r_avg


class TestApplyWhiteBalance:
    def test_off_mode(self):
        """wb_mode='off' should return the image unchanged."""
        img = _make_rgb_image(100, 100, 200, 128, 100).cast("uchar")
        result = _apply_white_balance(img, "off", 0.7, 0.0, 0.0)
        assert result is img

    def test_auto_mode(self):
        """wb_mode='auto' delegates to gray-world."""
        img = _make_rgb_image(100, 100, 200, 128, 100).cast("uchar")
        result = _apply_white_balance(img, "auto", 1.0, 0.0, 0.0)
        spread = max(result.extract_band(i).avg() for i in range(3)) - min(
            result.extract_band(i).avg() for i in range(3)
        )
        assert spread < 5

    def test_manual_mode(self):
        """wb_mode='manual' delegates to manual correction."""
        img = _make_rgb_image(100, 100, 128, 128, 128).cast("uchar")
        result = _apply_white_balance(img, "manual", 0.7, 200.0, 0.0)
        r_avg = result.extract_band(0).avg()
        b_avg = result.extract_band(2).avg()
        assert r_avg > b_avg


# ─── Watermark Tests ─────────────────────────────────────────────────


class TestCompositeWatermark:
    def test_bottom_right_position(self):
        """Watermark in bottom-right should not crash and return correct size."""
        img = _make_rgb_image(800, 600).cast("uchar")
        logo = _make_rgba_logo(100, 50)
        result = _composite_watermark(img, logo, opacity=0.3, position="bottom-right", scale=0.15, padding=0.02)
        assert result.width == 800
        assert result.height == 600

    def test_center_position(self):
        img = _make_rgb_image(800, 600).cast("uchar")
        logo = _make_rgba_logo(100, 50)
        result = _composite_watermark(img, logo, opacity=0.3, position="center", scale=0.15, padding=0.02)
        assert result.width == 800
        assert result.height == 600

    def test_bottom_left_position(self):
        img = _make_rgb_image(800, 600).cast("uchar")
        logo = _make_rgba_logo(100, 50)
        result = _composite_watermark(img, logo, opacity=0.3, position="bottom-left", scale=0.15, padding=0.02)
        assert result.width == 800
        assert result.height == 600

    def test_tiled_position(self):
        img = _make_rgb_image(800, 600).cast("uchar")
        logo = _make_rgba_logo(60, 30)
        result = _composite_watermark(img, logo, opacity=0.3, position="tiled", scale=0.08, padding=0.02)
        assert result.width == 800
        assert result.height == 600

    def test_tiled_custom_rotation_and_spacing(self):
        """Tiled watermark respects custom tile_rotation and tile_spacing."""
        img = _make_rgb_image(800, 600).cast("uchar")
        logo = _make_rgba_logo(60, 30)
        result = _composite_watermark(
            img, logo, opacity=0.3, position="tiled", scale=0.08, padding=0.02,
            tile_rotation=90.0, tile_spacing=1.0,
        )
        assert result.width == 800
        assert result.height == 600

    def test_tiled_zero_rotation(self):
        """Tiled watermark with 0 degree rotation produces same-dimension output."""
        img = _make_rgb_image(600, 400).cast("uchar")
        logo = _make_rgba_logo(60, 30)
        result = _composite_watermark(
            img, logo, opacity=0.5, position="tiled", scale=0.1, padding=0.02,
            tile_rotation=0.0, tile_spacing=0.3,
        )
        assert result.width == 600
        assert result.height == 400

    def test_tiled_large_scale(self):
        """Tiled watermark with large scale still produces visible tiling on small images."""
        img = _make_rgb_image(600, 400).cast("uchar")
        logo = _make_rgba_logo(350, 350)
        result = _composite_watermark(img, logo, opacity=0.1, position="tiled", scale=0.45, padding=0.02)
        assert result.width == 600
        assert result.height == 400
        # Watermark must actually alter pixels
        if result.hasalpha():
            result = result.flatten(background=[0, 0, 0])
        wm_bytes = result.webpsave_buffer(Q=85, strip=True)
        orig_bytes = img.webpsave_buffer(Q=85, strip=True)
        assert wm_bytes != orig_bytes

    def test_rgb_logo_gets_alpha(self):
        """An RGB logo (no alpha) should still work."""
        img = _make_rgb_image(800, 600).cast("uchar")
        logo = (pyvips.Image.black(100, 50, bands=3) + [255, 255, 255]).cast("uchar")
        assert logo.bands == 3
        result = _composite_watermark(img, logo, opacity=0.5, position="bottom-right", scale=0.1, padding=0.02)
        assert result.width == 800

    def test_greyscale_logo(self):
        """A greyscale logo should be converted to sRGB and composited."""
        img = _make_rgb_image(800, 600).cast("uchar")
        logo_grey = (pyvips.Image.black(100, 50) + 200).cast("uchar")
        assert logo_grey.bands == 1
        result = _composite_watermark(img, logo_grey, opacity=0.5, position="bottom-right", scale=0.1, padding=0.02)
        assert result.width == 800
        assert result.height == 600

    def test_greyscale_logo_with_alpha(self):
        """A greyscale+alpha logo should be handled correctly."""
        img = _make_rgb_image(800, 600).cast("uchar")
        grey = (pyvips.Image.black(100, 50) + 200).cast("uchar")
        alpha = (pyvips.Image.black(100, 50) + 180).cast("uchar")
        logo_ga = grey.bandjoin(alpha)
        assert logo_ga.bands == 2
        result = _composite_watermark(img, logo_ga, opacity=0.4, position="center", scale=0.15, padding=0.02)
        assert result.width == 800
        assert result.height == 600


# ─── Resize Tests ─────────────────────────────────────────────────────


class TestResizeToMaxSide:
    def test_landscape_downscale(self):
        """Landscape image: longest side (width) should equal PREVIEW_MAX_SIDE."""
        img = _make_rgb_image(4000, 3000)
        result = _resize_to_max_side(img, PREVIEW_MAX_SIDE)
        assert result.width == PREVIEW_MAX_SIDE
        # Aspect ratio preserved
        assert abs(result.height - 450) <= 1

    def test_portrait_downscale(self):
        """Portrait image: longest side (height) should equal PREVIEW_MAX_SIDE."""
        img = _make_rgb_image(3000, 4000)
        result = _resize_to_max_side(img, PREVIEW_MAX_SIDE)
        assert result.height == PREVIEW_MAX_SIDE
        assert abs(result.width - 450) <= 1

    def test_square_downscale(self):
        img = _make_rgb_image(2000, 2000)
        result = _resize_to_max_side(img, PREVIEW_MAX_SIDE)
        assert result.width == PREVIEW_MAX_SIDE
        assert result.height == PREVIEW_MAX_SIDE

    def test_no_upscale(self):
        """An image already fitting within max_side should be returned as-is."""
        img = _make_rgb_image(200, 150)
        result = _resize_to_max_side(img, PREVIEW_MAX_SIDE)
        assert result.width == 200
        assert result.height == 150

    def test_exact_size_unchanged(self):
        """An image whose longest side exactly equals max_side is unchanged."""
        img = _make_rgb_image(PREVIEW_MAX_SIDE, 400)
        result = _resize_to_max_side(img, PREVIEW_MAX_SIDE)
        assert result.width == PREVIEW_MAX_SIDE
        assert result.height == 400


# ─── Face-Centered Square Crop Tests ──────────────────────────────────


class TestFaceCenteredSquareCrop:
    def test_center_crop_no_face(self):
        """Without face coords, crop should be centered."""
        img = _make_rgb_image(800, 600).cast("uchar")
        result = _face_centered_square_crop(img, THUMBNAIL_SIZE, None, None)
        assert result.width == THUMBNAIL_SIZE
        assert result.height == THUMBNAIL_SIZE

    def test_face_center_crop(self):
        """With face coords, crop should still produce correct dimensions."""
        img = _make_rgb_image(800, 600).cast("uchar")
        result = _face_centered_square_crop(img, THUMBNAIL_SIZE, 0.3, 0.4)
        assert result.width == THUMBNAIL_SIZE
        assert result.height == THUMBNAIL_SIZE

    def test_face_at_edge(self):
        """Face near the edge should be clamped within image bounds."""
        img = _make_rgb_image(800, 600).cast("uchar")
        result = _face_centered_square_crop(img, THUMBNAIL_SIZE, 0.95, 0.95)
        assert result.width == THUMBNAIL_SIZE
        assert result.height == THUMBNAIL_SIZE

    def test_square_image(self):
        """A square image should crop to full extent then resize."""
        img = _make_rgb_image(500, 500).cast("uchar")
        result = _face_centered_square_crop(img, THUMBNAIL_SIZE, 0.5, 0.5)
        assert result.width == THUMBNAIL_SIZE
        assert result.height == THUMBNAIL_SIZE


# ─── Text Watermark Tests ─────────────────────────────────────────────


class TestTextWatermark:
    def test_produces_correct_size(self):
        """Text watermark should preserve original dimensions."""
        img = _make_rgb_image(800, 600).cast("uchar")
        result = _text_watermark(img, "Test Studio")
        assert result.width == 800
        assert result.height == 600

    def test_adds_alpha_channel(self):
        """Result should have an alpha band from compositing."""
        img = _make_rgb_image(800, 600).cast("uchar")
        assert img.bands == 3
        result = _text_watermark(img, "Studio", opacity=0.5)
        assert result.bands == 4


# ─── WebP Conversion / EXIF Strip ────────────────────────────────────


class TestWebPConversion:
    def test_produces_webp_bytes(self):
        img = _make_rgb_image(100, 100).cast("uchar")
        data = _strip_exif_and_convert_webp(img)
        assert data[:4] == b"RIFF"
        assert data[8:12] == b"WEBP"

    def test_output_is_smaller_reasonable(self):
        """WebP output for a solid-color image should be very small."""
        img = _make_rgb_image(200, 200).cast("uchar")
        data = _strip_exif_and_convert_webp(img)
        assert len(data) < 200 * 200 * 3  # definitely smaller than raw


# ─── MIME Type Detection ──────────────────────────────────────────────


class TestDetectMimeType:
    def test_jpeg(self):
        img = _make_rgb_image(50, 50).cast("uchar")
        data = _image_to_jpeg_bytes(img)
        assert _detect_mime_type(data) == "image/jpeg"

    def test_png(self):
        img = _make_rgb_image(50, 50).cast("uchar")
        data = _image_to_png_bytes(img)
        assert _detect_mime_type(data) == "image/png"

    def test_webp(self):
        img = _make_rgb_image(50, 50).cast("uchar")
        data = img.webpsave_buffer()
        assert _detect_mime_type(data) == "image/webp"

    def test_unknown(self):
        assert _detect_mime_type(b"not an image") == "application/octet-stream"


# ─── Validation ───────────────────────────────────────────────────────


class TestValidateImage:
    def test_valid_jpeg(self):
        img = _make_rgb_image(50, 50).cast("uchar")
        data = _image_to_jpeg_bytes(img)
        _validate_image(data)  # should not raise

    def test_invalid_data_raises(self):
        with pytest.raises(ValueError, match="Invalid image data"):
            _validate_image(b"this is not an image at all")


# ─── EXIF Extraction ─────────────────────────────────────────────────


class TestExtractSafeExif:
    def test_no_exif_returns_empty(self):
        """A synthetic image has no EXIF data."""
        img = _make_rgb_image(50, 50).cast("uchar")
        exif = _extract_safe_exif(img)
        assert isinstance(exif, dict)
        # Synthetic images won't have any EXIF fields
        assert "gps_latitude" not in exif
