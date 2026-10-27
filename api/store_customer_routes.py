"""Public store customer accounts: sign-up, sign-in, profile, order history, chat.

One account works across every B-SMART store. The JWT `typ` claim is ``"sc"``
(store-customer) so these tokens are never accepted by the business-staff auth
path and vice versa.
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .domain_models import Product, SalesDocument, SalesDocumentLine, Store, StoreCustomer, StoreMessage
from .security import DUMMY_HASH, hash_password, verify_password

router = APIRouter(prefix="/api/sc", tags=["store-customer"])
biz_router = APIRouter(prefix="/api/app/store-customers", tags=["store-customer-biz"])

Db = Session  # type alias; endpoints use db: Session = Depends(get_db)

_TOKEN_DAYS = 30
_EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


# ── JWT helpers ────────────────────────────────────────────────────────────────

def _issue(customer_id: str, token_version: int) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": customer_id,
        "typ": "sc",
        "tv": token_version,
        "iss": settings.app_name,
        "aud": settings.app_name,
        "iat": now,
        "exp": now + timedelta(days=_TOKEN_DAYS),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _decode(token: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience=settings.app_name, issuer=settings.app_name,
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("typ") != "sc":
        raise HTTPException(status_code=401, detail="Wrong token type")
    return payload


def _get_customer(authorization: str | None, db: Session, required: bool = True) -> StoreCustomer | None:
    if not authorization or not authorization.startswith("Bearer "):
        if required:
            raise HTTPException(status_code=401, detail="Authentication required")
        return None
    claims = _decode(authorization[7:])
    customer = db.get(StoreCustomer, claims["sub"])
    if not customer or not customer.is_active:
        raise HTTPException(status_code=401, detail="Account not found")
    if customer.token_version != claims.get("tv", 0):
        raise HTTPException(status_code=401, detail="Session revoked")
    return customer


# ── Schemas ────────────────────────────────────────────────────────────────────

class ScRegister(BaseModel):
    display_name: str = Field(min_length=2, max_length=100)
    email: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=20)
    password: str = Field(min_length=8, max_length=128)


class ScLogin(BaseModel):
    email_or_phone: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=128)


class ScProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    avatar_data_url: str | None = Field(default=None, max_length=1_500_000)
    division: str | None = Field(default=None, max_length=50)
    district: str | None = Field(default=None, max_length=50)
    thana: str | None = Field(default=None, max_length=80)
    address_detail: str | None = Field(default=None, max_length=400)


class ScMessageSend(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class ScBizReply(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


# ── Serializers ────────────────────────────────────────────────────────────────

def _customer_view(c: StoreCustomer) -> dict:
    return {
        "id": c.id,
        "display_name": c.display_name,
        "email": c.email,
        "phone": c.phone,
        "avatar_data_url": c.avatar_data_url,
        "division": c.division,
        "district": c.district,
        "thana": c.thana,
        "address_detail": c.address_detail,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _order_view(doc: SalesDocument, db: Session) -> dict:
    lines = db.scalars(
        select(SalesDocumentLine).where(SalesDocumentLine.document_id == doc.id)
    ).all()
    product_ids = [ln.product_id for ln in lines if ln.product_id]
    products_map = {
        p.id: p.name
        for p in db.scalars(select(Product).where(Product.id.in_(product_ids or [""]))).all()
    } if product_ids else {}
    return {
        "id": doc.id,
        "document_number": doc.document_number,
        "status": doc.status,
        "payment_status": getattr(doc, "payment_status", "pending"),
        "status_note": getattr(doc, "status_note", None),
        "issued_at": doc.issued_at.isoformat() if doc.issued_at else None,
        "subtotal": str(doc.subtotal),
        "delivery_fee": str(getattr(doc, "delivery_fee", 0) or 0),
        "total": str(doc.total),
        "notes": doc.notes,
        "access_token": doc.access_token,
        "organization_id": doc.organization_id,
        "shipping_name": doc.shipping_name,
        "shipping_phone": doc.shipping_phone,
        "shipping_address": doc.shipping_address,
        "items": [
            {
                "product_id": ln.product_id,
                "description": getattr(ln, "description", None) or products_map.get(ln.product_id, "পণ্য"),
                "quantity": str(ln.quantity),
                "unit_price": str(ln.unit_price),
                "line_total": str(ln.line_total),
            }
            for ln in lines
        ],
    }


def _msg_view(m: StoreMessage) -> dict:
    return {
        "id": m.id,
        "sender": m.sender,
        "body": m.body,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "read_at": m.read_at.isoformat() if m.read_at else None,
    }


# ── Auth endpoints ─────────────────────────────────────────────────────────────

@router.post("/register")
def register(payload: ScRegister, db: Db = Depends(get_db)):
    email = payload.email.strip().lower() if payload.email and payload.email.strip() else None
    phone = payload.phone.strip() if payload.phone and payload.phone.strip() else None
    if not email and not phone:
        raise HTTPException(status_code=422, detail="ইমেইল বা ফোন নম্বর দিতে হবে")
    if email and not re.fullmatch(_EMAIL_RE, email):
        raise HTTPException(status_code=422, detail="সঠিক ইমেইল ঠিকানা দিন")

    if email and db.scalar(select(StoreCustomer.id).where(func.lower(StoreCustomer.email) == email)):
        raise HTTPException(status_code=409, detail="এই ইমেইল দিয়ে আগেই অ্যাকাউন্ট আছে")
    if phone and db.scalar(select(StoreCustomer.id).where(StoreCustomer.phone == phone)):
        raise HTTPException(status_code=409, detail="এই ফোন নম্বর দিয়ে আগেই অ্যাকাউন্ট আছে")

    customer = StoreCustomer(
        display_name=payload.display_name.strip(),
        email=email,
        phone=phone,
        password_hash=hash_password(payload.password),
    )
    db.add(customer)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="এই ইমেইল বা ফোন নম্বর দিয়ে আগেই অ্যাকাউন্ট আছে")
    db.refresh(customer)
    return {"token": _issue(customer.id, customer.token_version), "customer": _customer_view(customer)}


@router.post("/login")
def login(payload: ScLogin, db: Db = Depends(get_db)):
    ep = payload.email_or_phone.strip().lower() if "@" in payload.email_or_phone else payload.email_or_phone.strip()
    if "@" in ep:
        customer = db.scalar(select(StoreCustomer).where(StoreCustomer.email == ep))
    else:
        customer = db.scalar(select(StoreCustomer).where(StoreCustomer.phone == ep))

    dummy = not customer
    if dummy:
        verify_password(payload.password, DUMMY_HASH)
        raise HTTPException(status_code=401, detail="ইমেইল/ফোন অথবা পাসওয়ার্ড ভুল")

    if not verify_password(payload.password, customer.password_hash):
        raise HTTPException(status_code=401, detail="ইমেইল/ফোন অথবা পাসওয়ার্ড ভুল")

    if not customer.is_active:
        raise HTTPException(status_code=403, detail="এই অ্যাকাউন্টটি নিষ্ক্রিয়")

    return {"token": _issue(customer.id, customer.token_version), "customer": _customer_view(customer)}


@router.get("/me")
def me(authorization: Annotated[str | None, Header()] = None, db: Db = Depends(get_db)):
    customer = _get_customer(authorization, db)
    return _customer_view(customer)


@router.patch("/me")
def update_me(
    payload: ScProfileUpdate,
    authorization: Annotated[str | None, Header()] = None,
    db: Db = Depends(get_db),
):
    customer = _get_customer(authorization, db)
    updates = payload.model_dump(exclude_unset=True)
    if "display_name" in updates and updates["display_name"] is not None:
        updates["display_name"] = updates["display_name"].strip()
    if "phone" in updates and updates["phone"]:
        updates["phone"] = updates["phone"].strip()
        existing = db.scalar(select(StoreCustomer.id).where(
            StoreCustomer.phone == updates["phone"], StoreCustomer.id != customer.id
        ))
        if existing:
            raise HTTPException(status_code=409, detail="এই ফোন নম্বর দিয়ে অন্য অ্যাকাউন্ট আছে")
    if updates.get("avatar_data_url") and not updates["avatar_data_url"].startswith("data:image/"):
        raise HTTPException(status_code=422, detail="প্রোফাইল ছবির ফরম্যাট সঠিক নয়")
    for field, value in updates.items():
        setattr(customer, field, value)
    db.commit()
    db.refresh(customer)
    return _customer_view(customer)


# ── Order history ──────────────────────────────────────────────────────────────

@router.get("/orders/{store_slug}")
def order_history(
    store_slug: str,
    status: str | None = None,
    page: int = 1,
    authorization: Annotated[str | None, Header()] = None,
    db: Db = Depends(get_db),
):
    customer = _get_customer(authorization, db)
    store = db.scalar(select(Store).where(Store.slug == store_slug))
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    q = select(SalesDocument).where(
        SalesDocument.organization_id == store.organization_id,
        SalesDocument.document_type == "order",
        # Match by linked account OR by phone number used at checkout
        (SalesDocument.store_customer_id == customer.id)
        | (SalesDocument.shipping_phone == customer.phone),
    )
    if status:
        q = q.where(SalesDocument.status == status)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    per_page = 10
    docs = db.scalars(q.order_by(SalesDocument.issued_at.desc()).offset((page - 1) * per_page).limit(per_page)).all()
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "orders": [_order_view(d, db) for d in docs],
    }


# ── Chat ──────────────────────────────────────────────────────────────────────

@router.get("/chat/{store_slug}")
def get_chat(
    store_slug: str,
    authorization: Annotated[str | None, Header()] = None,
    db: Db = Depends(get_db),
):
    customer = _get_customer(authorization, db)
    store = db.scalar(select(Store).where(Store.slug == store_slug))
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    msgs = db.scalars(
        select(StoreMessage)
        .where(StoreMessage.store_id == store.id, StoreMessage.customer_id == customer.id)
        .order_by(StoreMessage.created_at)
    ).all()

    # Mark store messages as read
    now = datetime.now(timezone.utc)
    for m in msgs:
        if m.sender == "store" and m.read_at is None:
            m.read_at = now
    db.commit()

    return {"messages": [_msg_view(m) for m in msgs]}


@router.post("/chat/{store_slug}")
def send_message(
    store_slug: str,
    payload: ScMessageSend,
    authorization: Annotated[str | None, Header()] = None,
    db: Db = Depends(get_db),
):
    customer = _get_customer(authorization, db)
    store = db.scalar(select(Store).where(Store.slug == store_slug))
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    msg = StoreMessage(
        store_id=store.id,
        customer_id=customer.id,
        sender="customer",
        body=payload.body,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return _msg_view(msg)


@router.get("/unread/{store_slug}")
def unread_count(
    store_slug: str,
    authorization: Annotated[str | None, Header()] = None,
    db: Db = Depends(get_db),
):
    """How many unread store-replies the customer has."""
    customer = _get_customer(authorization, db)
    store = db.scalar(select(Store).where(Store.slug == store_slug))
    if not store:
        return {"count": 0}
    count = db.scalar(
        select(func.count()).where(
            StoreMessage.store_id == store.id,
            StoreMessage.customer_id == customer.id,
            StoreMessage.sender == "store",
            StoreMessage.read_at.is_(None),
        )
    ) or 0
    return {"count": count}


# ── Business-side endpoints (require org JWT) ─────────────────────────────────

def _require_biz_customer(store_slug: str, authorization: str | None, db: Session) -> Store:
    """Validate business JWT and return store after verifying the caller belongs to its org."""
    from .auth import decode_token_claims
    from .domain_models import Membership
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    claims = decode_token_claims(authorization[7:], expected_type="access")
    store = db.scalar(select(Store).where(Store.slug == store_slug))
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    membership = db.scalar(select(Membership).where(
        Membership.user_id == claims["sub"],
        Membership.organization_id == store.organization_id,
        Membership.is_active.is_(True),
    ))
    if not membership:
        raise HTTPException(status_code=403, detail="Access denied")
    return store


@biz_router.get("/{store_slug}/analytics")
def customer_analytics(
    store_slug: str,
    authorization: Annotated[str | None, Header()] = None,
    db: Db = Depends(get_db),
):
    """Location breakdown + totals for all customers who ordered from this store."""
    store = _require_biz_customer(store_slug, authorization, db)

    # Customers who placed orders (by account or phone match)
    # Group by division/district/thana
    from sqlalchemy import case

    docs = db.scalars(
        select(SalesDocument).where(
            SalesDocument.organization_id == store.organization_id,
            SalesDocument.document_type == "order",
        )
    ).all()

    # Collect unique customer identifiers
    customer_ids = {d.store_customer_id for d in docs if d.store_customer_id}
    phones = {d.shipping_phone for d in docs if d.shipping_phone and not d.store_customer_id}

    customers_by_id = {
        c.id: c
        for c in db.scalars(select(StoreCustomer).where(StoreCustomer.id.in_(customer_ids))).all()
    } if customer_ids else {}

    customers_by_phone = {
        c.phone: c
        for c in db.scalars(select(StoreCustomer).where(StoreCustomer.phone.in_(phones))).all()
    } if phones else {}

    # Aggregate by location
    div_counts: dict[str, int] = {}
    dist_counts: dict[str, int] = {}
    thana_counts: dict[str, int] = {}
    registered = 0
    guest = 0

    seen_customers: set[str] = set()
    for doc in docs:
        cust = None
        if doc.store_customer_id:
            cust = customers_by_id.get(doc.store_customer_id)
        elif doc.shipping_phone:
            cust = customers_by_phone.get(doc.shipping_phone)

        if cust:
            if cust.id not in seen_customers:
                seen_customers.add(cust.id)
                registered += 1
                div = cust.division or "অজানা"
                dist = cust.district or "অজানা"
                thana = cust.thana or "অজানা"
                div_counts[div] = div_counts.get(div, 0) + 1
                dist_counts[dist] = dist_counts.get(dist, 0) + 1
                thana_counts[thana] = thana_counts.get(thana, 0) + 1
        else:
            guest += 1

    # Recent registered customers
    recent = db.scalars(
        select(StoreCustomer)
        .where(StoreCustomer.id.in_(list(customer_ids)[:100]))
        .order_by(StoreCustomer.created_at.desc())
        .limit(20)
    ).all() if customer_ids else []

    # ── Customer segments (RFM-lite) ──────────────────────────────────────────
    from datetime import datetime, timezone as tz, timedelta
    now = datetime.now(tz.utc)

    # Build per-customer order stats
    cust_stats: dict[str, dict] = {}
    for doc in docs:
        cid = doc.store_customer_id or doc.shipping_phone
        if not cid:
            continue
        s = cust_stats.setdefault(cid, {"orders": 0, "last": doc.issued_at})
        s["orders"] += 1
        if doc.issued_at and (s["last"] is None or doc.issued_at > s["last"]):
            s["last"] = doc.issued_at

    segments: dict[str, int] = {"নতুন": 0, "নিয়মিত": 0, "ভিআইপি": 0, "নিষ্ক্রিয়": 0}
    for s in cust_stats.values():
        last = s["last"]
        # make offset-aware if naive
        if last and last.tzinfo is None:
            from datetime import timezone
            last = last.replace(tzinfo=timezone.utc)
        recency_days = (now - last).days if last else 999
        orders = s["orders"]
        if recency_days > 90:
            segments["নিষ্ক্রিয়"] += 1
        elif orders >= 5:
            segments["ভিআইপি"] += 1
        elif orders >= 2:
            segments["নিয়মিত"] += 1
        else:
            segments["নতুন"] += 1

    return {
        "total_orders": len(docs),
        "registered_customers": registered,
        "guest_orders": guest,
        "division_breakdown": sorted(div_counts.items(), key=lambda x: -x[1]),
        "district_breakdown": sorted(dist_counts.items(), key=lambda x: -x[1])[:20],
        "thana_breakdown": sorted(thana_counts.items(), key=lambda x: -x[1])[:20],
        "recent_customers": [_customer_view(c) for c in recent],
        "segments": segments,
    }


@biz_router.get("/{store_slug}/chat")
def biz_chat_inbox(
    store_slug: str,
    authorization: Annotated[str | None, Header()] = None,
    db: Db = Depends(get_db),
):
    """All chat threads for this store (one row per customer, latest message preview)."""
    store = _require_biz_customer(store_slug, authorization, db)

    # Latest message per customer
    subq = (
        select(
            StoreMessage.customer_id,
            func.max(StoreMessage.created_at).label("last_at"),
        )
        .where(StoreMessage.store_id == store.id)
        .group_by(StoreMessage.customer_id)
        .subquery()
    )
    rows = db.execute(
        select(StoreMessage, StoreCustomer)
        .join(subq, (StoreMessage.customer_id == subq.c.customer_id) & (StoreMessage.created_at == subq.c.last_at))
        .join(StoreCustomer, StoreCustomer.id == StoreMessage.customer_id)
        .where(StoreMessage.store_id == store.id)
        .order_by(subq.c.last_at.desc())
    ).all()

    # Unread counts per customer (messages from customer not yet read by store)
    unread_q = db.execute(
        select(StoreMessage.customer_id, func.count().label("cnt"))
        .where(
            StoreMessage.store_id == store.id,
            StoreMessage.sender == "customer",
            StoreMessage.read_at.is_(None),
        )
        .group_by(StoreMessage.customer_id)
    ).all()
    unread_map = {r.customer_id: r.cnt for r in unread_q}

    return {
        "threads": [
            {
                "customer": _customer_view(cust),
                "last_message": _msg_view(msg),
                "unread": unread_map.get(cust.id, 0),
            }
            for msg, cust in rows
        ]
    }


@biz_router.get("/{store_slug}/chat/{customer_id}")
def biz_get_thread(
    store_slug: str,
    customer_id: str,
    authorization: Annotated[str | None, Header()] = None,
    db: Db = Depends(get_db),
):
    store = _require_biz_customer(store_slug, authorization, db)
    customer = db.get(StoreCustomer, customer_id)
    if not customer:
        raise HTTPException(status_code=404)

    msgs = db.scalars(
        select(StoreMessage)
        .where(StoreMessage.store_id == store.id, StoreMessage.customer_id == customer_id)
        .order_by(StoreMessage.created_at)
    ).all()

    # Mark customer messages as read by store
    now = datetime.now(timezone.utc)
    for m in msgs:
        if m.sender == "customer" and m.read_at is None:
            m.read_at = now
    db.commit()

    return {"customer": _customer_view(customer), "messages": [_msg_view(m) for m in msgs]}


@biz_router.post("/{store_slug}/chat/{customer_id}/reply")
def biz_reply(
    store_slug: str,
    customer_id: str,
    payload: ScBizReply,
    authorization: Annotated[str | None, Header()] = None,
    db: Db = Depends(get_db),
):
    store = _require_biz_customer(store_slug, authorization, db)
    customer = db.get(StoreCustomer, customer_id)
    if not customer:
        raise HTTPException(status_code=404)

    msg = StoreMessage(
        store_id=store.id,
        customer_id=customer_id,
        sender="store",
        body=payload.body,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return _msg_view(msg)


@biz_router.get("/{store_slug}/unread")
def biz_unread_count(
    store_slug: str,
    authorization: Annotated[str | None, Header()] = None,
    db: Db = Depends(get_db),
):
    """Total unread customer messages for this store (for tab badge)."""
    store = _require_biz_customer(store_slug, authorization, db)
    count = db.scalar(
        select(func.count()).where(
            StoreMessage.store_id == store.id,
            StoreMessage.sender == "customer",
            StoreMessage.read_at.is_(None),
        )
    ) or 0
    return {"count": count}


@biz_router.get("/{store_slug}/customers/{customer_id}")
def biz_customer_detail(
    store_slug: str,
    customer_id: str,
    authorization: Annotated[str | None, Header()] = None,
    db: Db = Depends(get_db),
):
    """Full profile + order history for one customer."""
    store = _require_biz_customer(store_slug, authorization, db)
    customer = db.get(StoreCustomer, customer_id)
    if not customer:
        raise HTTPException(status_code=404)

    docs = db.scalars(
        select(SalesDocument)
        .where(
            SalesDocument.organization_id == store.organization_id,
            SalesDocument.document_type == "order",
            (SalesDocument.store_customer_id == customer_id)
            | (SalesDocument.shipping_phone == customer.phone),
        )
        .order_by(SalesDocument.issued_at.desc())
        .limit(20)
    ).all()

    return {
        "customer": _customer_view(customer),
        "orders": [_order_view(d, db) for d in docs],
    }
