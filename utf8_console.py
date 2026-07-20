"""
=============================================================
UTF-8 CONSOLE SETUP
AI-Powered Business Analytics System — CSE 4th Year Thesis
=============================================================
Import this FIRST in any script that prints Unicode.

    import utf8_console  # noqa: F401

WHY THIS EXISTS
---------------
Every pipeline script prints characters like → ✓ ⚠ ✅ in its progress
output. The Windows console defaults to cp1252, which cannot encode them,
so the scripts used to die with:

    UnicodeEncodeError: 'charmap' codec can't encode character '\\u2192'

The previous workaround was to prefix every command with
PYTHONIOENCODING=utf-8. That is bash syntax, so it fails outright in
PowerShell:

    PYTHONIOENCODING=utf-8: The term '...' is not recognized

Rather than document a different incantation per shell, the scripts now
configure their own output. Nothing to set, nothing to remember, and it
works the same in PowerShell, cmd, bash and CI.

Importing for the side effect is deliberate — the reconfiguration must
happen before the first print, and an import is the earliest hook there is.
"""

import sys

for _stream in (sys.stdout, sys.stderr):
    # reconfigure() exists on TextIOWrapper (Python 3.7+). It is absent when
    # output is redirected through some wrappers, so failing softly here
    # matters: a logging convenience must never break the pipeline.
    try:
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")
    except (ValueError, AttributeError, OSError):
        pass
