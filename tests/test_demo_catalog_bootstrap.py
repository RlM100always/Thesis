"""Safety invariants for optional, clearly marked demo storefront seed."""
import os
from api import demo_catalog_bootstrap as seed

def test_all_demo_sectors_have_literal_product_fixtures():
    template = seed._catalogue()  # AST literal parsing; old script is NOT executed.
    assert len(seed.SPECS) == 10
    for sector, *_ in seed.SPECS:
        assert len(template[sector]) >= 5

def test_seed_disabled_by_default(monkeypatch):
    monkeypatch.delenv("BSMART_BOOTSTRAP_DEMO_CATALOG", raising=False)
    assert seed.seed_demo_catalogue()["status"] == "disabled"

def test_demo_seed_requires_postgresql(monkeypatch):
    monkeypatch.setenv("BSMART_BOOTSTRAP_DEMO_CATALOG", "YES")
    if seed.engine.dialect.name != "postgresql":
        result = seed.seed_demo_catalogue()
        assert result == {"status": "skipped", "reason": "requires_postgresql"}
