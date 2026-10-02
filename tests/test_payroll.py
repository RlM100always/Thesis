"""Payroll: draft generation, maker-checker approve/pay, frozen lines, and payslips."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

NOW = datetime.now(timezone.utc)
PERIOD = {"period_start": "2026-10-01", "period_end": "2026-10-31"}


def _cashier_membership_id(client_for):
    owner, headers = client_for("owner")
    staff = owner.get("/api/app/staff", headers=headers).json()
    return next(s["membership_id"] for s in staff if s["role"] == "cashier"), next(
        s["user_id"] for s in staff if s["role"] == "cashier")


def test_people_without_a_salary_are_skipped_in_the_draft(client_for):
    owner, headers = client_for("owner")
    run = owner.post("/api/app/payroll/runs", headers=headers, json=PERIOD)
    assert run.status_code == 200
    detail = owner.get(f"/api/app/payroll/runs/{run.json()['id']}", headers=headers).json()
    assert detail["lines"] == []  # nobody has base_salary set yet


def test_draft_includes_salary_and_commission(client_for, world):
    owner, headers = client_for("owner")
    cashier, cheaders = client_for("cashier")
    membership_id, cashier_user_id = _cashier_membership_id(client_for)
    owner.patch(f"/api/app/payroll/salary/{membership_id}", headers=headers, json={"base_salary": "15000"})
    owner.patch("/api/app/commission/rule", headers=headers, json={"active": True, "rate_percent": "5"})

    product = owner.post("/api/app/products", headers=headers, json={"sku": "PAY-1", "name": "P", "selling_price": "1000"}).json()
    owner.post("/api/app/inventory/adjust", headers=headers, json={
        "branch_id": world["branch_a"], "product_id": product["id"], "quantity_delta": "5", "reason": "stock in",
    })
    cashier.post("/api/app/sales", headers=cheaders, json={
        "branch_id": world["branch_a"], "invoice_number": "PAY-SALE-1",
        "sold_at": datetime(2026, 10, 10, tzinfo=timezone.utc).isoformat(),
        "items": [{"product_id": product["id"], "quantity": "1", "unit_price": "1000"}],
        "payments": [{"method": "cash", "amount": "1000"}],
    })

    run = owner.post("/api/app/payroll/runs", headers=headers, json=PERIOD).json()
    detail = owner.get(f"/api/app/payroll/runs/{run['id']}", headers=headers).json()
    line = next(l for l in detail["lines"] if l["user_id"] == cashier_user_id)
    assert Decimal(str(line["base_salary"])) == 15000
    assert Decimal(str(line["commission_amount"])) == 50  # 5% of 1000
    assert Decimal(str(line["net_pay"])) == 15050


def test_duplicate_period_is_rejected(client_for):
    owner, headers = client_for("owner")
    owner.post("/api/app/payroll/runs", headers=headers, json=PERIOD)
    dup = owner.post("/api/app/payroll/runs", headers=headers, json=PERIOD)
    assert dup.status_code == 409


def test_preparer_cannot_approve_their_own_run(client_for):
    owner, headers = client_for("owner")
    run = owner.post("/api/app/payroll/runs", headers=headers, json=PERIOD).json()
    response = owner.post(f"/api/app/payroll/runs/{run['id']}/approve", headers=headers)
    assert response.status_code == 403


def test_manager_drafts_owner_approves_accountant_pays(client_for):
    manager, mheaders = client_for("manager")
    owner, oheaders = client_for("owner")
    accountant, aheaders = client_for("accountant")

    run = manager.post("/api/app/payroll/runs", headers=mheaders, json=PERIOD)
    assert run.status_code == 200
    run = run.json()

    manager_cannot_approve = manager.post(f"/api/app/payroll/runs/{run['id']}/approve", headers=mheaders)
    assert manager_cannot_approve.status_code == 403  # manager lacks payroll:approve

    approved = owner.post(f"/api/app/payroll/runs/{run['id']}/approve", headers=oheaders)
    assert approved.status_code == 200 and approved.json()["status"] == "approved"

    manager_cannot_pay = manager.post(f"/api/app/payroll/runs/{run['id']}/pay", headers=mheaders)
    assert manager_cannot_pay.status_code == 403  # manager lacks payroll:pay

    paid = accountant.post(f"/api/app/payroll/runs/{run['id']}/pay", headers=aheaders)
    assert paid.status_code == 200 and paid.json()["status"] == "paid"


def test_cannot_pay_before_approval(client_for):
    owner, headers = client_for("owner")
    run = owner.post("/api/app/payroll/runs", headers=headers, json=PERIOD).json()
    response = owner.post(f"/api/app/payroll/runs/{run['id']}/pay", headers=headers)
    assert response.status_code == 409


def test_cashier_sees_payslip_only_after_payment(client_for, world):
    owner, oheaders = client_for("owner")
    manager, mheaders = client_for("manager")
    cashier, cheaders = client_for("cashier")
    membership_id, _ = _cashier_membership_id(client_for)
    owner.patch(f"/api/app/payroll/salary/{membership_id}", headers=oheaders, json={"base_salary": "10000"})

    run = manager.post("/api/app/payroll/runs", headers=mheaders, json=PERIOD).json()
    assert cashier.get("/api/app/payroll/me", headers=cheaders).json() == []

    owner.post(f"/api/app/payroll/runs/{run['id']}/approve", headers=oheaders)
    assert cashier.get("/api/app/payroll/me", headers=cheaders).json() == []  # approved, not yet paid

    owner.post(f"/api/app/payroll/runs/{run['id']}/pay", headers=oheaders)
    payslips = cashier.get("/api/app/payroll/me", headers=cheaders).json()
    assert len(payslips) == 1 and Decimal(str(payslips[0]["net_pay"])) == 10000


@pytest.mark.parametrize("role,allowed", [("owner", True), ("manager", True), ("accountant", False), ("cashier", False)])
def test_who_may_draft_payroll(client_for, role, allowed):
    client, headers = client_for(role)
    response = client.post("/api/app/payroll/runs", headers=headers, json=PERIOD)
    assert (response.status_code == 200) == allowed


@pytest.mark.parametrize("role,allowed", [("owner", True), ("manager", False), ("accountant", True), ("cashier", False)])
def test_who_may_pay_payroll(client_for, role, allowed, world):
    owner, oheaders = client_for("owner")
    manager, mheaders = client_for("manager")
    run = manager.post("/api/app/payroll/runs", headers=mheaders, json=PERIOD).json()
    owner.post(f"/api/app/payroll/runs/{run['id']}/approve", headers=oheaders)
    client, headers = client_for(role)
    response = client.post(f"/api/app/payroll/runs/{run['id']}/pay", headers=headers)
    assert (response.status_code == 200) == allowed


def test_only_owner_may_set_salary(client_for):
    membership_id, _ = _cashier_membership_id(client_for)
    manager, headers = client_for("manager")
    response = manager.patch(f"/api/app/payroll/salary/{membership_id}", headers=headers, json={"base_salary": "10000"})
    assert response.status_code == 403
