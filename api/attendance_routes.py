"""Attendance (SRD Panel H03). Self-service check-in/out needs no special
permission beyond active membership, same as the Notification Center -- it is
your own record. Viewing the whole team's attendance, or correcting someone
else's, is a manager/HR-level permission.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .app_schemas import AttendanceCheckIn, AttendanceCorrection, AttendanceView
from .audit import record_audit
from .auth import CurrentMembership, CurrentUser
from .database import get_db
from .domain_models import AttendanceRecord, Branch
from .permissions import require_permission

router = APIRouter(prefix="/api/app/attendance", tags=["attendance"])
Db = Annotated[Session, Depends(get_db)]


@router.post("/check-in", response_model=AttendanceView)
def check_in(payload: AttendanceCheckIn, membership: CurrentMembership, user: CurrentUser, db: Db):
    open_record = db.scalar(select(AttendanceRecord).where(
        AttendanceRecord.organization_id == membership.organization_id,
        AttendanceRecord.user_id == user.id, AttendanceRecord.check_out_at.is_(None),
    ))
    if open_record is not None:
        raise HTTPException(status_code=409, detail="Already checked in; check out first")
    if payload.branch_id is not None:
        branch = db.scalar(select(Branch).where(
            Branch.id == payload.branch_id, Branch.organization_id == membership.organization_id))
        if branch is None:
            raise HTTPException(status_code=404, detail="Branch not found")
    record = AttendanceRecord(
        organization_id=membership.organization_id, user_id=user.id,
        branch_id=payload.branch_id, note=payload.note,
        check_in_at=datetime.now(timezone.utc), source="device",
    )
    db.add(record)
    db.commit()
    return record


@router.post("/check-out", response_model=AttendanceView)
def check_out(membership: CurrentMembership, user: CurrentUser, db: Db):
    record = db.scalar(select(AttendanceRecord).where(
        AttendanceRecord.organization_id == membership.organization_id,
        AttendanceRecord.user_id == user.id, AttendanceRecord.check_out_at.is_(None),
    ).order_by(AttendanceRecord.check_in_at.desc()))
    if record is None:
        raise HTTPException(status_code=409, detail="Not checked in")
    record.check_out_at = datetime.now(timezone.utc)
    db.commit()
    return record


@router.get("/me", response_model=list[AttendanceView])
def my_attendance(membership: CurrentMembership, user: CurrentUser, db: Db, limit: int = Query(default=50, ge=1, le=500)):
    rows = db.scalars(
        select(AttendanceRecord).where(
            AttendanceRecord.organization_id == membership.organization_id, AttendanceRecord.user_id == user.id,
        ).order_by(AttendanceRecord.check_in_at.desc()).limit(limit)
    )
    return list(rows)


@router.get("", response_model=list[AttendanceView])
def list_attendance(
    membership: CurrentMembership, db: Db,
    user_id: str | None = Query(default=None),
    branch_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
):
    """Team-wide attendance -- HR/manager/owner only (SRD H01 Staff Directory's data source)."""
    require_permission(membership, "attendance:read")
    query = select(AttendanceRecord).where(AttendanceRecord.organization_id == membership.organization_id)
    if user_id:
        query = query.where(AttendanceRecord.user_id == user_id)
    if branch_id:
        query = query.where(AttendanceRecord.branch_id == branch_id)
    return list(db.scalars(query.order_by(AttendanceRecord.check_in_at.desc()).limit(limit)))


@router.post("/correct", response_model=AttendanceView)
def correct_attendance(payload: AttendanceCorrection, membership: CurrentMembership, db: Db):
    """Fix a missing/wrong punch. Adds a new record; the original (if any) is untouched."""
    require_permission(membership, "attendance:correct")
    if payload.check_out_at is not None and payload.check_out_at <= payload.check_in_at:
        raise HTTPException(status_code=422, detail="Check-out must be after check-in")
    if payload.branch_id is not None:
        branch = db.scalar(select(Branch).where(
            Branch.id == payload.branch_id, Branch.organization_id == membership.organization_id))
        if branch is None:
            raise HTTPException(status_code=404, detail="Branch not found")
    record = AttendanceRecord(
        organization_id=membership.organization_id, user_id=payload.user_id,
        branch_id=payload.branch_id, check_in_at=payload.check_in_at, check_out_at=payload.check_out_at,
        source="manager_correction", note=payload.note,
    )
    db.add(record)
    db.flush()
    record_audit(db, membership, "attendance.corrected", "attendance_record", record.id,
                 user_id=payload.user_id, reason=payload.note)
    db.commit()
    return record
