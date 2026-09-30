"""L1: the Bangla explanation gateway (api/llm_gateway.py).

The test environment never sets INTEGRATION_MODE=production or a real
ANTHROPIC_API_KEY, so every call here exercises the always-available
template path -- the same path a deployment with no key configured gets.
The number-verifier and the live-call branch are unit-tested directly
against the module's own functions instead, without a network call.
"""

from sqlalchemy.orm import Session

from api import llm_gateway
from api.domain_models import Recommendation


def test_sandbox_mode_always_returns_the_template_never_calling_out():
    item = {"reason": "স্টক কম, অর্ডার দিন।", "benefit_bdt": 100.0, "action_cost_bdt": 10.0,
            "risk_bdt": 5.0, "utility_bdt": 85.0, "quantity": 7}
    result = llm_gateway.explain(item)
    assert result == {"text": "স্টক কম, অর্ডার দিন।", "source": "template", "verified": None}


def test_a_recommendation_with_no_reason_gets_a_safe_default_text():
    result = llm_gateway.explain({})
    assert result["source"] == "template"
    assert result["text"]


def test_source_numbers_collects_every_legitimate_numeral():
    item = {
        "benefit_bdt": 1234.5, "action_cost_bdt": 10.0, "risk_bdt": 2.0, "utility_bdt": 1222.5,
        "quantity": 7,
        "explanation": {"why": {"lead_time_days": 5, "current_stock": "3.0"}},
    }
    numbers = llm_gateway._source_numbers(item)
    assert {"10", "2", "7", "5", "3.0"} <= numbers   # exact rounding of the BDT floats aside, these are exact


def test_numbers_in_normalizes_bengali_digits_to_western():
    text = "১০০ টাকা লাভ হবে, খরচ 10 টাকা।"
    found = llm_gateway._numbers_in(text)
    assert found == {"100", "10"}


def test_a_narration_using_only_source_numbers_is_verified(monkeypatch):
    item = {"reason": "fallback", "benefit_bdt": 500.0, "action_cost_bdt": 50.0,
            "risk_bdt": 10.0, "utility_bdt": 440.0, "quantity": 3}

    class FakeBlock:
        type = "text"
        text = "৫০০ টাকা লাভের সম্ভাবনা, খরচ 50 টাকা, ৩ ইউনিট অর্ডার করুন।"

    class FakeResponse:
        content = [FakeBlock()]

    class FakeMessages:
        def create(self, **kwargs):
            return FakeResponse()

    class FakeClient:
        def __init__(self, api_key):
            self.messages = FakeMessages()

    class FakeAnthropicModule:
        Anthropic = FakeClient

    import sys
    monkeypatch.setitem(sys.modules, "anthropic", FakeAnthropicModule())
    monkeypatch.setattr(llm_gateway, "get_settings",
                         lambda: type("S", (), {"integration_mode": "production", "anthropic_api_key": "sk-test"})())

    result = llm_gateway.explain(item)
    assert result["source"] == "llm"
    assert result["verified"] is True
    assert "50" in result["text"]


def test_a_narration_inventing_a_number_falls_back_to_the_template(monkeypatch):
    item = {"reason": "fallback text", "benefit_bdt": 500.0, "action_cost_bdt": 50.0,
            "risk_bdt": 10.0, "utility_bdt": 440.0, "quantity": 3}

    class FakeBlock:
        type = "text"
        text = "৯৯৯৯ টাকা লাভ হবে।"   # not in the source data -- a hallucination

    class FakeResponse:
        content = [FakeBlock()]

    class FakeMessages:
        def create(self, **kwargs):
            return FakeResponse()

    class FakeClient:
        def __init__(self, api_key):
            self.messages = FakeMessages()

    class FakeAnthropicModule:
        Anthropic = FakeClient

    import sys
    monkeypatch.setitem(sys.modules, "anthropic", FakeAnthropicModule())
    monkeypatch.setattr(llm_gateway, "get_settings",
                         lambda: type("S", (), {"integration_mode": "production", "anthropic_api_key": "sk-test"})())

    result = llm_gateway.explain(item)
    assert result["source"] == "template"
    assert result["verified"] is False
    assert result["text"] == "fallback text"


def test_an_api_error_falls_back_to_the_template_not_a_crash(monkeypatch):
    item = {"reason": "fallback text"}

    class FakeMessages:
        def create(self, **kwargs):
            raise RuntimeError("network unreachable")

    class FakeClient:
        def __init__(self, api_key):
            self.messages = FakeMessages()

    class FakeAnthropicModule:
        Anthropic = FakeClient

    import sys
    monkeypatch.setitem(sys.modules, "anthropic", FakeAnthropicModule())
    monkeypatch.setattr(llm_gateway, "get_settings",
                         lambda: type("S", (), {"integration_mode": "production", "anthropic_api_key": "sk-test"})())

    result = llm_gateway.explain(item)
    assert result == {"text": "fallback text", "source": "template", "verified": None}


# ── the /explain route, end to end through the real API ─────────────────────

def test_explain_route_returns_the_template_in_sandbox_mode(client_for, engine, world):
    client, headers = client_for("owner")
    with Session(engine) as db:
        reco = Recommendation(
            organization_id=world["org_a"], run_id="run-1", cutoff_date="2026-09-01",
            action_type="reorder", target_sku="RICE-1", quantity=20, benefit_bdt=100,
            action_cost_bdt=10, risk_bdt=5, utility_bdt=85, feasible=True, model_version="test",
            reason="Rice: reorder 20 units.",
        )
        db.add(reco)
        db.commit()
        reco_id = reco.id
    response = client.get(f"/api/app/bsmart/recommendations/{reco_id}/explain", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {"text": "Rice: reorder 20 units.", "source": "template", "verified": None}


def test_explain_route_404s_for_a_missing_or_cross_tenant_recommendation(client_for):
    client, headers = client_for("owner")
    assert client.get("/api/app/bsmart/recommendations/missing/explain", headers=headers).status_code == 404
