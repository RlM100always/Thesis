"""Append-only audit trail for tenant actions.

``record_audit`` adds a row to the caller's session; the route commits it in the
same transaction as the change it describes, so an action and its audit entry
succeed or fail together. There is deliberately no update or delete API for
audit rows.

Details go in ``metadata_json``. Record *what changed* (ids, amounts, roles),
never secrets: no passwords, tokens or raw phone numbers.
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from .domain_models import AuditLog, Membership


def record_audit(
    db: Session, membership: Membership, action: str, entity_type: str,
    entity_id: str | None = None, **details,
) -> None:
    db.add(AuditLog(
        organization_id=membership.organization_id,
        actor_user_id=membership.user_id,
        action=action, entity_type=entity_type, entity_id=entity_id,
        metadata_json=json.dumps(details, ensure_ascii=False, default=str) if details else None,
    ))
