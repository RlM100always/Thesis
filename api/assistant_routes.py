"""'ব্যবসা সম্পর্কে জিজ্ঞাসা করুন' -- an owner types a plain-Bangla question
about their own business and gets a real-data answer back.

This is NOT a free-form text-to-SQL assistant (an LLM writing its own query
against a multi-tenant database is a real injection/data-leak risk, and this
repo's own rule is "never fabricate a number"). Instead: the question is
matched against a small, fixed set of known intents by keyword (works with
zero configuration, zero hallucination risk, matching the bKash/WhatsApp
adapter pattern of "deterministic path always available"); each intent runs
one real, tenant-scoped query; and only the *phrasing* of the already-computed
real numbers is ever handed to an LLM, verified against those same numbers
before being shown -- identical discipline to api/llm_gateway.py's
recommendation-explanation path, reused here rather than re-invented.

An unrecognised question gets an honest "আমি এখনো এই প্রশ্নটা বুঝতে পারছি না"
with a list of what it *can* answer, never a guessed response.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .auth import CurrentMembership
from .database import get_db
from .domain_models import (
    Customer, InventoryBalance, LedgerEntry, Product, SalesOrder, SalesOrderItem,
)
from .llm_gateway import narrate_answer
from .permissions import require_permission

router = APIRouter(prefix="/api/app/assistant")
Db = Annotated[Session, Depends(get_db)]


def _money(value) -> float:
    return round(float(value or 0), 2)


# ── Intents: keyword set -> (label, handler) ──────────────────────────────
# Keyword matching is intentionally simple substring search, not an LLM call --
# this must work identically whether or not ANTHROPIC_API_KEY is configured.

def _today_sales(db: Session, org_id: str) -> dict:
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    total, count = db.execute(select(
        func.coalesce(func.sum(SalesOrder.total), 0), func.count(SalesOrder.id),
    ).where(SalesOrder.organization_id == org_id, SalesOrder.sold_at >= start)).one()
    yesterday_start = start - timedelta(days=1)
    y_total = db.scalar(select(func.coalesce(func.sum(SalesOrder.total), 0)).where(
        SalesOrder.organization_id == org_id, SalesOrder.sold_at >= yesterday_start, SalesOrder.sold_at < start,
    )) or 0
    data = {"today_sales_bdt": _money(total), "today_orders": int(count or 0), "yesterday_sales_bdt": _money(y_total)}
    diff = data["today_sales_bdt"] - data["yesterday_sales_bdt"]
    trend = "বেশি" if diff > 0 else "কম" if diff < 0 else "সমান"
    template = (
        f"আজ এখন পর্যন্ত ৳{data['today_sales_bdt']:,.0f} বিক্রি হয়েছে, {data['today_orders']}টা বিল থেকে। "
        f"গতকাল একই সময়ে ছিল ৳{data['yesterday_sales_bdt']:,.0f} -- আজ তার চেয়ে {trend}।"
    )
    return {"data": data, "template": template}


def _top_products(db: Session, org_id: str) -> dict:
    start = datetime.now(timezone.utc) - timedelta(days=30)
    rows = db.execute(
        select(Product.name, func.sum(SalesOrderItem.line_total).label("revenue"))
        .join(SalesOrderItem, SalesOrderItem.product_id == Product.id)
        .join(SalesOrder, SalesOrder.id == SalesOrderItem.order_id)
        .where(SalesOrder.organization_id == org_id, SalesOrder.sold_at >= start)
        .group_by(Product.id, Product.name).order_by(func.sum(SalesOrderItem.line_total).desc()).limit(5)
    ).all()
    data = {"period_days": 30, "top_products": [{"name": name, "revenue_bdt": _money(rev)} for name, rev in rows]}
    if not rows:
        return {"data": data, "template": "গত ৩০ দিনে কোনো বিক্রি রেকর্ড পাওয়া যায়নি।"}
    lines = ", ".join(f"{p['name']} (৳{p['revenue_bdt']:,.0f})" for p in data["top_products"])
    template = f"গত ৩০ দিনে সবচেয়ে বেশি বিক্রি হওয়া পণ্য: {lines}।"
    return {"data": data, "template": template}


def _low_stock(db: Session, org_id: str) -> dict:
    rows = db.execute(
        select(Product.name, func.coalesce(func.sum(InventoryBalance.quantity), 0).label("qty"), Product.reorder_level)
        .outerjoin(InventoryBalance, InventoryBalance.product_id == Product.id)
        .where(Product.organization_id == org_id, Product.active.is_(True))
        .group_by(Product.id, Product.name, Product.reorder_level)
        .having(func.coalesce(func.sum(InventoryBalance.quantity), 0) <= Product.reorder_level)
        .order_by(func.coalesce(func.sum(InventoryBalance.quantity), 0)).limit(10)
    ).all()
    data = {"low_stock_count": len(rows), "items": [{"name": n, "quantity": float(q)} for n, q, _ in rows]}
    if not rows:
        return {"data": data, "template": "এই মুহূর্তে কোনো পণ্যের স্টক reorder level-এর নিচে নেই।"}
    lines = ", ".join(f"{i['name']} ({i['quantity']:.0f} বাকি)" for i in data["items"][:5])
    template = f"{data['low_stock_count']}টা পণ্যের স্টক কমে গেছে: {lines}" + (" ইত্যাদি।" if data["low_stock_count"] > 5 else "।")
    return {"data": data, "template": template}


def _receivables(db: Session, org_id: str) -> dict:
    rows = db.execute(
        select(Customer.display_name, Customer.code, func.sum(LedgerEntry.amount_delta).label("balance"))
        .join(LedgerEntry, LedgerEntry.party_id == Customer.id)
        .where(LedgerEntry.organization_id == org_id, LedgerEntry.ledger_type == "receivable")
        .group_by(Customer.id, Customer.display_name, Customer.code)
        .having(func.sum(LedgerEntry.amount_delta) > 0)
        .order_by(func.sum(LedgerEntry.amount_delta).desc()).limit(5)
    ).all()
    total = db.scalar(select(func.coalesce(func.sum(LedgerEntry.amount_delta), 0)).where(
        LedgerEntry.organization_id == org_id, LedgerEntry.ledger_type == "receivable",
    )) or 0
    data = {
        "total_receivable_bdt": _money(total),
        "top_debtors": [{"name": name or code, "amount_bdt": _money(bal)} for name, code, bal in rows],
    }
    if not rows:
        return {"data": data, "template": "কোনো কাস্টমারের কাছে বাকি নেই।"}
    lines = ", ".join(f"{d['name']} (৳{d['amount_bdt']:,.0f})" for d in data["top_debtors"])
    template = f"মোট পাওনা ৳{data['total_receivable_bdt']:,.0f}। সবচেয়ে বেশি বাকি: {lines}।"
    return {"data": data, "template": template}


def _cash_position(db: Session, org_id: str) -> dict:
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    sales = db.scalar(select(func.coalesce(func.sum(SalesOrder.total), 0)).where(
        SalesOrder.organization_id == org_id, SalesOrder.sold_at >= start,
    )) or 0
    receivable = db.scalar(select(func.coalesce(func.sum(LedgerEntry.amount_delta), 0)).where(
        LedgerEntry.organization_id == org_id, LedgerEntry.ledger_type == "receivable",
    )) or 0
    payable = db.scalar(select(func.coalesce(func.sum(LedgerEntry.amount_delta), 0)).where(
        LedgerEntry.organization_id == org_id, LedgerEntry.ledger_type == "payable",
    )) or 0
    data = {"today_sales_bdt": _money(sales), "total_receivable_bdt": _money(receivable), "total_payable_bdt": _money(payable)}
    template = (
        f"আজ ৳{data['today_sales_bdt']:,.0f} বিক্রি হয়েছে। কাস্টমারদের কাছে মোট পাওনা ৳{data['total_receivable_bdt']:,.0f}, "
        f"সাপ্লায়ারদের কাছে দেনা ৳{data['total_payable_bdt']:,.0f}।"
    )
    return {"data": data, "template": template}


# Checked in order, most specific phrase first -- a generic single-word
# keyword (just "বিক্রি" or "পণ্য" alone) would false-match too many unrelated
# questions, so every keyword here is a multi-word phrase distinctive enough
# to that one intent. Order matters: "স্টক কম" and "বাকি কত" must be checked
# before the generic "আজকে কত বিক্রি" catch-all at the end.
INTENTS: list[tuple[list[str], str, callable]] = [
    (["স্টক কম", "স্টক কমে", "কমে গেছে", "ফুরিয়ে", "low stock"], "কম স্টক", _low_stock),
    (["বাকি", "পাওনা", "due", "receivable"], "কাস্টমারের বাকি", _receivables),
    (["সেরা বিক্রিত", "সেরা পণ্য", "বেশি বিক্রি হচ্ছে", "বেশি চলছে", "top product"], "সেরা পণ্য", _top_products),
    (["ক্যাশ", "হাতে কত টাকা", "টাকার অবস্থা", "cash position"], "ক্যাশের অবস্থা", _cash_position),
    (["আজ কত বিক্রি", "আজকে কত বিক্রি", "আজকের বিক্রি", "আজ বিক্রি কেমন", "today sale"], "আজকের বিক্রি", _today_sales),
]


def _classify(question: str) -> tuple[str, callable] | None:
    q = question.lower()
    for keywords, label, handler in INTENTS:
        if any(kw.lower() in q for kw in keywords):
            return label, handler
    return None


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=300)


@router.post("/ask")
def ask(payload: AskIn, membership: CurrentMembership, db: Db):
    require_permission(membership, "dashboard:read")
    match = _classify(payload.question)
    if match is None:
        return {
            "answered": False,
            "text": "আমি এখনো এই প্রশ্নটা বুঝতে পারছি না। আমি এখন এগুলো জানি: আজকের বিক্রি, সেরা বিক্রিত পণ্য, কম স্টক, কাস্টমারের বাকি, এবং ক্যাশের অবস্থা।",
        }
    label, handler = match
    result = handler(db, membership.organization_id)
    narration = narrate_answer(payload.question, result["template"], result["data"])
    return {
        "answered": True, "intent": label, "data": result["data"],
        "text": narration["text"], "source": narration["source"],
    }
