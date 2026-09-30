from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.domain_models import (
    Account, Batch, BatchStock, InventoryBalance, JournalLine, LedgerEntry,
    PurchaseReturn, StockMovement,
)

NOW = datetime.now(timezone.utc)


def _received_purchase(client, headers, world, *, tracked=False):
    supplier = client.post("/api/app/suppliers", headers=headers, json={
        "code": "RET-SUP", "name": "Return Supplier",
    }).json()
    product_id = world["product_a"]
    if tracked:
        product = client.post("/api/app/products", headers=headers, json={
            "sku": "RET-MED", "name": "Return Medicine", "selling_price": "15",
            "cost_price": "10", "track_expiry": True,
        }).json()
        product_id = product["id"]
    order = client.post("/api/app/purchases", headers=headers, json={
        "branch_id": world["branch_a"], "supplier_id": supplier["id"],
        "order_number": "PO-RETURN-BATCH" if tracked else "PO-RETURN",
        "ordered_at": NOW.isoformat(),
        "items": [{"product_id": product_id, "quantity": "5", "unit_cost": "10"}],
    }).json()
    details = next(row for row in client.get("/api/app/purchases", headers=headers).json()
                   if row["id"] == order["id"])
    line_id = details["items"][0]["id"]
    receive_item = {"purchase_order_item_id": line_id, "quantity": "5"}
    if tracked:
        receive_item.update({"batch_no": "RET-B-1", "expiry_date": (date.today() + timedelta(days=365)).isoformat()})
    response = client.post(f"/api/app/purchases/{order['id']}/receive", headers=headers, json={
        "received_at": NOW.isoformat(), "items": [receive_item],
    })
    assert response.status_code == 200, response.text
    return supplier, order, line_id, product_id


def _claim(client, headers, order_id, line_id, *, number="PR-001", quantity="2", batch_id=None):
    item = {"purchase_order_item_id": line_id, "quantity": quantity}
    if batch_id:
        item["batch_id"] = batch_id
    return client.post("/api/app/purchase-returns", headers=headers, json={
        "purchase_order_id": order_id, "return_number": number,
        "claim_type": "damaged", "reason": "Carton was damaged in transit",
        "submitted_at": NOW.isoformat(), "items": [item],
    })


def test_claim_dispatch_and_credit_note_keep_stock_subledger_and_journal_in_sync(client_for, world, engine):
    owner, owner_headers = client_for("owner")
    supplier, order, line_id, product_id = _received_purchase(owner, owner_headers, world)

    keeper, keeper_headers = client_for("stock_keeper")
    created = _claim(keeper, keeper_headers, order["id"], line_id)
    assert created.status_code == 200, created.text
    claim = created.json()
    assert claim["status"] == "submitted" and Decimal(str(claim["total"])) == Decimal("20")

    with Session(engine) as db:
        stock_before = db.scalar(select(InventoryBalance.quantity).where(
            InventoryBalance.organization_id == world["org_a"],
            InventoryBalance.branch_id == world["branch_a"],
            InventoryBalance.product_id == product_id,
        ))
        payable_before = db.scalar(select(func.sum(LedgerEntry.amount_delta)).where(
            LedgerEntry.party_id == supplier["id"], LedgerEntry.ledger_type == "payable",
        ))
    assert stock_before == Decimal("15")
    assert payable_before == Decimal("50")

    dispatched = keeper.post(f"/api/app/purchase-returns/{claim['id']}/dispatch", headers=keeper_headers,
                             json={"dispatched_at": NOW.isoformat()})
    assert dispatched.status_code == 200, dispatched.text
    assert dispatched.json()["status"] == "dispatched"

    with Session(engine) as db:
        stock_after = db.scalar(select(InventoryBalance.quantity).where(
            InventoryBalance.organization_id == world["org_a"],
            InventoryBalance.branch_id == world["branch_a"],
            InventoryBalance.product_id == product_id,
        ))
        payable_after_dispatch = db.scalar(select(func.sum(LedgerEntry.amount_delta)).where(
            LedgerEntry.party_id == supplier["id"], LedgerEntry.ledger_type == "payable",
        ))
        movement = db.scalar(select(StockMovement).where(
            StockMovement.reference_type == "purchase_return",
            StockMovement.reference_id == claim["id"],
        ))
    assert stock_after == Decimal("13")
    assert payable_after_dispatch == Decimal("50")  # supplier has not accepted it yet
    assert movement.quantity_delta == Decimal("-2")

    accountant, accountant_headers = client_for("accountant")
    settled = accountant.post(f"/api/app/purchase-returns/{claim['id']}/credit-note",
                              headers=accountant_headers, json={
        "credit_note_number": "CN-7788", "accepted_at": NOW.isoformat(),
        "supplier_note": "Accepted in full",
    })
    assert settled.status_code == 200, settled.text
    assert settled.json()["status"] == "settled"

    with Session(engine) as db:
        payable = db.scalar(select(func.sum(LedgerEntry.amount_delta)).where(
            LedgerEntry.party_id == supplier["id"], LedgerEntry.ledger_type == "payable",
        ))
        balances = dict(db.execute(
            select(Account.code, func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0))
            .join(JournalLine, JournalLine.account_id == Account.id)
            .where(Account.organization_id == world["org_a"], Account.code.in_(("1200", "1250", "2000")))
            .group_by(Account.code)
        ).all())
    assert payable == Decimal("30")
    assert balances["1200"] == Decimal("30")
    assert balances["1250"] == Decimal("0")
    assert balances["2000"] == Decimal("-30")


def test_return_cannot_exceed_received_quantity_or_dispatch_twice(client_for, world):
    owner, headers = client_for("owner")
    _, order, line_id, _ = _received_purchase(owner, headers, world)
    assert _claim(owner, headers, order["id"], line_id, quantity="6").status_code == 409
    claim = _claim(owner, headers, order["id"], line_id, quantity="3").json()
    # Pending claims reserve their quantity, preventing another claim over the receipt.
    assert _claim(owner, headers, order["id"], line_id, number="PR-002", quantity="3").status_code == 409
    endpoint = f"/api/app/purchase-returns/{claim['id']}/dispatch"
    assert owner.post(endpoint, headers=headers, json={"dispatched_at": NOW.isoformat()}).status_code == 200
    assert owner.post(endpoint, headers=headers, json={"dispatched_at": NOW.isoformat()}).status_code == 409


def test_batch_return_requires_received_batch_and_decrements_that_batch(client_for, world, engine):
    owner, headers = client_for("owner")
    _, order, line_id, product_id = _received_purchase(owner, headers, world, tracked=True)
    with Session(engine) as db:
        batch = db.scalar(select(Batch).where(Batch.product_id == product_id, Batch.batch_no == "RET-B-1"))
        batch_id = batch.id
    assert _claim(owner, headers, order["id"], line_id, number="PR-BAD").status_code == 422
    claim = _claim(owner, headers, order["id"], line_id, number="PR-BATCH", batch_id=batch_id).json()
    assert owner.post(f"/api/app/purchase-returns/{claim['id']}/dispatch", headers=headers,
                      json={"dispatched_at": NOW.isoformat()}).status_code == 200
    with Session(engine) as db:
        remaining = db.scalar(select(BatchStock.quantity).where(BatchStock.batch_id == batch_id))
    assert remaining == Decimal("3")


def test_permissions_and_tenant_isolation_for_purchase_returns(client_for, world):
    cashier, cashier_headers = client_for("cashier")
    assert cashier.get("/api/app/purchase-returns", headers=cashier_headers).status_code == 403
    other_owner, other_headers = client_for("owner", "org_b")
    assert other_owner.get("/api/app/purchase-returns", headers=other_headers).json() == []

