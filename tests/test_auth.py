from datetime import timedelta

import jwt
import pytest
from fastapi import HTTPException

from api.auth import create_access_token, decode_access_token
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
