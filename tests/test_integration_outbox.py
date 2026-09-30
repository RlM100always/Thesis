def test_sandbox_message_is_durable_idempotent_and_tenant_scoped(client_for):
    owner, headers = client_for("owner")
    body = {"channel": "whatsapp", "recipient": "8801712345678", "template": "receipt",
            "body": "আপনার রসিদ প্রস্তুত", "idempotency_key": "receipt-inv-1001"}
    first = owner.post("/api/app/integrations/messages", headers=headers, json=body)
    second = owner.post("/api/app/integrations/messages", headers=headers, json=body)
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["status"] == "simulated"
    assert first.json()["provider_message_id"].startswith("sandbox-")
    other, other_headers = client_for("owner", "org_b")
    assert other.get("/api/app/integrations/messages", headers=other_headers).json() == []

def test_cashier_can_send_but_cannot_read_business_outbox(client_for):
    cashier, headers = client_for("cashier")
    response = cashier.post("/api/app/integrations/messages", headers=headers, json={
        "channel": "sms", "recipient": "01712345678", "template": "receipt",
        "body": "রসিদ", "idempotency_key": "cashier-receipt-1"})
    assert response.status_code == 200
    assert cashier.get("/api/app/integrations/messages", headers=headers).status_code == 403
