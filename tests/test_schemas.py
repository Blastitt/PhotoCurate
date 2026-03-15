"""Tests for Pydantic schemas validation."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from photocurate.core.schemas.session import (
    ProcessingConfigUpdate,
    SessionCreate,
    UploadURLRequest,
)
from photocurate.core.schemas.gallery import (
    BrandingUpdate,
    GalleryCreate,
    SelectionCreate,
)


def test_session_create_valid():
    s = SessionCreate(title="Smith Wedding")
    assert s.title == "Smith Wedding"
    assert s.auto_pick_count == 50


def test_session_create_with_all_fields():
    s = SessionCreate(
        title="Jones Portrait",
        description="Family portraits in the park",
        shoot_date="2026-04-15",
        client_id=uuid.uuid4(),
        auto_pick_count=100,
    )
    assert s.auto_pick_count == 100


def test_session_create_invalid_auto_pick():
    with pytest.raises(ValidationError):
        SessionCreate(title="Test", auto_pick_count=0)
    with pytest.raises(ValidationError):
        SessionCreate(title="Test", auto_pick_count=501)


def test_processing_config_update_valid():
    cfg = ProcessingConfigUpdate(wb_mode="manual", wb_temp_shift=200.0, wb_tint_shift=0.5)
    assert cfg.wb_mode == "manual"


def test_processing_config_update_invalid_mode():
    with pytest.raises(ValidationError):
        ProcessingConfigUpdate(wb_mode="invalid")


def test_upload_url_request_valid():
    req = UploadURLRequest(filenames=["photo1.jpg", "photo2.jpg"])
    assert len(req.filenames) == 2


def test_upload_url_request_empty():
    with pytest.raises(ValidationError):
        UploadURLRequest(filenames=[])


def test_gallery_create_with_pin():
    g = GalleryCreate(pin="1234", max_selections=20)
    assert g.pin == "1234"


def test_gallery_create_invalid_pin():
    with pytest.raises(ValidationError):
        GalleryCreate(pin="abc")  # non-numeric
    with pytest.raises(ValidationError):
        GalleryCreate(pin="12")  # too short


def test_selection_create_valid():
    s = SelectionCreate(
        photo_ids=[uuid.uuid4(), uuid.uuid4()],
        client_name="John Smith",
        client_email="john@example.com",
    )
    assert len(s.photo_ids) == 2


def test_selection_create_empty_photos():
    with pytest.raises(ValidationError):
        SelectionCreate(photo_ids=[])


def test_branding_update_valid():
    b = BrandingUpdate(watermark_opacity=0.5, watermark_position="center")
    assert b.watermark_opacity == 0.5


def test_branding_update_invalid_position():
    with pytest.raises(ValidationError):
        BrandingUpdate(watermark_position="top-left")  # not in allowed set
