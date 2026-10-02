"""Read side of the Notification Center (SRD Panel G03): mine, unread count,
read/snooze/mark-all. Writing a notification is ``api/notifications.py``,
called by the domain routes that actually know something happened.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .app_schemas import NotificationView
from .auth import CurrentMembership, CurrentUser
from .database import get_db
from .domain_models import Notification

router = APIRouter(prefix="/api/app/notifications", tags=["notifications"])
Db = Annotated[Session, Depends(get_db)]


def _get(db: Session, membership, user, notification_id: str) -> Notification:
    row = db.scalar(select(Notification).where(
        Notification.id == notification_id, Notification.organization_id == membership.organization_id,
        Notification.recipient_user_id == user.id,
    ))
    if row is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return row


@router.get("", response_model=list[NotificationView])
def list_notifications(
    membership: CurrentMembership, user: CurrentUser, db: Db,
    unread_only: bool = Query(default=False),
    include_snoozed: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Every actor panel sees only their own notifications -- no permission
    gate beyond being a member of this organization, same as "My Work"."""
    now = datetime.now(timezone.utc)
    query = select(Notification).where(
        Notification.organization_id == membership.organization_id,
        Notification.recipient_user_id == user.id,
    )
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    if not include_snoozed:
        query = query.where(or_(Notification.snoozed_until.is_(None), Notification.snoozed_until <= now))
    return list(db.scalars(query.order_by(Notification.created_at.desc()).limit(limit)))


@router.get("/unread-count")
def unread_count(membership: CurrentMembership, user: CurrentUser, db: Db):
    now = datetime.now(timezone.utc)
    count = db.scalar(select(func.count(Notification.id)).where(
        Notification.organization_id == membership.organization_id,
        Notification.recipient_user_id == user.id, Notification.read_at.is_(None),
        or_(Notification.snoozed_until.is_(None), Notification.snoozed_until <= now),
    ))
    return {"unread_count": count or 0}


@router.post("/{notification_id}/read", response_model=NotificationView)
def mark_read(notification_id: str, membership: CurrentMembership, user: CurrentUser, db: Db):
    notification = _get(db, membership, user, notification_id)
    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc)
        db.commit()
    return notification


@router.post("/read-all")
def mark_all_read(membership: CurrentMembership, user: CurrentUser, db: Db):
    now = datetime.now(timezone.utc)
    rows = db.scalars(select(Notification).where(
        Notification.organization_id == membership.organization_id,
        Notification.recipient_user_id == user.id, Notification.read_at.is_(None),
    )).all()
    for row in rows:
        row.read_at = now
    db.commit()
    return {"marked_read": len(rows)}


class SnoozeIn(BaseModel):
    until: datetime


@router.post("/{notification_id}/snooze", response_model=NotificationView)
def snooze(notification_id: str, payload: SnoozeIn, membership: CurrentMembership, user: CurrentUser, db: Db):
    notification = _get(db, membership, user, notification_id)
    now = datetime.now(timezone.utc)
    deadline = payload.until if payload.until.tzinfo else payload.until.replace(tzinfo=timezone.utc)
    if deadline <= now:
        raise HTTPException(status_code=422, detail="Snooze time must be in the future")
    notification.snoozed_until = deadline
    db.commit()
    return notification
