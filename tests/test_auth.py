"""Tests for authentication utilities."""

from __future__ import annotations

import uuid

from photocurate.api.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    hash_pin,
    verify_password,
    verify_pin,
)


def test_hash_and_verify_password():
    password = "my-secure-password-123"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrong-password", hashed)


def test_hash_and_verify_pin():
    pin = "1234"
    hashed = hash_pin(pin)
    assert verify_pin(pin, hashed)
    assert not verify_pin("5678", hashed)


def test_create_and_decode_access_token():
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    role = "photographer"

    token = create_access_token(user_id=user_id, tenant_id=tenant_id, role=role)
    payload = decode_access_token(token)

    assert payload["sub"] == str(user_id)
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["role"] == role
    assert "exp" in payload
