from datetime import timedelta

import jwt
import pytest
from fastapi import HTTPException

from api.auth import create_access_token, decode_access_token, get_current_user
from api.config import get_settings


def test_access_token_round_trip():
    token = create_access_token("user-123")
    assert decode_access_token(token) == "user-123"


def test_wrong_audience_is_rejected():
    settings = get_settings()
    token = jwt.encode(
        {"sub": "user-123", "iss": settings.app_name, "aud": "someone-else"},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(HTTPException) as error:
        decode_access_token(token)
    assert error.value.status_code == 401


def test_render_hosted_runtime_never_uses_the_implicit_development_owner(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_MODE", "development")
    get_settings.cache_clear()
    try:
        with pytest.raises(HTTPException) as error:
            get_current_user(None, None)
        assert error.value.status_code == 401
        assert error.value.detail == "Authentication required"
    finally:
        get_settings.cache_clear()
