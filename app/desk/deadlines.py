"""Deadlines (D9, D13): a ticket's printed due date, else its issue date plus 21 days."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

# D13: Los Angeles gives 21 days from the issue date to request an initial review.
TICKET_DAYS_FROM_ISSUE = 21
COUNTED_FROM_ISSUE = f"counted {TICKET_DAYS_FROM_ISSUE} days from the issue date"


def ticket_deadline(fields: dict[str, Any]) -> tuple[str | None, str | None]:
    """(deadline, note): the printed due date with no note, else the printed issue
    date plus 21 days with the note saying so. Never counted from today."""
    if fields.get("due"):
        return str(fields["due"]), None
    issued = fields.get("issued")
    if not issued:
        return None, None
    return (date.fromisoformat(str(issued)) + timedelta(days=TICKET_DAYS_FROM_ISSUE)).isoformat(), COUNTED_FROM_ISSUE
