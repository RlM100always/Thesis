"""Payment gateway integrations: bKash Tokenized Checkout, Nagad Merchant API, SSLCommerz.

bKash flow (https://developer.bkash.com/):
  1. POST /bkash/initiate/{org_id}  → grant token → create payment → returns {bkashURL, paymentID}
  2. Customer redirected to bkashURL (official bKash page, enters PIN)
  3. bKash redirects to /bkash/callback?paymentID=...&status=success|failure|cancel
  4. We execute the payment → mark order paid

Nagad flow (https://nagad.com.bd/merchant/):
  1. POST /nagad/initiate/{org_id} → initialize order (RSA-signed) → returns {callBackUrl}
  2. Customer redirected to Nagad checkout page
  3. Nagad redirects to /nagad/callback?payment_ref_id=...&status=Success|Aborted

SSLCommerz flow (all-in-one: bKash + Nagad + cards):
  POST /initiate/{org_id} → SSLCommerz session → GatewayPageURL
"""

import base64
import json
import os
import re
import uuid
from urllib.parse import urlsplit
from decimal import Decimal

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .domain_models import SalesDocument, Store

router = APIRouter(prefix="/api/public/payment", tags=["payment"])

# Production gateway endpoints. Each store must supply its own verified live credentials.
BKASH_LIVE_BASE = "https://tokenized.pay.bka.sh/v1.2.0-beta"
NAGAD_LIVE_BASE = "https://api.nagad.com.bd"
SSLCZ_LIVE_INIT = "https://securepay.sslcommerz.com/gwprocess/v4/api.php"
SSLCZ_LIVE_VAL = "https://securepay.sslcommerz.com/validator/api/validationserverAPI.php"


def _base_url(request: Request) -> str:
    configured = os.getenv("PUBLIC_APP_URL", "https://thesis-j0n8.onrender.com").strip().rstrip("/")
    parsed = urlsplit(configured)
    if parsed.scheme not in ("https", "http") or not parsed.netloc:
        raise HTTPException(500, "PUBLIC_APP_URL is not a valid absolute URL.")
    if parsed.scheme != "https" and parsed.hostname not in ("localhost", "127.0.0.1", "testserver"):
        raise HTTPException(500, "Payment callback URLs must use HTTPS.")
    return f"{parsed.scheme}://{parsed.netloc}"


def _order_redirect(org_id: str, access_token: str, payment: str, base: str) -> RedirectResponse:
    return RedirectResponse(
        f"{base}/#/order-status/{org_id}/{access_token}?payment={payment}",
        status_code=303,
    )


def _get_order(order_id: str, org_id: str, db: Session) -> SalesDocument:
    order = db.scalar(select(SalesDocument).where(
        SalesDocument.id == order_id,
        SalesDocument.organization_id == org_id,
    ))
    if not order:
        raise HTTPException(404, "Order not found")
    if order.payment_status == "paid":
        raise HTTPException(409, "Order already paid")
    if str(getattr(order, "status", "")).lower() in ("cancelled", "canceled", "void"):
        raise HTTPException(409, "Cancelled orders cannot be paid")
    return order


# ═══════════════════════════════════════════════════════════════════════════════
# bKash Tokenized Checkout API
# ═══════════════════════════════════════════════════════════════════════════════

def _bkash_creds(store: Store) -> tuple[str, str, str, str, bool]:
    """Return only store-owned live bKash credentials."""
    ak, ase, un, pw = (
        store.bkash_app_key, store.bkash_app_secret,
        store.bkash_username, store.bkash_password,
    )
    if not all((ak, ase, un, pw)) or not bool(store.bkash_is_live):
        raise HTTPException(409, "bKash live credentials are not configured for this store.")
    return ak, ase, un, pw, True


def _bkash_base(is_live: bool) -> str:
    if not is_live:
        raise HTTPException(409, "bKash live checkout is not enabled for this store.")
    return BKASH_LIVE_BASE


async def _bkash_grant_token(ak: str, ase: str, un: str, pw: str, is_live: bool) -> str:
    """Step 1: get id_token from bKash."""
    url = f"{_bkash_base(is_live)}/checkout/token/grant"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "username": ak,
        "password": ase,
    }
    body = {"app_key": ak, "app_secret": ase}
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(url, json=body, headers=headers)
    data = r.json()
    token = data.get("id_token")
    if not token:
        raise HTTPException(502, f"bKash token error: {data.get('statusMessage', data)}")
    return token


async def _bkash_create_payment(
    ak: str, token: str, amount: float, invoice: str, callback_url: str, is_live: bool
) -> dict:
    """Step 2: create payment session."""
    url = f"{_bkash_base(is_live)}/checkout/payment/create"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": token,
        "X-APP-Key": ak,
    }
    body = {
        "mode": "0011",
        "payerReference": " ",
        "callbackURL": callback_url,
        "amount": f"{amount:.2f}",
        "currency": "BDT",
        "intent": "sale",
        "merchantInvoiceNumber": invoice,
    }
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(url, json=body, headers=headers)
    data = r.json()
    if data.get("statusCode") != "0000":
        raise HTTPException(502, f"bKash create error: {data.get('statusMessage', data)}")
    return data


async def _bkash_execute_payment(ak: str, token: str, payment_id: str, is_live: bool) -> dict:
    """Step 4: execute after customer approves."""
    url = f"{_bkash_base(is_live)}/checkout/payment/execute"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": token,
        "X-APP-Key": ak,
    }
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(url, json={"paymentID": payment_id}, headers=headers)
    return r.json()


@router.post("/bkash/initiate/{org_id}")
async def bkash_initiate(
    org_id: str,
    request: Request,
    db: Session = Depends(get_db),
    order_id: str | None = Form(default=None),
):
    """Start a bKash Tokenized Checkout session. Returns {bkashURL, paymentID}."""
    if not order_id:
        try: body = await request.json(); order_id = body.get("order_id")
        except Exception: pass
    order = _get_order(order_id or "", org_id, db)

    store = db.scalar(select(Store).where(Store.organization_id == org_id))
    if not store:
        raise HTTPException(404, "Store not found")

    ak, ase, un, pw, is_live = _bkash_creds(store)
    base = _base_url(request)
    callback_url = f"{base}/api/public/payment/bkash/callback"

    token = await _bkash_grant_token(ak, ase, un, pw, is_live)
    data = await _bkash_create_payment(
        ak, token,
        float(order.total or 0),
        order.document_number,
        callback_url,
        is_live,
    )

    # Stash token in order notes for callback use (short-lived, 1h)
    order.notes = json.dumps({
        **(json.loads(order.notes or "{}")),
        "_bkash_token": token,
        "_bkash_ak": ak,
        "_bkash_live": is_live,
        "_bkash_payment_id": data["paymentID"],
    })
    db.commit()

    return {
        "bkashURL": data["bkashURL"],
        "paymentID": data["paymentID"],
        "order_number": order.document_number,
        "amount": float(order.total or 0),
    }


@router.get("/bkash/callback")
async def bkash_callback(
    request: Request,
    db: Session = Depends(get_db),
    paymentID: str = "",
    status: str = "",
):
    """bKash redirects here after customer interaction."""
    base = _base_url(request)

    if status != "success" or not paymentID:
        # Find order by paymentID in notes (best-effort)
        return RedirectResponse(f"{base}/#/payment-result?status=cancelled&gateway=bkash", status_code=303)

    # Find order that has this paymentID in notes
    orders = db.scalars(select(SalesDocument).where(
        SalesDocument.notes.contains(paymentID)
    )).all()

    order = next((o for o in orders if paymentID in (o.notes or "")), None)
    if not order:
        return RedirectResponse(f"{base}/#/payment-result?status=error&gateway=bkash", status_code=303)

    try:
        meta = json.loads(order.notes or "{}")
        if str(meta.get("_bkash_payment_id") or "") != paymentID:
            raise ValueError("bKash payment reference mismatch")
        token = meta.get("_bkash_token")
        ak = meta.get("_bkash_ak")
        is_live = bool(meta.get("_bkash_live"))
        if not token or not ak or not is_live:
            raise ValueError("bKash live callback metadata is incomplete")
        if order.payment_status != "paid":
            result = await _bkash_execute_payment(ak, token, paymentID, is_live)
            if _bkash_payment_verified(result, paymentID, order):
                order.payment_status = "paid"
                meta["_bkash_trx_id"] = result.get("trxID", "")
                order.notes = json.dumps(meta)
            else:
                order.payment_status = "payment_failed"
            db.commit()
    except Exception:
        if order.payment_status != "paid":
            order.payment_status = "payment_failed"
            db.commit()

    payment_result = "success" if order.payment_status == "paid" else "failed"
    return _order_redirect(order.organization_id, order.access_token, payment_result, base)


# ═══════════════════════════════════════════════════════════════════════════════
# Nagad Merchant API
# ═══════════════════════════════════════════════════════════════════════════════

def _nagad_base(is_live: bool) -> str:
    if not is_live:
        raise HTTPException(409, "Nagad live checkout is not enabled for this store.")
    return NAGAD_LIVE_BASE


def _nagad_creds(store: Store) -> tuple[str, str, str, str, bool]:
    """Return only store-owned live Nagad credentials."""
    mid, mnum, pub, priv = (
        store.nagad_merchant_id, store.nagad_merchant_number,
        store.nagad_pub_key, store.nagad_priv_key,
    )
    if not all((mid, mnum, pub, priv)) or not bool(store.nagad_is_live):
        raise HTTPException(409, "Nagad live credentials are not configured for this store.")
    return mid, mnum, pub, priv, True


def _nagad_encrypt(data: str, pub_key_b64: str) -> str:
    """RSA-encrypt `data` with Nagad's public key."""
    pem = (
        "-----BEGIN PUBLIC KEY-----\n"
        + "\n".join(pub_key_b64[i:i+64] for i in range(0, len(pub_key_b64), 64))
        + "\n-----END PUBLIC KEY-----"
    )
    pub = serialization.load_pem_public_key(pem.encode())
    encrypted = pub.encrypt(data.encode(), padding.PKCS1v15())
    return base64.b64encode(encrypted).decode()


def _nagad_sign(data: str, priv_key_b64: str) -> str:
    """Sign `data` with merchant's RSA private key."""
    if not priv_key_b64:
        return ""
    pem = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        + "\n".join(priv_key_b64[i:i+64] for i in range(0, len(priv_key_b64), 64))
        + "\n-----END RSA PRIVATE KEY-----"
    )
    priv = serialization.load_pem_private_key(pem.encode(), password=None)
    sig = priv.sign(data.encode(), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(sig).decode()


@router.post("/nagad/initiate/{org_id}")
async def nagad_initiate(
    org_id: str,
    request: Request,
    db: Session = Depends(get_db),
    order_id: str | None = Form(default=None),
):
    """Initialize a Nagad payment. Returns {callBackUrl} to redirect the customer."""
    if not order_id:
        try: body = await request.json(); order_id = body.get("order_id")
        except Exception: pass
    order = _get_order(order_id or "", org_id, db)

    store = db.scalar(select(Store).where(Store.organization_id == org_id))
    if not store:
        raise HTTPException(404, "Store not found")

    mid, mnum, pub_key, priv_key, is_live = _nagad_creds(store)
    base_url = _nagad_base(is_live)
    callback = f"{_base_url(request)}/api/public/payment/nagad/callback"
    order_ref = order.document_number

    from datetime import datetime, timezone
    dt = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    # Sensitive payload to encrypt with Nagad public key
    sensitive = json.dumps({
        "merchantId": mid,
        "datetime": dt,
        "orderId": order_ref,
        "challenge": str(uuid.uuid4()).replace("-", "")[:20],
    })

    try:
        encrypted_sensitive = _nagad_encrypt(sensitive, pub_key)
        if not priv_key:
            raise HTTPException(409, "Nagad live signing key is not configured for this store.")
        signature = _nagad_sign(sensitive, priv_key)
    except Exception as e:
        raise HTTPException(502, f"Nagad encryption error: {e}")

    headers = {
        "Content-Type": "application/json",
        "X-KM-Api-Version": "v-0.2.0",
        "X-KM-IP-V4": request.client.host if request.client else "127.0.0.1",
        "X-KM-Client-Type": "PC_WEB",
    }
    init_url = f"{base_url}/remote-payment-gateway-1.0/api/dfs/check-out/initialize/{mid}/{order_ref}"
    body = {
        "dateTime": dt,
        "sensitiveData": encrypted_sensitive,
        "signature": signature,
    }

    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(init_url, json=body, headers=headers)

    data = r.json()
    if not data.get("callBackUrl"):
        raise HTTPException(502, f"Nagad init error: {data.get('message', data)}")

    # Extract payment reference ID for later confirmation
    payment_ref = data.get("paymentReferenceId", "")
    meta = json.loads(order.notes or "{}")
    meta.update({"_nagad_ref": payment_ref, "_nagad_mid": mid, "_nagad_live": is_live, "_nagad_priv": priv_key})
    order.notes = json.dumps(meta)
    db.commit()

    return {
        "callBackUrl": data["callBackUrl"],
        "paymentReferenceId": payment_ref,
        "order_number": order.document_number,
        "amount": float(order.total or 0),
    }


@router.get("/nagad/callback")
async def nagad_callback(
    request: Request,
    db: Session = Depends(get_db),
    payment_ref_id: str = "",
    status: str = "",
    order_id: str = "",
):
    """Nagad redirects here after payment."""
    base = _base_url(request)

    if status != "Success" or not payment_ref_id:
        return RedirectResponse(f"{base}/#/payment-result?status=cancelled&gateway=nagad", status_code=303)

    # Find order with this Nagad reference
    orders = db.scalars(select(SalesDocument).where(
        SalesDocument.notes.contains(payment_ref_id)
    )).all()
    order = next((o for o in orders if payment_ref_id in (o.notes or "")), None)

    if not order:
        return RedirectResponse(f"{base}/#/payment-result?status=error&gateway=nagad", status_code=303)

    # Verify the provider response against the exact order and merchant reference.
    try:
        meta = json.loads(order.notes or "{}")
        if str(meta.get("_nagad_ref") or "") != payment_ref_id:
            raise ValueError("Nagad payment reference mismatch")
        if order_id and str(order_id) != str(order.document_number):
            raise ValueError("Nagad order reference mismatch")
        mid = meta.get("_nagad_mid")
        is_live = bool(meta.get("_nagad_live"))
        if not mid or not is_live:
            raise ValueError("Nagad live callback metadata is incomplete")
        if order.payment_status != "paid":
            base_url = _nagad_base(is_live)
            verify_url = f"{base_url}/remote-payment-gateway-1.0/api/dfs/verify/payment/{payment_ref_id}"
            headers = {"X-KM-Api-Version": "v-0.2.0", "X-KM-IP-V4": "127.0.0.1", "X-KM-Client-Type": "PC_WEB"}
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.get(verify_url, headers=headers)
            vdata = r.json()
            if _nagad_payment_verified(vdata, payment_ref_id, mid, order):
                order.payment_status = "paid"
            else:
                order.payment_status = "payment_failed"
            db.commit()
    except Exception:
        if order.payment_status != "paid":
            order.payment_status = "payment_failed"
            db.commit()

    result = "success" if order.payment_status == "paid" else "failed"
    return _order_redirect(order.organization_id, order.access_token, result, base)


# ═══════════════════════════════════════════════════════════════════════════════
# SSLCommerz (all-in-one gateway: bKash + Nagad + cards)
# ═══════════════════════════════════════════════════════════════════════════════

def _sslcz_creds(store: Store) -> tuple[str, str, bool]:
    """Return only store-owned live SSLCommerz credentials."""
    sid, spwd = store.sslcz_store_id, store.sslcz_store_passwd
    if not sid or not spwd or not bool(store.sslcz_is_live):
        raise HTTPException(409, "SSLCommerz live credentials are not configured for this store.")
    return sid, spwd, True

def _amount_matches(actual: object, expected: object) -> bool:
    try:
        return Decimal(str(actual)).quantize(Decimal("0.01")) == Decimal(str(expected)).quantize(Decimal("0.01"))
    except Exception:
        return False


def _bkash_payment_verified(result: dict, payment_id: str, order: SalesDocument) -> bool:
    return (
        result.get("statusCode") == "0000"
        and str(result.get("paymentID") or "") == payment_id
        and str(result.get("currency") or "").upper() == "BDT"
        and _amount_matches(result.get("amount"), order.total)
    )


def _nagad_payment_verified(result: dict, payment_ref: str, merchant_id: str, order: SalesDocument) -> bool:
    returned_ref = result.get("paymentReferenceId") or result.get("payment_ref_id") or result.get("paymentRefId")
    returned_merchant = result.get("merchantId") or result.get("merchant_id")
    returned_order = result.get("orderId") or result.get("order_id")
    return (
        result.get("status") == "Success"
        and _amount_matches(result.get("amount") or result.get("amountBDT"), order.total)
        and (returned_ref is None or str(returned_ref) == payment_ref)
        and (returned_merchant is None or str(returned_merchant) == merchant_id)
        and (returned_order is None or str(returned_order) == order.document_number)
    )


def _sslcz_payment_verified(result: dict, order: SalesDocument, store: Store) -> bool:
    currency = result.get("currency") or result.get("currency_type")
    return (
        result.get("status") in ("VALID", "VALIDATED")
        and str(result.get("tran_id") or "") == order.id
        and str(result.get("store_id") or "") == str(store.sslcz_store_id)
        and str(currency or "").upper() == "BDT"
        and _amount_matches(result.get("amount"), order.total)
    )


@router.post("/initiate/{org_id}")
async def sslcz_initiate(
    org_id: str,
    request: Request,
    db: Session = Depends(get_db),
    order_id: str | None = Form(default=None),
    customer_email: str = Form(default=""),
    customer_city: str = Form(default=""),
):
    if not order_id:
        try:
            body = await request.json()
            order_id = body.get("order_id")
            customer_email = body.get("customer_email") or customer_email
            customer_city = body.get("customer_city") or customer_city
        except Exception:
            pass
    order = _get_order(order_id or "", org_id, db)
    customer_email = customer_email.strip().lower()
    customer_city = customer_city.strip()[:80]
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", customer_email):
        raise HTTPException(422, "A valid customer email is required for SSLCommerz checkout.")
    if not customer_city or not order.shipping_name or not order.shipping_phone or not order.shipping_address:
        raise HTTPException(422, "Complete customer name, phone, address and division are required for SSLCommerz checkout.")
    if not order.access_token:
        raise HTTPException(409, "This order is not eligible for public online payment.")

    store = db.scalar(select(Store).where(Store.organization_id == org_id))
    if not store:
        raise HTTPException(404, "Store not found")

    sid, spwd, is_live = _sslcz_creds(store)
    base = _base_url(request)
    amount = float(order.total or 0)
    if amount <= 0:
        raise HTTPException(400, "Order total must be > 0")

    if not is_live:
        raise HTTPException(409, "SSLCommerz live checkout is not enabled for this store.")
    init_url = SSLCZ_LIVE_INIT
    payload = {
        "store_id": sid, "store_passwd": spwd,
        "total_amount": f"{amount:.2f}", "currency": "BDT",
        "tran_id": order.id,
        "success_url": f"{base}/api/public/payment/success",
        "fail_url":    f"{base}/api/public/payment/fail",
        "cancel_url":  f"{base}/api/public/payment/cancel",
        "ipn_url":     f"{base}/api/public/payment/ipn",
        "cus_name":    order.shipping_name,
        "cus_email":   customer_email,
        "cus_phone":   order.shipping_phone,
        "cus_add1":    order.shipping_address,
        "cus_city":    customer_city, "cus_country": "Bangladesh",
        "ship_name":   order.shipping_name,
        "ship_add1":   order.shipping_address,
        "ship_city":   customer_city, "ship_postcode": "1000", "ship_country": "Bangladesh",
        "shipping_method": "Courier",
        "product_name": f"Order #{order.document_number}",
        "product_category": "general", "product_profile": "general",
        "num_of_item": "1",
        "multi_card_name": "mastercard,visacard,amexcard,bKash,nagad",
        "value_a": order.id, "value_b": org_id, "value_c": order.access_token,
    }
    async with httpx.AsyncClient(timeout=30) as c:
        resp = await c.post(init_url, data=payload)
    data = resp.json()
    if data.get("status") != "SUCCESS":
        raise HTTPException(502, f"SSLCommerz error: {data.get('failedreason', data)}")
    return {"gateway_url": data["GatewayPageURL"], "session_key": data.get("sessionkey", "")}


@router.post("/success")
async def sslcz_success(
    request: Request, db: Session = Depends(get_db),
    val_id: str = Form(...), tran_id: str = Form(...),
    value_b: str = Form(""), value_c: str = Form(""),
):
    store = db.scalar(select(Store).where(Store.organization_id == value_b))
    if not store:
        return RedirectResponse("/#/", status_code=303)
    sid, spwd, is_live = _sslcz_creds(store)
    if not is_live:
        raise HTTPException(409, "SSLCommerz live payment validation is not enabled for this store.")
    val_url = SSLCZ_LIVE_VAL
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(val_url, params={"val_id": val_id, "store_id": sid, "store_passwd": spwd, "format": "json"})
    vdata = r.json()
    order = db.scalar(select(SalesDocument).where(
        SalesDocument.id == tran_id, SalesDocument.organization_id == value_b,
    ))
    if not order or not value_c or order.access_token != value_c:
        return RedirectResponse(f"{_base_url(request)}/#/payment-result?status=error&gateway=sslcommerz", status_code=303)
    if order.payment_status != "paid":
        order.payment_status = "paid" if _sslcz_payment_verified(vdata, order, store) else "payment_failed"
        db.commit()
    return _order_redirect(value_b, value_c, "success" if order.payment_status == "paid" else "failed", _base_url(request))


@router.post("/fail")
async def sslcz_fail(
    request: Request, db: Session = Depends(get_db),
    tran_id: str = Form(...), value_b: str = Form(""), value_c: str = Form(""),
):
    order = db.scalar(select(SalesDocument).where(
        SalesDocument.id == tran_id, SalesDocument.organization_id == value_b,
    ))
    if not order or not value_c or order.access_token != value_c:
        return RedirectResponse(f"{_base_url(request)}/#/payment-result?status=error&gateway=sslcommerz", status_code=303)
    if order.payment_status != "paid":
        order.payment_status = "payment_failed"
        db.commit()
    return _order_redirect(value_b, value_c, "fail", _base_url(request))


@router.post("/cancel")
async def sslcz_cancel(
    request: Request,
    tran_id: str = Form(...), value_b: str = Form(""), value_c: str = Form(""),
    db: Session = Depends(get_db),
):
    return _order_redirect(value_b, value_c, "cancel", _base_url(request))


@router.post("/ipn")
async def sslcz_ipn(
    request: Request, db: Session = Depends(get_db),
    val_id: str = Form(""), tran_id: str = Form(""), value_b: str = Form(""),
):
    if not val_id or not tran_id or not value_b: return {"status": "ignored"}
    store = db.scalar(select(Store).where(Store.organization_id == value_b))
    if not store: return {"status": "store_not_found"}
    sid, spwd, is_live = _sslcz_creds(store)
    if not is_live:
        raise HTTPException(409, "SSLCommerz live payment validation is not enabled for this store.")
    val_url = SSLCZ_LIVE_VAL
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(val_url, params={"val_id": val_id, "store_id": sid, "store_passwd": spwd, "format": "json"})
    vdata = r.json()
    order = db.scalar(select(SalesDocument).where(
        SalesDocument.id == tran_id, SalesDocument.organization_id == value_b,
    ))
    if order and order.payment_status != "paid":
        order.payment_status = "paid" if _sslcz_payment_verified(vdata, order, store) else "payment_failed"
        db.commit()
    return {"status": "ok" if order else "order_not_found"}


# ── Query payment status (public) ─────────────────────────────────────────────
@router.get("/status/{org_id}/{order_id}")
def payment_status(org_id: str, order_id: str, db: Session = Depends(get_db)):
    order = db.scalar(select(SalesDocument).where(
        SalesDocument.id == order_id, SalesDocument.organization_id == org_id,
    ))
    if not order: raise HTTPException(404)
    return {"payment_status": order.payment_status, "order_number": order.document_number}
