"""Available-to-promise: on-hand minus active, unexpired reservations.

Imported by `commerce_routes.py`'s sale stock check and `reservation_routes.py`;
kept dependency-free of both so neither has to import the other.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .domain_models import Reservation

ZERO = Decimal("0")


def reserved_quantity(db: Session, org_id: str, branch_id: str, product_id: str) -> Decimal:
    """Sum of this product's active reservations that haven't expired.

    An expired reservation is treated as gone the moment it's read, with no
    background sweep needed -- the next read of this product's availability
    is already correct.
    """
    now = datetime.now(timezone.utc)
    total = db.scalar(select(func.coalesce(func.sum(Reservation.quantity), 0)).where(
        Reservation.organization_id == org_id, Reservation.branch_id == branch_id,
        Reservation.product_id == product_id, Reservation.status == "active",
        Reservation.expires_at > now,
    ))
    return Decimal(total)
