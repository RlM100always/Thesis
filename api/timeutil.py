"""Business-day arithmetic. A shop's "today" is a Bangladesh calendar day, not a UTC one:
a sale at 11 p.m. Dhaka time belongs to that day even though UTC has already turned over."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

DHAKA = timezone(timedelta(hours=6))  # Bangladesh has no daylight saving


def dhaka_today() -> date:
    return datetime.now(DHAKA).date()


def day_bounds(day: date) -> tuple[datetime, datetime]:
    """Start (inclusive) and end (exclusive) of a Dhaka calendar day, as UTC instants."""
    start = datetime(day.year, day.month, day.day, tzinfo=DHAKA)
    return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)
