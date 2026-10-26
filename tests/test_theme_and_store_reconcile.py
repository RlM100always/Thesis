"""Safety and UI regressions for dark-mode + storefront recovery."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_dark_public_comparison_uses_theme_tokens():
    css = (ROOT / "frontend/src/index.css").read_text(encoding="utf-8")
    assert "B-SMART THEME CONTRAST PATCH V2" in css
    for token in ("--pub-before-bg", "--pub-after-bg", "--pub-before-color", "--pub-after-color"):
        assert token in css
    for snippet in (
        ".public-site .owner-problem-section",
        ".public-site .before-after-cell.before",
        ".public-site .before-after-cell.after",
        ':root[data-theme="dark"] .public-site',
    ):
        assert snippet in css


def test_directory_dark_palette_and_responsive_wave():
    src = (ROOT / "frontend/src/pages/StoreDirectory.jsx").read_text(encoding="utf-8")
    assert ':root[data-theme="dark"] .sd-page' in src
    assert "var(--sd-card)" in src
    assert 'fill="currentColor"' in src
    assert "minmax(min(100%,155px),1fr)" in src


def test_restoration_requires_explicit_consent():
    from scripts.reconcile_existing_stores import main
    with pytest.raises(SystemExit):
        main(["--apply"])
    with pytest.raises(SystemExit):
        main(["--activate"])
    with pytest.raises(SystemExit):
        main(["--publish-new-products"])


def test_read_only_audit_can_run_without_mutation(capsys):
    # CI runs sqlite:// in memory; initialise the schema before the audit.
    from api.database import create_schema
    from scripts.reconcile_existing_stores import main
    create_schema()
    assert main([]) == 0
    assert "No records created or modified" in capsys.readouterr().out
