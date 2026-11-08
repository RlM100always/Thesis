from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.payment_routes import (
    _bkash_base,
    _bkash_creds,
    _nagad_base,
    _nagad_creds,
    _sslcz_creds,
    _amount_matches,
    _bkash_payment_verified,
    _nagad_payment_verified,
    _sslcz_payment_verified,
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


def test_gateway_amount_comparison_uses_decimal_minor_units():
    assert _amount_matches("125.00", Decimal("125"))
    assert _amount_matches("125.0", Decimal("125.00"))
    assert not _amount_matches("124.99", Decimal("125.00"))
    assert not _amount_matches("not-a-number", Decimal("125.00"))


def test_bkash_callback_requires_matching_payment_id_currency_and_amount():
    order = SimpleNamespace(total=Decimal("250.00"))
    valid = {"statusCode": "0000", "paymentID": "pay-123", "currency": "BDT", "amount": "250.00"}
    assert _bkash_payment_verified(valid, "pay-123", order)
    assert not _bkash_payment_verified({**valid, "amount": "249.00"}, "pay-123", order)
    assert not _bkash_payment_verified({**valid, "currency": "USD"}, "pay-123", order)
    assert not _bkash_payment_verified({**valid, "paymentID": "other"}, "pay-123", order)


def test_nagad_callback_requires_matching_amount_and_provider_references():
    order = SimpleNamespace(total=Decimal("375.00"), document_number="ORD-9")
    valid = {
        "status": "Success", "amount": "375.00", "paymentReferenceId": "ref-1",
        "merchantId": "merchant-1", "orderId": "ORD-9",
    }
    assert _nagad_payment_verified(valid, "ref-1", "merchant-1", order)
    assert not _nagad_payment_verified({**valid, "amount": "370.00"}, "ref-1", "merchant-1", order)
    assert not _nagad_payment_verified({**valid, "paymentReferenceId": "other"}, "ref-1", "merchant-1", order)
    assert not _nagad_payment_verified({**valid, "merchantId": "other"}, "ref-1", "merchant-1", order)


def test_sslcommerz_callback_requires_matching_store_order_currency_and_amount():
    order = SimpleNamespace(id="order-1", total=Decimal("500.00"))
    store = SimpleNamespace(sslcz_store_id="store-1")
    valid = {"status": "VALID", "tran_id": "order-1", "store_id": "store-1", "currency": "BDT", "amount": "500.00"}
    assert _sslcz_payment_verified(valid, order, store)
    assert not _sslcz_payment_verified({**valid, "amount": "499.99"}, order, store)
    assert not _sslcz_payment_verified({**valid, "tran_id": "other"}, order, store)
    assert not _sslcz_payment_verified({**valid, "store_id": "other"}, order, store)
    assert not _sslcz_payment_verified({**valid, "currency": "USD"}, order, store)
