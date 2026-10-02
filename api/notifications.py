"""Create in-app notifications (SRD Panel G03). The read/list/dismiss API lives
in ``notification_routes.py``; this module is the write side other routes call
into, kept separate so it carries no FastAPI/router import and can't create a
circular import with the route modules that need it.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .domain_models import Membership, Notification

CATEGORIES = ("action_required", "money", "stock", "staff", "system", "security")
SEVERITIES = ("info", "warning", "critical")


def notify_user(
    db: Session, organization_id: str, recipient_user_id: str, category: str, title: str,
    body: str | None = None, severity: str = "info", link_type: str | None = None, link_id: str | None = None,
) -> Notification:
    assert category in CATEGORIES, f"Unknown notification category: {category}"
    assert severity in SEVERITIES, f"Unknown notification severity: {severity}"
    notification = Notification(
        organization_id=organization_id, recipient_user_id=recipient_user_id,
        category=category, severity=severity, title=title, body=body,
        link_type=link_type, link_id=link_id,
    )
    db.add(notification)
    return notification


def notify_roles(
    db: Session, organization_id: str, roles: tuple[str, ...], category: str, title: str, **kwargs,
) -> list[Notification]:
    """Notify every active member holding one of ``roles`` -- e.g. every owner/manager
    when something needs attention above an individual's pay grade."""
    recipients = db.scalars(select(Membership.user_id).where(
        Membership.organization_id == organization_id, Membership.role.in_(roles),
        Membership.active.is_(True),
    )).all()
    return [
        notify_user(db, organization_id, user_id, category, title, **kwargs)
        for user_id in recipients
    ]
