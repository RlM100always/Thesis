from pathlib import Path

import pytest

from api.config import Settings


def production_settings(**overrides):
    values = {
        "app_env": "production",
        "auth_mode": "jwt",
        "database_url": "postgresql+psycopg://user:password@localhost/bsmart",
        "jwt_secret": "a" * 64,
        "public_app_url": "https://thesis-j0n8.onrender.com",
        "integration_mode": "sandbox",
    }
    values.update(overrides)
    return Settings(**values)


def test_production_accepts_persistent_postgres_https_and_jwt():
    production_settings().validate_runtime()


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"auth_mode": "development"}, "AUTH_MODE=jwt"),
        ({"database_url": "sqlite:///./bsmart.db"}, "PostgreSQL DATABASE_URL"),
        ({"jwt_secret": "development-only-change-me-32-bytes"}, "JWT_SECRET"),
        ({"public_app_url": "http://thesis-j0n8.onrender.com"}, "HTTPS"),
    ],
)
def test_production_rejects_unsafe_runtime_configuration(overrides, message):
    with pytest.raises(RuntimeError, match=message):
        production_settings(**overrides).validate_runtime()


def test_production_docker_entrypoint_runs_alembic_before_uvicorn():
    dockerfile = Path(__file__).resolve().parents[1].joinpath("Dockerfile").read_text()
    assert "alembic upgrade head" in dockerfile
    assert 'APP_ENV:-development' in dockerfile
