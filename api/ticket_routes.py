"""Support tickets (SRD Panel C07). Resolution happens through the normal
return/refund/order workflow elsewhere; a ticket tracks the conversation and
SLA, it never itself mutates stock, money or an order.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .app_schemas import TicketCreate, TicketMessageCreate, TicketMessageView, TicketUpdate, TicketView
from .audit import record_audit
from .auth import CurrentMembership, CurrentUser
from .database import get_db
from .domain_models import Branch, Customer, Membership, SupportTicket, TicketMessage
from .notifications import notify_roles
from .permissions import require_permission

router = APIRouter(prefix="/api/app/tickets", tags=["tickets"])
Db = Annotated[Session, Depends(get_db)]


def _get_ticket(db: Session, membership: Membership, ticket_id: str) -> SupportTicket:
    ticket = db.scalar(select(SupportTicket).where(
        SupportTicket.id == ticket_id, SupportTicket.organization_id == membership.organization_id,
    ))
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.post("", response_model=TicketView)
def create_ticket(payload: TicketCreate, membership: CurrentMembership, user: CurrentUser, db: Db):
    require_permission(membership, "tickets:write")
    if payload.branch_id is not None:
        branch = db.scalar(select(Branch).where(
            Branch.id == payload.branch_id, Branch.organization_id == membership.organization_id))
        if branch is None:
            raise HTTPException(status_code=404, detail="Branch not found")
    if payload.customer_id is not None:
        customer = db.scalar(select(Customer).where(
            Customer.id == payload.customer_id, Customer.organization_id == membership.organization_id))
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer not found")
    ticket = SupportTicket(
        organization_id=membership.organization_id, created_by_user_id=user.id,
        **payload.model_dump(),
    )
    db.add(ticket)
    db.flush()
    record_audit(db, membership, "ticket.created", "support_ticket", ticket.id,
                 subject=ticket.subject, priority=ticket.priority)
    if ticket.priority in ("high", "urgent"):
        notify_roles(
            db, membership.organization_id, ("owner", "manager"), "action_required",
            title=f"{ticket.priority.title()} priority ticket: {ticket.subject}",
            severity="warning" if ticket.priority == "high" else "critical",
            link_type="support_ticket", link_id=ticket.id,
        )
    db.commit()
    return ticket


@router.get("", response_model=list[TicketView])
def list_tickets(
    membership: CurrentMembership, db: Db,
    status: str | None = Query(default=None, pattern=r"^(open|pending|resolved|closed)$"),
    assigned_to_user_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    require_permission(membership, "tickets:read")
    query = select(SupportTicket).where(SupportTicket.organization_id == membership.organization_id)
    if status:
        query = query.where(SupportTicket.status == status)
    if assigned_to_user_id:
        query = query.where(SupportTicket.assigned_to_user_id == assigned_to_user_id)
    return list(db.scalars(query.order_by(SupportTicket.created_at.desc()).limit(limit)))


@router.get("/{ticket_id}", response_model=TicketView)
def get_ticket(ticket_id: str, membership: CurrentMembership, db: Db):
    require_permission(membership, "tickets:read")
    return _get_ticket(db, membership, ticket_id)


@router.patch("/{ticket_id}", response_model=TicketView)
def update_ticket(ticket_id: str, payload: TicketUpdate, membership: CurrentMembership, db: Db):
    require_permission(membership, "tickets:write")
    ticket = _get_ticket(db, membership, ticket_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="Nothing to change")
    before = {field: getattr(ticket, field) for field in changes}
    for field, value in changes.items():
        setattr(ticket, field, value)
    if changes.get("status") in ("resolved", "closed") and ticket.resolved_at is None:
        ticket.resolved_at = datetime.now(timezone.utc)
    elif changes.get("status") in ("open", "pending"):
        ticket.resolved_at = None
    record_audit(db, membership, "ticket.updated", "support_ticket", ticket.id,
                 before=before, after=changes)
    db.commit()
    return ticket


@router.post("/{ticket_id}/messages", response_model=TicketMessageView)
def add_message(
    ticket_id: str, payload: TicketMessageCreate, membership: CurrentMembership, user: CurrentUser, db: Db,
):
    require_permission(membership, "tickets:write")
    ticket = _get_ticket(db, membership, ticket_id)
    message = TicketMessage(ticket_id=ticket.id, author_user_id=user.id, **payload.model_dump())
    db.add(message)
    db.commit()
    return message


@router.get("/{ticket_id}/messages", response_model=list[TicketMessageView])
def list_messages(ticket_id: str, membership: CurrentMembership, db: Db):
    require_permission(membership, "tickets:read")
    _get_ticket(db, membership, ticket_id)
    return list(db.scalars(
        select(TicketMessage).where(TicketMessage.ticket_id == ticket_id)
        .order_by(TicketMessage.created_at.asc())
    ))
