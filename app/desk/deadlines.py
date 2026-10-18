"""Deadlines (D9, D13, D14, D20, D21): what the card and the texts say is due, and when the
day-before text goes.

A ticket's deadline is its printed due date, else its printed issue date plus 21 days
(D13). A bill carries its printed due date. A product has none (D21). The day-before
text goes at nine in the morning local time on the day before the deadline (D20,
ratified D32), read on the desk's clock: virtual in test mode, real live.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

# D13: Los Angeles gives 21 days from the issue date to request an initial review.
TICKET_DAYS_FROM_ISSUE = 21
COUNTED_FROM_ISSUE = f"counted {TICKET_DAYS_FROM_ISSUE} days from the issue date"
# D20, D32: nine in the morning, local time, the day before the deadline.
REMINDER_TIME = time(9, 0)
REMINDER_DAYS_BEFORE = 1
# D20, D21: the kinds of chore whose deadline brings a second text. A product has no deadline.
REMINDED_KINDS = frozenset({"ticket", "bill"})


def ticket_deadline(fields: dict[str, Any]) -> tuple[str | None, str | None]:
    """(deadline, note): the printed due date with no note, else the printed issue
    date plus 21 days with the note saying so. Never counted from today."""
    if fields.get("due"):
        return str(fields["due"]), None
    issued = fields.get("issued")
    if not issued:
        return None, None
    return (date.fromisoformat(str(issued)) + timedelta(days=TICKET_DAYS_FROM_ISSUE)).isoformat(), COUNTED_FROM_ISSUE


def deadline_for(kind: str, fields: dict[str, Any]) -> tuple[str | None, str | None]:
    """(deadline, note) for any identified thing: a ticket's (D13), a bill's printed
    due date (D14), and none for a product (D21)."""
    if kind == "ticket":
        return ticket_deadline(fields)
    if kind == "bill" and fields.get("due"):
        return str(fields["due"]), None
    return None, None


def reminder_at(deadline: str) -> datetime:
    """When the day-before text goes: 09:00 local on the day before the deadline (D20)."""
    return datetime.combine(date.fromisoformat(deadline) - timedelta(days=REMINDER_DAYS_BEFORE), REMINDER_TIME)


def human_date(iso: str) -> str:
    """2026-11-02 → "Nov 2, 2026", the way a text says it."""
    d = date.fromisoformat(iso)
    return f"{d:%b} {d.day}, {d.year}"
