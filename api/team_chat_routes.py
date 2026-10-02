"""One shared staff chat channel per organization.

Deliberately simple: no DMs, no per-branch rooms, no read receipts. A small
shop's team already coordinates in one WhatsApp group; this gives them the
same thing without leaving the app. Polled by the frontend (GET with
`after_id`), not websockets -- consistent with the rest of this app's
REST-only architecture, and a chat channel for a handful of staff does not
need push infrastructure.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .app_schemas import TeamMessageCreate, TeamMessageView
from .auth import CurrentMembership, CurrentUser
from .database import get_db
from .domain_models import TeamMessage, User

router = APIRouter(prefix="/api/app/team-chat", tags=["team-chat"])
Db = Annotated[Session, Depends(get_db)]


def _view(message: TeamMessage, author_name: str) -> TeamMessageView:
    return TeamMessageView(
        id=message.id, user_id=message.user_id, author_name=author_name,
        branch_id=message.branch_id, body=message.body, created_at=message.created_at,
    )


@router.get("/messages", response_model=list[TeamMessageView])
def list_messages(
    membership: CurrentMembership, db: Db,
    after_id: str | None = Query(default=None, description="Return only messages newer than this id"),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Any active staff member can read -- there's no finer-grained
    permission here on purpose, matching a single shared channel."""
    query = (
        select(TeamMessage, User.display_name)
        .join(User, User.id == TeamMessage.user_id)
        .where(TeamMessage.organization_id == membership.organization_id)
    )
    if after_id:
        anchor = db.get(TeamMessage, after_id)
        if anchor is not None:
            query = query.where(TeamMessage.created_at > anchor.created_at)
    rows = db.execute(query.order_by(TeamMessage.created_at.desc()).limit(limit)).all()
    return [_view(message, name) for message, name in reversed(rows)]


@router.post("/messages", response_model=TeamMessageView)
def post_message(payload: TeamMessageCreate, membership: CurrentMembership, user: CurrentUser, db: Db):
    message = TeamMessage(
        organization_id=membership.organization_id, user_id=user.id,
        branch_id=payload.branch_id, body=payload.body.strip(),
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return _view(message, user.display_name)
