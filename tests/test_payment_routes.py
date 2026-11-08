from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.payment_routes import (
    _bkash_base,
    _bkash_creds,
    _nagad_base,
    _nagad_creds,
    _sslcz_creds,
)


def _store(**overrides):
    values = {
        "bkash_app_key": None,
        "bkash_app_secret": None,
        "bkash_username": None,
        "bkash_password": None,
        "bkash_is_live": False,
        "nagad_merchant_id": None,
        "nagad_merchant_number": None,
        "nagad_pub_key": None,
        "nagad_priv_key": None,
        "nagad_is_live": False,
        "sslcz_store_id": None,
        "sslcz_store_passwd": None,
        "sslcz_is_live": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.parametrize(
    "resolver,fields",
    [
        (_bkash_creds, ("bkash_app_key", "bkash_app_secret", "bkash_username", "bkash_password", "bkash_is_live")),
        (_nagad_creds, ("nagad_merchant_id", "nagad_merchant_number", "nagad_pub_key", "nagad_priv_key", "nagad_is_live")),
        (_sslcz_creds, ("sslcz_store_id", "sslcz_store_passwd", "sslcz_is_live")),
    ],
)
def test_payment_gateways_never_fall_back_to_shared_credentials(resolver, fields):
    with pytest.raises(HTTPException) as exc:
        resolver(_store())
    assert exc.value.status_code == 409
    assert "live credentials" in exc.value.detail.lower()


@pytest.mark.parametrize(
    "resolver,fields",
    [
        (_bkash_creds, ("bkash_app_key", "bkash_app_secret", "bkash_username", "bkash_password", "bkash_is_live")),
        (_nagad_creds, ("nagad_merchant_id", "nagad_merchant_number", "nagad_pub_key", "nagad_priv_key", "nagad_is_live")),
        (_sslcz_creds, ("sslcz_store_id", "sslcz_store_passwd", "sslcz_is_live")),
    ],
)
def test_payment_gateways_reject_sandbox_mode_even_when_credentials_exist(resolver, fields):
    values = {name: f"merchant-{name}" for name in fields[:-1]}
    values[fields[-1]] = False
    with pytest.raises(HTTPException) as exc:
        resolver(_store(**values))
    assert exc.value.status_code == 409


def test_payment_gateways_accept_only_complete_store_owned_live_credentials():
    bkash = _bkash_creds(_store(
        bkash_app_key="merchant-app-key",
        bkash_app_secret="merchant-app-secret",
        bkash_username="merchant-user",
        bkash_password="merchant-password",
        bkash_is_live=True,
    ))
    assert bkash == ("merchant-app-key", "merchant-app-secret", "merchant-user", "merchant-password", True)

    nagad = _nagad_creds(_store(
        nagad_merchant_id="merchant-id",
        nagad_merchant_number="01700000000",
        nagad_pub_key="merchant-public-key",
        nagad_priv_key="merchant-private-key",
        nagad_is_live=True,
    ))
    assert nagad == ("merchant-id", "01700000000", "merchant-public-key", "merchant-private-key", True)

    sslcz = _sslcz_creds(_store(
        sslcz_store_id="merchant-store-id",
        sslcz_store_passwd="merchant-store-password",
        sslcz_is_live=True,
    ))
    assert sslcz == ("merchant-store-id", "merchant-store-password", True)


def test_payment_gateway_endpoint_helpers_refuse_non_live_mode():
    with pytest.raises(HTTPException):
        _bkash_base(False)
    with pytest.raises(HTTPException):
        _nagad_base(False)
