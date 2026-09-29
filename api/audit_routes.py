"""Read side of the audit trail: who did what, when, in this business."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from .auth import CurrentMembership
from .database import get_db
from .domain_models import AuditLog, User
from .permissions import require_permission

router = APIRouter(prefix="/api/app")
Db = Annotated[Session, Depends(get_db)]

# Action names are lowercase words joined by dots/underscores (``staff.invited``).
# Validating the prefix keeps LIKE wildcards out of the query.
PREFIX = re.compile(r"^[a-z_.]{1,80}$")


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        stamp, row_id = cursor.split("|", 1)
        return datetime.fromisoformat(stamp), row_id
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid cursor") from exc


def _details(raw: str | None):
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None  # never let one malformed row break the whole page


@router.get("/audit", tags=["audit"])
def list_audit(
    membership: CurrentMembership, db: Db,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
    actions: str | None = Query(default=None, max_length=400, description="Comma-separated action prefixes"),
    actor: str | None = Query(default=None, max_length=36),
):
    """Newest first. Page with ``next_cursor``; filter by action prefix or actor."""
    require_permission(membership, "audit:read")
    statement = (
        select(AuditLog, User)
        .outerjoin(User, User.id == AuditLog.actor_user_id)
        .where(AuditLog.organization_id == membership.organization_id)
    )
    if actions:
        prefixes = [p.strip() for p in actions.split(",") if p.strip()]
        if not prefixes or any(not PREFIX.match(p) for p in prefixes):
            raise HTTPException(status_code=422, detail="Invalid action filter")
        statement = statement.where(or_(*[AuditLog.action.like(f"{p}%") for p in prefixes]))
    if actor:
        statement = statement.where(AuditLog.actor_user_id == actor)
    if cursor:
        stamp, row_id = _decode_cursor(cursor)
        statement = statement.where(or_(
            AuditLog.created_at < stamp,
            and_(AuditLog.created_at == stamp, AuditLog.id < row_id),
        ))
    rows = db.execute(
        statement.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit + 1)
    ).all()

    page, extra = rows[:limit], rows[limit:]
    items = [{
        "id": entry.id,
        "created_at": entry.created_at.isoformat(),
        "action": entry.action,
        "entity_type": entry.entity_type,
        "entity_id": entry.entity_id,
        "actor": None if user is None else {
            "id": user.id, "name": user.display_name, "email": user.email,
        },
        "details": _details(entry.metadata_json),
    } for entry, user in page]
    next_cursor = f"{page[-1][0].created_at.isoformat()}|{page[-1][0].id}" if extra else None
    return {"items": items, "next_cursor": next_cursor}
