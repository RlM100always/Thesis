"""L1: a Bangla explanation of one B-SMART recommendation card.

`docs/BUSINESS_OS_VISION.md` section 7 lists nine possible LLM use cases;
this ships exactly one, deliberately, not the whole menu. The deterministic
template (the recommendation's own ``reason`` field) is the default, always-
available explanation -- a missing or unset ``ANTHROPIC_API_KEY`` never
blocks anything, the same rule every other external connector in this
codebase follows (see ``api/integration_routes.py``'s docstring). A real key
narrates the identical numbers in fuller Bangla prose; it is never allowed to
introduce a numeral that is not already in the recommendation's own JSON --
the number-verifier below checks every call, and falls back to the template
whenever a narration fails it, an empty response comes back, or the API call
itself errors. A hallucinated number can never reach an owner through this
path.

The live-call branch is exercised only when ``INTEGRATION_MODE=production``
and a real ``ANTHROPIC_API_KEY`` is set -- neither is true in this
development/CI environment, so, like the bKash/WhatsApp adapters in
``api/integration_routes.py``, it has been written carefully but not
exercised end to end against the real API here.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from .config import get_settings

MODEL = "claude-haiku-4-5-20251001"

_NUMBER = re.compile(r"\d[\d,.]*\d|\d")
_BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


def _numbers_in(text: str) -> set[str]:
    """Digits in ``text``, Bengali numerals normalized to Western first.

    The prompt is written in Bangla, so a real response is expected to use
    Bengali digits (৳৫০০, না ৳500) -- comparing scripts as raw text would
    make the verifier reject a faithful narration just for using the numeral
    system the prompt itself is written in.
    """
    return {n.replace(",", "").rstrip(".") for n in _NUMBER.findall(text.translate(_BN_DIGITS))}


def _source_numbers(item: dict[str, Any]) -> set[str]:
    """Every numeral that may legitimately appear in a narration of this item."""
    numbers: set[str] = set()
    for key in ("benefit_bdt", "action_cost_bdt", "risk_bdt", "utility_bdt", "quantity"):
        value = item.get(key)
        if value is not None:
            try:
                numbers.add(str(abs(round(float(value)))))
            except (TypeError, ValueError):
                pass
    why = (item.get("explanation") or {}).get("why") or {}
    for value in why.values():
        numbers |= _numbers_in(str(value))
    return numbers


def _template(item: dict[str, Any]) -> str:
    return item.get("reason") or "এই সুপারিশের জন্য বিস্তারিত ব্যাখ্যা পাওয়া যায়নি।"


def explain(item: dict[str, Any]) -> dict[str, Any]:
    """Return ``{"text": str, "source": "llm" | "template", "verified": bool | None}``.

    ``verified`` is ``None`` when the template ran because no key/production
    mode was configured (nothing to verify), ``True``/``False`` when an LLM
    call actually happened and the numbers did or didn't check out.
    """
    settings = get_settings()
    template = _template(item)
    if settings.integration_mode != "production" or not settings.anthropic_api_key:
        return {"text": template, "source": "template", "verified": None}

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        prompt = (
            "তুমি একজন বাংলাদেশি দোকান মালিকের সহকারী। নিচের JSON ডেটা থেকে ২-৩ "
            "বাক্যে বাংলায় সহজ ভাষায় ব্যাখ্যা দাও কেন এই কাজটি করা উচিত। শুধু এই "
            "ডেটায় থাকা সংখ্যা ব্যবহার করবে, নতুন কোনো সংখ্যা বানাবে না, আর কোনো "
            "চিকিৎসা পরামর্শ দেবে না।\n\n"
            f"{item}"
        )
        response = client.messages.create(
            model=MODEL, max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        ).strip()
    except Exception:
        return {"text": template, "source": "template", "verified": None}

    if not text:
        return {"text": template, "source": "template", "verified": None}

    if not _numbers_in(text) <= _source_numbers(item):
        return {"text": template, "source": "template", "verified": False}
    return {"text": text, "source": "llm", "verified": True}


def _data_numbers(data: dict[str, Any]) -> set[str]:
    """Every numeral legitimately present anywhere in an already-computed
    answer payload (flat values and nested lists of dicts alike)."""
    numbers: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, (int, float, Decimal)):
            numbers.add(str(abs(round(float(value)))))
        elif isinstance(value, dict):
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)
        elif isinstance(value, str):
            numbers.update(_numbers_in(value))

    walk(data)
    return numbers


def narrate_answer(question: str, template: str, data: dict[str, Any]) -> dict[str, Any]:
    """Rephrase an already-computed, real-data ``template`` answer to a plain-
    Bangla business question in fuller natural language. Same anti-
    hallucination contract as ``explain()``: the template is the always-
    available default, a real key only ever rephrases numbers that are
    already in ``data``, and any narration introducing a number that isn't
    falls back to the template rather than ever reaching the owner."""
    settings = get_settings()
    if settings.integration_mode != "production" or not settings.anthropic_api_key:
        return {"text": template, "source": "template"}

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        prompt = (
            "তুমি একজন বাংলাদেশি দোকান মালিকের সহকারী। মালিক জিজ্ঞেস করেছেন: "
            f"\"{question}\"। নিচের তথ্য থেকে স্বাভাবিক কথোপকথনের ভাষায় ২-৩ বাক্যে "
            "উত্তর দাও। শুধু এই তথ্যে থাকা সংখ্যা ব্যবহার করবে, নতুন কোনো সংখ্যা "
            f"বানাবে না।\n\nতথ্য: {data}\n\nইতিমধ্যে একটা সহজ উত্তর আছে এটা: {template}"
        )
        response = client.messages.create(
            model=MODEL, max_tokens=250,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        ).strip()
    except Exception:
        return {"text": template, "source": "template"}

    if not text or not _numbers_in(text) <= _data_numbers(data):
        return {"text": template, "source": "template"}
    return {"text": text, "source": "llm"}
