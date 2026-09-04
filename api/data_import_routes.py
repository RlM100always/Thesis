"""Durable real-data intake, validation, provenance, and research export."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import CurrentMembership, CurrentUser
from .commerce_routes import require_role
from .database import get_db
from .domain_models import (
    ImportBatch, Product, SalesOrder, SalesOrderItem,
)

router = APIRouter(prefix="/api/app")
Db = Annotated[Session, Depends(get_db)]
MAX_BYTES = 25 * 1024 * 1024
UPLOAD_ROOT = Path("data/uploads")
REQUIRED_SALES_ROLES = ("invoice_number", "date", "sku", "quantity", "unit_price")


def read_frame(content: bytes, suffix: str) -> pd.DataFrame:
    try:
        if suffix == ".csv":
            return pd.read_csv(io.BytesIO(content))
        return pd.read_excel(io.BytesIO(content))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"File could not be parsed: {exc}") from exc


@router.post("/imports", tags=["real-data"])
async def upload_real_data(
    membership: CurrentMembership, user: CurrentUser, db: Db,
    file: UploadFile = File(...), source_system: str = Form("unknown"),
):
    require_role(membership, "owner", "manager", "accountant")
    filename = Path(file.filename or "upload.csv").name
    suffix = Path(filename).suffix.lower()
    if suffix not in {".csv", ".xlsx"}:
        raise HTTPException(status_code=400, detail="Only CSV and XLSX files are accepted")
    content = await file.read(MAX_BYTES + 1)
    if not content or len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File must be between 1 byte and 25 MB")
    checksum = hashlib.sha256(content).hexdigest()
    frame = read_frame(content, suffix)
    if frame.empty:
        raise HTTPException(status_code=400, detail="The file has no data rows")
    org_dir = UPLOAD_ROOT / membership.organization_id
    org_dir.mkdir(parents=True, exist_ok=True)
    stored = org_dir / f"{checksum}{suffix}"
    if not stored.exists():
        stored.write_bytes(content)
    batch = ImportBatch(
        organization_id=membership.organization_id, uploaded_by=user.id,
        original_filename=filename, stored_path=str(stored), checksum_sha256=checksum,
        source_system=source_system[:80], row_count=len(frame),
    )
    db.add(batch)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        batch = db.scalar(select(ImportBatch).where(
            ImportBatch.organization_id == membership.organization_id,
            ImportBatch.checksum_sha256 == checksum,
        ))
    return {
        "id": batch.id, "filename": batch.original_filename,
        "checksum_sha256": checksum, "row_count": len(frame),
        "columns": [str(c) for c in frame.columns],
        "sample_rows": frame.head(5).fillna("").astype(str).to_dict(orient="records"),
        "status": batch.status,
    }


@router.post("/imports/{batch_id}/validate-sales", tags=["real-data"])
def validate_sales_import(
    batch_id: str, mapping: dict[str, str], membership: CurrentMembership, db: Db,
):
    batch = db.scalar(select(ImportBatch).where(
        ImportBatch.id == batch_id, ImportBatch.organization_id == membership.organization_id
    ))
    if batch is None:
        raise HTTPException(status_code=404, detail="Import batch not found")
    missing_roles = [role for role in REQUIRED_SALES_ROLES if not mapping.get(role)]
    if missing_roles:
        raise HTTPException(status_code=422, detail=f"Missing mappings: {', '.join(missing_roles)}")
    path = Path(batch.stored_path)
    if not path.is_file():
        raise HTTPException(status_code=410, detail="Stored source file is unavailable")
    frame = read_frame(path.read_bytes(), path.suffix.lower())
    absent = [column for column in mapping.values() if column and column not in frame.columns]
    if absent:
        raise HTTPException(status_code=422, detail=f"Unknown columns: {', '.join(absent)}")
    errors = []
    quantity = pd.to_numeric(frame[mapping["quantity"]], errors="coerce")
    price = pd.to_numeric(frame[mapping["unit_price"]], errors="coerce")
    dates = pd.to_datetime(frame[mapping["date"]], errors="coerce")
    if quantity.isna().any() or (quantity <= 0).any(): errors.append("quantity contains missing/non-positive values")
    if price.isna().any() or (price < 0).any(): errors.append("unit_price contains missing/negative values")
    if dates.isna().any(): errors.append("date contains unreadable values")
    blank_sku = frame[mapping["sku"]].isna() | frame[mapping["sku"]].astype(str).str.strip().eq("")
    if blank_sku.any(): errors.append("sku contains blank values")
    known_skus = set(db.scalars(select(Product.sku).where(
        Product.organization_id == membership.organization_id
    )))
    file_skus = set(frame[mapping["sku"]].dropna().astype(str).str.strip())
    unknown_skus = sorted(file_skus - known_skus)
    report = {
        "valid": not errors and not unknown_skus,
        "errors": errors, "unknown_skus": unknown_skus[:100],
        "unknown_sku_count": len(unknown_skus),
        "rows": len(frame), "invoices": int(frame[mapping["invoice_number"]].nunique()),
        "date_from": None if dates.isna().all() else dates.min().date().isoformat(),
        "date_to": None if dates.isna().all() else dates.max().date().isoformat(),
    }
    batch.mapping_json = json.dumps(mapping, ensure_ascii=False)
    batch.validation_json = json.dumps(report, ensure_ascii=False)
    batch.status = "validated" if report["valid"] else "validation_failed"
    db.commit()
    return report


@router.get("/datasets/sales.csv", tags=["real-data"])
def export_anonymized_sales(membership: CurrentMembership, db: Db):
    rows = db.execute(
        select(SalesOrder, SalesOrderItem, Product)
        .join(SalesOrderItem, SalesOrderItem.order_id == SalesOrder.id)
        .join(Product, Product.id == SalesOrderItem.product_id)
        .where(SalesOrder.organization_id == membership.organization_id)
        .order_by(SalesOrder.sold_at, SalesOrder.invoice_number)
    ).all()
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([
        "organization_id", "branch_id", "invoice_id", "line_id", "sold_at",
        "customer_pseudo_id", "sku", "category", "quantity", "unit_price",
        "unit_cost_at_sale", "discount_amount", "line_total", "channel", "status",
    ])
    for order, line, product in rows:
        writer.writerow([
            order.organization_id, order.branch_id, order.id, line.id,
            order.sold_at.isoformat(), order.customer_id or "ANONYMOUS", product.sku,
            product.category or "", line.quantity, line.unit_price,
            line.unit_cost_at_sale, line.discount_amount, line.line_total,
            order.channel, order.status,
        ])
    data = output.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        iter([data]), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="bsmart_sales_anonymized.csv"'},
    )
