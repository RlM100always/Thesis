"""Operational settings selected during onboarding shape the live workspace."""


def test_owner_configures_payment_methods_and_channels(client_for):
    owner, headers = client_for("owner")
    response = owner.patch("/api/app/organization/operations", headers=headers, json={
        "business_mode": "both",
        "payment_methods": ["cash", "bkash", "bangla_qr"],
        "sales_channels": ["in_store", "whatsapp"],
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["business_mode"] == "both"
    assert body["payment_methods"] == ["cash", "bkash", "bangla_qr"]
    assert body["sales_channels"] == ["in_store", "whatsapp"]

    listed = owner.get("/api/app/organizations").json()[0]
    assert listed["payment_methods"] == ["cash", "bkash", "bangla_qr"]


def test_non_owner_cannot_change_operational_settings(client_for):
    cashier, headers = client_for("cashier")
    response = cashier.patch("/api/app/organization/operations", headers=headers, json={
        "business_mode": "products", "payment_methods": ["cash"], "sales_channels": ["in_store"],
    })
    assert response.status_code == 403


def test_unknown_payment_method_is_rejected(client_for):
    owner, headers = client_for("owner")
    response = owner.patch("/api/app/organization/operations", headers=headers, json={
        "business_mode": "products", "payment_methods": ["cash", "magic_money"],
        "sales_channels": ["in_store"],
    })
    assert response.status_code == 422
