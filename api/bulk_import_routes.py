"""Bring a shop's existing lists into the system: products, customers, opening stock.

Two steps so nothing is guessed silently:
  1. ``preview`` reads the file and proposes which column is which (English or Bangla headers);
  2. ``commit`` applies the owner's confirmed mapping and reports, row by row, what was
     created, updated, skipped, or rejected and why. Nothing is stored between the steps.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from .audit import record_audit
from .auth import CurrentMembership
from .batches import add_to_batch, balance_row, get_or_create_batch
from .data_import_routes import read_frame
from .database import get_db
from .directory_routes import phone_hash
from .domain_models import Branch, Customer, Product, StockMovement, new_id, utcnow
from .permissions import has_permission, require_permission

router = APIRouter(prefix="/api/app/import")
Db = Annotated[Session, Depends(get_db)]

MAX_BYTES = 8 * 1024 * 1024
MAX_ROWS = 5000

KINDS = {
    "products": {
        "required": ["sku", "name", "selling_price"],
        "optional": ["cost_price", "category", "unit", "barcode", "reorder_level", "track_expiry"],
    },
    "customers": {"required": ["code"], "optional": ["display_name", "phone", "marketing_consent"]},
    "opening_stock": {"required": ["sku", "quantity"], "optional": ["batch_no", "expiry_date", "unit_cost"]},
}

# Header words a shop might use, English and Bangla. Compared after lower-casing and dropping punctuation.
SYNONYMS = {
    "sku": ["sku", "code", "itemcode", "productcode", "কোড", "পণ্যকোড", "আইটেমকোড", "পণ্যেরকোড"],
    "name": ["name", "productname", "item", "itemname", "নাম", "পণ্য", "পণ্যেরনাম", "ওষুধেরনাম", "বিবরণ"],
    "selling_price": ["sellingprice", "price", "mrp", "saleprice", "rate", "বিক্রয়মূল্য", "বিক্রিরদাম", "দাম", "মূল্য", "এমআরপি"],
    "cost_price": ["costprice", "cost", "purchaseprice", "buyprice", "ক্রয়মূল্য", "কেনাদাম", "ক্রয়দাম"],
    "category": ["category", "type", "group", "ক্যাটাগরি", "ধরন", "বিভাগ"],
    "unit": ["unit", "uom", "একক"],
    "barcode": ["barcode", "bar", "বারকোড"],
    "reorder_level": ["reorderlevel", "minstock", "minimumstock", "reorder", "পুনঃঅর্ডার", "নূন্যতমস্টক", "সর্বনিম্নস্টক"],
    "track_expiry": ["trackexpiry", "expirytracking", "hasexpiry", "expiry", "মেয়াদট্র্যাক", "মেয়াদআছে"],
    "code": ["code", "customercode", "id", "customerid", "কোড", "কাস্টমারকোড", "আইডি"],
    "display_name": ["name", "customername", "displayname", "নাম", "কাস্টমারেরনাম"],
    "phone": ["phone", "mobile", "phonenumber", "mobilenumber", "contact", "ফোন", "মোবাইল", "মোবাইলনম্বর"],
    "marketing_consent": ["consent", "marketingconsent", "sms", "সম্মতি", "প্রচারেরসম্মতি"],
    "quantity": ["quantity", "qty", "stock", "openingstock", "onhand", "পরিমাণ", "স্টক", "মজুত"],
    "batch_no": ["batch", "batchno", "batchnumber", "lot", "ব্যাচ", "ব্যাচনম্বর"],
    "expiry_date": ["expiry", "expirydate", "expdate", "exp", "মেয়াদ", "মেয়াদশেষ", "মেয়াদউত্তীর্ণ"],
    "unit_cost": ["unitcost", "cost", "costprice", "ক্রয়মূল্য", "কেনাদাম"],
}
_BN = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
YES = {"yes", "y", "true", "1", "হ্যাঁ", "হা", "আছে", "✓"}
NO = {"no", "n", "false", "0", "না", "নাই", "নেই", ""}


def _norm(header: object) -> str:
    return re.sub(r"[\s_\-./:()]+", "", str(header).strip().lower())


def _blank(value: object) -> bool:
    return value is None or (isinstance(value, float) and pd.isna(value)) or str(value).strip() == ""


def _text(value: object) -> str | None:
    if _blank(value):
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)  # Excel turns codes like 1001 into 1001.0
    return str(value).strip()


def _number(value: object) -> Decimal | None:
    if _blank(value):
        return None
    cleaned = re.sub(r"[৳,\s]|tk\.?|bdt", "", str(value).translate(_BN), flags=re.I)
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"'{value}' is not a number") from exc


def _flag(value: object) -> bool:
    key = str(value).strip().lower() if not _blank(value) else ""
    if key in YES:
        return True
    if key in NO:
        return False
    raise ValueError(f"'{value}' should be yes/no (হ্যাঁ/না)")


def _date(value: object) -> date | None:
    if _blank(value):
        return None
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.date()
    text = str(value).translate(_BN).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%m/%Y", "%b-%y", "%b %Y"):
        try:
            parsed = datetime.strptime(text, fmt).date()
            # A month/year expiry (e.g. "08/2027") means the last day of that month.
            if fmt in ("%m/%Y", "%b-%y", "%b %Y"):
                nxt = date(parsed.year + (parsed.month == 12), parsed.month % 12 + 1, 1)
                parsed = date.fromordinal(nxt.toordinal() - 1)
            return parsed
        except ValueError:
            continue
    raise ValueError(f"'{value}' is not a date (use 2027-08-31 or 31/08/2027)")


def _phone(value: object) -> str | None:
    if _blank(value):
        return None
    digits = re.sub(r"[^\d+]", "", str(value).translate(_BN))
    if digits.startswith("+880"):
        digits = "0" + digits[4:]
    elif digits.startswith("880") and len(digits) == 13:
        digits = "0" + digits[3:]
    if not re.fullmatch(r"01\d{9}", digits):
        raise ValueError(f"'{value}' is not a Bangladeshi mobile number (01XXXXXXXXX)")
    return digits


def _read(upload_bytes: bytes, filename: str) -> pd.DataFrame:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in (".csv", ".xlsx"):
        raise HTTPException(status_code=400, detail="Only CSV and Excel (.xlsx) files are accepted")
    if not upload_bytes or len(upload_bytes) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File must be between 1 byte and 8 MB")
    if suffix == ".csv":
        # Excel saves Bangla CSVs with a byte-order mark; utf-8-sig reads both.
        try:
            frame = pd.read_csv(pd.io.common.BytesIO(upload_bytes), encoding="utf-8-sig", dtype=object)
        except Exception:
            frame = read_frame(upload_bytes, suffix)
    else:
        frame = read_frame(upload_bytes, suffix).astype(object)
    if frame.empty:
        raise HTTPException(status_code=400, detail="The file has no data rows")
    if len(frame) > MAX_ROWS:
        raise HTTPException(status_code=413, detail=f"At most {MAX_ROWS} rows per import")
    return frame


def _require(membership, kind: str) -> None:
    if kind not in KINDS:
        raise HTTPException(status_code=422, detail="Unknown import kind")
    require_permission(membership, "imports:write")
    if kind == "opening_stock":
        require_permission(membership, "inventory:adjust")
    if kind == "products" and not has_permission(membership.role, "catalog:write"):
        raise HTTPException(status_code=403, detail="Your role cannot perform this action")
    if kind == "customers":
        require_permission(membership, "customers:write")


@router.post("/preview", tags=["import"])
async def preview(membership: CurrentMembership, kind: Annotated[str, Form()], file: UploadFile = File(...)):
    """Read the file and propose which column holds which field. Nothing is saved."""
    _require(membership, kind)
    frame = _read(await file.read(MAX_BYTES + 1), file.filename or "")
    columns = [str(c) for c in frame.columns]
    spec = KINDS[kind]
    guess: dict[str, str | None] = {}
    taken: set[str] = set()
    for field in spec["required"] + spec["optional"]:
        wanted = {_norm(s) for s in SYNONYMS.get(field, [field])}
        match = next((c for c in columns if _norm(c) in wanted and c not in taken), None)
        guess[field] = match
        if match:
            taken.add(match)
    sample = [{str(k): (_text(v) or "") for k, v in row.items()} for row in frame.head(5).to_dict(orient="records")]
    return {"kind": kind, "columns": columns, "rows": len(frame), "sample": sample, "mapping": guess,
            "required": spec["required"], "optional": spec["optional"]}


@router.post("/commit", tags=["import"])
async def commit(
    membership: CurrentMembership, db: Db,
    kind: Annotated[str, Form()], mapping: Annotated[str, Form()],
    mode: Annotated[str, Form()] = "skip_existing", branch_id: Annotated[str | None, Form()] = None,
    file: UploadFile = File(...),
):
    """Apply the confirmed mapping. Rows that fail are reported and skipped; the rest are saved."""
    _require(membership, kind)
    if mode not in ("skip_existing", "update_existing"):
        raise HTTPException(status_code=422, detail="Unknown mode")
    try:
        picks = json.loads(mapping)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid mapping") from exc
    frame = _read(await file.read(MAX_BYTES + 1), file.filename or "")
    spec = KINDS[kind]
    missing = [f for f in spec["required"] if not picks.get(f) or picks[f] not in frame.columns]
    if missing:
        raise HTTPException(status_code=422, detail=f"Map a column for: {', '.join(missing)}")

    org_id = membership.organization_id
    result = {"created": 0, "updated": 0, "skipped": 0, "errors": []}

    def get(row, field):
        column = picks.get(field)
        return row.get(column) if column in row else None

    def fail(number, message):
        result["errors"].append({"row": number, "message": message})

    if kind == "products":
        existing = {p.sku: p for p in db.scalars(select(Product).where(Product.organization_id == org_id))}
        seen: set[str] = set()
        for index, row in enumerate(frame.to_dict(orient="records"), start=2):
            try:
                sku, name, price = _text(get(row, "sku")), _text(get(row, "name")), _number(get(row, "selling_price"))
                if not sku or not name:
                    raise ValueError("SKU and name are required")
                if price is None or price < 0:
                    raise ValueError("selling price is required and cannot be negative")
                cost = _number(get(row, "cost_price"))
                reorder = _number(get(row, "reorder_level"))
                if (cost is not None and cost < 0) or (reorder is not None and reorder < 0):
                    raise ValueError("cost and reorder level cannot be negative")
                if sku in seen:
                    raise ValueError(f"SKU {sku} appears twice in the file")
                seen.add(sku)
                fields = {
                    "name": name[:200], "selling_price": price, "category": (_text(get(row, "category")) or None),
                    "unit": (_text(get(row, "unit")) or "pcs")[:20], "barcode": _text(get(row, "barcode")),
                }
                if cost is not None:
                    fields["cost_price"] = cost
                if reorder is not None:
                    fields["reorder_level"] = reorder
                track = None if _blank(get(row, "track_expiry")) else _flag(get(row, "track_expiry"))
            except ValueError as exc:
                fail(index, str(exc))
                continue
            current = existing.get(sku)
            if current is None:
                db.add(Product(organization_id=org_id, sku=sku, track_expiry=bool(track), **fields))
                result["created"] += 1
            elif mode == "update_existing":
                for key, value in fields.items():
                    if value is not None:
                        setattr(current, key, value)
                result["updated"] += 1
            else:
                result["skipped"] += 1
    elif kind == "customers":
        existing = {c.code for c in db.scalars(select(Customer).where(Customer.organization_id == org_id))}
        seen = set()
        for index, row in enumerate(frame.to_dict(orient="records"), start=2):
            try:
                code = _text(get(row, "code"))
                if not code:
                    raise ValueError("customer code is required")
                if code in seen:
                    raise ValueError(f"code {code} appears twice in the file")
                seen.add(code)
                phone = _phone(get(row, "phone"))
                consent = False if _blank(get(row, "marketing_consent")) else _flag(get(row, "marketing_consent"))
            except ValueError as exc:
                fail(index, str(exc))
                continue
            if code in existing:
                result["skipped"] += 1
                continue
            db.add(Customer(organization_id=org_id, code=code[:80], display_name=(_text(get(row, "display_name")) or None),
                            phone_hash=phone_hash(org_id, phone), marketing_consent=consent))
            result["created"] += 1
    else:  # opening_stock
        branch = db.scalar(select(Branch).where(Branch.id == branch_id, Branch.organization_id == org_id)) if branch_id else None
        if branch is None:
            raise HTTPException(status_code=422, detail="Choose the branch this stock is in")
        products = {p.sku: p for p in db.scalars(select(Product).where(Product.organization_id == org_id))}
        for index, row in enumerate(frame.to_dict(orient="records"), start=2):
            try:
                sku, quantity = _text(get(row, "sku")), _number(get(row, "quantity"))
                product = products.get(sku or "")
                if product is None:
                    raise ValueError(f"no product with SKU {sku}; import the products first")
                if quantity is None or quantity <= 0:
                    raise ValueError("quantity must be more than zero")
                cost = _number(get(row, "unit_cost"))
                batch_no, expiry = _text(get(row, "batch_no")), _date(get(row, "expiry_date"))
                if product.track_expiry and (not batch_no or expiry is None):
                    raise ValueError(f"{sku} tracks expiry: batch number and expiry date are required")
                if product.track_expiry and expiry < date.today():
                    raise ValueError(f"{sku} batch {batch_no} is already expired")
            except ValueError as exc:
                fail(index, str(exc))
                continue
            movement_batch = None
            if product.track_expiry:
                batch = get_or_create_batch(db, org_id, product, batch_no, expiry,
                                            cost if cost is not None else (product.cost_price if product.cost_price > 0 else None),
                                            None, utcnow(), "opening")
                add_to_batch(db, org_id, branch.id, batch, quantity)
                movement_batch = batch.id
            else:
                balance_row(db, org_id, branch.id, product.id).quantity += quantity
            db.add(StockMovement(
                organization_id=org_id, branch_id=branch.id, product_id=product.id, movement_type="adjustment",
                quantity_delta=quantity, reference_type="opening_stock", reference_id=new_id(), batch_id=movement_batch,
                unit_cost=cost if cost is not None else (product.cost_price if product.cost_price > 0 else None),
            ))
            result["created"] += 1

    record_audit(db, membership, "import.bulk", "import", None, kind=kind, created=result["created"],
                 updated=result["updated"], skipped=result["skipped"], rejected=len(result["errors"]))
    db.commit()
    result["errors"] = result["errors"][:200]
    return result
