"""Credential-safe notification outbox with deterministic sandbox delivery."""
from typing import Annotated, Literal
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .audit import record_audit
from .auth import CurrentMembership
from .config import get_settings
from .database import get_db
from .domain_models import OutboundMessage, utcnow
from .permissions import require_permission

router = APIRouter(prefix="/api/app/integrations", tags=["integrations"])
Db = Annotated[Session, Depends(get_db)]

class MessageIn(BaseModel):
    channel: Literal["sms", "whatsapp"]
    recipient: str = Field(min_length=10, max_length=40)
    template: str = Field(min_length=1, max_length=80)
    body: str = Field(min_length=1, max_length=1500)
    idempotency_key: str = Field(min_length=8, max_length=100)

def view(row):
    return {"id": row.id, "channel": row.channel, "recipient": row.recipient,
            "template": row.template, "status": row.status,
            "provider_message_id": row.provider_message_id, "last_error": row.last_error,
            "created_at": row.created_at, "sent_at": row.sent_at}

@router.post("/messages")
def send_message(body: MessageIn, membership: CurrentMembership, db: Db):
    require_permission(membership, "notifications:send")
    existing = db.scalar(select(OutboundMessage).where(
        OutboundMessage.organization_id == membership.organization_id,
        OutboundMessage.idempotency_key == body.idempotency_key))
    if existing:
        if existing.channel != body.channel or existing.recipient != body.recipient or existing.body != body.body:
            raise HTTPException(status_code=409, detail="Idempotency key was used for another message")
        return view(existing)
    settings = get_settings()
    configured = bool(settings.sms_api_key if body.channel == "sms" else
                      settings.whatsapp_access_token and settings.whatsapp_phone_number_id)
    if settings.integration_mode == "production" and not configured:
        raise HTTPException(status_code=503, detail=f"{body.channel} credentials are not configured")
    # Sandbox is an honest local delivery simulator. Production transport is
    # deliberately not called until provider-issued credentials exist.
    now = utcnow()
    row = OutboundMessage(
        organization_id=membership.organization_id, requested_by_user_id=membership.user_id,
        **body.model_dump(), status="simulated" if settings.integration_mode == "sandbox" else "queued",
        provider_message_id=f"sandbox-{uuid.uuid4()}" if settings.integration_mode == "sandbox" else None,
        sent_at=now if settings.integration_mode == "sandbox" else None)
    db.add(row); db.flush()
    record_audit(db, membership, "notification.queued", "outbound_message", row.id,
                 channel=row.channel, status=row.status)
    db.commit(); return view(row)

@router.get("/messages")
def messages(membership: CurrentMembership, db: Db, limit: int = Query(100, ge=1, le=500)):
    require_permission(membership, "notifications:read")
    return [view(row) for row in db.scalars(select(OutboundMessage).where(
        OutboundMessage.organization_id == membership.organization_id)
        .order_by(OutboundMessage.created_at.desc()).limit(limit))]
