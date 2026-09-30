"""Double-entry accounting: the chart of accounts, journal posting, trial
balance and profit & loss.

This sits *alongside* the existing single-purpose `LedgerEntry` (payable/
receivable/expense balances) rather than replacing it — every place that posts
a `LedgerEntry` today keeps doing so (the Dashboard, `/api/app/ledger/*` and
`/api/app/receivables/ageing` all still work unchanged) and, in the same
transaction, now also posts a balanced journal entry here. Two views of the
same event, not two sources of truth: the journal is derived from the same
numbers, so it can never disagree with the subledgers it stands beside.

Rule this module enforces: **an entry that does not balance is refused, not
silently posted.** Money never simply appears or disappears in the books.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import NamedTuple

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .domain_models import Account, JournalEntry, JournalLine

ZERO = Decimal("0")
MONEY = Decimal("0.01")

# code, name, type, is_system. Seeded once per organization at creation time
# (and by a one-off migration for organizations that existed before this).
DEFAULT_ACCOUNTS: list[tuple[str, str, str]] = [
    ("1000", "Cash", "asset"),
    ("1010", "Mobile Banking (bKash/Nagad)", "asset"),
    ("1020", "Bank", "asset"),
    ("1100", "Accounts Receivable", "asset"),
    ("1200", "Inventory", "asset"),
    ("1250", "Supplier Claims", "asset"),
    ("2000", "Accounts Payable", "liability"),
    ("2100", "VAT Payable", "liability"),
    ("3000", "Owner's Equity", "equity"),
    ("4000", "Sales Revenue", "revenue"),
    ("4100", "Sales Returns and Allowances", "revenue"),   # contra-revenue: normal balance is a debit
    ("5000", "Cost of Goods Sold", "expense"),
    ("5900", "Operating Expenses", "expense"),
    ("5910", "Inventory Shrinkage/Adjustment", "expense"),   # contra like 4100: a found-stock count nets this down
    ("5950", "Cash Over/Short", "expense"),
]
# A payment/settlement method string (as stored on Payment.method, LedgerEntry.payment_method,
# Expense.payment_method) to the asset account it moves. Anything not listed here — including
# free-text expense payment methods a shop typed themselves — falls back to "1020" (Bank), the
# safest "not literally cash" default, so a mistyped method never silently posts as cash on hand.
METHOD_ACCOUNT: dict[str, str] = {
    "cash": "1000", "bkash": "1010", "nagad": "1010", "bangla_qr": "1010",
    "bank": "1020", "card": "1020", "cod": "1000", "other": "1020",
}


def account_for_method(method: str | None) -> str:
    return METHOD_ACCOUNT.get((method or "").lower(), "1020")


def seed_default_accounts(db: Session, org_id: str) -> None:
    existing = set(db.scalars(select(Account.code).where(Account.organization_id == org_id)))
    for code, name, type_ in DEFAULT_ACCOUNTS:
        if code in existing:
            continue
        db.add(Account(organization_id=org_id, code=code, name=name, type=type_, is_system=True))


class Line(NamedTuple):
    account_code: str
    debit: Decimal
    credit: Decimal
    party_type: str | None = None
    party_id: str | None = None


def post_journal(
    db: Session, org_id: str, branch_id: str | None, occurred_at: datetime,
    reference_type: str, reference_id: str, lines: list[Line], memo: str | None = None,
) -> JournalEntry:
    """Post one balanced journal entry. Raises if debits and credits do not match,
    if any line is zero, or if an account code does not exist for this org — a
    typo in a code must fail loudly, not post to the wrong account."""
    lines = [ln for ln in lines if ln.debit != 0 or ln.credit != 0]
    if not lines:
        raise ValueError("A journal entry needs at least one non-zero line")
    total_debit = sum((ln.debit for ln in lines), ZERO)
    total_credit = sum((ln.credit for ln in lines), ZERO)
    if total_debit.quantize(MONEY) != total_credit.quantize(MONEY):
        raise ValueError(f"Journal entry does not balance: debit {total_debit} vs credit {total_credit}")

    accounts = {a.code: a for a in db.scalars(select(Account).where(
        Account.organization_id == org_id, Account.code.in_({ln.account_code for ln in lines})))}
    missing = {ln.account_code for ln in lines} - set(accounts)
    if missing:
        raise ValueError(f"Unknown account code(s) for this organization: {sorted(missing)}")

    entry = JournalEntry(
        organization_id=org_id, branch_id=branch_id, occurred_at=occurred_at,
        memo=memo, reference_type=reference_type, reference_id=reference_id,
    )
    db.add(entry)
    db.flush()
    for ln in lines:
        db.add(JournalLine(
            organization_id=org_id, journal_entry_id=entry.id, account_id=accounts[ln.account_code].id,
            debit=ln.debit, credit=ln.credit, party_type=ln.party_type, party_id=ln.party_id,
        ))
    return entry


def trial_balance(db: Session, org_id: str, as_of: datetime | None = None) -> list[dict]:
    """Every account's running debit/credit total, plus a plain balance signed the
    way that account's type normally reads (positive = its natural side)."""
    statement = (
        select(Account, func.coalesce(func.sum(JournalLine.debit), 0), func.coalesce(func.sum(JournalLine.credit), 0))
        .outerjoin(JournalLine, (JournalLine.account_id == Account.id) & (JournalLine.organization_id == org_id))
        .outerjoin(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
    )
    if as_of is not None:
        statement = statement.where((JournalEntry.occurred_at <= as_of) | (JournalEntry.id.is_(None)))
    statement = statement.where(Account.organization_id == org_id, Account.active.is_(True)).group_by(Account.id)

    rows = []
    for account, debit, credit in db.execute(statement).all():
        debit, credit = Decimal(debit), Decimal(credit)
        debit_normal = account.type in ("asset", "expense")
        balance = (debit - credit) if debit_normal else (credit - debit)
        rows.append({
            "code": account.code, "name": account.name, "type": account.type,
            "debit": debit, "credit": credit, "balance": balance,
        })
    rows.sort(key=lambda r: r["code"])
    return rows


def profit_and_loss(db: Session, org_id: str, date_from: datetime, date_to: datetime) -> dict:
    """Revenue, cost of goods sold, gross profit, operating expenses and net
    profit for a period — read straight off the journal, not re-derived from
    sales tables, so it can never drift from what the ledger actually posted."""
    rows = db.execute(
        select(Account.code, Account.name, Account.type,
               func.coalesce(func.sum(JournalLine.debit), 0), func.coalesce(func.sum(JournalLine.credit), 0))
        .join(JournalLine, JournalLine.account_id == Account.id)
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
        .where(Account.organization_id == org_id, Account.type.in_(("revenue", "expense")),
               JournalEntry.occurred_at >= date_from, JournalEntry.occurred_at < date_to)
        .group_by(Account.id)
    ).all()
    revenue_lines, expense_lines = [], []
    revenue = cogs = opex = ZERO
    for code, name, type_, debit, credit in rows:
        debit, credit = Decimal(debit), Decimal(credit)
        if type_ == "revenue":
            amount = credit - debit    # revenue's normal side is credit; a debit here is a return
            revenue += amount
            revenue_lines.append({"code": code, "name": name, "amount": amount})
        else:
            amount = debit - credit
            expense_lines.append({"code": code, "name": name, "amount": amount})
            if code == "5000":
                cogs += amount
            else:
                opex += amount
    gross_profit = revenue - cogs
    net_profit = gross_profit - opex
    return {
        "from": date_from, "to": date_to, "revenue": revenue, "cogs": cogs, "gross_profit": gross_profit,
        "operating_expenses": opex, "net_profit": net_profit,
        "revenue_lines": revenue_lines, "expense_lines": expense_lines,
    }


def balance_sheet(db: Session, org_id: str, as_of: datetime) -> dict:
    """Assets, liabilities and equity as of a moment, plus retained earnings
    (accumulated net profit to date) so the sheet actually balances — a shop's
    equity is not just what the owner put in, it is that plus everything the
    business has earned and not yet withdrawn."""
    rows = trial_balance(db, org_id, as_of)
    by_type: dict[str, list[dict]] = {"asset": [], "liability": [], "equity": []}
    for row in rows:
        if row["type"] in by_type and row["balance"] != 0:
            by_type[row["type"]].append(row)
    assets = sum((r["balance"] for r in by_type["asset"]), ZERO)
    liabilities = sum((r["balance"] for r in by_type["liability"]), ZERO)
    paid_in_equity = sum((r["balance"] for r in by_type["equity"]), ZERO)
    # Retained earnings = all-time revenue minus all-time expense, from the epoch to `as_of`.
    epoch = datetime(2000, 1, 1, tzinfo=as_of.tzinfo)
    retained_earnings = profit_and_loss(db, org_id, epoch, as_of)["net_profit"]
    return {
        "as_of": as_of, "assets": by_type["asset"], "liabilities": by_type["liability"],
        "equity": by_type["equity"], "total_assets": assets, "total_liabilities": liabilities,
        "paid_in_equity": paid_in_equity, "retained_earnings": retained_earnings,
        "total_equity": paid_in_equity + retained_earnings,
        "balances": (assets - (liabilities + paid_in_equity + retained_earnings)).quantize(MONEY) == ZERO,
    }
