"""Public, source-attributed Bangladesh reference data."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .bangladesh_reference import rows
from .database import get_db
from .domain_models import ReferenceValue

router = APIRouter(prefix="/api/reference", tags=["reference data"])
Db = Annotated[Session, Depends(get_db)]


def seed_bangladesh_reference(db: Session) -> None:
    existing = {(kind, code) for kind, code in db.execute(
        select(ReferenceValue.kind, ReferenceValue.code)
    )}
    for row in rows():
        if (row["kind"], row["code"]) not in existing:
            db.add(ReferenceValue(**row))


@router.get("/bangladesh")
def bangladesh_reference(db: Db):
    # create_all-based local/test databases do not run Alembic, so seed once on
    # first read as well. Production gets the exact same records by migration.
    if db.scalar(select(ReferenceValue.id).limit(1)) is None:
        seed_bangladesh_reference(db)
        db.commit()
    values = list(db.scalars(select(ReferenceValue).order_by(
        ReferenceValue.kind, ReferenceValue.parent_code, ReferenceValue.label_en
    )))
    shaped = [({
        "code": row.code, "parent_code": row.parent_code,
        "label_en": row.label_en, "label_bn": row.label_bn,
        "details": row.details, "source_url": row.source_url,
        "verified_on": row.verified_on,
    }, row.kind) for row in values]
    return {
        "country": {"code": "BD", "label_en": "Bangladesh", "label_bn": "বাংলাদেশ"},
        "divisions": [row for row, kind in shaped if kind == "division"],
        "districts": [row for row, kind in shaped if kind == "district"],
        "mfs_providers": [row for row, kind in shaped if kind == "mfs_provider"],
    }
